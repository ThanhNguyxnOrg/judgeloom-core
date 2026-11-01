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

func TestNoopCheckerAcceptsAnything(t *testing.T) {
	result, err := (NoopChecker{}).Check(context.Background(), api.Checker{Type: "none"}, []byte("1"), []byte("2"), []byte("anything"), time.Second, 1024)
	if err != nil || result.Status != "AC" {
		t.Fatalf("unexpected result: %+v err=%v", result, err)
	}
}

func TestExactChecker(t *testing.T) {
	got, _ := (ExactChecker{}).Check(context.Background(), api.Checker{}, []byte("1 2\n"), []byte("3\n"), []byte("3\r\n"), time.Second, 1024)
	if got.Status != "AC" {
		t.Fatalf("expected AC, got %+v", got)
	}
	got, _ = (ExactChecker{}).Check(context.Background(), api.Checker{}, []byte("1 2\n"), []byte("3\n"), []byte("4\n"), time.Second, 1024)
	if got.Status != "WA" {
		t.Fatalf("expected WA, got %+v", got)
	}
}

func TestTestlibCheckerMapsExitCodes(t *testing.T) {
	tests := []struct {
		name       string
		exitStatus int
		stderr     string
		wantStatus string
		wantPoints float64
	}{
		{name: "accepted", exitStatus: 0, wantStatus: "AC"},
		{name: "wrong answer", exitStatus: 1, wantStatus: "WA"},
		{name: "presentation", exitStatus: 2, wantStatus: "PE"},
		{name: "fail", exitStatus: 3, wantStatus: "IE"},
		{name: "partial", exitStatus: 5, stderr: "points 50\n", wantStatus: "PT", wantPoints: 50},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			calls := 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				calls++
				if calls == 1 {
					_ = json.NewEncoder(w).Encode([]map[string]any{{"status": "Accepted", "exitStatus": 0, "fileIds": map[string]string{"checker": "chk-1"}}})
					return
				}
				_ = json.NewEncoder(w).Encode([]map[string]any{{"status": "NonZeroExitStatus", "exitStatus": test.exitStatus, "files": map[string]string{"stderr": test.stderr}}})
			}))
			defer server.Close()

			checker := &TestlibChecker{Judge: &executor.GoJudge{BaseURL: server.URL, Client: server.Client()}}
			result, err := checker.Check(context.Background(), api.Checker{Type: "testlib", Source: "checker"}, []byte("1"), []byte("1"), []byte("1"), time.Second, 1024*1024)
			if err != nil {
				t.Fatalf("Check: %v", err)
			}
			if result.Status != test.wantStatus || result.Points != test.wantPoints {
				t.Fatalf("unexpected result: %+v", result)
			}
			if calls != 2 {
				t.Fatalf("expected compile + run, got %d calls", calls)
			}
		})
	}
}

func TestTestlibCheckerPassesOutputBeforeAnswer(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		var request struct {
			Cmd []struct {
				Args []string `json:"args"`
			} `json:"cmd"`
		}
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		if calls == 1 {
			_ = json.NewEncoder(w).Encode([]map[string]any{{"status": "Accepted", "fileIds": map[string]string{"checker": "chk-1"}}})
			return
		}
		args := request.Cmd[0].Args
		want := []string{"/w/checker", "/w/input.txt", "/w/output.txt", "/w/answer.txt"}
		if len(args) != len(want) {
			t.Fatalf("unexpected args: %v", args)
		}
		for index := range want {
			if args[index] != want[index] {
				t.Fatalf("args[%d] = %q, want %q", index, args[index], want[index])
			}
		}
		_ = json.NewEncoder(w).Encode([]map[string]any{{"status": "Accepted", "exitStatus": 0}})
	}))
	defer server.Close()

	checker := &TestlibChecker{Judge: &executor.GoJudge{BaseURL: server.URL, Client: server.Client()}}
	result, err := checker.Check(context.Background(), api.Checker{Type: "testlib", Source: "checker"}, []byte("1"), []byte("2"), []byte("3"), time.Second, 1024*1024)
	if err != nil || result.Status != "AC" {
		t.Fatalf("unexpected result: %+v err=%v", result, err)
	}
}

func TestTestlibCheckerCompileFailure(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode([]map[string]any{{"status": "NonZeroExitStatus", "exitStatus": 1, "files": map[string]string{"stderr": "bad"}}})
	}))
	defer server.Close()

	checker := &TestlibChecker{Judge: &executor.GoJudge{BaseURL: server.URL, Client: server.Client()}}
	result, err := checker.Check(context.Background(), api.Checker{Type: "testlib", Source: "bad"}, nil, nil, nil, time.Second, 1024*1024)
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if result.Status != "IE" || result.Message == "" {
		t.Fatalf("unexpected compile result: %+v", result)
	}
}

func TestTestlibCheckerRequiresSource(t *testing.T) {
	result, err := (&TestlibChecker{}).Check(context.Background(), api.Checker{Type: "testlib"}, nil, nil, nil, time.Second, 1024)
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if result.Status != "IE" {
		t.Fatalf("unexpected result: %+v", result)
	}
}

func itoa(value int) string {
	data, _ := json.Marshal(value)
	return string(data)
}
