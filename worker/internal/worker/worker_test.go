package worker

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/runner"
)

type fakeClient struct {
	mu          sync.Mutex
	registered  bool
	registeredC map[string]any
	heartbeats  int
	claimed     bool
	started     int
	caseCalls   int
	finished    int
	failed      int
	failResult  string
	job         *api.Job
}

func (f *fakeClient) Register(_ context.Context, req api.RegisterRequest) (api.RegisterResponse, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.registered = true
	f.registeredC = req.Capabilities
	return api.RegisterResponse{JudgeID: 1, HeartbeatInterval: 1}, nil
}

func (f *fakeClient) Heartbeat(_ context.Context, _ api.HeartbeatRequest) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.heartbeats++
	return nil
}

func (f *fakeClient) Claim(_ context.Context, _ api.ClaimRequest) (*api.Job, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.claimed {
		return nil, nil
	}
	f.claimed = true
	return f.job, nil
}

func (f *fakeClient) Start(_ context.Context, _ int64) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.started++
	return nil
}

func (f *fakeClient) Cases(_ context.Context, _ int64, _ api.CasesRequest) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.caseCalls++
	return nil
}

func (f *fakeClient) Finish(_ context.Context, _ int64, _ api.FinishRequest) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.finished++
	return nil
}

func (f *fakeClient) Fail(_ context.Context, _ int64, req api.FailRequest) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.failed++
	f.failResult = req.Result
	return nil
}

func (f *fakeClient) DownloadPackage(_ context.Context, _ int64, _ string) ([]byte, error) {
	return nil, nil
}

type fakeExecutor struct {
	err   error
	cases []api.CaseResult
}

func (f fakeExecutor) Execute(_ context.Context, _ *api.Job) ([]api.CaseResult, error) {
	return f.cases, f.err
}

func testJob() *api.Job {
	return &api.Job{
		JobID:        7,
		SubmissionID: 9,
		Language:     "PY3",
		Package:      api.Package{ProblemID: 1, SHA256: "abc"},
		Cases:        []api.Case{{ID: "1"}},
	}
}

func runWorker(t *testing.T, client *fakeClient, executor Executor) {
	t.Helper()
	worker := &Worker{
		Client:         client,
		Executor:       executor,
		Languages:      []string{"PY3"},
		SandboxVersion: "v1.13.3",
		Poll:           2 * time.Millisecond,
		Heartbeat:      2 * time.Millisecond,
	}
	ctx, cancel := context.WithTimeout(context.Background(), 80*time.Millisecond)
	defer cancel()
	if err := worker.Run(ctx); err != nil && !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("Run: %v", err)
	}
}

func TestWorkerRegistersAndCompletesJob(t *testing.T) {
	client := &fakeClient{job: testJob()}
	executor := fakeExecutor{cases: []api.CaseResult{{CaseNumber: 1, Status: "AC", Points: 100, TotalPoints: 100}}}

	runWorker(t, client, executor)

	client.mu.Lock()
	defer client.mu.Unlock()
	if !client.registered {
		t.Fatal("worker did not register")
	}
	if languages, ok := client.registeredC["languages"].([]string); !ok || len(languages) != 1 || languages[0] != "PY3" {
		t.Fatalf("unexpected capabilities: %+v", client.registeredC)
	}
	if client.registeredC["go_judge_version"] != "v1.13.3" {
		t.Fatalf("missing sandbox version: %+v", client.registeredC)
	}
	if client.started != 1 || client.caseCalls != 1 || client.finished != 1 || client.failed != 0 {
		t.Fatalf("unexpected lifecycle counts: %+v", client)
	}
	if client.heartbeats == 0 {
		t.Fatal("worker did not heartbeat")
	}
}

func TestWorkerFailsJobWhenExecutorErrors(t *testing.T) {
	client := &fakeClient{job: testJob()}
	executor := fakeExecutor{err: errors.New("compile failed")}

	runWorker(t, client, executor)

	client.mu.Lock()
	defer client.mu.Unlock()
	if client.started != 1 || client.finished != 0 || client.failed != 1 {
		t.Fatalf("unexpected lifecycle counts: %+v", client)
	}
}

func TestWorkerReportsCompileErrorAsCE(t *testing.T) {
	client := &fakeClient{job: testJob()}
	executor := fakeExecutor{err: &runner.CompileError{Message: "bad"}}

	runWorker(t, client, executor)

	client.mu.Lock()
	defer client.mu.Unlock()
	if client.failed != 1 || client.failResult != "CE" {
		t.Fatalf("unexpected failure report: failed=%d result=%q", client.failed, client.failResult)
	}
}

func TestWorkerStopsWhenContextIsCancelled(t *testing.T) {
	client := &fakeClient{}
	worker := &Worker{
		Client:    client,
		Executor:  fakeExecutor{},
		Languages: []string{"PY3"},
		Poll:      time.Second,
		Heartbeat: time.Second,
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	if err := worker.Run(ctx); err != nil {
		t.Fatalf("Run: %v", err)
	}
}
