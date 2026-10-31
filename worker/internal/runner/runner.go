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

func (r *Runner) CompileAndRun(
	ctx context.Context,
	languageKey string,
	source string,
	input []byte,
	timeLimit time.Duration,
	memoryLimit int64,
) (executor.RunResult, error) {
	profile, ok := language.Get(languageKey)
	if !ok {
		return executor.RunResult{}, ErrUnsupportedLanguage
	}
	if r.Judge == nil {
		return executor.RunResult{}, errors.New("go-judge executor is not configured")
	}

	env := []string{"PATH=/usr/local/bin:/usr/bin:/bin", "LANG=C.UTF-8"}
	runSpec := profile.Run
	runSpec.Env = env
	runSpec.StdIn = input
	runSpec.CPUTime = timeLimit
	runSpec.ClockTime = 2 * timeLimit
	runSpec.MemoryBytes = memoryLimit
	runSpec.ProcLimit = 64

	if profile.Compile != nil {
		compileSpec := *profile.Compile
		compileSpec.Env = env
		compileSpec.CopyIn = map[string][]byte{profile.SourceName: []byte(source)}
		compileSpec.CPUTime = 10 * time.Second
		compileSpec.ClockTime = 20 * time.Second
		compileSpec.MemoryBytes = memoryLimit
		compileSpec.ProcLimit = 64
		compiled, err := r.Judge.Run(ctx, compileSpec)
		if err != nil {
			return executor.RunResult{}, err
		}
		if compiled.Status != "AC" {
			message := strings.TrimSpace(string(compiled.Stderr))
			if message == "" {
				message = fmt.Sprintf("compiler status %s", compiled.Status)
			}
			return executor.RunResult{}, &CompileError{Message: message}
		}
		fileID := compiled.FileIDs["main"]
		if fileID == "" {
			return executor.RunResult{}, &CompileError{Message: "compiler did not produce a binary"}
		}
		runSpec.CopyInCached = map[string]string{"main": fileID}
	} else {
		runSpec.CopyIn = map[string][]byte{profile.SourceName: []byte(source)}
	}

	return r.Judge.Run(ctx, runSpec)
}
