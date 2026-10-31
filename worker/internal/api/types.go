package api

import (
	"fmt"
)

type RegisterRequest struct {
	ProtocolVersion int            `json:"protocol_version"`
	Capabilities    map[string]any `json:"capabilities"`
}

type RegisterResponse struct {
	JudgeID           int64 `json:"judge_id"`
	HeartbeatInterval int   `json:"heartbeat_interval"`
}

type HeartbeatRequest struct {
	Load           float64  `json:"load"`
	RunningJobs    int      `json:"running_jobs"`
	CachedPackages []string `json:"cached_packages,omitempty"`
}

type ClaimRequest struct {
	Languages   []string `json:"languages"`
	MaxJobs     int      `json:"max_jobs,omitempty"`
	WaitSeconds int      `json:"wait_seconds,omitempty"`
}

type Limits struct {
	Time   float64 `json:"time"`
	Memory int64   `json:"memory"`
}

type Package struct {
	ProblemID int64  `json:"problem_id"`
	SHA256    string `json:"sha256"`
	URL       string `json:"url"`
}

type Checker struct {
	Type     string `json:"type"`
	Language string `json:"language,omitempty"`
	Source   string `json:"source,omitempty"`
}

type Case struct {
	ID     string  `json:"id"`
	Input  string  `json:"input"`
	Answer string  `json:"answer"`
	Points float64 `json:"points"`
	Group  string  `json:"group"`
}

type Group struct {
	ID     string  `json:"id"`
	Points float64 `json:"points"`
	Mode   string  `json:"mode"`
}

type Job struct {
	JobID          int64    `json:"job_id"`
	SubmissionID   int64    `json:"submission_id"`
	Language       string   `json:"language"`
	Source         string   `json:"source"`
	Mode           string   `json:"mode"`
	CustomInput    string   `json:"custom_input"`
	ExpectedOutput string   `json:"expected_output"`
	Limits         Limits   `json:"limits"`
	ShortCircuit   bool     `json:"short_circuit"`
	PartialScore   bool     `json:"partial_score"`
	ContestPoints  *float64 `json:"contest_points,omitempty"`
	Package        Package  `json:"package"`
	Checker        Checker  `json:"checker"`
	Cases          []Case   `json:"cases"`
	Groups         []Group  `json:"groups"`
	LeaseSeconds   int      `json:"lease_seconds"`
}

type CaseResult struct {
	CaseNumber  int     `json:"case_number"`
	Status      string  `json:"status"`
	TimeUsed    float64 `json:"time_used"`
	MemoryUsed  int64   `json:"memory_used"`
	Points      float64 `json:"points"`
	TotalPoints float64 `json:"total_points"`
	Feedback    string  `json:"feedback,omitempty"`
	Output      string  `json:"output,omitempty"`
}

type CasesRequest struct {
	PackageSHA256 string       `json:"package_sha256,omitempty"`
	Cases         []CaseResult `json:"cases"`
}

type FinishRequest struct {
	PackageSHA256 string  `json:"package_sha256,omitempty"`
	Status        string  `json:"status"`
	Result        *string `json:"result,omitempty"`
	Points        float64 `json:"points"`
	TimeUsed      float64 `json:"time_used"`
	MemoryUsed    int64   `json:"memory_used"`
	CaseTotal     int     `json:"case_total"`
	CasePassed    int     `json:"case_passed"`
	ErrorMessage  string  `json:"error_message,omitempty"`
}

type FailRequest struct {
	PackageSHA256 string `json:"package_sha256,omitempty"`
	Status        string `json:"status"`
	Result        string `json:"result"`
	ErrorMessage  string `json:"error_message,omitempty"`
}

type APIError struct {
	StatusCode int    `json:"-"`
	Message    string `json:"error"`
	Code       string `json:"code"`
}

func (e *APIError) Error() string {
	return fmt.Sprintf("judge api %d: %s (%s)", e.StatusCode, e.Message, e.Code)
}
