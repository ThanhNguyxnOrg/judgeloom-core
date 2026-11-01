package authoring

import (
	"archive/zip"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/checker"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/runner"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/third_party/testlib"
)

const (
	generatorCPUTime      = 30 * time.Second
	generatorMemoryBytes  = 1 << 30
	compileMinMemoryBytes = 256 << 20
)

type Builder struct {
	Judge  *executor.GoJudge
	Runner *runner.Runner
}

type Result struct {
	Path      string
	SHA256    string
	SizeBytes int64
	Cases     int
}

type packageManifest struct {
	Schema       int               `json:"schema"`
	ProblemCode  string            `json:"problem_code"`
	TimeLimit    float64           `json:"time_limit"`
	MemoryLimit  int64             `json:"memory_limit"`
	PartialScore bool              `json:"partial_score"`
	ShortCircuit bool              `json:"short_circuit"`
	Checker      manifestChecker   `json:"checker"`
	Validator    *manifestChecker  `json:"validator,omitempty"`
	Generator    manifestGenerator `json:"generator"`
	Solution     manifestSolution  `json:"solution"`
	Cases        []manifestCase    `json:"cases"`
	Groups       []GroupSpec       `json:"groups"`
	Authoring    manifestAuthoring `json:"authoring"`
}

type manifestChecker struct {
	Type   string `json:"type"`
	Source string `json:"source,omitempty"`
}

type manifestGenerator struct {
	Language     string              `json:"language"`
	SourceSHA256 string              `json:"source_sha256"`
	Cases        []generatorCaseMeta `json:"cases,omitempty"`
}

type manifestSolution struct {
	Language     string `json:"language"`
	SourceSHA256 string `json:"source_sha256"`
}

type generatorCaseMeta struct {
	ID   string   `json:"id"`
	Args []string `json:"args,omitempty"`
}

type manifestCase struct {
	ID           string  `json:"id"`
	Input        string  `json:"input"`
	Answer       string  `json:"answer"`
	InputSHA256  string  `json:"input_sha256"`
	AnswerSHA256 string  `json:"answer_sha256"`
	Points       float64 `json:"points"`
	Group        string  `json:"group"`
}

type manifestAuthoring struct {
	Tool string `json:"tool"`
}

