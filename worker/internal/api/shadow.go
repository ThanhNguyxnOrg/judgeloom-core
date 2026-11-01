package api

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
)

type ShadowClient struct {
	*HTTPClient
}

func NewShadowClient(baseURL, token string, httpClient *http.Client) *ShadowClient {
	return &ShadowClient{HTTPClient: NewClient(baseURL, token, httpClient)}
}

func (c *ShadowClient) Claim(ctx context.Context, req ClaimRequest) (*Job, error) {
	status, body, err := c.request(ctx, http.MethodPost, "/shadow/jobs/claim", req)
	if err != nil {
		return nil, err
	}
	if status == http.StatusNoContent {
		return nil, nil
	}
	var job Job
	if err := json.Unmarshal(body, &job); err != nil {
		return nil, fmt.Errorf("decode shadow claim: %w", err)
	}
	return &job, nil
}

func (c *ShadowClient) Start(ctx context.Context, jobID int64) error {
	return c.doJSON(ctx, http.MethodPost, fmt.Sprintf("/shadow/jobs/%d/start", jobID), struct{}{}, nil)
}

func (c *ShadowClient) Cases(ctx context.Context, jobID int64, req CasesRequest) error {
	return c.doJSON(ctx, http.MethodPost, fmt.Sprintf("/shadow/jobs/%d/cases", jobID), req, nil)
}

func (c *ShadowClient) Finish(ctx context.Context, jobID int64, req FinishRequest) error {
	return c.doJSON(ctx, http.MethodPost, fmt.Sprintf("/shadow/jobs/%d/finish", jobID), req, nil)
}

func (c *ShadowClient) Fail(ctx context.Context, jobID int64, req FailRequest) error {
	return c.doJSON(ctx, http.MethodPost, fmt.Sprintf("/shadow/jobs/%d/fail", jobID), req, nil)
}
