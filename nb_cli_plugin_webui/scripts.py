import sys
import json
import subprocess
from pathlib import Path

import httpx

from nb_cli_plugin_webui import get_version


def extract():
    from babel.messages.frontend import CommandLineInterface

    version = get_version()
    CommandLineInterface().run(
        [
            "pybabel",
            "extract",
            "-o",
            "messages.pot",
            "--project",
            "nb-cli-plugin-webui",
            "--version",
            version,
            "nb_cli_plugin_webui/",
        ]
    )


def init():
    from babel.messages.frontend import CommandLineInterface

    args = sys.argv[1:]
    if len(args) != 1:
        print("Usage: poetry run init <lang>")
        exit(-1)

    extract()

    CommandLineInterface().run(
        [
            "pybabel",
            "init",
            "-D",
            "nb-cli-plugin-webui",
            "-i",
            "messages.pot",
            "-d",
            "nb_cli_plugin_webui/locale",
            "-l",
            args[0],
        ]
    )


def update():
    from babel.messages.frontend import CommandLineInterface

    extract()
    CommandLineInterface().run(
        [
            "pybabel",
            "update",
            "-D",
            "nb-cli-plugin-webui",
            "-i",
            "messages.pot",
            "-d",
            "nb_cli_plugin_webui/locale",
        ]
    )


def compile():
    from babel.messages.frontend import CommandLineInterface

    CommandLineInterface().run(
        [
            "pybabel",
            "compile",
            "-D",
            "nb-cli-plugin-webui",
            "-d",
            "nb_cli_plugin_webui/locale",
        ]
    )


def _get_openapi():
    args = sys.argv[1:]
    if len(args) != 2:
        print("Usage: poetry run generate <host> <port>")
        exit(-1)

    host = args[0]
    port = args[1]
    url = f"http://{host}:{port}/api/docs/openapi.json"
    response = httpx.get(url, proxies=dict())
    if response.status_code == 502:
        print("Error: Could not fetch OpenAPI schema")
        exit(-1)

    with open("./openapi.json", "w") as f:
        f.write(json.dumps(response.json()))


def generate_openapi():
    _get_openapi()
    subprocess.run(
        [
            "pnpm",
            "-r",
            "openapi-ts",
        ]
    )


def reset_token():
    """
    Reset WebUI login token. Reads /app/config.json, generates a new token,
    updates the file, and prints the new token to stdout.

    Usage (inside Docker container):
        python -m nb_cli_plugin_webui.scripts reset_token
    Or if installed as a script entry point:
        reset-token
    """
    from nb_cli_plugin_webui.app.config import CONFIG_FILE_PATH
    from nb_cli_plugin_webui.app.utils.string_utils import generate_access_token
    from nb_cli_plugin_webui.app.utils.security.salt import reset_token as create_new_token

    if not CONFIG_FILE_PATH.exists():
        print(f"Error: Config file not found at {CONFIG_FILE_PATH}")
        print("Please ensure the WebUI has been initialized first.")
        sys.exit(1)

    try:
        raw_text = CONFIG_FILE_PATH.read_text(encoding="utf-8")
        config_data = json.loads(raw_text)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error: Could not read or parse config file: {e}")
        sys.exit(1)

    # Generate new token
    new_token = generate_access_token().replace('"', "'")
    new_credentials = create_new_token(new_token)

    # Update config
    config_data["salt"] = new_credentials.salt
    config_data["hashed_token"] = new_credentials.hashed_token

    try:
        CONFIG_FILE_PATH.write_text(json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        print(f"Error: Could not write config file: {e}")
        sys.exit(1)

    print("=" * 60)
    print("WebUI login token has been reset successfully.")
    print("=" * 60)
    print(f"\nYour new token is:\n")
    print(f"    {new_token}\n")
    print("ATTENTION: Token is only shown once. Please save it securely.")
    print("=" * 60)
    print("\nIMPORTANT: You must restart the container for changes to take effect:")
    print("    docker restart nonebot-webui")
    print("=" * 60)


if __name__ == "__main__":
    # When called as: python -m nb_cli_plugin_webui.scripts <command>
    if len(sys.argv) > 1 and sys.argv[1] == "reset_token":
        reset_token()
    else:
        print("Usage: python -m nb_cli_plugin_webui.scripts reset_token")
        sys.exit(1)
