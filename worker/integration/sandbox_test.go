package integration

import (
	"context"
	"errors"
	"net/http"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/checker"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/runner"
)

func TestSandboxPythonAndCpp(t *testing.T) {
	baseURL := os.Getenv("GO_JUDGE_URL")
	if baseURL == "" {
		t.Skip("GO_JUDGE_URL is not set")
	}
	judge := &executor.GoJudge{
		BaseURL:    baseURL,
		Client:     &http.Client{Timeout: 30 * time.Second},
		AuthToken:  os.Getenv("GO_JUDGE_TOKEN"),
		RetryDelay: 100 * time.Millisecond,
	}
	runnerInstance := &runner.Runner{Judge: judge}
	input := readFile(t, "testdata/aplusb/01.in")
	answer := readFile(t, "testdata/aplusb/01.ans")

	t.Run("python ac", func(t *testing.T) {
		result := runCase(t, runnerInstance, "PY3", "testdata/sources/python/ac.py", input)
		if result.Status != "AC" || string(result.Stdout) != "8\n" {
			t.Fatalf("unexpected result: %+v stdout=%q", result, result.Stdout)
		}
		checked, err := (checker.ExactChecker{}).Check(context.Background(), apiChecker(), input, answer, result.Stdout, time.Second, 1<<20)
		if err != nil || checked.Status != "AC" {
			t.Fatalf("checker: %+v err=%v", checked, err)
		}
	})

	t.Run("python wa", func(t *testing.T) {
		result := runCase(t, runnerInstance, "PY3", "testdata/sources/python/wa.py", input)
		if result.Status != "AC" {
			t.Fatalf("runner should accept WA output: %+v", result)
		}
		checked, err := (checker.ExactChecker{}).Check(context.Background(), apiChecker(), input, answer, result.Stdout, time.Second, 1<<20)
		if err != nil || checked.Status != "WA" {
			t.Fatalf("expected WA, got %+v err=%v", checked, err)
		}
	})

	t.Run("python tle", func(t *testing.T) {
		result := runCaseWithLimit(t, runnerInstance, "PY3", "testdata/sources/python/tle.py", input, 200*time.Millisecond)
		if result.Status != "TLE" {
			t.Fatalf("expected TLE, got %+v", result)
		}
	})

	t.Run("python mle", func(t *testing.T) {
		result := runCaseWithLimit(t, runnerInstance, "PY3", "testdata/sources/python/mle.py", input, 2*time.Second)
		if result.Status != "MLE" {
			t.Fatalf("expected MLE, got %+v", result)
		}
	})

	t.Run("python rte", func(t *testing.T) {
		result := runCase(t, runnerInstance, "PY3", "testdata/sources/python/rte.py", input)
		if result.Status != "RTE" {
			t.Fatalf("expected RTE, got %+v", result)
		}
	})

	t.Run("cpp ac", func(t *testing.T) {
		result := runCase(t, runnerInstance, "CPP17", "testdata/sources/cpp/ac.cpp", input)
		if result.Status != "AC" || string(result.Stdout) != "8\n" {
			t.Fatalf("unexpected result: %+v stdout=%q", result, result.Stdout)
		}
	})

	t.Run("cpp ce", func(t *testing.T) {
		_, err := runnerInstance.CompileAndRun(context.Background(), "CPP17", string(readFile(t, "testdata/sources/cpp/ce.cpp")), input, 2*time.Second, 64<<20)
		var compileErr *runner.CompileError
		if !errors.As(err, &compileErr) {
			t.Fatalf("expected CompileError, got %v", err)
		}
	})
}

func runCase(t *testing.T, runnerInstance *runner.Runner, language, sourcePath string, input []byte) executor.RunResult {
	t.Helper()
	return runCaseWithLimit(t, runnerInstance, language, sourcePath, input, 2*time.Second)
}

func runCaseWithLimit(t *testing.T, runnerInstance *runner.Runner, language, sourcePath string, input []byte, limit time.Duration) executor.RunResult {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	result, err := runnerInstance.CompileAndRun(ctx, language, string(readFile(t, sourcePath)), input, limit, 64<<20)
	if err != nil {
		t.Fatalf("CompileAndRun: %v", err)
	}
	return result
}

func readFile(t *testing.T, path string) []byte {
	t.Helper()
	data, err := os.ReadFile(filepath.Clean(path))
	if err != nil {
		t.Fatal(err)
	}
	return data
}

func apiChecker() api.Checker {
	return api.Checker{Type: "exact"}
}
