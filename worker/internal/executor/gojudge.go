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
			Args:           spec.Args,
			Env:            spec.Env,
			Files:          []fileSpec{memoryInput(spec.StdIn), pipeOutput("stdout"), pipeOutput("stderr")},
			CPUTimeLimit:   uint64(maxDuration(spec.CPUTime, 0)),
			ClockTimeLimit: uint64(maxDuration(spec.ClockTime, spec.CPUTime*2)),
			MemoryLimit:    uint64(maxInt64(spec.MemoryBytes, 0)),
			ProcLimit:      uint64(maxInt(spec.ProcLimit, 1)),
			CopyIn:         copyInFiles(spec.CopyIn),
			CopyOutCached:  copyOutCached(spec.CopyOutCached),
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

	var response runResponse
	if err := json.Unmarshal(body, &response); err != nil {
		return RunResult{}, err
	}
	if response.Error != "" || len(response.Results) == 0 {
		return RunResult{Status: "IE", Error: response.Error}, nil
	}
	result := response.Results[0]
	return RunResult{
		Status:     normalizeStatus(result.Status),
		ExitStatus: result.ExitStatus,
		Time:       time.Duration(result.Time),
		Memory:     int64(result.Memory),
		Stdout:     result.Files["stdout"],
		Stderr:     result.Files["stderr"],
		FileIDs:    result.FileIDs,
		Error:      result.Error,
	}, nil
}

type runRequest struct {
	RequestID string    `json:"requestID"`
	Cmd       []cmdSpec `json:"cmd"`
}

type cmdSpec struct {
	Args           []string            `json:"args"`
	Env            []string            `json:"env,omitempty"`
	Files          []fileSpec          `json:"files,omitempty"`
	CPUTimeLimit   uint64              `json:"cpuTimeLimit,omitempty"`
	ClockTimeLimit uint64              `json:"clockTimeLimit,omitempty"`
	MemoryLimit    uint64              `json:"memoryLimit,omitempty"`
	ProcLimit      uint64              `json:"procLimit,omitempty"`
	CopyIn         map[string]fileSpec `json:"copyIn,omitempty"`
	CopyOutCached  []copyOutFile       `json:"copyOutCached,omitempty"`
}

type fileSpec struct {
	Memory *memoryFile `json:"memory,omitempty"`
	Pipe   *pipeFile   `json:"pipe,omitempty"`
}

type memoryFile struct {
	Content []byte `json:"content"`
}

type pipeFile struct {
	Name string `json:"name"`
	Max  uint64 `json:"max"`
}

type copyOutFile struct {
	Name string `json:"name"`
}

type runResponse struct {
	RequestID string      `json:"requestID"`
	Results   []runResult `json:"results"`
	Error     string      `json:"error"`
}

type runResult struct {
	Status     json.RawMessage   `json:"status"`
	ExitStatus int               `json:"exitStatus"`
	Error      string            `json:"error"`
	Time       uint64            `json:"time"`
	Memory     uint64            `json:"memory"`
	Files      map[string][]byte `json:"files"`
	FileIDs    map[string]string `json:"fileIDs"`
}

func memoryInput(content []byte) fileSpec {
	return fileSpec{Memory: &memoryFile{Content: content}}
}

func pipeOutput(name string) fileSpec {
	return fileSpec{Pipe: &pipeFile{Name: name, Max: 16 << 20}}
}

func copyInFiles(files map[string][]byte) map[string]fileSpec {
	if len(files) == 0 {
		return nil
	}
	result := make(map[string]fileSpec, len(files))
	for name, content := range files {
		result[name] = memoryInput(content)
	}
	return result
}

func copyOutCached(names []string) []copyOutFile {
	result := make([]copyOutFile, 0, len(names))
	for _, name := range names {
		result = append(result, copyOutFile{Name: name})
	}
	return result
}

func normalizeStatus(raw json.RawMessage) string {
	var text string
	if json.Unmarshal(raw, &text) == nil {
		switch strings.ToLower(strings.ReplaceAll(text, "_", "")) {
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
		}
		return "IE"
	}
	var number int
	if json.Unmarshal(raw, &number) == nil {
		switch number {
		case 1:
			return "AC"
		case 2:
			return "WA"
		case 3:
			return "PT"
		case 4:
			return "MLE"
		case 5:
			return "TLE"
		case 6:
			return "OLE"
		case 8, 9:
			return "RTE"
		}
	}
	return "IE"
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
