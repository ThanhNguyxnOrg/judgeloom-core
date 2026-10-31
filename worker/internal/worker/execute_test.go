package worker

import (
	"archive/zip"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/checker"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
	store "github.com/ThanhNguyxnOrg/judgeloom-worker/internal/package"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/runner"
)

type fakeDownloader struct {
	payload []byte
}

func (f fakeDownloader) DownloadPackage(_ context.Context, _ int64, _ string) ([]byte, error) {
	return f.payload, nil
}

func zipPackage(t *testing.T, manifest map[string]any) []byte {
	t.Helper()
	var buffer bytes.Buffer
	writer := zip.NewWriter(&buffer)
	manifestData, err := json.Marshal(manifest)
	if err != nil {
		t.Fatal(err)
	}
	entries := map[string][]byte{
		"manifest.json": manifestData,
		"data/01.in":    []byte("1 2\n"),
		"data/01.ans":   []byte("3\n"),
		"data/02.in":    []byte("3 4\n"),
		"data/02.ans":   []byte("7\n"),
	}
	for name, content := range entries {
		file, err := writer.Create(name)
		if err != nil {
			t.Fatal(err)
		}
		_, _ = file.Write(content)
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	return buffer.Bytes()
}

var testPackageOnce sync.Once
var testPackageBytes []byte

func testPackage(t *testing.T) []byte {
	t.Helper()
	testPackageOnce.Do(func() {
		testPackageBytes = zipPackage(t, map[string]any{
			"cases": []map[string]any{
				{"input": "data/01.in", "answer": "data/01.ans", "points": 50, "group": "default"},
				{"input": "data/02.in", "answer": "data/02.ans", "points": 50, "group": "default"},
			},
			"groups": []map[string]any{{"id": "default", "points": 100, "mode": "sum"}},
		})
	})
	return testPackageBytes
}

func testExecutor(t *testing.T, _ string, jobChecker api.Checker, serverHandler http.HandlerFunc) *JobExecutor {
	t.Helper()
	server := httptest.NewServer(serverHandler)
	t.Cleanup(server.Close)
	judge := &executor.GoJudge{BaseURL: server.URL, Client: server.Client()}
	store := &store.Store{Root: t.TempDir(), Client: fakeDownloader{payload: testPackage(t)}}
	return &JobExecutor{
		Store:   store,
		Runner:  &runner.Runner{Judge: judge},
		Judge:   judge,
		Checker: &checker.ExactChecker{},
	}
}

func executionJob(t *testing.T, language string) *api.Job {
	payload := testPackage(t)
	sum := sha256.Sum256(payload)
	digest := hex.EncodeToString(sum[:])
	return &api.Job{
		JobID:        1,
		SubmissionID: 2,
		Language:     language,
		Source:       "print(1)",
		Limits:       api.Limits{Time: 1, Memory: 1024},
		Package:      api.Package{ProblemID: 7, SHA256: digest},
		Cases: []api.Case{
			{ID: "1", Input: "data/01.in", Answer: "data/01.ans", Points: 50, Group: "default"},
			{ID: "2", Input: "data/02.in", Answer: "data/02.ans", Points: 50, Group: "default"},
		},
		Checker: api.Checker{Type: "exact"},
	}
}

func TestExecuteRunModeUsesCustomInput(t *testing.T) {
	var requestBody map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := json.NewDecoder(r.Body).Decode(&requestBody); err != nil {
			t.Fatal(err)
		}
		_ = json.NewEncoder(w).Encode([]map[string]any{{
			"status":     "Accepted",
			"exitStatus": 0,
			"time":       1000000,
			"memory":     2048,
			"files":      map[string]string{"stdout": "hello\n"},
		}})
	}))
	defer server.Close()

	judge := &executor.GoJudge{BaseURL: server.URL, Client: server.Client()}
	jobExecutor := &JobExecutor{Runner: &runner.Runner{Judge: judge}}
	job := &api.Job{
		JobID:          1,
		SubmissionID:   2,
		Language:       "PY3",
		Mode:           "run",
		Source:         "print(1)",
		CustomInput:    "custom stdin\n",
		ExpectedOutput: "hello\n",
		Limits:         api.Limits{Time: 1, Memory: 1024},
	}

	cases, err := jobExecutor.Execute(context.Background(), job)
	if err != nil {
		t.Fatalf("Execute: %v", err)
	}
	if len(cases) != 1 || cases[0].Status != "AC" || cases[0].Output != "hello\n" {
		t.Fatalf("unexpected run cases: %+v", cases)
	}
	if cases[0].Points != 0 || cases[0].TotalPoints != 0 {
		t.Fatalf("run should not award points: %+v", cases[0])
	}

	cmd := requestBody["cmd"].([]any)[0].(map[string]any)
	files := cmd["files"].([]any)
	stdin := files[0].(map[string]any)
	if stdin["content"] != "custom stdin\n" {
		t.Fatalf("unexpected custom stdin: %+v", stdin)
	}
}

