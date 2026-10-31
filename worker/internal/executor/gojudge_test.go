package executor

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestGoJudgeVersion(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet || r.URL.Path != "/version" {
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		_, _ = w.Write([]byte(`{"buildVersion":"v1.13.3","goVersion":"go1.27.2","os":"linux","platform":"amd64"}`))
	}))
	defer server.Close()

	judge := &GoJudge{BaseURL: server.URL, Client: server.Client()}
	info, err := judge.Version(context.Background())
	if err != nil {
		t.Fatalf("Version: %v", err)
	}
	if info.BuildVersion != "v1.13.3" || info.GoVersion != "go1.27.2" {
		t.Fatalf("unexpected version: %+v", info)
	}
}

func TestGoJudgeVersionRejectsMissingBuildVersion(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"goVersion":"go1.27.2"}`))
	}))
	defer server.Close()

	judge := &GoJudge{BaseURL: server.URL, Client: server.Client()}
	if _, err := judge.Version(context.Background()); err == nil {
		t.Fatal("expected missing buildVersion to fail")
	}
}

func TestGoJudgeRunRequestShapeAndResponse(t *testing.T) {
	var requestBody map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/run" {
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		if err := json.NewDecoder(r.Body).Decode(&requestBody); err != nil {
			t.Fatal(err)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`[{
			"status":"Accepted",
			"exitStatus":0,
			"time":1500000000,
			"memory":2048,
			"files":{"stdout":"hello\n","stderr":""},
			"fileIds":{"main":"file-1"}
		}]`))
	}))
	defer server.Close()

	judge := &GoJudge{BaseURL: server.URL, Client: server.Client(), RetryDelay: time.Millisecond}
	result, err := judge.Run(context.Background(), RunSpec{
		Args:        []string{"python3", "main.py"},
		Env:         []string{"PATH=/usr/bin"},
		StdIn:       []byte("1 2\n"),
		CopyIn:      map[string][]byte{"main.py": []byte("print(1)\n")},
		CPUTime:     2 * time.Second,
		ClockTime:   4 * time.Second,
		MemoryBytes: 262144 * 1024,
		ProcLimit:   64,
	})
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	if result.Status != "AC" || result.ExitStatus != 0 || result.Time != 1500*time.Millisecond || result.Memory != 2048 {
		t.Fatalf("unexpected result: %+v", result)
	}
	if string(result.Stdout) != "hello\n" || result.FileIDs["main"] != "file-1" {
		t.Fatalf("unexpected output: %+v", result)
	}

	cmd := requestBody["cmd"].([]any)[0].(map[string]any)
	if cmd["cpuLimit"].(float64) != float64((2 * time.Second).Nanoseconds()) {
		t.Fatalf("unexpected cpu limit: %v", cmd["cpuLimit"])
	}
	if cmd["clockLimit"].(float64) != float64((4 * time.Second).Nanoseconds()) {
		t.Fatalf("unexpected clock limit: %v", cmd["clockLimit"])
	}
	if cmd["memoryLimit"].(float64) != float64(262144*1024) || cmd["procLimit"].(float64) != 64 {
		t.Fatalf("unexpected limits: %+v", cmd)
	}
	copyIn := cmd["copyIn"].(map[string]any)["main.py"].(map[string]any)
	if copyIn["content"] != "print(1)\n" {
		t.Fatalf("unexpected copyIn: %+v", copyIn)
	}
	files := cmd["files"].([]any)
	if len(files) != 3 {
		t.Fatalf("expected 3 files, got %d", len(files))
	}
	stdoutPipe := files[1].(map[string]any)
	if stdoutPipe["name"] != "stdout" || stdoutPipe["pipe"] != true {
		t.Fatalf("unexpected stdout pipe: %+v", stdoutPipe)
	}
}

func TestGoJudgeMapsStatuses(t *testing.T) {
	tests := []struct {
		name   string
		status string
		want   string
	}{
		{name: "accepted", status: "Accepted", want: "AC"},
		{name: "tle", status: "TimeLimitExceeded", want: "TLE"},
		{name: "mle", status: "MemoryLimitExceeded", want: "MLE"},
		{name: "ole", status: "OutputLimitExceeded", want: "OLE"},
		{name: "rte", status: "NonZeroExitStatus", want: "RTE"},
		{name: "signal", status: "Signalled", want: "RTE"},
		{name: "dangerous", status: "DangerousSyscall", want: "IE"},
		{name: "internal", status: "InternalError", want: "IE"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				_ = json.NewEncoder(w).Encode([]map[string]any{{"status": test.status, "exitStatus": 0}})
			}))
			defer server.Close()
			judge := &GoJudge{BaseURL: server.URL, Client: server.Client()}
			result, err := judge.Run(context.Background(), RunSpec{Args: []string{"true"}})
			if err != nil {
				t.Fatalf("Run: %v", err)
			}
			if result.Status != test.want {
				t.Fatalf("status = %q, want %q", result.Status, test.want)
			}
		})
	}
}

func TestGoJudgeHTTPFailureRetriesThenReturnsIE(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		http.Error(w, "unavailable", http.StatusServiceUnavailable)
	}))
	defer server.Close()

	judge := &GoJudge{BaseURL: server.URL, Client: server.Client(), RetryDelay: time.Millisecond}
	result, err := judge.Run(context.Background(), RunSpec{Args: []string{"true"}})
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	if result.Status != "IE" || calls != 2 {
		t.Fatalf("unexpected result/calls: %+v calls=%d", result, calls)
	}
}
