package runner

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/language"
)

func TestProfiles(t *testing.T) {
	python, ok := language.Get("PY3")
	if !ok || python.SourceName != "main.py" || python.Run.Args[0] != "python3" || python.Compile != nil {
		t.Fatalf("unexpected Python profile: %+v", python)
	}
	cpp, ok := language.Get("CPP17")
	if !ok || cpp.SourceName != "main.cpp" || cpp.Compile == nil {
		t.Fatalf("unexpected C++ profile: %+v", cpp)
	}
	if strings.Join(cpp.Compile.Args, " ") != "g++ -O2 -std=c++17 -o main main.cpp" {
		t.Fatalf("unexpected C++ compile args: %v", cpp.Compile.Args)
	}
	if len(cpp.Compile.CopyOutCached) != 1 || cpp.Compile.CopyOutCached[0] != "main" {
		t.Fatalf("unexpected C++ copyOutCached: %v", cpp.Compile.CopyOutCached)
	}
	if _, ok := language.Get("RUST"); ok {
		t.Fatal("unexpected RUST profile")
	}
}

func TestRunnerPythonCompileAndRun(t *testing.T) {
	var request map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		_, _ = w.Write([]byte(`[{"status":"Accepted","exitStatus":0,"time":1000000,"memory":1024,"files":{"stdout":"hello\n"}}]`))
	}))
	defer server.Close()

	runner := &Runner{Judge: &executor.GoJudge{BaseURL: server.URL, Client: server.Client()}}
	result, err := runner.CompileAndRun(context.Background(), "PY3", "print(1)\n", []byte("1 2\n"), 2*time.Second, 262144*1024)
	if err != nil {
		t.Fatalf("CompileAndRun: %v", err)
	}
	if result.Status != "AC" || string(result.Stdout) != "hello\n" {
		t.Fatalf("unexpected result: %+v", result)
	}

	cmd := request["cmd"].([]any)[0].(map[string]any)
	if strings.Join(anyStrings(cmd["args"]), " ") != "python3 main.py" {
		t.Fatalf("unexpected args: %v", cmd["args"])
	}
	copyIn := cmd["copyIn"].(map[string]any)["main.py"].(map[string]any)
	if copyIn["content"] != "print(1)\n" {
		t.Fatalf("unexpected source copyIn: %+v", copyIn)
	}
	files := cmd["files"].([]any)
	stdin := files[0].(map[string]any)
	if stdin["content"] != "1 2\n" {
		t.Fatalf("unexpected stdin: %+v", stdin)
	}
}

func TestRunnerCppCompilesCachedBinaryThenRuns(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		cmd := request["cmd"].([]any)[0].(map[string]any)
		if calls == 1 {
			if strings.Join(anyStrings(cmd["args"]), " ") != "g++ -O2 -std=c++17 -o main main.cpp" {
				t.Fatalf("unexpected compile args: %v", cmd["args"])
			}
			cached := cmd["copyOutCached"].([]any)[0].(string)
			if cached != "main" {
				t.Fatalf("unexpected copyOutCached: %v", cached)
			}
			_, _ = w.Write([]byte(`[{"status":"Accepted","exitStatus":0,"fileIds":{"main":"bin-1"}}]`))
			return
		}
		if strings.Join(anyStrings(cmd["args"]), " ") != "/w/main" {
			t.Fatalf("unexpected run args: %v", cmd["args"])
		}
		mainFile := cmd["copyIn"].(map[string]any)["main"].(map[string]any)
		if mainFile["fileId"] != "bin-1" {
			t.Fatalf("unexpected cached binary: %+v", mainFile)
		}
		_, _ = w.Write([]byte(`[{"status":"Accepted","exitStatus":0}]`))
	}))
	defer server.Close()

	runner := &Runner{Judge: &executor.GoJudge{BaseURL: server.URL, Client: server.Client()}}
	result, err := runner.CompileAndRun(context.Background(), "CPP17", "int main(){}", []byte(""), time.Second, 262144*1024)
	if err != nil {
		t.Fatalf("CompileAndRun: %v", err)
	}
	if result.Status != "AC" || calls != 2 {
		t.Fatalf("unexpected result/calls: %+v calls=%d", result, calls)
	}
}

func TestRunnerCompileErrorDoesNotRun(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		_, _ = w.Write([]byte(`[{"status":"NonZeroExitStatus","exitStatus":1,"files":{"stderr":"bad"}}]`))
	}))
	defer server.Close()

	runner := &Runner{Judge: &executor.GoJudge{BaseURL: server.URL, Client: server.Client()}}
	_, err := runner.CompileAndRun(context.Background(), "CPP17", "bad", nil, time.Second, 1024*1024)
	var compileErr *CompileError
	if !errors.As(err, &compileErr) {
		t.Fatalf("expected CompileError, got %v", err)
	}
	if calls != 1 {
		t.Fatalf("expected one compile call, got %d", calls)
	}
}

func TestRunnerRejectsUnknownLanguage(t *testing.T) {
	runner := &Runner{}
	_, err := runner.CompileAndRun(context.Background(), "RUST", "fn main(){}", nil, time.Second, 1024*1024)
	if !errors.Is(err, ErrUnsupportedLanguage) {
		t.Fatalf("expected ErrUnsupportedLanguage, got %v", err)
	}
}

func anyStrings(value any) []string {
	items := value.([]any)
	result := make([]string, 0, len(items))
	for _, item := range items {
		result = append(result, item.(string))
	}
	return result
}
