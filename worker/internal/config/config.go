package config

import (
	"errors"
	"os"
	"strings"
	"time"
)

type Config struct {
	APIURL       string
	JudgeToken   string
	JudgeName    string
	GoJudgeURL   string
	Languages    []string
	PollInterval time.Duration
	Heartbeat    time.Duration
	CacheDir     string
}

func Load() (Config, error) {
	cfg := Config{
		APIURL:       envOr("JUDGELOOM_API_URL", "http://localhost:8000/api/v1"),
		JudgeToken:   os.Getenv("JUDGELOOM_JUDGE_TOKEN"),
		JudgeName:    os.Getenv("JUDGELOOM_JUDGE_NAME"),
		GoJudgeURL:   envOr("GO_JUDGE_URL", "http://localhost:5050"),
		Languages:    languagesEnv("WORKER_LANGUAGES", "PY3,CPP17"),
		PollInterval: durationEnv("WORKER_POLL_INTERVAL", 2*time.Second),
		Heartbeat:    durationEnv("WORKER_HEARTBEAT", 10*time.Second),
		CacheDir:     envOr("WORKER_CACHE_DIR", "./worker-cache"),
	}
	if cfg.JudgeToken == "" {
		return Config{}, errors.New("JUDGELOOM_JUDGE_TOKEN is required")
	}
	if cfg.JudgeName == "" {
		return Config{}, errors.New("JUDGELOOM_JUDGE_NAME is required")
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
