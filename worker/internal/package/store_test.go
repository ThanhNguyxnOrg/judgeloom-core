package store

import (
	"archive/zip"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
)

type fakeDownloader struct {
	mu      sync.Mutex
	payload []byte
	calls   int
	err     error
}

func (f *fakeDownloader) DownloadPackage(_ context.Context, _ int64, _ string) ([]byte, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.calls++
	if f.err != nil {
		return nil, f.err
	}
	return f.payload, nil
}

func makeZip(t *testing.T, entries map[string][]byte) []byte {
	t.Helper()
	var buffer bytes.Buffer
	writer := zip.NewWriter(&buffer)
	for name, content := range entries {
		file, err := writer.Create(name)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := file.Write(content); err != nil {
			t.Fatal(err)
		}
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	return buffer.Bytes()
}

func digest(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func TestStoreEnsureExtractsAndCaches(t *testing.T) {
	payload := makeZip(t, map[string][]byte{
		"manifest.json": []byte(`{"cases":[]}`),
		"data/01.in":    []byte("1 2\n"),
		"data/01.ans":   []byte("3\n"),
	})
	downloader := &fakeDownloader{payload: payload}
	store := &Store{Root: t.TempDir(), Client: downloader}
	hash := digest(payload)

	dir, err := store.Ensure(context.Background(), 7, hash)
	if err != nil {
		t.Fatalf("Ensure: %v", err)
	}
	if dir != filepath.Join(store.Root, hash) {
		t.Fatalf("unexpected dir: %s", dir)
	}
	content, err := os.ReadFile(filepath.Join(dir, "data", "01.in"))
	if err != nil {
		t.Fatal(err)
	}
	if string(content) != "1 2\n" {
		t.Fatalf("unexpected input: %q", content)
	}

	if _, err := store.Ensure(context.Background(), 7, hash); err != nil {
		t.Fatalf("second Ensure: %v", err)
	}
	if downloader.calls != 1 {
		t.Fatalf("expected one download, got %d", downloader.calls)
	}
}

func TestStoreRejectsWrongHash(t *testing.T) {
	payload := makeZip(t, map[string][]byte{"manifest.json": []byte("{}")})
	store := &Store{Root: t.TempDir(), Client: &fakeDownloader{payload: payload}}

	_, err := store.Ensure(context.Background(), 7, digest([]byte("different")))
	if !errors.Is(err, api.ErrHashMismatch) {
		t.Fatalf("expected ErrHashMismatch, got %v", err)
	}
}

func TestStoreRejectsPathTraversal(t *testing.T) {
	payload := makeZip(t, map[string][]byte{"../evil.txt": []byte("evil")})
	store := &Store{Root: t.TempDir(), Client: &fakeDownloader{payload: payload}}

	_, err := store.Ensure(context.Background(), 7, digest(payload))
	if err == nil {
		t.Fatal("expected traversal error")
	}
	if _, statErr := os.Stat(filepath.Join(store.Root, "evil.txt")); !os.IsNotExist(statErr) {
		t.Fatalf("traversal file escaped: %v", statErr)
	}
}

func TestStoreConcurrentEnsureDownloadsOnce(t *testing.T) {
	payload := makeZip(t, map[string][]byte{"manifest.json": []byte("{}")})
	downloader := &fakeDownloader{payload: payload}
	store := &Store{Root: t.TempDir(), Client: downloader}
	hash := digest(payload)

	var wg sync.WaitGroup
	errs := make(chan error, 8)
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, err := store.Ensure(context.Background(), 7, hash)
			errs <- err
		}()
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		if err != nil {
			t.Fatalf("Ensure: %v", err)
		}
	}
	if downloader.calls != 1 {
		t.Fatalf("expected one download, got %d", downloader.calls)
	}
}

func TestStoreCleanupRemovesOldDirectories(t *testing.T) {
	root := t.TempDir()
	old := filepath.Join(root, "old")
	newer := filepath.Join(root, "newer")
	if err := os.MkdirAll(old, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(newer, 0o700); err != nil {
		t.Fatal(err)
	}
	oldTime := time.Now().Add(-48 * time.Hour)
	if err := os.Chtimes(old, oldTime, oldTime); err != nil {
		t.Fatal(err)
	}

	store := &Store{Root: root}
	if err := store.Cleanup(24 * time.Hour); err != nil {
		t.Fatalf("Cleanup: %v", err)
	}
	if _, err := os.Stat(old); !os.IsNotExist(err) {
		t.Fatal("old directory was not removed")
	}
	if _, err := os.Stat(newer); err != nil {
		t.Fatalf("newer directory removed: %v", err)
	}
}
