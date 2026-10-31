package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/config"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
	store "github.com/ThanhNguyxnOrg/judgeloom-worker/internal/package"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/runner"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/worker"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatal(err)
	}
	client := api.NewClient(cfg.APIURL, cfg.JudgeToken, nil)
	cache := &store.Store{Root: cfg.CacheDir, Client: client}
	if err := cache.Cleanup(72 * time.Hour); err != nil {
		log.Printf("package cache cleanup failed: %v", err)
	}
	judge := &executor.GoJudge{BaseURL: cfg.GoJudgeURL}
	selfTestCtx, cancelSelfTest := context.WithTimeout(context.Background(), 5*time.Second)
	version, err := judge.Version(selfTestCtx)
	cancelSelfTest()
	if err != nil {
		log.Fatalf("go-judge self-test failed: %v", err)
	}
	log.Printf("go-judge self-test passed: build=%s go=%s %s/%s", version.BuildVersion, version.GoVersion, version.OS, version.Platform)
	jobExecutor := &worker.JobExecutor{
		Store:  cache,
		Runner: &runner.Runner{Judge: judge},
		Judge:  judge,
	}
	workerInstance := &worker.Worker{
		Client:         client,
		Executor:       jobExecutor,
		Languages:      cfg.Languages,
		SandboxVersion: version.BuildVersion,
		Poll:           cfg.PollInterval,
		Heartbeat:      cfg.Heartbeat,
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	log.Printf("JudgeLoom worker %s starting for %s (go-judge %s)", cfg.JudgeName, cfg.APIURL, cfg.GoJudgeURL)
	if err := workerInstance.Run(ctx); err != nil {
		log.Fatal(err)
	}
}
