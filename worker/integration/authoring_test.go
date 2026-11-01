package integration

import (
	"archive/zip"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/authoring"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/checker"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/runner"
)

const testlibGeneratorSource = `
#include "testlib.h"
#include <cstdio>
#include <cstdlib>
int main(int argc, char **argv) {
    registerGen(argc, argv, 1);
    int a = atoi(argv[1]);
    int b = atoi(argv[2]);
    printf("%d %d\n", a, b);
    return 0;
}
`

const testlibValidatorSource = `
#include "testlib.h"
int main(int argc, char **argv) {
    registerValidation(argc, argv);
    inf.readInt(0, 1000000, "a");
    inf.readSpace();
    inf.readInt(0, 1000000, "b");
    inf.readEoln();
    inf.readEof();
    return 0;
}
`

const testlibCheckerSource = `
#include "testlib.h"
int main(int argc, char **argv) {
    registerTestlibCmd(argc, argv);
    long long a = inf.readLong();
    long long b = inf.readLong();
    long long expected = ans.readLong();
    long long got = ouf.readLong();
    if (a + b != expected) {
        quitf(_fail, "bad jury answer");
    }
    if (expected != got) {
        quitf(_wa, "expected %lld, got %lld", expected, got);
    }
    quitf(_ok, "ok");
}
`

const authoringSolutionSource = `
#include <iostream>
int main() {
    long long a = 0, b = 0;
    std::cin >> a >> b;
    std::cout << a + b << "\n";
    return 0;
}
`

func TestTestlibCheckerAgainstGoJudge(t *testing.T) {
	baseURL := os.Getenv("GO_JUDGE_URL")
	if baseURL == "" {
		t.Skip("GO_JUDGE_URL is not set")
	}
	judge := &executor.GoJudge{
		BaseURL:   baseURL,
		Client:    &http.Client{Timeout: 60 * time.Second},
		AuthToken: os.Getenv("GO_JUDGE_TOKEN"),
	}
	checkerImpl := &checker.TestlibChecker{Judge: judge}
	spec := api.Checker{Type: "testlib", Source: testlibCheckerSource}
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()

	accepted, err := checkerImpl.Check(ctx, spec, []byte("1 2\n"), []byte("3\n"), []byte("3\n"), 2*time.Second, 256<<20)
	if err != nil || accepted.Status != "AC" {
		t.Fatalf("expected AC, got %+v err=%v", accepted, err)
	}
	rejected, err := checkerImpl.Check(ctx, spec, []byte("1 2\n"), []byte("3\n"), []byte("4\n"), 2*time.Second, 256<<20)
	if err != nil || rejected.Status != "WA" {
		t.Fatalf("expected WA, got %+v err=%v", rejected, err)
	}
}

func TestPackageBuilderAgainstGoJudge(t *testing.T) {
	baseURL := os.Getenv("GO_JUDGE_URL")
	if baseURL == "" {
		t.Skip("GO_JUDGE_URL is not set")
	}
	judge := &executor.GoJudge{
		BaseURL:   baseURL,
		Client:    &http.Client{Timeout: 60 * time.Second},
		AuthToken: os.Getenv("GO_JUDGE_TOKEN"),
	}
	builder := &authoring.Builder{Judge: judge, Runner: &runner.Runner{Judge: judge}}

	points := 50.0
	spec := authoring.Spec{
		ProblemCode: "aplusb",
		TimeLimit:   2,
		MemoryLimit: 262144,
		Checker:     authoring.CheckerSpec{Type: "testlib", Source: testlibCheckerSource},
		Validator:   &authoring.ValidatorSpec{Type: "testlib", Source: testlibValidatorSource},
		Generator:   authoring.ProgramSpec{Language: "CPP17", Source: testlibGeneratorSource},
		Solution:    authoring.ProgramSpec{Language: "CPP17", Source: authoringSolutionSource},
		Cases: []authoring.CaseSpec{
			{Args: []string{"1", "2"}, Points: &points, Group: "default"},
			{Args: []string{"3", "4"}, Points: &points, Group: "default"},
		},
	}

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	outPath := filepath.Join(t.TempDir(), "aplusb.zip")
	result, err := builder.Build(ctx, spec, outPath)
	if err != nil {
		t.Fatalf("Build: %v", err)
	}
	if result.Cases != 2 || result.SizeBytes <= 0 {
		t.Fatalf("unexpected result: %+v", result)
	}

	reader, err := zip.OpenReader(outPath)
	if err != nil {
		t.Fatalf("open package: %v", err)
	}
	defer reader.Close()
	entries := map[string][]byte{}
	for _, file := range reader.File {
		handle, err := file.Open()
		if err != nil {
			t.Fatal(err)
		}
		data, err := io.ReadAll(handle)
		_ = handle.Close()
		if err != nil {
			t.Fatal(err)
		}
		entries[file.Name] = data
	}

	if string(entries["data/01.in"]) != "1 2\n" || string(entries["data/01.ans"]) != "3\n" {
		t.Fatalf("unexpected first case: %q %q", entries["data/01.in"], entries["data/01.ans"])
	}
	if string(entries["data/02.in"]) != "3 4\n" || string(entries["data/02.ans"]) != "7\n" {
		t.Fatalf("unexpected second case: %q %q", entries["data/02.in"], entries["data/02.ans"])
	}

	var manifest struct {
		Cases []struct {
			Input        string `json:"input"`
			Answer       string `json:"answer"`
			InputSHA256  string `json:"input_sha256"`
			AnswerSHA256 string `json:"answer_sha256"`
		} `json:"cases"`
		Generator struct {
			Language     string `json:"language"`
			SourceSHA256 string `json:"source_sha256"`
			Cases        []struct {
				Args []string `json:"args"`
			} `json:"cases"`
		} `json:"generator"`
		Validator *struct {
			Type string `json:"type"`
		} `json:"validator"`
	}
	if err := json.Unmarshal(entries["manifest.json"], &manifest); err != nil {
		t.Fatalf("decode manifest: %v", err)
	}
	if len(manifest.Cases) != 2 || manifest.Cases[0].InputSHA256 == "" || manifest.Cases[0].AnswerSHA256 == "" {
		t.Fatalf("unexpected manifest cases: %+v", manifest.Cases)
	}
	if manifest.Generator.Language != "CPP17" || manifest.Generator.SourceSHA256 == "" || len(manifest.Generator.Cases) != 2 {
		t.Fatalf("unexpected generator metadata: %+v", manifest.Generator)
	}
	if manifest.Validator == nil || manifest.Validator.Type != "testlib" {
		t.Fatalf("unexpected validator metadata: %+v", manifest.Validator)
	}
}
