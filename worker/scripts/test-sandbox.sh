#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
docker compose up -d go-judge
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:5050/version >/dev/null; then
    break
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:5050/version
echo
GO_JUDGE_URL=http://127.0.0.1:5050 go test ./worker/integration -v
