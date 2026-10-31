package worker

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/checker"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
	store "github.com/ThanhNguyxnOrg/judgeloom-worker/internal/package"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/runner"
)

type JobExecutor struct {
	Store   *store.Store
	Runner  *runner.Runner
	Judge   *executor.GoJudge
	Checker checker.Checker
}

type packageManifest struct {
	Cases   []packageCase `json:"cases"`
	Checker api.Checker   `json:"checker"`
}

type packageCase struct {
	ID           string  `json:"id"`
	Input        string  `json:"input"`
	Answer       string  `json:"answer"`
	InputSHA256  string  `json:"input_sha256"`
	AnswerSHA256 string  `json:"answer_sha256"`
	Points       float64 `json:"points"`
	Group        string  `json:"group"`
}

func (e *JobExecutor) Execute(ctx context.Context, job *api.Job) ([]api.CaseResult, error) {
	if e.Runner == nil {
		return nil, fmt.Errorf("job executor runner is required")
	}

	timeLimit := time.Duration(job.Limits.Time * float64(time.Second))
	if timeLimit <= 0 {
		timeLimit = 2 * time.Second
	}
	memoryBytes := job.Limits.Memory * 1024
	if memoryBytes <= 0 {
		memoryBytes = 256 * 1024 * 1024
	}

	if job.Mode == "run" {
		run, err := e.Runner.CompileAndRun(ctx, job.Language, job.Source, []byte(job.CustomInput), timeLimit, memoryBytes)
		if err != nil {
			return nil, err
		}
		result := api.CaseResult{
			CaseNumber: 1,
			Status:     run.Status,
			TimeUsed:   float64(run.Time) / float64(time.Second),
			MemoryUsed: run.Memory / 1024,
			Feedback:   run.Error,
			Output:     truncate(run.Stdout, 4096),
		}
		return []api.CaseResult{result}, nil
	}

	if e.Store == nil {
		return nil, fmt.Errorf("job executor store is required for submissions")
	}
	dir, err := e.Store.Ensure(ctx, job.Package.ProblemID, job.Package.SHA256)
	if err != nil {
		return nil, err
	}

	manifest, err := loadManifest(dir)
	if err != nil {
		return nil, err
	}
	cases := manifest.Cases
	if len(cases) == 0 {
		cases = make([]packageCase, 0, len(job.Cases))
		for _, item := range job.Cases {
			cases = append(cases, packageCase{
				ID:     item.ID,
				Input:  item.Input,
				Answer: item.Answer,
				Points: item.Points,
				Group:  item.Group,
			})
		}
	}
	if len(cases) == 0 {
		return nil, fmt.Errorf("package contains no test cases")
	}

	checkerSpec := manifest.Checker
	if checkerSpec.Type == "" {
		checkerSpec = job.Checker
	}
	checkerImpl := e.Checker
	if checkerSpec.Type == "testlib" {
		checkerImpl = &checker.TestlibChecker{Judge: e.Judge}
	}
	if checkerImpl == nil {
		checkerImpl = &checker.ExactChecker{}
	}

	results := make([]api.CaseResult, 0, len(cases))
	for index, testCase := range cases {
		input, err := readPackageFile(dir, testCase.Input)
		if err != nil {
			return nil, err
		}
		answer, err := readPackageFile(dir, testCase.Answer)
		if err != nil {
			return nil, err
		}
		if err := verifyFileHash(input, testCase.InputSHA256); err != nil {
			return nil, err
		}
		if err := verifyFileHash(answer, testCase.AnswerSHA256); err != nil {
			return nil, err
		}

		run, err := e.Runner.CompileAndRun(ctx, job.Language, job.Source, input, timeLimit, memoryBytes)
		if err != nil {
			return nil, err
		}

		result := api.CaseResult{
			CaseNumber:  index + 1,
			TotalPoints: testCase.Points,
			TimeUsed:    float64(run.Time) / float64(time.Second),
			MemoryUsed:  run.Memory / 1024,
		}

		if run.Status != "AC" {
			result.Status = run.Status
			result.Feedback = run.Error
			results = append(results, result)
			if job.ShortCircuit {
				break
			}
			continue
		}

		checked, err := checkerImpl.Check(ctx, checkerSpec, input, answer, run.Stdout, timeLimit, memoryBytes)
		if err != nil {
			return nil, err
		}
		result.Status = checked.Status
		result.Feedback = checked.Message
		result.Output = truncate(run.Stdout, 4096)
		if checked.Status == "AC" {
			result.Points = testCase.Points
		} else if checked.Status == "PT" {
			result.Points = min(checked.Points, testCase.Points)
		}
		results = append(results, result)
		if job.ShortCircuit && checked.Status != "AC" {
			break
		}
	}
	return results, nil
}

func loadManifest(dir string) (packageManifest, error) {
	payload, err := os.ReadFile(filepath.Join(dir, "manifest.json"))
	if err != nil {
		return packageManifest{}, err
	}
	var manifest packageManifest
	if err := json.Unmarshal(payload, &manifest); err != nil {
		return packageManifest{}, err
	}
	return manifest, nil
}

func readPackageFile(root, relative string) ([]byte, error) {
	cleanRoot := filepath.Clean(root)
	target := filepath.Clean(filepath.Join(root, filepath.FromSlash(relative)))
	if target != cleanRoot && !strings.HasPrefix(target, cleanRoot+string(os.PathSeparator)) {
		return nil, fmt.Errorf("package file escapes root: %q", relative)
	}
	return os.ReadFile(target)
}

func verifyFileHash(data []byte, expected string) error {
	if expected == "" {
		return nil
	}
	sum := sha256.Sum256(data)
	if hex.EncodeToString(sum[:]) != expected {
		return fmt.Errorf("package file hash mismatch")
	}
	return nil
}

func truncate(data []byte, limit int) string {
	if len(data) <= limit {
		return string(data)
	}
	return string(data[:limit])
}

func min(left, right float64) float64 {
	if left < right {
		return left
	}
	return right
}
