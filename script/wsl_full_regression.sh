#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TOKEN="${WEBUI_TEST_TOKEN:-TestToken1!A}"
SESSION_HOURS_DEFAULT="${WEBUI_TEST_SESSION_HOURS_DEFAULT:-24}"
SESSION_HOURS_TEMP="${WEBUI_TEST_SESSION_HOURS_TEMP:-2}"
IMAGE_TAG="${WEBUI_TEST_IMAGE_TAG:-xisoul/nonebot-webui:latest}"
CONTAINER_NAME="${WEBUI_TEST_CONTAINER_NAME:-nonebot-webui}"

CONFIG_PATH="$ROOT_DIR/data/config.json"
PROJECT_PATH="$ROOT_DIR/data/project.json"
PROJECTS_DIR="$ROOT_DIR/data/projects"
EXTERNAL_DIR="$ROOT_DIR/data/external-projects"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing command: $1" >&2
    exit 1
  }
}

require_cmd docker
require_cmd python3
require_cmd corepack
require_cmd curl

echo "[1/8] type-check frontend"
corepack pnpm -C frontend run type-check

echo "[2/8] build frontend dist"
corepack pnpm -C frontend run build-only

echo "[3/8] py_compile backend"
python3 -m py_compile \
  nb_cli_plugin_webui/app/application.py \
  nb_cli_plugin_webui/app/config.py \
  nb_cli_plugin_webui/app/auth/router.py \
  nb_cli_plugin_webui/app/auth/utils.py \
  nb_cli_plugin_webui/app/system/router.py \
  nb_cli_plugin_webui/app/system/schemas.py \
  nb_cli_plugin_webui/app/utils/security/jwt.py

echo "[4/8] build docker image: $IMAGE_TAG"
docker build -t "$IMAGE_TAG" .

echo "[5/8] generate known permanent token hash"
readarray -t TOKEN_LINES < <(
  docker run --rm --entrypoint python "$IMAGE_TAG" -c \
  "from nb_cli_plugin_webui.app.utils.security import salt; token='$TOKEN'; s=salt.gen_salt(); print(s); print(salt.get_token_hash(s + token))"
)
TOKEN_SALT="${TOKEN_LINES[0]}"
TOKEN_HASH="${TOKEN_LINES[1]}"

echo "[6/8] patch config with known permanent token"
python3 - <<PY
import json
from pathlib import Path

config_path = Path(r"$CONFIG_PATH")
cfg = json.loads(config_path.read_text(encoding="utf-8"))
cfg["secret_key"] = "manual-test-secret-20260505"
cfg["salt"] = "$TOKEN_SALT"
cfg["hashed_token"] = "$TOKEN_HASH"
cfg["login_token_mode"] = "permanent"
cfg["login_token_expires_at"] = 0
cfg["login_token_random_expire_hours"] = 24
cfg["session_token_expire_hours"] = $SESSION_HOURS_DEFAULT
config_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
PY

echo "[7/8] recreate container: $CONTAINER_NAME"
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart always \
  --network host \
  -e HOST=0.0.0.0 \
  -e PORT=18080 \
  -v "$PROJECTS_DIR:/projects" \
  -v "$EXTERNAL_DIR:/external-projects" \
  -v "$CONFIG_PATH:/app/config.json" \
  -v "$PROJECT_PATH:/app/project.json" \
  "$IMAGE_TAG" >/dev/null

echo "[8/8] functional regression"
python3 - <<PY
import base64
import json
import pathlib
import subprocess
import tempfile
import time

TOKEN = "$TOKEN"
DEFAULT_HOURS = $SESSION_HOURS_DEFAULT
TEMP_HOURS = $SESSION_HOURS_TEMP
BASE_URL = "http://127.0.0.1:18080"

results = []

def run(cmd):
    res = subprocess.run(["sh", "-lc", cmd], capture_output=True, text=True)
    return res.stdout.strip(), res.stderr.strip(), res.returncode

def record(name, ok, detail):
    results.append({"name": name, "ok": ok, "detail": detail})

for _ in range(30):
    out, err, _ = run("docker inspect nonebot-webui --format '{{.State.Health.Status}}'")
    if out == "healthy":
        record("container_healthy", True, out)
        break
    time.sleep(2)
else:
    record("container_healthy", False, out or err)

for name, path in [
    ("noauth_security_blocked", "/v1/system/security"),
    ("noauth_project_list_blocked", "/v1/project/list"),
]:
    out, _, _ = run(f"curl -s -o /tmp/out -w '%{{http_code}}' {BASE_URL}{path}")
    body = pathlib.Path("/tmp/out").read_text(encoding="utf-8", errors="replace")
    record(name, out == "403", f"status={out} body={body}")

