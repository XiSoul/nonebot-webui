#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CONTAINER_NAME="${WEBUI_TEST_CONTAINER_NAME:-nonebot-webui}"
BASE_URL="${WEBUI_TEST_BASE_URL:-http://127.0.0.1:18080}"
TOKEN="${WEBUI_TEST_TOKEN:-TestToken1!A}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing command: $1" >&2
    exit 1
  }
}

require_cmd docker
require_cmd python3
require_cmd curl

echo "[1/5] wait for container health: $CONTAINER_NAME"
for _ in $(seq 1 60); do
  status="$(docker inspect "$CONTAINER_NAME" --format '{{.State.Health.Status}}' 2>/dev/null || true)"
  if [[ "$status" == "healthy" ]]; then
    break
  fi
  sleep 2
done
if [[ "${status:-}" != "healthy" ]]; then
  echo "container is not healthy: ${status:-unknown}" >&2
  exit 1
fi

echo "[2/5] type-check frontend"
python3 - <<'PY'
import subprocess, sys
result = subprocess.run(["cmd.exe", "/c", "cd /d E:\\document\\nonebot-webui\\frontend && npm run type-check"], check=False)
sys.exit(result.returncode)
PY

echo "[3/5] build frontend dist"
python3 - <<'PY'
import subprocess, sys
result = subprocess.run(["cmd.exe", "/c", "cd /d E:\\document\\nonebot-webui\\frontend && npm run build-only"], check=False)
sys.exit(result.returncode)
PY

echo "[4/5] py_compile backend"
python3 - <<'PY'
import py_compile

for path in [
    r"nb_cli_plugin_webui/app/application.py",
    r"nb_cli_plugin_webui/app/process/router.py",
    r"nb_cli_plugin_webui/app/process/service.py",
]:
    py_compile.compile(path, doraise=True)
    print(path)
PY

echo "[5/5] terminal multi-session regression"
docker exec "$CONTAINER_NAME" python - <<'PY'
import json
from datetime import timedelta

from fastapi.testclient import TestClient

from nb_cli_plugin_webui.app.application import app
from nb_cli_plugin_webui.app.auth.utils import ensure_login_token_is_active
from nb_cli_plugin_webui.app.config import Config
from nb_cli_plugin_webui.app.utils.security import jwt


def recv_until(ws, predicate, limit=30):
    seen = []
    for _ in range(limit):
        message = ws.receive_json()
        seen.append(message)
        if predicate(message):
            return message, seen
    raise RuntimeError(json.dumps(seen, ensure_ascii=False))


ensure_login_token_is_active()
secret = Config.secret_key.get_secret_value()
token = jwt.create_jwt({"mark": "terminal-regression"}, secret, timedelta(hours=1))

results = {}

with TestClient(app) as client:
    projects_resp = client.get(
        "/v1/project/list", headers={"Authorization": f"Bearer {token}"}
    )
    projects_payload = projects_resp.json()
    project_id = next(iter(projects_payload["detail"].keys()))
    results["project_list"] = {
        "status": projects_resp.status_code,
        "project_id": project_id,
    }

    first_created = client.post(
        f"/v1/process/terminal/session/create?project_id={project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    second_created = client.post(
        f"/v1/process/terminal/session/create?project_id={project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    first_payload = first_created.json()["detail"]
    second_payload = second_created.json()["detail"]
    first_id = first_payload["session_id"]
    second_id = second_payload["session_id"]

    results["created"] = {
        "first": first_payload,
        "second": second_payload,
    }

    with client.websocket_connect("/v1/process/terminal/ws") as ws:
        ws.send_text(token)

        ws.send_json(
            {"type": "attach", "project_id": project_id, "session_id": first_id}
        )
        first_ready, first_seen = recv_until(
            ws, lambda item: item.get("type") == "ready" and item.get("session_id") == first_id
        )

        ws.send_json(
            {
                "type": "input",
                "project_id": project_id,
                "session_id": first_id,
                "data": 'printf "FIRST_SESSION_OK\\n"\\n',
            }
        )
        first_output, first_output_seen = recv_until(
            ws,
            lambda item: item.get("type") == "output"
            and "FIRST_SESSION_OK" in str(item.get("data", "")),
        )

        ws.send_json(
            {"type": "switch", "project_id": project_id, "session_id": second_id}
        )
        second_ready, second_seen = recv_until(
            ws, lambda item: item.get("type") == "ready" and item.get("session_id") == second_id
        )

        ws.send_json(
            {
                "type": "input",
                "project_id": project_id,
                "session_id": second_id,
                "data": 'printf "SECOND_SESSION_OK\\n"\\n',
            }
        )
        second_output, second_output_seen = recv_until(
            ws,
            lambda item: item.get("type") == "output"
            and "SECOND_SESSION_OK" in str(item.get("data", "")),
        )

        ws.send_json(
            {"type": "close", "project_id": project_id, "session_id": second_id}
        )
        close_state, close_seen = recv_until(
            ws,
            lambda item: item.get("type") == "sessions"
            and len(item.get("sessions", [])) == 1,
        )

    sessions_resp = client.get(
        f"/v1/process/terminal/sessions?project_id={project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    sessions_payload = sessions_resp.json()["detail"]

results["ws"] = {
    "first_ready": first_ready,
    "first_output": first_output,
    "second_ready": second_ready,
    "second_output": second_output,
    "close_state": close_state,
    "samples": {
        "first_seen": first_seen[:8],
        "first_output_seen": first_output_seen[:8],
        "second_seen": second_seen[:8],
        "second_output_seen": second_output_seen[:8],
        "close_seen": close_seen[:8],
    },
}
results["final_sessions"] = sessions_payload
results["checks"] = {
    "created_two_sessions": first_id != second_id,
    "attached_first_session": first_ready["session_id"] == first_id,
    "first_output_seen": "FIRST_SESSION_OK" in str(first_output.get("data", "")),
    "attached_second_session": second_ready["session_id"] == second_id,
    "second_output_seen": "SECOND_SESSION_OK" in str(second_output.get("data", "")),
    "close_left_one_session": len(close_state.get("sessions", [])) == 1,
    "rest_left_one_session": len(sessions_payload) == 1,
}

print(json.dumps(results, ensure_ascii=False, indent=2))

if not all(results["checks"].values()):
    raise SystemExit(1)
PY

echo
echo "terminal session regression passed"
