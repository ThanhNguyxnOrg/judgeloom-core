package checker

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/runner"
)

func TestInteractiveCheckerRunsInteractorAndParticipant(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		if calls == 1 {
			_ = json.NewEncoder(w).Encode([]map[string]any{{
				"status":  "Accepted",
				"fileIds": map[string]string{"interactor": "interactor-file"},
			}})
			return
		}
		_ = json.NewEncoder(w).Encode([]map[string]any{
			{"status": "Accepted", "exitStatus": 0},
			{"status": "Accepted", "exitStatus": 0},
		})
	}))
	defer server.Close()

	judge := &executor.GoJudge{BaseURL: server.URL, Client: server.Client()}
	checker := &InteractiveChecker{
		Judge:  judge,
		Runner: &runner.Runner{Judge: judge},
	}
	result, err := checker.Check(
		context.Background(),
		api.Checker{Type: "interactive", Source: "int main() { return 0; }"},
		"PY3",
		"print(1)",
		[]byte("1 2\n"),
		time.Second,
		1024,
	)
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if result.Status != "AC" || calls != 2 {
		t.Fatalf("unexpected result/calls: %+v calls=%d", result, calls)
	}
}
