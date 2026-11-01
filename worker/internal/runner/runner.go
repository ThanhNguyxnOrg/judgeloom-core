package runner

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/language"
)

var ErrUnsupportedLanguage = errors.New("unsupported language")

type CompileError struct {
	Message string
}

func (e *CompileError) Error() string {
	if e.Message == "" {
		return "compile failed"
	}
	return "compile failed: " + e.Message
}

type Runner struct {
	Judge *executor.GoJudge
}

func (r *Runner) Prepare(
	ctx context.Context,
	languageKey string,
	source string,
	memoryLimit int64,
) (executor.RunSpec, error) {
	return r.PrepareWithFiles(ctx, languageKey, source, memoryLimit, nil)
}

// PrepareWithFiles compiles trusted package code (checkers, validators,
// generators) with extra files such as testlib.h.
func (r *Runner) PrepareWithFiles(
	ctx context.Context,
	languageKey string,
	source string,
	memoryLimit int64,
	extraFiles map[string][]byte,
) (executor.RunSpec, error) {
	profile, ok := language.Get(languageKey)
	if !ok {
		return executor.RunSpec{}, ErrUnsupportedLanguage
	}
	if r.Judge == nil {
		return executor.RunSpec{}, errors.New("go-judge executor is not configured")
	}

	env := []string{"PATH=/usr/local/bin:/usr/bin:/bin", "LANG=C.UTF-8"}
	runSpec := profile.Run
	runSpec.Env = env

	copyIn := map[string][]byte{profile.SourceName: []byte(source)}
	for name, content := range extraFiles {
		copyIn[name] = content
	}

	if profile.Compile != nil {
		compileSpec := *profile.Compile
		compileSpec.Env = env
		compileSpec.CopyIn = copyIn
		compileSpec.CPUTime = 10 * time.Second
		compileSpec.ClockTime = 20 * time.Second
		compileSpec.MemoryBytes = memoryLimit
		compileSpec.ProcLimit = 64
		compiled, err := r.Judge.Run(ctx, compileSpec)
		if err != nil {
			return executor.RunSpec{}, err
		}
		if compiled.Status != "AC" {
			message := strings.TrimSpace(string(compiled.Stderr))
			if message == "" {
				message = fmt.Sprintf("compiler status %s", compiled.Status)
			}
			return executor.RunSpec{}, &CompileError{Message: message}
		}
		fileID := compiled.FileIDs["main"]
		if fileID == "" {
			return executor.RunSpec{}, &CompileError{Message: "compiler did not produce a binary"}
		}
		runSpec.CopyInCached = map[string]string{"main": fileID}
	} else {
		runSpec.CopyIn = copyIn
	}
	return runSpec, nil
}

func (r *Runner) CompileAndRun(
	ctx context.Context,
	languageKey string,
	source string,
	input []byte,
	timeLimit time.Duration,
	memoryLimit int64,
) (executor.RunResult, error) {
	runSpec, err := r.Prepare(ctx, languageKey, source, memoryLimit)
	if err != nil {
		return executor.RunResult{}, err
	}
	return r.RunPrepared(ctx, runSpec, input, nil, timeLimit, memoryLimit)
}

// RunPrepared runs a compiled/prepared sandbox spec with optional argv.
func (r *Runner) RunPrepared(
	ctx context.Context,
	prepared executor.RunSpec,
	input []byte,
	args []string,
	timeLimit time.Duration,
	memoryLimit int64,
) (executor.RunResult, error) {
	if r.Judge == nil {
		return executor.RunResult{}, errors.New("go-judge executor is not configured")
	}
	runSpec := prepared
	runSpec.Args = append(append([]string(nil), prepared.Args...), args...)
	runSpec.StdIn = input
	runSpec.CPUTime = timeLimit
	runSpec.ClockTime = 2 * timeLimit
	runSpec.MemoryBytes = memoryLimit
	runSpec.ProcLimit = 64
	return r.Judge.Run(ctx, runSpec)
}
