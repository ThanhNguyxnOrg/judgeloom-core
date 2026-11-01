package checker

import (
	"context"
	"errors"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/third_party/testlib"
)

var pointsPattern = regexp.MustCompile(`(?i)points?\s+([0-9]+(?:\.[0-9]+)?)`)

type Result struct {
	Status  string
	Points  float64
	Message string
}

type Checker interface {
	Check(ctx context.Context, spec api.Checker, input, answer, output []byte, timeLimit time.Duration, memoryLimit int64) (Result, error)
}

type ExactChecker struct{}

func (ExactChecker) Check(_ context.Context, _ api.Checker, input, answer, output []byte, _ time.Duration, _ int64) (Result, error) {
	if normalize(answer) == normalize(output) {
		return Result{Status: "AC"}, nil
	}
	return Result{Status: "WA", Message: "output differs"}, nil
}

type NoopChecker struct{}

func (NoopChecker) Check(context.Context, api.Checker, []byte, []byte, []byte, time.Duration, int64) (Result, error) {
	return Result{Status: "AC"}, nil
}

type TestlibChecker struct {
	Judge *executor.GoJudge

	mu     sync.Mutex
	fileID string
}

func (c *TestlibChecker) Check(
	ctx context.Context,
	spec api.Checker,
	input, answer, output []byte,
	timeLimit time.Duration,
	memoryLimit int64,
) (Result, error) {
	if spec.Source == "" {
		return Result{Status: "IE", Message: "testlib checker source is missing"}, nil
	}
	if c.Judge == nil {
		return Result{Status: "IE", Message: "go-judge executor is not configured"}, nil
	}

	fileID, err := c.compiled(ctx, spec, memoryLimit)
	if err != nil {
		return Result{Status: "IE", Message: err.Error()}, nil
	}

	limit := checkerTimeLimit(timeLimit)
	ran, err := c.Judge.Run(ctx, executor.RunSpec{
		Args: []string{"/w/checker", "/w/input.txt", "/w/output.txt", "/w/answer.txt"},
		CopyIn: map[string][]byte{
			"input.txt":  input,
			"answer.txt": answer,
			"output.txt": output,
		},
		CopyInCached: map[string]string{"checker": fileID},
		CPUTime:      limit,
		ClockTime:    2 * limit,
		MemoryBytes:  compileMemoryLimit(memoryLimit),
		ProcLimit:    64,
	})
	if err != nil {
		return Result{Status: "IE", Message: err.Error()}, nil
	}
	if ran.Status == "TLE" || ran.Status == "MLE" || ran.Status == "OLE" || ran.Status == "IE" {
		return Result{Status: ran.Status, Message: checkerMessage(ran)}, nil
	}

	switch ran.ExitStatus {
	case 0:
		return Result{Status: "AC"}, nil
	case 1:
		return Result{Status: "WA", Message: checkerMessage(ran)}, nil
	case 2:
		return Result{Status: "PE", Message: checkerMessage(ran)}, nil
	case 5:
		return Result{Status: "PT", Points: parsePoints(string(ran.Stderr)), Message: checkerMessage(ran)}, nil
	default:
		return Result{Status: "IE", Message: checkerMessage(ran)}, nil
	}
}

func (c *TestlibChecker) compiled(ctx context.Context, spec api.Checker, memoryLimit int64) (string, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.fileID != "" {
		return c.fileID, nil
	}

	compiled, err := c.Judge.Run(ctx, executor.RunSpec{
		Args:          []string{"g++", "-O2", "-std=c++17", "-o", "checker", "checker.cpp"},
		Env:           []string{"PATH=/usr/local/bin:/usr/bin:/bin", "LANG=C.UTF-8"},
		CopyIn:        map[string][]byte{"checker.cpp": []byte(spec.Source), "testlib.h": testlib.Header},
		CopyOutCached: []string{"checker"},
		CPUTime:       10 * time.Second,
		ClockTime:     20 * time.Second,
		MemoryBytes:   compileMemoryLimit(memoryLimit),
		ProcLimit:     64,
	})
	if err != nil {
		return "", err
	}
	if compiled.Status != "AC" {
		return "", errors.New(checkerMessage(compiled))
	}
	fileID := compiled.FileIDs["checker"]
	if fileID == "" {
		return "", errors.New("checker binary was not produced")
	}
	c.fileID = fileID
	return fileID, nil
}

func compileMemoryLimit(memoryLimit int64) int64 {
	const minimum = 256 << 20
	if memoryLimit < minimum {
		return minimum
	}
	return memoryLimit
}

func checkerTimeLimit(limit time.Duration) time.Duration {
	const minimum = 2 * time.Second
	if limit < minimum {
		return minimum
	}
	return limit
}

func normalize(data []byte) string {
	lines := strings.Split(strings.ReplaceAll(string(data), "\r\n", "\n"), "\n")
	for index, line := range lines {
		lines[index] = strings.TrimRight(line, " \t")
	}
	return strings.TrimRight(strings.Join(lines, "\n"), "\n")
}

func checkerMessage(result executor.RunResult) string {
	if message := strings.TrimSpace(string(result.Stderr)); message != "" {
		return message
	}
	if result.Error != "" {
		return result.Error
	}
	return result.Status
}

func parsePoints(stderr string) float64 {
	match := pointsPattern.FindStringSubmatch(stderr)
	if len(match) != 2 {
		return 0
	}
	points, err := strconv.ParseFloat(match[1], 64)
	if err != nil {
		return 0
	}
	return points
}
