package executor

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
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

type VersionInfo struct {
	BuildVersion string `json:"buildVersion"`
	GoVersion    string `json:"goVersion"`
	OS           string `json:"os"`
	Platform     string `json:"platform"`
}

type InteractiveResult struct {
	Participant RunResult
	Interactor  RunResult
}

type pipeIndex struct {
	Index int `json:"index"`
	FD    int `json:"fd"`
}

type pipeMap struct {
	In    pipeIndex `json:"in"`
	Out   pipeIndex `json:"out"`
	Proxy bool      `json:"proxy,omitempty"`
	Name  string    `json:"name,omitempty"`
}

func (g *GoJudge) Version(ctx context.Context) (VersionInfo, error) {
	httpClient := g.Client
	if httpClient == nil {
		httpClient = http.DefaultClient
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, strings.TrimRight(g.BaseURL, "/")+"/version", nil)
	if err != nil {
		return VersionInfo{}, err
	}
	resp, err := httpClient.Do(req)
	if err != nil {
		return VersionInfo{}, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return VersionInfo{}, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return VersionInfo{}, fmt.Errorf("go-judge version: %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}
	var info VersionInfo
	if err := json.Unmarshal(body, &info); err != nil {
		return VersionInfo{}, fmt.Errorf("decode go-judge version: %w", err)
	}
	if info.BuildVersion == "" {
		return VersionInfo{}, errors.New("go-judge version response is missing buildVersion")
	}
	return info, nil
}

func (g *GoJudge) Run(ctx context.Context, spec RunSpec) (RunResult, error) {
	request := runRequest{
		RequestID: requestID(),
		Cmd:       []cmdSpec{runCommand(spec, []*cmdFile{filePtr(memoryInput(spec.StdIn)), filePtr(pipeOutput("stdout")), filePtr(pipeOutput("stderr"))})},
	}
	results, err := g.doRunWithRetry(ctx, request)
	if err != nil {
		return RunResult{Status: "IE", Error: err.Error()}, nil
	}
	if len(results) == 0 {
		return RunResult{Status: "IE", Error: "go-judge returned no results"}, nil
	}
	return toRunResult(results[0], "stdout", "stderr"), nil
}

func (g *GoJudge) RunInteractive(ctx context.Context, participant, interactor RunSpec) (InteractiveResult, error) {
	request := runRequest{
		RequestID: requestID(),
		Cmd: []cmdSpec{
			runCommand(interactor, []*cmdFile{nil, nil, filePtr(pipeOutput("interactor_stderr"))}),
			runCommand(participant, []*cmdFile{nil, nil, filePtr(pipeOutput("participant_stderr"))}),
		},
		PipeMapping: []pipeMap{
			{In: pipeIndex{Index: 0, FD: 1}, Out: pipeIndex{Index: 1, FD: 0}},
			{In: pipeIndex{Index: 1, FD: 1}, Out: pipeIndex{Index: 0, FD: 0}},
		},
	}
	results, err := g.doRunWithRetry(ctx, request)
	if err != nil {
		return InteractiveResult{}, err
	}
	if len(results) < 2 {
		return InteractiveResult{}, errors.New("go-judge returned fewer than two interactive results")
	}
	return InteractiveResult{
		Interactor:  toRunResult(results[0], "stdout", "interactor_stderr"),
		Participant: toRunResult(results[1], "stdout", "participant_stderr"),
	}, nil
}

func (g *GoJudge) doRunWithRetry(ctx context.Context, request runRequest) ([]runResult, error) {
	delay := g.RetryDelay
	if delay <= 0 {
		delay = time.Second
	}
	var lastErr error
	for attempt := 0; attempt < 2; attempt++ {
		results, err := g.doRun(ctx, request)
		if err == nil {
			return results, nil
		}
		lastErr = err
		if attempt == 0 {
			timer := time.NewTimer(delay)
			select {
			case <-ctx.Done():
				timer.Stop()
				return nil, ctx.Err()
			case <-timer.C:
			}
		}
	}
	return nil, lastErr
}

func (g *GoJudge) doRun(ctx context.Context, request runRequest) ([]runResult, error) {
	payload, err := json.Marshal(request)
	if err != nil {
		return nil, err
	}

	url := strings.TrimRight(g.BaseURL, "/") + "/run"
	httpClient := g.Client
	if httpClient == nil {
		httpClient = http.DefaultClient
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("go-judge %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}

	var results []runResult
	if err := json.Unmarshal(body, &results); err != nil {
		return nil, err
	}
	return results, nil
}

func runCommand(spec RunSpec, files []*cmdFile) cmdSpec {
	return cmdSpec{
		Args:          spec.Args,
		Env:           spec.Env,
		Files:         files,
		CPULimit:      uint64(maxDuration(spec.CPUTime, 0)),
		ClockLimit:    uint64(maxDuration(spec.ClockTime, spec.CPUTime*2)),
		MemoryLimit:   uint64(maxInt64(spec.MemoryBytes, 0)),
		ProcLimit:     uint64(maxInt(spec.ProcLimit, 1)),
		CopyIn:        copyInFiles(spec.CopyIn, spec.CopyInCached),
		CopyOutCached: spec.CopyOutCached,
	}
}

func toRunResult(result runResult, stdoutKey, stderrKey string) RunResult {
	return RunResult{
		Status:     normalizeStatus(result.Status),
		ExitStatus: result.ExitStatus,
		Time:       time.Duration(result.Time),
		Memory:     int64(result.Memory),
		Stdout:     []byte(result.Files[stdoutKey]),
		Stderr:     []byte(result.Files[stderrKey]),
		FileIDs:    result.FileIDs,
		Error:      result.Error,
	}
}

func filePtr(file cmdFile) *cmdFile {
	return &file
}

type runRequest struct {
	RequestID   string    `json:"requestId"`
	Cmd         []cmdSpec `json:"cmd"`
	PipeMapping []pipeMap `json:"pipeMapping,omitempty"`
}

type cmdSpec struct {
	Args          []string           `json:"args"`
	Env           []string           `json:"env,omitempty"`
	Files         []*cmdFile         `json:"files,omitempty"`
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
