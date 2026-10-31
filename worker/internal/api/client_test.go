package api

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func testClient(t *testing.T, handler http.HandlerFunc) *HTTPClient {
	t.Helper()
	server := httptest.NewServer(handler)
	t.Cleanup(server.Close)
	return NewClient(server.URL+"/api/v1", "secret", server.Client())
}

func TestClientClaim(t *testing.T) {
	client := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/api/v1/jobs/claim" {
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		if got := r.Header.Get("Authorization"); got != "Bearer secret" {
			t.Fatalf("unexpected auth header: %q", got)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{
			"job_id":101,
			"submission_id":55,
			"language":"PY3",
			"source":"print(1)",
			"limits":{"time":2.0,"memory":262144},
			"short_circuit":false,
			"partial_score":false,
			"package":{"problem_id":7,"sha256":"abc","url":"/api/v1/judge/packages/7?sha256=abc"},
			"checker":{"type":"exact"},
			"cases":[{"id":"1","input":"data/01.in","answer":"data/01.ans","points":50,"group":"default"}],
			"groups":[{"id":"default","points":100,"mode":"sum"}],
			"lease_seconds":60
		}`))
	})

	job, err := client.Claim(context.Background(), ClaimRequest{Languages: []string{"PY3"}})
	if err != nil {
		t.Fatalf("Claim: %v", err)
	}
	if job == nil || job.JobID != 101 || job.SubmissionID != 55 || job.Language != "PY3" {
		t.Fatalf("unexpected job: %+v", job)
	}
	if job.Package.SHA256 != "abc" || len(job.Cases) != 1 || job.Groups[0].Mode != "sum" {
		t.Fatalf("unexpected job payload: %+v", job)
	}
}

func TestClientClaimNoContent(t *testing.T) {
	client := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNoContent)
	})

	job, err := client.Claim(context.Background(), ClaimRequest{Languages: []string{"PY3"}})
	if err != nil {
		t.Fatalf("Claim: %v", err)
	}
	if job != nil {
		t.Fatalf("expected nil job, got %+v", job)
	}
}

func TestClientPostsCaseFinishAndFail(t *testing.T) {
	paths := map[string]bool{}
	client := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		paths[r.URL.Path] = true
		if r.Method != http.MethodPost {
			t.Fatalf("unexpected method: %s", r.Method)
		}
		if got := r.Header.Get("Authorization"); got != "Bearer secret" {
			t.Fatalf("unexpected auth header: %q", got)
		}
		_, _ = w.Write([]byte(`{"ok":true}`))
	})

	if err := client.Cases(context.Background(), 101, CasesRequest{PackageSHA256: "abc", Cases: []CaseResult{{CaseNumber: 1, Status: "AC", Points: 50, TotalPoints: 50}}}); err != nil {
		t.Fatalf("Cases: %v", err)
	}
	if err := client.Finish(context.Background(), 101, FinishRequest{PackageSHA256: "abc", Status: "completed"}); err != nil {
		t.Fatalf("Finish: %v", err)
	}
	if err := client.Fail(context.Background(), 101, FailRequest{PackageSHA256: "abc", Status: "error", Result: "CE"}); err != nil {
		t.Fatalf("Fail: %v", err)
	}

	for _, path := range []string{"/api/v1/jobs/101/cases", "/api/v1/jobs/101/finish", "/api/v1/jobs/101/fail"} {
		if !paths[path] {
			t.Fatalf("missing request path %s", path)
		}
	}
}

func TestClientDownloadPackageVerifiesHash(t *testing.T) {
	payload := []byte("package bytes")
	sum := sha256.Sum256(payload)
	digest := hex.EncodeToString(sum[:])

	var queries []string
	client := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet || r.URL.Path != "/api/v1/packages/7" {
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		queries = append(queries, r.URL.Query().Get("sha256"))
		_, _ = w.Write(payload)
	})

	got, err := client.DownloadPackage(context.Background(), 7, digest)
	if err != nil {
		t.Fatalf("DownloadPackage: %v", err)
	}
	if string(got) != string(payload) {
		t.Fatalf("unexpected payload: %q", got)
	}

	wrong := strings.Repeat("0", 64)
	_, err = client.DownloadPackage(context.Background(), 7, wrong)
	if !errors.Is(err, ErrHashMismatch) {
		t.Fatalf("expected ErrHashMismatch, got %v", err)
	}
	if len(queries) != 2 || queries[0] != digest || queries[1] != wrong {
		t.Fatalf("unexpected hash queries: %v", queries)
	}
}

func TestClientReturnsAPIError(t *testing.T) {
	client := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusConflict)
		_ = json.NewEncoder(w).Encode(APIError{StatusCode: http.StatusConflict, Message: "job conflict", Code: "judge_job_conflict"})
	})

	err := client.Start(context.Background(), 101)
	if err == nil {
		t.Fatal("expected error")
	}
	var apiErr *APIError
	if !errors.As(err, &apiErr) {
		t.Fatalf("expected APIError, got %T: %v", err, err)
	}
	if apiErr.StatusCode != http.StatusConflict || apiErr.Code != "judge_job_conflict" {
		t.Fatalf("unexpected API error: %+v", apiErr)
	}
}
