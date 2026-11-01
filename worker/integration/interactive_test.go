package integration

import (
	"context"
	"net/http"
	"os"
	"testing"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/checker"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/runner"
)

func TestInteractiveCheckerAgainstGoJudge(t *testing.T) {
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
	interactor := `
#include <fstream>
#include <iostream>
int main(int argc, char **argv) {
    std::ifstream input(argv[1]);
    int a, b;
    input >> a >> b;
    std::cout << a + b << std::endl;
    int answer;
    std::cin >> answer;
    return answer == a + b ? 0 : 1;
}
`
	participant := "x = int(input())\nprint(x)\n"
	checkerInstance := &checker.InteractiveChecker{
		Judge:  judge,
		Runner: &runner.Runner{Judge: judge},
	}

	result, err := checkerInstance.Check(
		context.Background(),
		api.Checker{Type: "interactive", Source: interactor},
		"PY3",
		participant,
		[]byte("2 3\n"),
		2*time.Second,
		256<<20,
	)
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if result.Status != "AC" {
		t.Fatalf("expected AC, got %+v", result)
	}
}
