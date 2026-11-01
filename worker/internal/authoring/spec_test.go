package authoring

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func baseSpec() map[string]any {
	return map[string]any{
		"problem_code": "aplusb",
		"generator":    map[string]any{"language": "CPP17", "source": "// GENERATOR\n"},
		"solution":     map[string]any{"language": "CPP17", "source": "// SOLUTION\n"},
		"cases": []any{
			map[string]any{"args": []string{"1", "2"}},
		},
	}
}

func writeSpec(t *testing.T, directory string, spec map[string]any) string {
	t.Helper()
	data, err := json.Marshal(spec)
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(directory, "package.json")
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestLoadSpecAppliesDefaults(t *testing.T) {
	directory := t.TempDir()
	spec, err := LoadSpec(writeSpec(t, directory, baseSpec()))
	if err != nil {
		t.Fatalf("LoadSpec: %v", err)
	}

	if spec.Schema != 1 || spec.Points != 100 || spec.TimeLimit != 2 || spec.MemoryLimit != 262144 {
		t.Fatalf("unexpected defaults: %+v", spec)
	}
	if spec.Checker.Type != "exact" {
		t.Fatalf("unexpected checker: %+v", spec.Checker)
	}
	testCase := spec.Cases[0]
	if testCase.ID != "01" || testCase.Group != "default" || testCase.Points == nil || *testCase.Points != 100 {
		t.Fatalf("unexpected case defaults: %+v", testCase)
	}
	if len(spec.Groups) != 1 || spec.Groups[0].ID != "default" || spec.Groups[0].Points != 100 || spec.Groups[0].Mode != "sum" {
		t.Fatalf("unexpected groups: %+v", spec.Groups)
	}
}

func TestLoadSpecResolvesRelativeSourcesAndNormalizesLanguage(t *testing.T) {
	directory := t.TempDir()
	if err := os.WriteFile(filepath.Join(directory, "generator.cpp"), []byte("// GENERATOR FILE\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(directory, "solution.cpp"), []byte("// SOLUTION FILE\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	spec := baseSpec()
	spec["generator"] = map[string]any{"language": "cpp17", "source_file": "generator.cpp"}
	spec["solution"] = map[string]any{"language": "cpp17", "source_file": "solution.cpp"}

	loaded, err := LoadSpec(writeSpec(t, directory, spec))
	if err != nil {
		t.Fatalf("LoadSpec: %v", err)
	}
	if loaded.Generator.Language != "CPP17" || loaded.Generator.Source != "// GENERATOR FILE\n" {
		t.Fatalf("unexpected generator: %+v", loaded.Generator)
	}
	if loaded.Solution.Source != "// SOLUTION FILE\n" {
		t.Fatalf("unexpected solution: %+v", loaded.Solution)
	}
}

func TestLoadSpecRejectsUnknownFields(t *testing.T) {
	spec := baseSpec()
	spec["typo"] = true
	_, err := LoadSpec(writeSpec(t, t.TempDir(), spec))
	if err == nil || !strings.Contains(err.Error(), "unknown field") {
		t.Fatalf("expected unknown field error, got %v", err)
	}
}

func TestLoadSpecRejectsInvalidInputs(t *testing.T) {
	tests := []struct {
		name   string
		mutate func(map[string]any)
		match  string
	}{
		{
			name:   "missing generator",
			mutate: func(spec map[string]any) { delete(spec, "generator") },
			match:  "generator: source is required",
		},
		{
			name: "source and source file",
			mutate: func(spec map[string]any) {
				spec["generator"] = map[string]any{"language": "CPP17", "source": "x", "source_file": "x.cpp"}
			},
			match: "not both",
		},
		{
			name: "escaping source file",
			mutate: func(spec map[string]any) {
				spec["generator"] = map[string]any{"language": "CPP17", "source_file": "../evil.cpp"}
			},
			match: "escapes",
		},
		{
			name: "interactive checker",
			mutate: func(spec map[string]any) {
				spec["checker"] = map[string]any{"type": "interactive", "source": "x"}
			},
			match: "interactive packages need static answers",
		},
		{
			name: "unknown group",
			mutate: func(spec map[string]any) {
				spec["cases"] = []any{map[string]any{"args": []string{"1"}, "group": "missing"}}
			},
			match: "unknown group",
		},
		{
			name: "testlib checker without source",
			mutate: func(spec map[string]any) {
				spec["checker"] = map[string]any{"type": "testlib"}
			},
			match: "testlib requires",
		},
		{
			name: "unsupported language",
			mutate: func(spec map[string]any) {
				spec["generator"] = map[string]any{"language": "RUST", "source": "x"}
			},
			match: "unsupported language",
		},
		{
			name: "invalid problem code",
			mutate: func(spec map[string]any) {
				spec["problem_code"] = "a b"
			},
			match: "problem_code",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			spec := baseSpec()
			test.mutate(spec)
			_, err := LoadSpec(writeSpec(t, t.TempDir(), spec))
			if err == nil || !strings.Contains(err.Error(), test.match) {
				t.Fatalf("expected %q, got %v", test.match, err)
			}
		})
	}
}

func TestLoadSpecRejectsTooManyCases(t *testing.T) {
	cases := make([]any, 0, MaxCases+1)
	for index := 0; index <= MaxCases; index++ {
		cases = append(cases, map[string]any{"args": []string{"1"}, "points": 1})
	}
	spec := baseSpec()
	spec["cases"] = cases
	_, err := LoadSpec(writeSpec(t, t.TempDir(), spec))
	if err == nil || !strings.Contains(err.Error(), "between 1 and 200") {
		t.Fatalf("expected case limit error, got %v", err)
	}
}

func TestLoadSpecAcceptsTestlibCheckerAndValidator(t *testing.T) {
	spec := baseSpec()
	spec["checker"] = map[string]any{"type": "testlib", "source": "// CHECKER\n"}
	spec["validator"] = map[string]any{"source": "// VALIDATOR\n"}
	loaded, err := LoadSpec(writeSpec(t, t.TempDir(), spec))
	if err != nil {
		t.Fatalf("LoadSpec: %v", err)
	}
	if loaded.Checker.Type != "testlib" || loaded.Checker.Source != "// CHECKER\n" {
		t.Fatalf("unexpected checker: %+v", loaded.Checker)
	}
	if loaded.Validator == nil || loaded.Validator.Type != "testlib" || loaded.Validator.Source != "// VALIDATOR\n" {
		t.Fatalf("unexpected validator: %+v", loaded.Validator)
	}
}
