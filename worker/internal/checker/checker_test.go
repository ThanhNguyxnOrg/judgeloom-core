package checker

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
)

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
					_, _ = w.Write([]byte(`{"results":[{"status":"Accepted","exitStatus":0,"fileIDs":{"checker":"chk-1"}}]}`))
					return
				}
				_, _ = w.Write([]byte(`{"results":[{"status":"NonZeroExitStatus","exitStatus":` + itoa(test.exitStatus) + `,"files":{"stderr":"` + base64.StdEncoding.EncodeToString([]byte(test.stderr)) + `"}}]}`))
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

func TestTestlibCheckerCompileFailure(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"results":[{"status":"NonZeroExitStatus","exitStatus":1,"files":{"stderr":"YmFk"}}]}`))
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
