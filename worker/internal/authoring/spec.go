package authoring

import (
	"bytes"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/language"
)

const (
	MaxCases               = 200
	MaxSpecBytes           = 8 << 20
	MaxSourceBytes         = 256 << 10
	MaxCaseArgs            = 32
	MaxArgBytes            = 256
	MaxGeneratedInputBytes = 16 << 20
	MaxAnswerBytes         = 16 << 20
	MaxPackageDataBytes    = 255 << 20
	MaxArchiveBytes        = 64 << 20
	MaxManifestPoints      = 1_000_000.0
	MaxProblemCodeBytes    = 32
)

var (
	problemCodePattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_-]*$`)
	caseIDPattern      = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.-]*$`)
	groupIDPattern     = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_-]*$`)
)

type Spec struct {
	Schema       int            `json:"schema"`
	ProblemCode  string         `json:"problem_code"`
	Points       float64        `json:"points,omitempty"`
	TimeLimit    float64        `json:"time_limit,omitempty"`
	MemoryLimit  int64          `json:"memory_limit,omitempty"`
	PartialScore bool           `json:"partial_score,omitempty"`
	ShortCircuit bool           `json:"short_circuit,omitempty"`
	Checker      CheckerSpec    `json:"checker"`
	Validator    *ValidatorSpec `json:"validator,omitempty"`
	Generator    ProgramSpec    `json:"generator"`
	Solution     ProgramSpec    `json:"solution"`
	Cases        []CaseSpec     `json:"cases"`
	Groups       []GroupSpec    `json:"groups,omitempty"`
}

type CheckerSpec struct {
	Type       string `json:"type,omitempty"`
	Source     string `json:"source,omitempty"`
	SourceFile string `json:"source_file,omitempty"`
}

type ValidatorSpec struct {
	Type       string `json:"type,omitempty"`
	Source     string `json:"source,omitempty"`
	SourceFile string `json:"source_file,omitempty"`
}

type ProgramSpec struct {
	Language   string `json:"language"`
	Source     string `json:"source,omitempty"`
	SourceFile string `json:"source_file,omitempty"`
}

type CaseSpec struct {
	ID     string   `json:"id,omitempty"`
	Args   []string `json:"args,omitempty"`
	Points *float64 `json:"points,omitempty"`
	Group  string   `json:"group,omitempty"`
}

type GroupSpec struct {
	ID     string  `json:"id"`
	Points float64 `json:"points"`
	Mode   string  `json:"mode,omitempty"`
}

func LoadSpec(path string) (Spec, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Spec{}, err
	}
	if len(data) > MaxSpecBytes {
		return Spec{}, fmt.Errorf("spec exceeds %d bytes", MaxSpecBytes)
	}

	var spec Spec
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&spec); err != nil {
		return Spec{}, fmt.Errorf("decode spec: %w", err)
	}

	baseDir, err := filepath.Abs(filepath.Dir(path))
	if err != nil {
		return Spec{}, err
	}
	spec.applyDefaults()
	if err := spec.resolveSources(baseDir); err != nil {
		return Spec{}, err
	}
	if err := spec.validate(); err != nil {
		return Spec{}, err
	}
	return spec, nil
}

func (s *Spec) applyDefaults() {
	if s.Schema == 0 {
		s.Schema = 1
	}
	if s.Points <= 0 {
		s.Points = 100
	}
	if s.TimeLimit <= 0 {
		s.TimeLimit = 2
	}
	if s.MemoryLimit <= 0 {
		s.MemoryLimit = 262144
	}
	if s.Checker.Type == "" {
		s.Checker.Type = "exact"
	}
	s.Checker.Type = strings.ToLower(strings.TrimSpace(s.Checker.Type))
	if s.Validator != nil {
		if s.Validator.Type == "" {
			if strings.TrimSpace(s.Validator.Source) != "" || strings.TrimSpace(s.Validator.SourceFile) != "" {
				s.Validator.Type = "testlib"
			} else {
				s.Validator.Type = "none"
			}
		}
		s.Validator.Type = strings.ToLower(strings.TrimSpace(s.Validator.Type))
	}

	count := len(s.Cases)
	for index := range s.Cases {
		if s.Cases[index].ID == "" {
			s.Cases[index].ID = fmt.Sprintf("%02d", index+1)
		}
		if s.Cases[index].Group == "" {
			s.Cases[index].Group = "default"
		}
		if s.Cases[index].Points == nil && count > 0 {
			points := round2(s.Points / float64(count))
			s.Cases[index].Points = &points
		}
	}
	for index := range s.Groups {
		if s.Groups[index].Mode == "" {
			s.Groups[index].Mode = "sum"
		}
	}
	if len(s.Groups) == 0 {
		total := 0.0
		for _, testCase := range s.Cases {
			if testCase.Points != nil {
				total += *testCase.Points
			}
		}
		s.Groups = []GroupSpec{{ID: "default", Points: round2(total), Mode: "sum"}}
	}
}

func (s *Spec) resolveSources(baseDir string) error {
	if err := resolveSource(&s.Checker.Source, &s.Checker.SourceFile, baseDir, "checker"); err != nil {
		return err
	}
	if s.Validator != nil {
		if err := resolveSource(&s.Validator.Source, &s.Validator.SourceFile, baseDir, "validator"); err != nil {
			return err
		}
	}
	if err := resolveSource(&s.Generator.Source, &s.Generator.SourceFile, baseDir, "generator"); err != nil {
		return err
	}
	return resolveSource(&s.Solution.Source, &s.Solution.SourceFile, baseDir, "solution")
}

func resolveSource(source *string, sourceFile *string, baseDir string, field string) error {
	inline := strings.TrimSpace(*source) != ""
	file := strings.TrimSpace(*sourceFile)
	if inline && file != "" {
		return fmt.Errorf("%s: use source or source_file, not both", field)
	}
	if !inline && file == "" {
		return nil
	}
	if len(*source) > MaxSourceBytes {
		return fmt.Errorf("%s: source exceeds %d bytes", field, MaxSourceBytes)
	}
	if file == "" {
		return nil
	}
	if filepath.IsAbs(file) {
		return fmt.Errorf("%s: source_file must be relative to the spec", field)
	}
	clean := filepath.Clean(file)
	if clean == ".." || strings.HasPrefix(clean, ".."+string(os.PathSeparator)) {
		return fmt.Errorf("%s: source_file escapes the spec directory", field)
	}
	full := filepath.Join(baseDir, clean)
	relative, err := filepath.Rel(baseDir, full)
	if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(os.PathSeparator)) {
		return fmt.Errorf("%s: source_file escapes the spec directory", field)
	}
	data, err := os.ReadFile(full)
	if err != nil {
		return fmt.Errorf("%s: %w", field, err)
	}
	if len(data) > MaxSourceBytes {
		return fmt.Errorf("%s: source exceeds %d bytes", field, MaxSourceBytes)
	}
	*source = string(data)
	return nil
}

func (s *Spec) validate() error {
	if s.Schema != 1 {
		return fmt.Errorf("unsupported schema %d", s.Schema)
	}
	if len(s.ProblemCode) == 0 || len(s.ProblemCode) > MaxProblemCodeBytes || !problemCodePattern.MatchString(s.ProblemCode) {
		return fmt.Errorf("problem_code must match [A-Za-z0-9][A-Za-z0-9_-]* and be at most %d bytes", MaxProblemCodeBytes)
	}
	if !finite(s.Points) || s.Points <= 0 || s.Points > MaxManifestPoints {
		return fmt.Errorf("points must be finite and in (0, %.0f]", MaxManifestPoints)
	}
	if !finite(s.TimeLimit) || s.TimeLimit < 0.1 || s.TimeLimit > 60 {
		return fmt.Errorf("time_limit must be between 0.1 and 60 seconds")
	}
	if s.MemoryLimit < 1024 || s.MemoryLimit > 1_048_576 {
		return fmt.Errorf("memory_limit must be between 1024 and 1048576 KiB")
	}
	if len(s.Cases) == 0 || len(s.Cases) > MaxCases {
		return fmt.Errorf("cases must contain between 1 and %d entries", MaxCases)
	}

	switch s.Checker.Type {
	case "exact", "none":
		if strings.TrimSpace(s.Checker.Source) != "" {
			return fmt.Errorf("checker: source is only valid for testlib")
		}
	case "testlib":
		if strings.TrimSpace(s.Checker.Source) == "" {
			return fmt.Errorf("checker: testlib requires inline source or source_file")
		}
		if len(s.Checker.Source) > MaxSourceBytes {
			return fmt.Errorf("checker: source exceeds %d bytes", MaxSourceBytes)
		}
	case "interactive":
		return fmt.Errorf("checker: interactive packages need static answers; use exact, testlib, or none")
	default:
		return fmt.Errorf("checker: unsupported type %q", s.Checker.Type)
	}

	if s.Validator != nil {
		switch s.Validator.Type {
		case "none":
			if strings.TrimSpace(s.Validator.Source) != "" {
				return fmt.Errorf("validator: source is only valid for testlib")
			}
		case "testlib":
			if strings.TrimSpace(s.Validator.Source) == "" {
				return fmt.Errorf("validator: testlib requires inline source or source_file")
			}
			if len(s.Validator.Source) > MaxSourceBytes {
				return fmt.Errorf("validator: source exceeds %d bytes", MaxSourceBytes)
			}
		default:
			return fmt.Errorf("validator: unsupported type %q", s.Validator.Type)
		}
	}

	if err := validateProgram(&s.Generator, "generator"); err != nil {
		return err
	}
	if err := validateProgram(&s.Solution, "solution"); err != nil {
		return err
	}

	caseIDs := make(map[string]struct{}, len(s.Cases))
	groupIDs := make(map[string]struct{}, len(s.Groups))
	for _, group := range s.Groups {
		if len(group.ID) == 0 || len(group.ID) > 32 || !groupIDPattern.MatchString(group.ID) {
			return fmt.Errorf("groups: invalid id %q", group.ID)
		}
		if _, exists := groupIDs[group.ID]; exists {
			return fmt.Errorf("groups: duplicate id %q", group.ID)
		}
		groupIDs[group.ID] = struct{}{}
		if !finite(group.Points) || group.Points < 0 || group.Points > MaxManifestPoints {
			return fmt.Errorf("groups: %s points must be finite and in [0, %.0f]", group.ID, MaxManifestPoints)
		}
		if group.Mode != "sum" && group.Mode != "min" {
			return fmt.Errorf("groups: unsupported mode %q", group.Mode)
		}
	}

	for _, testCase := range s.Cases {
		if len(testCase.ID) == 0 || len(testCase.ID) > 64 || !caseIDPattern.MatchString(testCase.ID) {
			return fmt.Errorf("cases: invalid id %q", testCase.ID)
		}
		if _, exists := caseIDs[testCase.ID]; exists {
			return fmt.Errorf("cases: duplicate id %q", testCase.ID)
		}
		caseIDs[testCase.ID] = struct{}{}
		if _, exists := groupIDs[testCase.Group]; !exists {
			return fmt.Errorf("cases: %s references unknown group %q", testCase.ID, testCase.Group)
		}
		if len(testCase.Args) > MaxCaseArgs {
			return fmt.Errorf("cases: %s has more than %d args", testCase.ID, MaxCaseArgs)
		}
		for _, arg := range testCase.Args {
			if len(arg) > MaxArgBytes || strings.ContainsRune(arg, '\x00') {
				return fmt.Errorf("cases: %s has an invalid arg", testCase.ID)
			}
		}
		if testCase.Points == nil || !finite(*testCase.Points) || *testCase.Points < 0 || *testCase.Points > MaxManifestPoints {
			return fmt.Errorf("cases: %s points must be finite and in [0, %.0f]", testCase.ID, MaxManifestPoints)
		}
	}
	return nil
}

func validateProgram(program *ProgramSpec, field string) error {
	if strings.TrimSpace(program.Source) == "" {
		return fmt.Errorf("%s: source is required", field)
	}
	if len(program.Source) > MaxSourceBytes {
		return fmt.Errorf("%s: source exceeds %d bytes", field, MaxSourceBytes)
	}
	profile, ok := language.Get(program.Language)
	if !ok {
		return fmt.Errorf("%s: unsupported language %q", field, program.Language)
	}
	program.Language = profile.Key
	return nil
}

func (s Spec) memoryBytes() int64 {
	return s.MemoryLimit * 1024
}

func round2(value float64) float64 {
	return math.Round(value*100) / 100
}

func finite(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0)
}