func TestExecuteRunModeMarksWrongExpectedOutput(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode([]map[string]any{{
			"status":     "Accepted",
			"exitStatus": 0,
			"time":       1000000,
			"memory":     2048,
			"files":      map[string]string{"stdout": "actual\n"},
		}})
	}))
	defer server.Close()

	judge := &executor.GoJudge{BaseURL: server.URL, Client: server.Client()}
	jobExecutor := &JobExecutor{Runner: &runner.Runner{Judge: judge}}
	job := &api.Job{
		Language:       "PY3",
		Mode:           "run",
		Source:         "print(1)",
		CustomInput:    "custom\n",
		ExpectedOutput: "expected\n",
		Limits:         api.Limits{Time: 1, Memory: 1024},
	}

	cases, err := jobExecutor.Execute(context.Background(), job)
	if err != nil {
		t.Fatalf("Execute: %v", err)
	}
	if len(cases) != 1 || cases[0].Status != "WA" {
		t.Fatalf("expected WA, got %+v", cases)
	}
}

func TestExecuteMapsCaseResults(t *testing.T) {
	calls := 0
	executorUnderTest := testExecutor(t, "PY3", api.Checker{}, func(w http.ResponseWriter, r *http.Request) {
		calls++
		output := "3"
		if calls == 2 {
			output = "0"
		}
		_ = json.NewEncoder(w).Encode([]map[string]any{{
			"status":     "Accepted",
			"exitStatus": 0,
			"time":       1000000,
			"memory":     2048,
			"files":      map[string]string{"stdout": output},
		}})
	})

	cases, err := executorUnderTest.Execute(context.Background(), executionJob(t, "PY3"))
	if err != nil {
		t.Fatalf("Execute: %v", err)
	}
	if len(cases) != 2 {
		t.Fatalf("expected 2 cases, got %d", len(cases))
	}
	if cases[0].Status != "AC" || cases[0].Points != 50 || cases[0].TotalPoints != 50 {
		t.Fatalf("unexpected first case: %+v", cases[0])
	}
	if cases[1].Status != "WA" || cases[1].Points != 0 {
		t.Fatalf("unexpected second case: %+v", cases[1])
	}
	if cases[0].TimeUsed != 0.001 || cases[0].MemoryUsed != 2 {
		t.Fatalf("unexpected metrics: %+v", cases[0])
	}
}

func TestExecuteMapsTLE(t *testing.T) {
	executorUnderTest := testExecutor(t, "PY3", api.Checker{}, func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode([]map[string]any{{"status": "TimeLimitExceeded", "exitStatus": 9, "time": 1000000000}})
	})

	cases, err := executorUnderTest.Execute(context.Background(), executionJob(t, "PY3"))
	if err != nil {
		t.Fatalf("Execute: %v", err)
	}
	if len(cases) == 0 || cases[0].Status != "TLE" || cases[0].Points != 0 {
		t.Fatalf("unexpected TLE cases: %+v", cases)
	}
}

func TestExecutePropagatesCompileError(t *testing.T) {
	executorUnderTest := testExecutor(t, "CPP17", api.Checker{}, func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode([]map[string]any{{"status": "NonZeroExitStatus", "exitStatus": 1, "files": map[string]string{"stderr": "bad"}}})
	})
	job := executionJob(t, "CPP17")
	job.Cases = job.Cases[:1]

	_, err := executorUnderTest.Execute(context.Background(), job)
	var compileErr *runner.CompileError
	if !errors.As(err, &compileErr) {
		t.Fatalf("expected CompileError, got %v", err)
	}
}

func TestExecuteShortCircuitsAfterFailure(t *testing.T) {
	calls := 0
	executorUnderTest := testExecutor(t, "PY3", api.Checker{}, func(w http.ResponseWriter, r *http.Request) {
		calls++
		_ = json.NewEncoder(w).Encode([]map[string]any{{"status": "Accepted", "exitStatus": 0, "files": map[string]string{"stdout": "0"}}})
	})
	job := executionJob(t, "PY3")
	job.ShortCircuit = true

	cases, err := executorUnderTest.Execute(context.Background(), job)
	if err != nil {
		t.Fatalf("Execute: %v", err)
	}
	if len(cases) != 1 || calls != 1 {
		t.Fatalf("expected one short-circuited case, got %d cases, %d calls", len(cases), calls)
	}
}

func TestExecuteWorksWithEmptyCheckerType(t *testing.T) {
	executorUnderTest := testExecutor(t, "PY3", api.Checker{}, func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode([]map[string]any{{"status": "Accepted", "exitStatus": 0, "files": map[string]string{"stdout": "3"}}})
	})
	job := executionJob(t, "PY3")
	job.Cases = job.Cases[:1]
	job.Checker = api.Checker{}
	if _, err := executorUnderTest.Execute(context.Background(), job); err != nil {
		t.Fatalf("Execute: %v", err)
	}
}

func TestExecuteRejectsMissingPackage(t *testing.T) {
	judge := &executor.GoJudge{}
	store := &store.Store{Root: t.TempDir(), Client: fakeDownloader{payload: []byte("not a zip")}}
	jobExecutor := &JobExecutor{Store: store, Runner: &runner.Runner{Judge: judge}, Judge: judge}
	if _, err := jobExecutor.Execute(context.Background(), executionJob(t, "PY3")); err == nil {
		t.Fatal("expected package error")
	}
}
