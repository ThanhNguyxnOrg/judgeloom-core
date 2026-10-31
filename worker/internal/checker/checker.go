package checker

import (
	"context"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
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

type TestlibChecker struct {
	Judge *executor.GoJudge
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

	compiled, err := c.Judge.Run(ctx, executor.RunSpec{
		Args:          []string{"g++", "-O2", "-std=c++17", "-o", "checker", "checker.cpp"},
		CopyIn:        map[string][]byte{"checker.cpp": []byte(spec.Source)},
		CopyOutCached: []string{"checker"},
		CPUTime:       10 * time.Second,
		ClockTime:     20 * time.Second,
		MemoryBytes:   memoryLimit,
		ProcLimit:     64,
	})
	if err != nil {
		return Result{Status: "IE", Message: err.Error()}, nil
	}
	if compiled.Status != "AC" {
		return Result{Status: "IE", Message: checkerMessage(compiled)}, nil
	}
	fileID := compiled.FileIDs["checker"]
	if fileID == "" {
		return Result{Status: "IE", Message: "checker binary was not produced"}, nil
	}

	ran, err := c.Judge.Run(ctx, executor.RunSpec{
		Args: []string{"/w/checker", "/w/input.txt", "/w/answer.txt", "/w/output.txt"},
		CopyIn: map[string][]byte{
			"input.txt":  input,
			"answer.txt": answer,
			"output.txt": output,
		},
		CopyInCached: map[string]string{"checker": fileID},
		CPUTime:      timeLimit,
		ClockTime:    2 * timeLimit,
		MemoryBytes:  memoryLimit,
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
