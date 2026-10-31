package executor

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type GoJudge struct {
	BaseURL    string
	Client     *http.Client
	RetryDelay time.Duration
}

type RunSpec struct {
	Args          []string
	Env           []string
	StdIn         []byte
	CopyIn        map[string][]byte
	CopyInCached  map[string]string
	CopyOutCached []string
	CPUTime       time.Duration
	ClockTime     time.Duration
	MemoryBytes   int64
	ProcLimit     int
}

type RunResult struct {
	Status     string
	ExitStatus int
	Time       time.Duration
	Memory     int64
	Stdout     []byte
	Stderr     []byte
	FileIDs    map[string]string
	Error      string
}

func (g *GoJudge) Run(ctx context.Context, spec RunSpec) (RunResult, error) {
	delay := g.RetryDelay
	if delay <= 0 {
		delay = time.Second
	}
	var lastErr error
	for attempt := 0; attempt < 2; attempt++ {
		result, err := g.runOnce(ctx, spec)
		if err == nil {
			return result, nil
		}
		lastErr = err
		if attempt == 0 {
			timer := time.NewTimer(delay)
			select {
			case <-ctx.Done():
				timer.Stop()
				return RunResult{Status: "IE", Error: ctx.Err().Error()}, nil
			case <-timer.C:
			}
		}
	}
	return RunResult{Status: "IE", Error: lastErr.Error()}, nil
}

func (g *GoJudge) runOnce(ctx context.Context, spec RunSpec) (RunResult, error) {
	request := runRequest{
		RequestID: requestID(),
		Cmd: []cmdSpec{{
			Args:          spec.Args,
			Env:           spec.Env,
			Files:         []cmdFile{memoryInput(spec.StdIn), pipeOutput("stdout"), pipeOutput("stderr")},
			CPULimit:      uint64(maxDuration(spec.CPUTime, 0)),
			ClockLimit:    uint64(maxDuration(spec.ClockTime, spec.CPUTime*2)),
			MemoryLimit:   uint64(maxInt64(spec.MemoryBytes, 0)),
			ProcLimit:     uint64(maxInt(spec.ProcLimit, 1)),
			CopyIn:        copyInFiles(spec.CopyIn, spec.CopyInCached),
			CopyOutCached: spec.CopyOutCached,
		}},
	}
	payload, err := json.Marshal(request)
	if err != nil {
		return RunResult{}, err
	}

	url := strings.TrimRight(g.BaseURL, "/") + "/run"
	httpClient := g.Client
	if httpClient == nil {
		httpClient = http.DefaultClient
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(payload))
	if err != nil {
		return RunResult{}, err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := httpClient.Do(req)
	if err != nil {
		return RunResult{}, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return RunResult{}, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return RunResult{}, fmt.Errorf("go-judge %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}

	var results []runResult
	if err := json.Unmarshal(body, &results); err != nil {
		return RunResult{}, err
	}
	if len(results) == 0 {
		return RunResult{Status: "IE", Error: "go-judge returned no results"}, nil
	}
	result := results[0]
	return RunResult{
		Status:     normalizeStatus(result.Status),
		ExitStatus: result.ExitStatus,
		Time:       time.Duration(result.Time),
		Memory:     int64(result.Memory),
		Stdout:     []byte(result.Files["stdout"]),
		Stderr:     []byte(result.Files["stderr"]),
		FileIDs:    result.FileIDs,
		Error:      result.Error,
	}, nil
}

type runRequest struct {
	RequestID string    `json:"requestId"`
	Cmd       []cmdSpec `json:"cmd"`
}

type cmdSpec struct {
	Args          []string           `json:"args"`
	Env           []string           `json:"env,omitempty"`
	Files         []cmdFile          `json:"files,omitempty"`
	CPULimit      uint64             `json:"cpuLimit,omitempty"`
	ClockLimit    uint64             `json:"clockLimit,omitempty"`
	MemoryLimit   uint64             `json:"memoryLimit,omitempty"`
	ProcLimit     uint64             `json:"procLimit,omitempty"`
	CopyIn        map[string]cmdFile `json:"copyIn,omitempty"`
	CopyOutCached []string           `json:"copyOutCached,omitempty"`
}

type cmdFile struct {
	Content *string `json:"content,omitempty"`
	FileID  *string `json:"fileId,omitempty"`
	Name    *string `json:"name,omitempty"`
	Max     *int64  `json:"max,omitempty"`
	Pipe    bool    `json:"pipe,omitempty"`
}

type runResult struct {
	Status     string            `json:"status"`
	ExitStatus int               `json:"exitStatus"`
	Error      string            `json:"error"`
	Time       uint64            `json:"time"`
	Memory     uint64            `json:"memory"`
	Files      map[string]string `json:"files"`
	FileIDs    map[string]string `json:"fileIds"`
}

func memoryInput(content []byte) cmdFile {
	text := string(content)
	return cmdFile{Content: &text}
}

func pipeOutput(name string) cmdFile {
	max := int64(16 << 20)
	return cmdFile{Name: &name, Max: &max, Pipe: true}
}

func copyInFiles(files map[string][]byte, cached map[string]string) map[string]cmdFile {
	if len(files) == 0 && len(cached) == 0 {
		return nil
	}
	result := make(map[string]cmdFile, len(files)+len(cached))
	for name, content := range files {
		result[name] = memoryInput(content)
	}
	for name, fileID := range cached {
		result[name] = cmdFile{FileID: &fileID}
	}
	return result
}

func normalizeStatus(status string) string {
	normalized := strings.ToLower(strings.NewReplacer("_", "", " ", "").Replace(status))
	switch normalized {
	case "accepted", "ok":
		return "AC"
	case "wronganswer":
		return "WA"
	case "partiallycorrect":
		return "PT"
	case "timelimitexceeded":
		return "TLE"
	case "memorylimitexceeded":
		return "MLE"
	case "outputlimitexceeded":
		return "OLE"
	case "nonzeroexitstatus", "signalled":
		return "RTE"
	default:
		return "IE"
	}
}

func requestID() string {
	var data [8]byte
	if _, err := rand.Read(data[:]); err != nil {
		return fmt.Sprintf("%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(data[:])
}

func maxDuration(value, fallback time.Duration) time.Duration {
	if value > 0 {
		return value
	}
	return fallback
}

func maxInt64(value, fallback int64) int64 {
	if value > 0 {
		return value
	}
	return fallback
}

func maxInt(value, fallback int) int {
	if value > 0 {
		return value
	}
	return fallback
}
