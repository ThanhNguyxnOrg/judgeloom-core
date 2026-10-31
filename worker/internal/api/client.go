package api

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
)

var ErrHashMismatch = errors.New("package hash mismatch")

type Client interface {
	Register(ctx context.Context, req RegisterRequest) (RegisterResponse, error)
	Heartbeat(ctx context.Context, req HeartbeatRequest) error
	Claim(ctx context.Context, req ClaimRequest) (*Job, error)
	Start(ctx context.Context, jobID int64) error
	Cases(ctx context.Context, jobID int64, req CasesRequest) error
	Finish(ctx context.Context, jobID int64, req FinishRequest) error
	Fail(ctx context.Context, jobID int64, req FailRequest) error
	DownloadPackage(ctx context.Context, problemID int64, sha256 string) ([]byte, error)
}

type HTTPClient struct {
	baseURL string
	token   string
	http    *http.Client
}

func NewClient(baseURL, token string, httpClient *http.Client) *HTTPClient {
	if httpClient == nil {
		httpClient = http.DefaultClient
	}
	return &HTTPClient{
		baseURL: strings.TrimRight(baseURL, "/"),
		token:   token,
		http:    httpClient,
	}
}

func (c *HTTPClient) Register(ctx context.Context, req RegisterRequest) (RegisterResponse, error) {
	var out RegisterResponse
	err := c.doJSON(ctx, http.MethodPost, "/register", req, &out)
	return out, err
}

func (c *HTTPClient) Heartbeat(ctx context.Context, req HeartbeatRequest) error {
	return c.doJSON(ctx, http.MethodPost, "/heartbeat", req, nil)
}

func (c *HTTPClient) Claim(ctx context.Context, req ClaimRequest) (*Job, error) {
	status, body, err := c.request(ctx, http.MethodPost, "/jobs/claim", req)
	if err != nil {
		return nil, err
	}
	if status == http.StatusNoContent {
		return nil, nil
	}
	var job Job
	if err := json.Unmarshal(body, &job); err != nil {
		return nil, fmt.Errorf("decode claim: %w", err)
	}
	return &job, nil
}

func (c *HTTPClient) Start(ctx context.Context, jobID int64) error {
	return c.doJSON(ctx, http.MethodPost, fmt.Sprintf("/jobs/%d/start", jobID), struct{}{}, nil)
}

func (c *HTTPClient) Cases(ctx context.Context, jobID int64, req CasesRequest) error {
	return c.doJSON(ctx, http.MethodPost, fmt.Sprintf("/jobs/%d/cases", jobID), req, nil)
}

func (c *HTTPClient) Finish(ctx context.Context, jobID int64, req FinishRequest) error {
	return c.doJSON(ctx, http.MethodPost, fmt.Sprintf("/jobs/%d/finish", jobID), req, nil)
}

func (c *HTTPClient) Fail(ctx context.Context, jobID int64, req FailRequest) error {
	return c.doJSON(ctx, http.MethodPost, fmt.Sprintf("/jobs/%d/fail", jobID), req, nil)
}

func (c *HTTPClient) DownloadPackage(ctx context.Context, problemID int64, digest string) ([]byte, error) {
	path := fmt.Sprintf("/packages/%d?sha256=%s", problemID, url.QueryEscape(digest))
	_, body, err := c.request(ctx, http.MethodGet, path, nil)
	if err != nil {
		return nil, err
	}
	sum := sha256.Sum256(body)
	if hex.EncodeToString(sum[:]) != digest {
		return nil, ErrHashMismatch
	}
	return body, nil
}

func (c *HTTPClient) doJSON(ctx context.Context, method, path string, in, out any) error {
	_, body, err := c.request(ctx, method, path, in)
	if err != nil {
		return err
	}
	if out != nil && len(body) > 0 {
		if err := json.Unmarshal(body, out); err != nil {
			return fmt.Errorf("decode %s %s: %w", method, path, err)
		}
	}
	return nil
}

func (c *HTTPClient) request(ctx context.Context, method, path string, in any) (int, []byte, error) {
	var body io.Reader
	if in != nil {
		payload, err := json.Marshal(in)
		if err != nil {
			return 0, nil, fmt.Errorf("encode request: %w", err)
		}
		body = bytes.NewReader(payload)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, body)
	if err != nil {
		return 0, nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.http.Do(req)
	if err != nil {
		return 0, nil, fmt.Errorf("judge api: %w", err)
	}
	defer resp.Body.Close()

	payload, err := io.ReadAll(resp.Body)
	if err != nil {
		return resp.StatusCode, nil, fmt.Errorf("read response: %w", err)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		var apiErr APIError
		if json.Unmarshal(payload, &apiErr) == nil && apiErr.Code != "" {
			apiErr.StatusCode = resp.StatusCode
			return resp.StatusCode, payload, &apiErr
		}
		return resp.StatusCode, payload, fmt.Errorf("judge api %d: %s", resp.StatusCode, strings.TrimSpace(string(payload)))
	}
	return resp.StatusCode, payload, nil
}
