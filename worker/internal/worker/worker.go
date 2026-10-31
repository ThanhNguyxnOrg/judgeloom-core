package worker

import (
	"context"
	"errors"
	"log"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/runner"
)

type Executor interface {
	Execute(ctx context.Context, job *api.Job) ([]api.CaseResult, error)
}

type Worker struct {
	Client         api.Client
	Executor       Executor
	Languages      []string
	SandboxVersion string
	Poll           time.Duration
	Heartbeat      time.Duration
}

func (w *Worker) Run(ctx context.Context) error {
	if w.Client == nil || w.Executor == nil {
		return errors.New("worker client and executor are required")
	}
	if w.Poll <= 0 {
		w.Poll = 2 * time.Second
	}
	if w.Heartbeat <= 0 {
		w.Heartbeat = 10 * time.Second
	}

	capabilities := map[string]any{
		"languages": w.Languages,
		"sandbox":   "go-judge",
	}
	if w.SandboxVersion != "" {
		capabilities["go_judge_version"] = w.SandboxVersion
	}
	if _, err := w.Client.Register(ctx, api.RegisterRequest{ProtocolVersion: 1, Capabilities: capabilities}); err != nil {
		return err
	}

	heartbeatCtx, cancelHeartbeat := context.WithCancel(ctx)
	defer cancelHeartbeat()
	go w.heartbeat(heartbeatCtx)

	for {
		if ctx.Err() != nil {
			return nil
		}
		job, err := w.Client.Claim(ctx, api.ClaimRequest{Languages: w.Languages, MaxJobs: 1})
		if err != nil {
			if ctx.Err() != nil {
				return nil
			}
			log.Printf("claim failed: %v", err)
			if !wait(ctx, w.Poll) {
				return nil
			}
			continue
		}
		if job == nil {
			if !wait(ctx, w.Poll) {
				return nil
			}
			continue
		}
		if err := w.Client.Start(ctx, job.JobID); err != nil {
			log.Printf("job %d start failed: %v", job.JobID, err)
			if !wait(ctx, w.Poll) {
				return nil
			}
			continue
		}

		cases, err := w.Executor.Execute(ctx, job)
		if err != nil {
			w.failJob(ctx, job, err)
			if !wait(ctx, w.Poll) {
				return nil
			}
			continue
		}

		caseTotal := len(job.Cases)
		if caseTotal == 0 {
			caseTotal = len(cases)
		}
		casePassed := 0
		for _, result := range cases {
			if result.Status == "AC" {
				casePassed++
			}
		}

		if err := w.Client.Cases(ctx, job.JobID, api.CasesRequest{PackageSHA256: job.Package.SHA256, Cases: cases}); err != nil {
			log.Printf("job %d case report failed: %v", job.JobID, err)
			if !wait(ctx, w.Poll) {
				return nil
			}
			continue
		}
		if err := w.Client.Finish(ctx, job.JobID, api.FinishRequest{
			PackageSHA256: job.Package.SHA256,
			Status:        "completed",
			CaseTotal:     caseTotal,
			CasePassed:    casePassed,
		}); err != nil {
			log.Printf("job %d finish failed: %v", job.JobID, err)
			if !wait(ctx, w.Poll) {
				return nil
			}
		}
	}
}

func (w *Worker) heartbeat(ctx context.Context) {
	ticker := time.NewTicker(w.Heartbeat)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := w.Client.Heartbeat(ctx, api.HeartbeatRequest{}); err != nil && ctx.Err() == nil {
				log.Printf("heartbeat failed: %v", err)
			}
		}
	}
}

func (w *Worker) failJob(ctx context.Context, job *api.Job, err error) {
	result := "IE"
	var compileErr *runner.CompileError
	if errors.As(err, &compileErr) {
		result = "CE"
	}
	if failErr := w.Client.Fail(ctx, job.JobID, api.FailRequest{
		PackageSHA256: job.Package.SHA256,
		Status:        "error",
		Result:        result,
		ErrorMessage:  err.Error(),
	}); failErr != nil {
		log.Printf("job %d fail report failed: %v", job.JobID, failErr)
	}
}

func wait(ctx context.Context, delay time.Duration) bool {
	timer := time.NewTimer(delay)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return false
	case <-timer.C:
		return true
	}
}