func (b *Builder) Build(ctx context.Context, spec Spec, outPath string) (Result, error) {
	if b.Judge == nil || b.Runner == nil {
		return Result{}, errors.New("go-judge executor and runner are required")
	}
	spec.applyDefaults()
	if err := spec.validate(); err != nil {
		return Result{}, err
	}
	if strings.TrimSpace(outPath) == "" {
		return Result{}, errors.New("output path is required")
	}

	caseTimeLimit := time.Duration(spec.TimeLimit * float64(time.Second))
	caseMemory := spec.memoryBytes()
	compileMemory := maxInt64(caseMemory, compileMinMemoryBytes)

	var generatorFiles map[string][]byte
	if spec.Generator.Language == "CPP17" {
		generatorFiles = map[string][]byte{"testlib.h": testlib.Header}
	}
	generatorSpec, err := b.Runner.PrepareWithFiles(
		ctx,
		spec.Generator.Language,
		spec.Generator.Source,
		generatorMemoryBytes,
		generatorFiles,
	)
	if err != nil {
		return Result{}, fmt.Errorf("compile generator: %w", err)
	}
	solutionSpec, err := b.Runner.PrepareWithFiles(
		ctx,
		spec.Solution.Language,
		spec.Solution.Source,
		compileMemory,
		nil,
	)
	if err != nil {
		return Result{}, fmt.Errorf("compile solution: %w", err)
	}

	var validator *checker.TestlibValidator
	if spec.Validator != nil && spec.Validator.Type == "testlib" {
		validator, err = checker.NewTestlibValidator(
			ctx,
			b.Judge,
			api.Checker{Type: "testlib", Source: spec.Validator.Source},
			compileMemory,
		)
		if err != nil {
			return Result{}, fmt.Errorf("compile validator: %w", err)
		}
	}

	var checkerImpl checker.Checker
	switch spec.Checker.Type {
	case "exact":
		checkerImpl = checker.ExactChecker{}
	case "testlib":
		checkerImpl = &checker.TestlibChecker{Judge: b.Judge}
	case "none":
	default:
		return Result{}, fmt.Errorf("unsupported checker type %q", spec.Checker.Type)
	}

	inputs := make([][]byte, 0, len(spec.Cases))
	answers := make([][]byte, 0, len(spec.Cases))
	manifestCases := make([]manifestCase, 0, len(spec.Cases))
	generatorCases := make([]generatorCaseMeta, 0, len(spec.Cases))
	var totalBytes int64

	for _, testCase := range spec.Cases {
		generated, err := b.Runner.RunPrepared(
			ctx,
			generatorSpec,
			nil,
			testCase.Args,
			generatorCPUTime,
			generatorMemoryBytes,
		)
		if err != nil {
			return Result{}, fmt.Errorf("case %s: run generator: %w", testCase.ID, err)
		}
		if generated.Status != "AC" {
			return Result{}, runFailure(testCase.ID, "generator", generated)
		}
		input := generated.Stdout
		if len(input) > MaxGeneratedInputBytes {
			return Result{}, fmt.Errorf("case %s: generated input exceeds %d bytes", testCase.ID, MaxGeneratedInputBytes)
		}
		if validator != nil {
			validated, err := validator.Validate(ctx, input, validatorTimeLimit(caseTimeLimit), compileMemory)
			if err != nil {
				return Result{}, fmt.Errorf("case %s: validate input: %w", testCase.ID, err)
			}
			if validated.Status != "AC" {
				return Result{}, fmt.Errorf("case %s: validator rejected generated input (%s): %s", testCase.ID, validated.Status, validated.Message)
			}
		}

		solved, err := b.Runner.RunPrepared(ctx, solutionSpec, input, nil, caseTimeLimit, caseMemory)
		if err != nil {
			return Result{}, fmt.Errorf("case %s: run solution: %w", testCase.ID, err)
		}
		if solved.Status != "AC" {
			return Result{}, runFailure(testCase.ID, "solution", solved)
		}
		answer := solved.Stdout
		if len(answer) > MaxAnswerBytes {
			return Result{}, fmt.Errorf("case %s: generated answer exceeds %d bytes", testCase.ID, MaxAnswerBytes)
		}
		totalBytes += int64(len(input) + len(answer))
		if totalBytes > MaxPackageDataBytes {
			return Result{}, fmt.Errorf("generated test data exceeds %d bytes", MaxPackageDataBytes)
		}
		if checkerImpl != nil {
			checked, err := checkerImpl.Check(
				ctx,
				api.Checker{Type: spec.Checker.Type, Source: spec.Checker.Source},
				input,
				answer,
				answer,
				caseTimeLimit,
				caseMemory,
			)
			if err != nil {
				return Result{}, fmt.Errorf("case %s: checker: %w", testCase.ID, err)
			}
			if checked.Status != "AC" {
				return Result{}, fmt.Errorf("case %s: checker rejected model answer (%s): %s", testCase.ID, checked.Status, checked.Message)
			}
		}

		inputs = append(inputs, input)
		answers = append(answers, answer)
		number := len(inputs)
		manifestCases = append(manifestCases, manifestCase{
			ID:           testCase.ID,
			Input:        fmt.Sprintf("data/%02d.in", number),
			Answer:       fmt.Sprintf("data/%02d.ans", number),
			InputSHA256:  sha256Hex(input),
			AnswerSHA256: sha256Hex(answer),
			Points:       *testCase.Points,
			Group:        testCase.Group,
		})
		generatorCases = append(generatorCases, generatorCaseMeta{ID: testCase.ID, Args: testCase.Args})
	}

	manifest := packageManifest{
		Schema:       1,
		ProblemCode:  spec.ProblemCode,
		TimeLimit:    spec.TimeLimit,
		MemoryLimit:  spec.MemoryLimit,
		PartialScore: spec.PartialScore,
		ShortCircuit: spec.ShortCircuit,
		Checker:      manifestChecker{Type: spec.Checker.Type, Source: spec.Checker.Source},
		Generator: manifestGenerator{
			Language:     spec.Generator.Language,
			SourceSHA256: sha256Hex([]byte(spec.Generator.Source)),
			Cases:        generatorCases,
		},
		Solution: manifestSolution{
			Language:     spec.Solution.Language,
			SourceSHA256: sha256Hex([]byte(spec.Solution.Source)),
		},
		Cases:     manifestCases,
		Groups:    spec.Groups,
		Authoring: manifestAuthoring{Tool: "judgeloom-package"},
	}
	if spec.Validator != nil && spec.Validator.Type == "testlib" {
		manifest.Validator = &manifestChecker{Type: "testlib", Source: spec.Validator.Source}
	}

	manifestData, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return Result{}, err
	}
	manifestData = append(manifestData, '\n')

	if err := writePackage(outPath, manifestData, inputs, answers); err != nil {
		return Result{}, err
	}
	digest, err := fileSHA256(outPath)
	if err != nil {
		return Result{}, err
	}
	info, err := os.Stat(outPath)
	if err != nil {
		return Result{}, err
	}
	if info.Size() > MaxArchiveBytes {
		_ = os.Remove(outPath)
		return Result{}, fmt.Errorf("package archive exceeds %d bytes", MaxArchiveBytes)
	}
	return Result{
		Path:      outPath,
		SHA256:    digest,
		SizeBytes: info.Size(),
		Cases:     len(inputs),
	}, nil
}

