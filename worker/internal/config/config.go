package config

import (
	"errors"
	"fmt"
	"net/url"
	"os"
	"strings"
	"time"
)

type Config struct {
	APIURL            string
	JudgeToken        string
	JudgeName         string
	GoJudgeURL        string
	Languages         []string
	PollInterval      time.Duration
	Heartbeat         time.Duration
	CacheDir          string
	AllowInsecureHTTP bool
	ShadowMode        bool
}

func Load() (Config, error) {
	cfg := Config{
		APIURL:            envOr("JUDGELOOM_API_URL", "http://localhost:8000/api/v1"),
		JudgeToken:        os.Getenv("JUDGELOOM_JUDGE_TOKEN"),
		JudgeName:         os.Getenv("JUDGELOOM_JUDGE_NAME"),
		GoJudgeURL:        envOr("GO_JUDGE_URL", "http://localhost:5050"),
		Languages:         languagesEnv("WORKER_LANGUAGES", "PY3,CPP17"),
		PollInterval:      durationEnv("WORKER_POLL_INTERVAL", 2*time.Second),
		Heartbeat:         durationEnv("WORKER_HEARTBEAT", 10*time.Second),
		CacheDir:          envOr("WORKER_CACHE_DIR", "./worker-cache"),
		AllowInsecureHTTP: boolEnv("WORKER_ALLOW_INSECURE_HTTP", false),
		ShadowMode:        boolEnv("WORKER_SHADOW", false),
	}
	if cfg.JudgeToken == "" {
		return Config{}, errors.New("JUDGELOOM_JUDGE_TOKEN is required")
	}
	if cfg.JudgeName == "" {
		return Config{}, errors.New("JUDGELOOM_JUDGE_NAME is required")
	}
	parsed, err := url.Parse(cfg.APIURL)
	if err != nil || (parsed.Scheme != "http" && parsed.Scheme != "https") || parsed.Host == "" {
		return Config{}, fmt.Errorf("JUDGELOOM_API_URL must be an absolute http(s) URL")
	}
	if parsed.Scheme == "http" && !cfg.AllowInsecureHTTP {
		return Config{}, errors.New("JUDGELOOM_API_URL must use https; set WORKER_ALLOW_INSECURE_HTTP=true only for local development")
	}
	return cfg, nil
}

func envOr(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func languagesEnv(key, fallback string) []string {
	raw := envOr(key, fallback)
	parts := strings.Split(raw, ",")
	result := make([]string, 0, len(parts))
	for _, part := range parts {
		if trimmed := strings.TrimSpace(part); trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
}

func boolEnv(key string, fallback bool) bool {
	value := strings.ToLower(strings.TrimSpace(os.Getenv(key)))
	switch value {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return fallback
	}
}

func durationEnv(key string, fallback time.Duration) time.Duration {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}
	parsed, err := time.ParseDuration(value)
	if err != nil || parsed <= 0 {
		return fallback
	}
	return parsed
}
