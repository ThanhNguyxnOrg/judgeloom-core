package api

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestShadowClientUsesShadowEndpoints(t *testing.T) {
	paths := map[string]bool{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		paths[r.URL.Path] = true
		if r.Method != http.MethodPost {
			t.Fatalf("unexpected method: %s", r.Method)
		}
		if r.URL.Path == "/api/v1/shadow/jobs/claim" {
			_ = json.NewEncoder(w).Encode(Job{JobID: 7, SubmissionID: 9, Language: "PY3"})
			return
		}
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer server.Close()

	client := NewShadowClient(server.URL+"/api/v1", "secret", server.Client())
	job, err := client.Claim(context.Background(), ClaimRequest{Languages: []string{"PY3"}})
	if err != nil {
		t.Fatalf("Claim: %v", err)
	}
	if job == nil || job.JobID != 7 {
		t.Fatalf("unexpected job: %+v", job)
	}
	if err := client.Start(context.Background(), 7); err != nil {
		t.Fatalf("Start: %v", err)
	}
	if err := client.Cases(context.Background(), 7, CasesRequest{}); err != nil {
		t.Fatalf("Cases: %v", err)
	}
	if err := client.Finish(context.Background(), 7, FinishRequest{}); err != nil {
		t.Fatalf("Finish: %v", err)
	}
	if err := client.Fail(context.Background(), 7, FailRequest{}); err != nil {
		t.Fatalf("Fail: %v", err)
	}

	for _, path := range []string{
		"/api/v1/shadow/jobs/claim",
		"/api/v1/shadow/jobs/7/start",
		"/api/v1/shadow/jobs/7/cases",
		"/api/v1/shadow/jobs/7/finish",
		"/api/v1/shadow/jobs/7/fail",
	} {
		if !paths[path] {
			t.Fatalf("missing shadow path %s", path)
		}
	}
}
