package authoring

import (
	"archive/zip"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/runner"
)

type fakeJudge struct {
	generatorCompiled bool
	solutionCompiled  bool
	generatorHeader   bool
	solutionHeader    bool
	generatorRuns     int
	solutionRuns      int
	failGenerator     bool
	failSolution      bool
}

type fakeCommand struct {
	Args  []string `json:"args"`
	Files []*struct {
		Content *string `json:"content"`
	} `json:"files"`
	CopyIn map[string]struct {
		Content *string `json:"content"`
		FileID  string  `json:"fileId"`
	} `json:"copyIn"`
}

type fakeRequest struct {
	Cmd []fakeCommand `json:"cmd"`
}

func (f *fakeJudge) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	var request fakeRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if len(request.Cmd) != 1 {
		http.Error(w, "expected one command", http.StatusBadRequest)
		return
	}
	command := request.Cmd[0]
	if len(command.Args) > 0 && command.Args[0] == "g++" {
		source := command.CopyIn["main.cpp"].Content
		if source == nil {
			http.Error(w, "missing source", http.StatusBadRequest)
			return
		}
		if strings.Contains(*source, "GENERATOR") {
			f.generatorCompiled = true
			f.generatorHeader = command.CopyIn["testlib.h"].Content != nil
			writeResult(w, map[string]any{"status": "Accepted", "exitStatus": 0, "fileIds": map[string]string{"main": "gen-bin"}})
			return
		}
		f.solutionCompiled = true
		_, hasHeader := command.CopyIn["testlib.h"]
		f.solutionHeader = hasHeader
		writeResult(w, map[string]any{"status": "Accepted", "exitStatus": 0, "fileIds": map[string]string{"main": "sol-bin"}})
		return
	}

	if len(command.Files) == 0 || command.Files[0] == nil || command.Files[0].Content == nil {
		http.Error(w, "missing stdin", http.StatusBadRequest)
		return
	}
	switch command.CopyIn["main"].FileID {
	case "gen-bin":
		f.generatorRuns++
		if f.failGenerator {
			writeResult(w, map[string]any{"status": "TimeLimitExceeded", "exitStatus": 0, "files": map[string]string{"stderr": "generator timeout"}})
			return
		}
		args := command.Args[1:]
		writeResult(w, map[string]any{"status": "Accepted", "exitStatus": 0, "files": map[string]string{"stdout": strings.Join(args, " ") + "\n"}})
	case "sol-bin":
		f.solutionRuns++
		if f.failSolution {
			writeResult(w, map[string]any{"status": "NonZeroExitStatus", "exitStatus": 1, "files": map[string]string{"stderr": "solution crashed"}})
			return
		}
		fields := strings.Fields(*command.Files[0].Content)
		sum := 0
		for _, field := range fields {
			value, err := strconv.Atoi(field)
			if err != nil {
				http.Error(w, err.Error(), http.StatusBadRequest)
				return
			}
			sum += value
		}
		writeResult(w, map[string]any{"status": "Accepted", "exitStatus": 0, "files": map[string]string{"stdout": fmt.Sprintf("%d\n", sum)}})
	default:
		http.Error(w, "unknown binary", http.StatusBadRequest)
	}
}

func writeResult(w http.ResponseWriter, result map[string]any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode([]map[string]any{result})
}

func testBuilder(t *testing.T, fake *fakeJudge) (*Builder, func()) {
	t.Helper()
	server := httptest.NewServer(fake)
	judge := &executor.GoJudge{BaseURL: server.URL, Client: server.Client()}
	return &Builder{Judge: judge, Runner: &runner.Runner{Judge: judge}}, server.Close
}

func validSpec() Spec {
	points := 50.0
	return Spec{
		ProblemCode: "aplusb",
		TimeLimit:   2,
		MemoryLimit: 262144,
		Checker:     CheckerSpec{Type: "exact"},
		Generator:   ProgramSpec{Language: "CPP17", Source: "// GENERATOR\n"},
		Solution:    ProgramSpec{Language: "CPP17", Source: "// SOLUTION\n"},
		Cases: []CaseSpec{
			{Args: []string{"1", "2"}, Points: &points, Group: "default"},
			{Args: []string{"3", "4"}, Points: &points, Group: "default"},
		},
		Groups: []GroupSpec{{ID: "default", Points: 100, Mode: "sum"}},
	}
}

