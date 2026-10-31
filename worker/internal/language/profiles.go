package language

import (
	"strings"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/executor"
)

type Profile struct {
	Key        string
	SourceName string
	Compile    *executor.RunSpec
	Run        executor.RunSpec
}

func Get(key string) (Profile, bool) {
	switch strings.ToUpper(strings.TrimSpace(key)) {
	case "PY3", "PYTHON3", "PYTHON":
		return Profile{
			Key:        "PY3",
			SourceName: "main.py",
			Run:        executor.RunSpec{Args: []string{"python3", "main.py"}},
		}, true
	case "CPP17", "CPP", "C++17":
		return Profile{
			Key:        "CPP17",
			SourceName: "main.cpp",
			Compile: &executor.RunSpec{
				Args:          []string{"g++", "-O2", "-std=c++17", "-o", "main", "main.cpp"},
				CopyOutCached: []string{"main"},
			},
			Run: executor.RunSpec{Args: []string{"/w/main"}},
		}, true
	default:
		return Profile{}, false
	}
}
