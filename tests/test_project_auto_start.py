import json
import tempfile
import unittest
from pathlib import Path

from nb_cli_plugin_webui.app.handlers import project as project_handler
from nb_cli_plugin_webui.app.handlers.process import ProcessManager
from nb_cli_plugin_webui.app.models.base import ModuleInfo, NoneBotProjectMeta
from nb_cli_plugin_webui.app.project.router import update_project_auto_start
from nb_cli_plugin_webui.app.project.schemas import AutoStartProjectData
from nb_cli_plugin_webui.app.project.service import (
    auto_start_enabled_projects,
    list_nonebot_project,
    set_nonebot_project_auto_start,
    start_auto_start_projects,
)


def write_project_toml(project_dir: Path, name: str) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\ndependencies = ["nonebot2"]\n',
        encoding="utf-8",
    )


def build_meta(project_id: str, project_dir: Path, *, auto_start: bool = False):
    return NoneBotProjectMeta(
        project_id=project_id,
        project_name=project_id,
        project_dir=str(project_dir),
        mirror_url="",
        adapters=[ModuleInfo(module_name="nonebot.adapters.console", name="Console")],
        drivers=[ModuleInfo(module_name="~fastapi", name="fastapi")],
        plugins=[],
        plugin_dirs=[],
        builtin_plugins=[],
        auto_start=auto_start,
    )


class CachedProcess:
    def __init__(self, running: bool) -> None:
        self.running = running
        self.log_storage = LogStorageStub()

    def refresh_runtime_state(self) -> bool:
        return self.running


class LogStorageStub:
    def __init__(self) -> None:
        self.listeners = {}


class ProjectAutoStartTest(unittest.IsolatedAsyncioTestCase):
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

    def write_projects(self, metas):
        project_handler.PROJECT_DATA_PATH.write_text(
            json.dumps({meta.project_id: json.loads(meta.json()) for meta in metas}),
            encoding="utf-8",
        )

    def test_old_project_json_defaults_auto_start_false(self) -> None:
        project_dir = self.root / "old"
        write_project_toml(project_dir, "old")
        raw = json.loads(build_meta("old", project_dir).json())
        raw.pop("auto_start", None)
        project_handler.PROJECT_DATA_PATH.write_text(
            json.dumps({"old": raw}),
            encoding="utf-8",
        )

        projects = list_nonebot_project()

        self.assertFalse(projects["old"].auto_start)

    async def test_set_auto_start_persists_single_project(self) -> None:
        project_dir = self.root / "demo"
        write_project_toml(project_dir, "demo")
        self.write_projects([build_meta("demo", project_dir)])

        updated = set_nonebot_project_auto_start("demo", True)

        stored = json.loads(project_handler.PROJECT_DATA_PATH.read_text("utf-8"))
        self.assertTrue(updated.auto_start)
        self.assertTrue(stored["demo"]["auto_start"])

    async def test_set_auto_start_api_persists_single_project(self) -> None:
        project_dir = self.root / "api-demo"
        write_project_toml(project_dir, "api-demo")
        self.write_projects([build_meta("api-demo", project_dir)])

        response = await update_project_auto_start(
            AutoStartProjectData(project_id="api-demo", auto_start=True)
        )

        stored = json.loads(project_handler.PROJECT_DATA_PATH.read_text("utf-8"))
        self.assertTrue(response.detail.auto_start)
        self.assertTrue(stored["api-demo"]["auto_start"])

    async def test_start_auto_start_projects_skips_running_missing_and_isolates_errors(self) -> None:
        enabled_dir = self.root / "enabled"
        running_dir = self.root / "running"
        failing_dir = self.root / "failing"
        missing_dir = self.root / "missing"
        for project_dir in (enabled_dir, running_dir, failing_dir):
            write_project_toml(project_dir, project_dir.name)
        self.write_projects([
            build_meta("enabled", enabled_dir, auto_start=True),
            build_meta("running", running_dir, auto_start=True),
            build_meta("failing", failing_dir, auto_start=True),
            build_meta("missing", missing_dir, auto_start=True),
            build_meta("disabled", self.root / "disabled", auto_start=False),
        ])
        ProcessManager.processes["running"] = CachedProcess(running=True)
        started = []

        async def fake_runner(project):
            if project.project_id == "failing":
                raise RuntimeError("boom")
            started.append(project.project_id)

        await start_auto_start_projects(delay_seconds=0, runner=fake_runner)

        self.assertEqual(started, ["enabled"])

    def test_auto_start_enabled_projects_filters_enabled_existing_stopped_projects(self) -> None:
        enabled_dir = self.root / "enabled"
        running_dir = self.root / "running"
        write_project_toml(enabled_dir, "enabled")
        write_project_toml(running_dir, "running")
        self.write_projects([
            build_meta("enabled", enabled_dir, auto_start=True),
            build_meta("running", running_dir, auto_start=True),
            build_meta("disabled", self.root / "disabled", auto_start=False),
        ])
        ProcessManager.processes["running"] = CachedProcess(running=True)

        self.assertEqual(
            [project.project_id for project in auto_start_enabled_projects()],
            ["enabled"],
        )


if __name__ == "__main__":
    unittest.main()