func TestBuildWritesImportablePackage(t *testing.T) {
	fake := &fakeJudge{}
	builder, closeServer := testBuilder(t, fake)
	defer closeServer()

	outPath := filepath.Join(t.TempDir(), "aplusb.zip")
	result, err := builder.Build(context.Background(), validSpec(), outPath)
	if err != nil {
		t.Fatalf("Build: %v", err)
	}
	if !fake.generatorCompiled || !fake.solutionCompiled {
		t.Fatalf("expected both compiles: %+v", fake)
	}
	if !fake.generatorHeader || fake.solutionHeader {
		t.Fatalf("unexpected testlib header usage: %+v", fake)
	}
	if fake.generatorRuns != 2 || fake.solutionRuns != 2 {
		t.Fatalf("unexpected run counts: %+v", fake)
	}
	if result.Cases != 2 || result.SizeBytes <= 0 || len(result.SHA256) != 64 {
		t.Fatalf("unexpected result: %+v", result)
	}

	reader, err := zip.OpenReader(outPath)
	if err != nil {
		t.Fatalf("open archive: %v", err)
	}
	defer reader.Close()
	entries := map[string][]byte{}
	for _, file := range reader.File {
		handle, err := file.Open()
		if err != nil {
			t.Fatal(err)
		}
		data, readErr := io.ReadAll(handle)
		_ = handle.Close()
		if readErr != nil {
			t.Fatal(readErr)
		}
		entries[file.Name] = data
	}

	var manifest packageManifest
	if err := json.Unmarshal(entries["manifest.json"], &manifest); err != nil {
		t.Fatalf("decode manifest: %v", err)
	}
	if manifest.Schema != 1 || manifest.ProblemCode != "aplusb" || manifest.Checker.Type != "exact" {
		t.Fatalf("unexpected manifest: %+v", manifest)
	}
	if manifest.Generator.Language != "CPP17" || manifest.Generator.SourceSHA256 != sha256Hex([]byte("// GENERATOR\n")) {
		t.Fatalf("unexpected generator metadata: %+v", manifest.Generator)
	}
	if len(manifest.Generator.Cases) != 2 || strings.Join(manifest.Generator.Cases[1].Args, " ") != "3 4" {
		t.Fatalf("unexpected generator cases: %+v", manifest.Generator.Cases)
	}
	if manifest.Solution.SourceSHA256 != sha256Hex([]byte("// SOLUTION\n")) {
		t.Fatalf("unexpected solution metadata: %+v", manifest.Solution)
	}
	if len(manifest.Cases) != 2 {
		t.Fatalf("unexpected cases: %+v", manifest.Cases)
	}
	if string(entries["data/01.in"]) != "1 2\n" || string(entries["data/01.ans"]) != "3\n" {
		t.Fatalf("unexpected first case files: %q %q", entries["data/01.in"], entries["data/01.ans"])
	}
	if manifest.Cases[0].InputSHA256 != sha256Hex([]byte("1 2\n")) || manifest.Cases[0].AnswerSHA256 != sha256Hex([]byte("3\n")) {
		t.Fatalf("unexpected hashes: %+v", manifest.Cases[0])
	}
	if manifest.Cases[0].Points != 50 || manifest.Cases[0].Group != "default" {
		t.Fatalf("unexpected case metadata: %+v", manifest.Cases[0])
	}
}

func TestBuildReportsGeneratorFailure(t *testing.T) {
	fake := &fakeJudge{failGenerator: true}
	builder, closeServer := testBuilder(t, fake)
	defer closeServer()

	_, err := builder.Build(context.Background(), validSpec(), filepath.Join(t.TempDir(), "out.zip"))
	if err == nil || !strings.Contains(err.Error(), "generator failed") {
		t.Fatalf("expected generator failure, got %v", err)
	}
	if fake.solutionRuns != 0 {
		t.Fatalf("solution should not run: %+v", fake)
	}
}

func TestBuildReportsSolutionFailure(t *testing.T) {
	fake := &fakeJudge{failSolution: true}
	builder, closeServer := testBuilder(t, fake)
	defer closeServer()

	_, err := builder.Build(context.Background(), validSpec(), filepath.Join(t.TempDir(), "out.zip"))
	if err == nil || !strings.Contains(err.Error(), "solution failed") {
		t.Fatalf("expected solution failure, got %v", err)
	}
}
