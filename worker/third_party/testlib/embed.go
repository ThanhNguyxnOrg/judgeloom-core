package testlib

import _ "embed"

// Header is the vendored Testlib header (MIT) copied into trusted checker,
// validator, and generator compilation sandboxes.
//
//go:embed testlib.h
var Header []byte
