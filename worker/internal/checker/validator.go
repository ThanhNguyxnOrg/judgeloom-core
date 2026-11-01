package checker

import (
	"context"
	"fmt"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/third_party/testlib"
)

type TestlibValidator struct {
	judge  *executor.GoJudge
	fileID string
}

func NewTestlibValidator(
	ctx context.Context,
	judge *executor.GoJudge,
	spec api.Checker,
	memoryLimit int64,
) (*TestlibValidator, error) {
	if spec.Source == "" {
		return nil, fmt.Errorf("validator source is missing")
	}
	if judge == nil {
		return nil, fmt.Errorf("go-judge executor is not configured")
	}

	compiled, err := judge.Run(ctx, executor.RunSpec{
		Args:          []string{"g++", "-O2", "-std=c++17", "-o", "validator", "validator.cpp"},
		Env:           []string{"PATH=/usr/local/bin:/usr/bin:/bin", "LANG=C.UTF-8"},
		CopyIn:        map[string][]byte{"validator.cpp": []byte(spec.Source), "testlib.h": testlib.Header},
		CopyOutCached: []string{"validator"},
		CPUTime:       10 * time.Second,
		ClockTime:     20 * time.Second,
		MemoryBytes:   compileMemoryLimit(memoryLimit),
		ProcLimit:     64,
	})
	if err != nil {
		return nil, err
	}
	if compiled.Status != "AC" {
		return nil, fmt.Errorf("validator compile failed: %s", checkerMessage(compiled))
	}
	fileID := compiled.FileIDs["validator"]
	if fileID == "" {
		return nil, fmt.Errorf("validator binary was not produced")
	}
	return &TestlibValidator{judge: judge, fileID: fileID}, nil
}

func (v *TestlibValidator) Validate(
	ctx context.Context,
	input []byte,
	timeLimit time.Duration,
	memoryLimit int64,
) (Result, error) {
	limit := checkerTimeLimit(timeLimit)
	ran, err := v.judge.Run(ctx, executor.RunSpec{
		Args:         []string{"/w/validator"},
		StdIn:        input,
		CopyInCached: map[string]string{"validator": v.fileID},
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
	if ran.ExitStatus == 0 {
		return Result{Status: "AC"}, nil
	}
	return Result{Status: "IE", Message: checkerMessage(ran)}, nil
}
