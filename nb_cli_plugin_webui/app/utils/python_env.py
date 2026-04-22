import os
from pathlib import Path


def _safe_resolve(path: Path) -> Path:
    try:
        return path.expanduser().resolve()
    except Exception:
        return path.expanduser().absolute()


def resolve_project_python_path(project_dir: Path) -> str:
    resolved_project_dir = _safe_resolve(project_dir)
    if os.name == "nt":
        python_rel_path = Path("Scripts") / "python.exe"
    else:
        python_rel_path = Path("bin") / "python"

    for env_name in (".venv", "venv"):
        candidate = resolved_project_dir / env_name / python_rel_path
        if candidate.is_file():
            return str(candidate)

    try:
        child_dirs = sorted(
            (child for child in resolved_project_dir.iterdir() if child.is_dir()),
            key=lambda child: child.name,
        )
    except OSError:
        return ""

    for child in child_dirs:
        if child.name.startswith(".venv.webui-"):
            continue
        if not (child / "pyvenv.cfg").is_file():
            continue

        candidate = child / python_rel_path
        if candidate.is_file():
            return str(candidate)

    return ""
