import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from nb_cli_plugin_webui.app.handlers import project as project_handler
from nb_cli_plugin_webui.app.handlers.process import ProcessManager
from nb_cli_plugin_webui.app.models.base import NoneBotProjectMeta
from nb_cli_plugin_webui.app.project.service import update_nonebot_project_dir


class CachedProcess:
    def __init__(self) -> None:
        self.log_storage = SimpleNamespace(listeners={})
        self.stopped = False

    def refresh_runtime_state(self) -> bool:
        return False

    async def stop(self) -> None:
        self.stopped = True


def write_project_toml(project_dir: Path, name: str) -> None:
    project_dir.mkdir()
    (project_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\ndependencies = ["nonebot2"]\n',
        encoding="utf-8",
    )


class UpdateProjectDirTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.original_project_data_path = project_handler.PROJECT_DATA_PATH
        project_handler.PROJECT_DATA_PATH = self.root / "project.json"
        ProcessManager.processes.clear()

    async def asyncTearDown(self) -> None:
        ProcessManager.processes.clear()
        project_handler.PROJECT_DATA_PATH = self.original_project_data_path
        self.temp_dir.cleanup()

    async def test_update_project_dir_drops_cached_runtime_process(self) -> None:
        old_dir = self.root / "old-project"
        new_dir = self.root / "new-project"
        write_project_toml(old_dir, "old-project")
        write_project_toml(new_dir, "new-project")

        project_id = "project-1"
        meta = NoneBotProjectMeta(
            project_id=project_id,
            project_name="demo",
            project_dir=str(old_dir),
            mirror_url="",
            adapters=[],
            drivers=[],
            plugins=[],
            plugin_dirs=[],
            builtin_plugins=[],
        )
        project_handler.PROJECT_DATA_PATH.write_text(
            json.dumps({project_id: json.loads(meta.json())}),
            encoding="utf-8",
        )

        ProcessManager.processes[project_id] = CachedProcess()

        result = await update_nonebot_project_dir(project_id, str(new_dir))

        stored = json.loads(project_handler.PROJECT_DATA_PATH.read_text("utf-8"))
        self.assertEqual(result, str(new_dir.absolute()))
        self.assertEqual(stored[project_id]["project_dir"], str(new_dir.absolute()))
        self.assertNotIn(project_id, ProcessManager.processes)


if __name__ == "__main__":
    unittest.main()
