package checker

import (
	"context"
	"strings"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/runner"
)

type InteractiveChecker struct {
	Judge  *executor.GoJudge
	Runner *runner.Runner
}

func (c *InteractiveChecker) Check(
	ctx context.Context,
	spec api.Checker,
	language string,
	source string,
	input []byte,
	timeLimit time.Duration,
	memoryLimit int64,
) (Result, error) {
	if spec.Source == "" {
		return Result{Status: "IE", Message: "interactive checker source is missing"}, nil
	}
	if c.Judge == nil || c.Runner == nil {
		return Result{Status: "IE", Message: "interactive checker is not configured"}, nil
	}

	compiled, err := c.Judge.Run(ctx, executor.RunSpec{
		Args:          []string{"g++", "-O2", "-std=c++17", "-o", "interactor", "interactor.cpp"},
		Env:           []string{"PATH=/usr/local/bin:/usr/bin:/bin", "LANG=C.UTF-8"},
		CopyIn:        map[string][]byte{"interactor.cpp": []byte(spec.Source)},
		CopyOutCached: []string{"interactor"},
		CPUTime:       10 * time.Second,
		ClockTime:     20 * time.Second,
		MemoryBytes:   compileMemoryLimit(memoryLimit),
		ProcLimit:     64,
	})
	if err != nil {
		return Result{Status: "IE", Message: err.Error()}, nil
	}
	if compiled.Status != "AC" {
		return Result{Status: "IE", Message: checkerMessage(compiled)}, nil
	}
	interactorFileID := compiled.FileIDs["interactor"]
	if interactorFileID == "" {
		return Result{Status: "IE", Message: "interactor binary was not produced"}, nil
	}

	participant, err := c.Runner.Prepare(ctx, language, source, memoryLimit)
	if err != nil {
		return Result{}, err
	}
	participant.CPUTime = timeLimit
	participant.ClockTime = 2 * timeLimit
	participant.MemoryBytes = memoryLimit
	participant.ProcLimit = 64
	interactorLimit := checkerTimeLimit(2 * timeLimit)
	interactor := executor.RunSpec{
		Args:         []string{"/w/interactor", "/w/input.txt"},
		CopyIn:       map[string][]byte{"input.txt": input},
		CopyInCached: map[string]string{"interactor": interactorFileID},
		CPUTime:      interactorLimit,
		ClockTime:    2 * interactorLimit,
		MemoryBytes:  compileMemoryLimit(memoryLimit),
		ProcLimit:    64,
	}

	result, err := c.Judge.RunInteractive(ctx, participant, interactor)
	if err != nil {
		return Result{Status: "IE", Message: err.Error()}, nil
	}
	if result.Participant.Status != "AC" {
		message := strings.TrimSpace(string(result.Participant.Stderr))
		if message == "" {
			message = result.Participant.Error
		}
		return Result{Status: result.Participant.Status, Message: message}, nil
	}
	if result.Interactor.Status == "TLE" || result.Interactor.Status == "MLE" ||
		result.Interactor.Status == "OLE" || result.Interactor.Status == "IE" {
		return Result{Status: result.Interactor.Status, Message: checkerMessage(result.Interactor)}, nil
	}

	switch result.Interactor.ExitStatus {
	case 0:
		return Result{Status: "AC"}, nil
	case 1:
		return Result{Status: "WA", Message: checkerMessage(result.Interactor)}, nil
	case 2:
		return Result{Status: "PE", Message: checkerMessage(result.Interactor)}, nil
	case 5:
		return Result{
			Status:  "PT",
			Points:  parsePoints(string(result.Interactor.Stderr)),
			Message: checkerMessage(result.Interactor),
		}, nil
	default:
		return Result{Status: "IE", Message: checkerMessage(result.Interactor)}, nil
	}
}