def post_json(path, payload, bearer=None):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
        json.dump(payload, f)
        temp_path = pathlib.Path(f.name)
    try:
        auth = f"-H 'Authorization: Bearer {bearer}' " if bearer else ""
        out, _, _ = run(
            f"curl -s -o /tmp/out -w '%{{http_code}}' -X POST {BASE_URL}{path} "
            f"{auth}-H 'Content-Type: application/json' --data-binary '@{temp_path}'"
        )
        body = pathlib.Path('/tmp/out').read_text(encoding='utf-8', errors='replace')
        return out, body
    finally:
        temp_path.unlink(missing_ok=True)

def put_json(path, payload, bearer):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
        json.dump(payload, f)
        temp_path = pathlib.Path(f.name)
    try:
        out, _, _ = run(
            f"curl -s -o /tmp/out -w '%{{http_code}}' -X PUT {BASE_URL}{path} "
            f"-H 'Authorization: Bearer {bearer}' "
            f"-H 'Content-Type: application/json' --data-binary '@{temp_path}'"
        )
        body = pathlib.Path('/tmp/out').read_text(encoding='utf-8', errors='replace')
        return out, body
    finally:
        temp_path.unlink(missing_ok=True)

status, body = post_json("/v1/auth/login", {"token": TOKEN, "mark": "functional-test"})
login_json = json.loads(body) if body else {}
jwt_token = login_json.get("detail", "")
record("login_with_permanent_token", status == "200" and bool(jwt_token), f"status={status}")

status, body = post_json("/v1/auth/verify", {"jwt_token": jwt_token})
verify_json = json.loads(body) if body else {}
record("verify_session_token", status == "200" and "detail" in verify_json, f"status={status}")

parts = jwt_token.split(".")
exp_ok = False
exp_detail = "missing jwt"
if len(parts) == 3:
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    payload_json = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    delta = int(payload_json["exp"]) - int(time.time())
    exp_ok = 86000 <= delta <= 86500
    exp_detail = f"delta={delta}"
record("jwt_default_24h", exp_ok, exp_detail)

out, _, _ = run(f"curl -s -o /tmp/out -w '%{{http_code}}' {BASE_URL}/v1/system/security -H 'Authorization: Bearer {jwt_token}'")
body = pathlib.Path('/tmp/out').read_text(encoding='utf-8', errors='replace')
security_json = json.loads(body) if body else {}
record(
    "security_response_has_session_hours",
    out == "200" and security_json.get("detail", {}).get("session_token_expire_hours") == DEFAULT_HOURS,
    body,
)

status, body = put_json(
    "/v1/system/security",
    {
        "current_token": "",
        "new_token": "",
        "service_port": 18080,
        "token_mode": "permanent",
        "random_token_expire_hours": 24,
        "session_token_expire_hours": TEMP_HOURS,
    },
    jwt_token,
)
update_json = json.loads(body) if body else {}
record(
    "update_session_expiry_to_2h",
    status == "200" and update_json.get("detail", {}).get("session_token_expire_hours") == TEMP_HOURS,
    body,
)

status, body = post_json("/v1/auth/login", {"token": TOKEN, "mark": "functional-test-2h"})
login2_json = json.loads(body) if body else {}
jwt_token_2h = login2_json.get("detail", "")
parts = jwt_token_2h.split(".")
exp_ok = False
exp_detail = "missing jwt"
if len(parts) == 3:
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    payload_json = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    delta = int(payload_json["exp"]) - int(time.time())
    exp_ok = 7100 <= delta <= 7300
    exp_detail = f"delta={delta}"
record("jwt_updated_to_2h", exp_ok, exp_detail)

status, body = put_json(
    "/v1/system/security",
    {
        "current_token": "",
        "new_token": "",
        "service_port": 18080,
        "token_mode": "permanent",
        "random_token_expire_hours": 24,
        "session_token_expire_hours": DEFAULT_HOURS,
    },
    jwt_token_2h,
)
restore_json = json.loads(body) if body else {}
record(
    "restore_session_expiry_24h",
    status == "200" and restore_json.get("detail", {}).get("session_token_expire_hours") == DEFAULT_HOURS,
    body,
)

run("docker restart nonebot-webui >/dev/null")
for _ in range(30):
    out, err, _ = run("docker inspect nonebot-webui --format '{{.State.Health.Status}}'")
    if out == "healthy":
        break
    time.sleep(2)

status, body = post_json("/v1/auth/login", {"token": TOKEN, "mark": "functional-test-after-restart"})
login3_json = json.loads(body) if body else {}
record("permanent_token_survives_restart", status == "200" and bool(login3_json.get("detail")), f"status={status}")

print(json.dumps(results, ensure_ascii=False, indent=2))
PY

echo
echo "Current permanent token: $TOKEN"
