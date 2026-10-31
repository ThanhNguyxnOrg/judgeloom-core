package store

import (
	"archive/zip"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
)

const (
	defaultMaxArchiveBytes      = 64 << 20
	defaultMaxUncompressedBytes = 256 << 20
	defaultMaxFiles             = 1000
)

type Downloader interface {
	DownloadPackage(ctx context.Context, problemID int64, sha256 string) ([]byte, error)
}

type Store struct {
	Root                 string
	Client               Downloader
	MaxArchiveBytes      int64
	MaxUncompressedBytes int64
	MaxFiles             int

	mu sync.Mutex
}

func (s *Store) Ensure(ctx context.Context, problemID int64, digest string) (string, error) {
	if s.Root == "" {
		return "", fmt.Errorf("package cache root is required")
	}
	if s.Client == nil {
		return "", fmt.Errorf("package downloader is required")
	}
	if _, err := hex.DecodeString(digest); err != nil || len(digest) != 64 {
		return "", fmt.Errorf("invalid package digest")
	}
	if err := os.MkdirAll(s.Root, 0o700); err != nil {
		return "", fmt.Errorf("create cache root: %w", err)
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	target := filepath.Join(s.Root, digest)
	if _, err := os.Stat(filepath.Join(target, "manifest.json")); err == nil {
		return target, nil
	}

	payload, err := s.Client.DownloadPackage(ctx, problemID, digest)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(payload)
	if hex.EncodeToString(sum[:]) != digest {
		return "", api.ErrHashMismatch
	}
	if limit := s.archiveLimit(); int64(len(payload)) > limit {
		return "", fmt.Errorf("package archive exceeds %d bytes", limit)
	}

	temp, err := os.MkdirTemp(s.Root, digest+".tmp-")
	if err != nil {
		return "", fmt.Errorf("create temp package dir: %w", err)
	}
	defer os.RemoveAll(temp)

	if err := s.extract(temp, payload); err != nil {
		return "", err
	}
	if err := os.Rename(temp, target); err != nil {
		if _, statErr := os.Stat(filepath.Join(target, "manifest.json")); statErr == nil {
			return target, nil
		}
		return "", fmt.Errorf("publish package dir: %w", err)
	}
	return target, nil
}

func (s *Store) Cleanup(maxAge time.Duration) error {
	if s.Root == "" {
		return nil
	}
	s.mu.Lock()
	defer s.mu.Unlock()

	entries, err := os.ReadDir(s.Root)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return err
	}
	cutoff := time.Now().Add(-maxAge)
	for _, entry := range entries {
		info, err := entry.Info()
		if err != nil || !entry.IsDir() || !info.ModTime().Before(cutoff) {
			continue
		}
		if err := os.RemoveAll(filepath.Join(s.Root, entry.Name())); err != nil {
			return err
		}
	}
	return nil
}

func (s *Store) extract(root string, payload []byte) error {
	reader, err := zip.NewReader(bytes.NewReader(payload), int64(len(payload)))
	if err != nil {
		return fmt.Errorf("open package archive: %w", err)
	}
	if limit := s.fileLimit(); len(reader.File) > limit {
		return fmt.Errorf("package contains too many files")
	}

	var total uint64
	for _, file := range reader.File {
		total += file.UncompressedSize64
	}
	if limit := s.uncompressedLimit(); total > uint64(limit) {
		return fmt.Errorf("package exceeds %d uncompressed bytes", limit)
	}

	cleanRoot := filepath.Clean(root)
	for _, file := range reader.File {
		name := strings.ReplaceAll(file.Name, "\\", "/")
		normalized := path.Clean(name)
		if normalized == "." || normalized == ".." || strings.HasPrefix(normalized, "../") || path.IsAbs(normalized) || hasDrivePrefix(normalized) {
			return fmt.Errorf("invalid package path: %q", file.Name)
		}
		target := filepath.Join(root, filepath.FromSlash(normalized))
		if target != cleanRoot && !strings.HasPrefix(target, cleanRoot+string(os.PathSeparator)) {
			return fmt.Errorf("package path escapes root: %q", file.Name)
		}
		if file.FileInfo().IsDir() {
			if err := os.MkdirAll(target, 0o700); err != nil {
				return err
			}
			continue
		}
		if file.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("package contains a symlink: %q", file.Name)
		}
		if err := os.MkdirAll(filepath.Dir(target), 0o700); err != nil {
			return err
		}
		if err := writeZipFile(target, file); err != nil {
			return err
		}
	}
	return nil
}

func writeZipFile(target string, file *zip.File) error {
	source, err := file.Open()
	if err != nil {
		return err
	}
	defer source.Close()

	destination, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o600)
	if err != nil {
		return err
	}
	if _, err := io.Copy(destination, source); err != nil {
		_ = destination.Close()
		return err
	}
	return destination.Close()
}

func hasDrivePrefix(name string) bool {
	return len(name) >= 2 && name[1] == ':'
}

func (s *Store) archiveLimit() int64 {
	if s.MaxArchiveBytes > 0 {
		return s.MaxArchiveBytes
	}
	return defaultMaxArchiveBytes
}

func (s *Store) uncompressedLimit() int64 {
	if s.MaxUncompressedBytes > 0 {
		return s.MaxUncompressedBytes
	}
	return defaultMaxUncompressedBytes
}

func (s *Store) fileLimit() int {
	if s.MaxFiles > 0 {
		return s.MaxFiles
	}
	return defaultMaxFiles
}
