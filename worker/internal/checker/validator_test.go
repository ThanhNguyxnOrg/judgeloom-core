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
)

func TestTestlibValidatorCompilesOnceAndValidatesInput(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		cmd := request["cmd"].([]any)[0].(map[string]any)
		if calls == 1 {
			args := cmd["args"].([]any)
			if args[0] != "g++" || args[5] != "validator.cpp" {
				t.Fatalf("unexpected compiler args: %v", args)
			}
			_ = json.NewEncoder(w).Encode([]map[string]any{{
				"status":  "Accepted",
				"fileIds": map[string]string{"validator": "validator-file"},
			}})
			return
		}
		cached := cmd["copyIn"].(map[string]any)["validator"].(map[string]any)
		if cached["fileId"] != "validator-file" {
			t.Fatalf("unexpected validator cache: %+v", cached)
		}
		stdin := cmd["files"].([]any)[0].(map[string]any)
		if stdin["content"] != "1 2\n" {
			t.Fatalf("unexpected validator stdin: %+v", stdin)
		}
		_ = json.NewEncoder(w).Encode([]map[string]any{{
			"status":     "Accepted",
			"exitStatus": 0,
			"time":       1000000,
			"memory":     2048,
		}})
	}))
	defer server.Close()

	judge := &executor.GoJudge{BaseURL: server.URL, Client: server.Client()}
	validator, err := NewTestlibValidator(
		context.Background(),
		judge,
		api.Checker{Type: "testlib", Source: "int main() { return 0; }"},
		1024,
	)
	if err != nil {
		t.Fatalf("NewTestlibValidator: %v", err)
	}
	result, err := validator.Validate(context.Background(), []byte("1 2\n"), time.Second, 1024)
	if err != nil {
		t.Fatalf("Validate: %v", err)
	}
	if result.Status != "AC" || calls != 2 {
		t.Fatalf("unexpected validator result/calls: %+v calls=%d", result, calls)
	}
}

func TestTestlibValidatorRejectsInvalidInput(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if calls == 1 {
			_ = json.NewEncoder(w).Encode([]map[string]any{{
				"status":  "Accepted",
				"fileIds": map[string]string{"validator": "validator-file"},
			}})
			return
		}
		_ = json.NewEncoder(w).Encode([]map[string]any{{
			"status":     "Accepted",
			"exitStatus": 1,
			"stderr":     "invalid input",
		}})
	}))
	defer server.Close()

	judge := &executor.GoJudge{BaseURL: server.URL, Client: server.Client()}
	validator, err := NewTestlibValidator(
		context.Background(),
		judge,
		api.Checker{Type: "testlib", Source: "int main() { return 1; }"},
		1024,
	)
	if err != nil {
		t.Fatalf("NewTestlibValidator: %v", err)
	}
	result, err := validator.Validate(context.Background(), []byte("bad\n"), time.Second, 1024)
	if err != nil {
		t.Fatalf("Validate: %v", err)
	}
	if result.Status != "IE" {
		t.Fatalf("expected IE, got %+v", result)
	}
}
