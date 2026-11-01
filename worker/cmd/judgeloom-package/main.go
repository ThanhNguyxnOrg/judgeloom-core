package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/authoring"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/runner"
)

func main() {
	specPath := flag.String("spec", "", "path to the package spec JSON")
	outPath := flag.String("out", "", "path to write the generated package ZIP")
	goJudgeURL := flag.String("go-judge", envOr("GO_JUDGE_URL", "http://localhost:5050"), "go-judge base URL")
	token := flag.String("token", os.Getenv("GO_JUDGE_TOKEN"), "go-judge bearer token")
	timeout := flag.Duration("timeout", 30*time.Minute, "overall build timeout")
	flag.Parse()

	if *specPath == "" || *outPath == "" {
		flag.Usage()
		os.Exit(2)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	ctx, cancel := context.WithTimeout(ctx, *timeout)
	defer cancel()

	spec, err := authoring.LoadSpec(*specPath)
	if err != nil {
		log.Fatalf("load spec: %v", err)
	}
	judge := &executor.GoJudge{BaseURL: *goJudgeURL, AuthToken: *token}
	if err := judge.CheckAuth(ctx); err != nil {
		log.Fatalf("go-judge auth: %v", err)
	}
	builder := &authoring.Builder{
		Judge:  judge,
		Runner: &runner.Runner{Judge: judge},
	}
	result, err := builder.Build(ctx, spec, *outPath)
	if err != nil {
		log.Fatalf("build package: %v", err)
	}
	fmt.Printf(
		"wrote %s (%d cases, %d bytes, sha256=%s)\n",
		result.Path,
		result.Cases,
		result.SizeBytes,
		result.SHA256,
	)
}

func envOr(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
