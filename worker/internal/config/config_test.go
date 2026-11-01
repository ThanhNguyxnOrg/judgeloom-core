package config

import (
	"strings"
	"testing"
)

func setRequiredEnv(t *testing.T, apiURL string) {
	t.Helper()
	t.Setenv("JUDGELOOM_API_URL", apiURL)
	t.Setenv("JUDGELOOM_JUDGE_TOKEN", "dummy-token")
	t.Setenv("JUDGELOOM_JUDGE_NAME", "dummy-judge")
	t.Setenv("WORKER_ALLOW_INSECURE_HTTP", "")
}

func TestLoadRejectsPlainHTTPByDefault(t *testing.T) {
	setRequiredEnv(t, "http://control-plane:8000/api/v1")

	_, err := Load()
	if err == nil || !strings.Contains(err.Error(), "must use https") {
		t.Fatalf("expected HTTPS enforcement, got %v", err)
	}
}

func TestLoadAllowsPlainHTTPWhenExplicitlyEnabled(t *testing.T) {
	setRequiredEnv(t, "http://control-plane:8000/api/v1")
	t.Setenv("WORKER_ALLOW_INSECURE_HTTP", "true")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if !cfg.AllowInsecureHTTP {
		t.Fatal("expected insecure HTTP override")
	}
}

func TestLoadReadsShadowMode(t *testing.T) {
	setRequiredEnv(t, "https://judgeloom.example.com/api/v1")
	t.Setenv("WORKER_SHADOW", "true")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if !cfg.ShadowMode {
		t.Fatal("expected shadow mode")
	}
}

func TestLoadAcceptsHTTPS(t *testing.T) {
	setRequiredEnv(t, "https://judgeloom.example.com/api/v1")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.APIURL != "https://judgeloom.example.com/api/v1" {
		t.Fatalf("unexpected API URL: %s", cfg.APIURL)
	}
}

func TestLoadReadsGoJudgeToken(t *testing.T) {
	setRequiredEnv(t, "https://judgeloom.example.com/api/v1")
	t.Setenv("GO_JUDGE_TOKEN", "sandbox-secret")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.GoJudgeToken != "sandbox-secret" {
		t.Fatalf("unexpected go-judge token: %q", cfg.GoJudgeToken)
	}
}

func TestLoadRejectsNonAbsoluteURL(t *testing.T) {
	setRequiredEnv(t, "control-plane:8000/api/v1")

	if _, err := Load(); err == nil {
		t.Fatal("expected invalid URL rejection")
	}
}
