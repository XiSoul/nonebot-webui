import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class DockerStorageMigrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.app_dir = self.root / "app"
        self.data_dir.mkdir()
        self.app_dir.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_ensure_docker_config_migrates_legacy_app_config_to_data_without_regenerating_token(self) -> None:
        legacy_config = {
            "base_dir": "/projects",
            "host": "0.0.0.0",
            "port": "18080",
            "secret_key": "existing-secret",
            "salt": "existing-salt",
            "hashed_token": "existing-hash",
            "login_token_mode": "permanent",
        }
        (self.app_dir / "config.json").write_text(json.dumps(legacy_config), encoding="utf-8")

        with patch.dict(
            os.environ,
            {
                "WEBUI_BUILD": "1",
                "WEBUI_DATA_DIR": str(self.data_dir),
                "WEBUI_CONFIG_DIR": str(self.data_dir),
                "WEBUI_CACHE_DIR": str(self.data_dir),
                "WEBUI_LEGACY_APP_DIR": str(self.app_dir),
            },
            clear=False,
        ):
            import nb_cli_plugin_webui.app.utils.storage as storage
            import nb_cli_plugin_webui.app.config as config

            importlib.reload(storage)
            config = importlib.reload(config)

            generated_token = config.ensure_docker_config()

        stored_config = json.loads((self.data_dir / "config.json").read_text("utf-8"))
        self.assertIsNone(generated_token)
        self.assertEqual(stored_config["secret_key"], "existing-secret")
        self.assertEqual(stored_config["salt"], "existing-salt")
        self.assertEqual(stored_config["hashed_token"], "existing-hash")

    def test_project_registry_migrates_legacy_app_project_json_to_data(self) -> None:
        legacy_project = {
            "demo": {
                "project_id": "demo",
                "project_name": "demo",
                "project_dir": str(self.root / "demo"),
                "mirror_url": "",
                "adapters": [],
                "drivers": [],
                "plugins": [],
                "plugin_dirs": [],
                "builtin_plugins": [],
            }
        }
        (self.app_dir / "project.json").write_text(
            json.dumps(legacy_project), encoding="utf-8"
        )

        with patch.dict(
            os.environ,
            {
                "WEBUI_BUILD": "1",
                "WEBUI_DATA_DIR": str(self.data_dir),
                "WEBUI_CONFIG_DIR": str(self.data_dir),
                "WEBUI_CACHE_DIR": str(self.data_dir),
                "WEBUI_LEGACY_APP_DIR": str(self.app_dir),
            },
            clear=False,
        ):
            import nb_cli_plugin_webui.app.utils.storage as storage
            import nb_cli_plugin_webui.app.handlers.project as project_handler

            importlib.reload(storage)
            project_handler = importlib.reload(project_handler)

            projects = project_handler.NoneBotProjectManager.get_project()

        stored_project = json.loads((self.data_dir / "project.json").read_text("utf-8"))
        self.assertIn("demo", projects)
        self.assertEqual(stored_project["demo"]["project_id"], "demo")


if __name__ == "__main__":
    unittest.main()
