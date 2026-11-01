#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

if [ -f .env ]; then
  ENV_TOKEN=$(sed -n 's/^GO_JUDGE_AUTH_TOKEN=//p' .env | tail -n 1)
  TOKEN="${GO_JUDGE_AUTH_TOKEN:-${ENV_TOKEN:-dev-judge-token}}"
else
  TOKEN="${GO_JUDGE_AUTH_TOKEN:-dev-judge-token}"
fi

docker compose up -d go-judge
for _ in $(seq 1 30); do
  if curl -fsS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5050/version >/dev/null; then
    break
  fi
  sleep 1
done
curl -fsS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5050/version
echo
# /version is public for health checks; execution endpoints must reject anonymous calls.
STATUS=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  -H 'Content-Type: application/json' \
  -d '{"requestId":"auth-probe","cmd":[{"args":["true"]}]}' \
  http://127.0.0.1:5050/run)
if [ "$STATUS" != "401" ]; then
  echo "go-judge did not reject an unauthenticated /run request (HTTP $STATUS)" >&2
  exit 1
fi
(
  cd worker
  GO_JUDGE_URL=http://127.0.0.1:5050 GO_JUDGE_TOKEN="$TOKEN" go test -count=1 ./integration -v
)