func writePackage(path string, manifest []byte, inputs, answers [][]byte) error {
	directory := filepath.Dir(path)
	if directory == "" {
		directory = "."
	}
	if err := os.MkdirAll(directory, 0o755); err != nil {
		return fmt.Errorf("create output directory: %w", err)
	}

	temp, err := os.CreateTemp(directory, ".judgeloom-package-*.zip")
	if err != nil {
		return fmt.Errorf("create output archive: %w", err)
	}
	tempPath := temp.Name()
	renamed := false
	defer func() {
		if !renamed {
			_ = os.Remove(tempPath)
		}
	}()

	writer := zip.NewWriter(temp)
	add := func(name string, data []byte) error {
		header := &zip.FileHeader{Name: name, Method: zip.Deflate}
		header.SetMode(0o644)
		entry, err := writer.CreateHeader(header)
		if err != nil {
			return err
		}
		_, err = entry.Write(data)
		return err
	}
	if err := add("manifest.json", manifest); err != nil {
		_ = writer.Close()
		_ = temp.Close()
		return err
	}
	for index := range inputs {
		if err := add(fmt.Sprintf("data/%02d.in", index+1), inputs[index]); err != nil {
			_ = writer.Close()
			_ = temp.Close()
			return err
		}
		if err := add(fmt.Sprintf("data/%02d.ans", index+1), answers[index]); err != nil {
			_ = writer.Close()
			_ = temp.Close()
			return err
		}
	}
	if err := writer.Close(); err != nil {
		_ = temp.Close()
		return err
	}
	if err := temp.Close(); err != nil {
		return err
	}

	if err := os.Rename(tempPath, path); err != nil {
		if removeErr := os.Remove(path); removeErr != nil {
			return fmt.Errorf("publish output archive: %w", err)
		}
		if err := os.Rename(tempPath, path); err != nil {
			return fmt.Errorf("publish output archive: %w", err)
		}
	}
	renamed = true
	return nil
}

func validatorTimeLimit(caseLimit time.Duration) time.Duration {
	if caseLimit < 2*time.Second {
		return 2 * time.Second
	}
	return caseLimit
}

func runFailure(caseID, stage string, result executor.RunResult) error {
	message := strings.TrimSpace(string(result.Stderr))
	if message == "" {
		message = result.Error
	}
	if message == "" {
		message = result.Status
	}
	return fmt.Errorf("case %s: %s failed (%s): %s", caseID, stage, result.Status, message)
}

func sha256Hex(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func fileSHA256(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}
	return hex.EncodeToString(hash.Sum(nil)), nil
}

func maxInt64(left, right int64) int64 {
	if left > right {
		return left
	}
	return right
}
