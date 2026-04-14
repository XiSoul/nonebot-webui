from typing import List, Tuple
from pathlib import Path, PurePosixPath

from fastapi import HTTPException, status

from nb_cli_plugin_webui.app.config import Config
from nb_cli_plugin_webui.app.handlers.project import NoneBotProjectManager
from nb_cli_plugin_webui.app.utils.container import is_docker_runtime

from .schemas import FileInfo, FileManagerScope


TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "gb18030", "latin-1")


def list_file(path: Path, path_relative: Path = Path()) -> List[FileInfo]:
    data = list()
    for f in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        if f.name == ".DS_Store":
            continue
        _path = (path / f.name).relative_to(path_relative)
        absolute_path = (path / f.name).resolve()
        data.append(
            FileInfo(
                name=f.name,
                is_dir=f.is_dir(),
                modified_time=str(f.stat().st_mtime),
                path=str(_path).replace("\\", "/"),
                absolute_path=str(absolute_path).replace("\\", "/"),
                size=0 if f.is_dir() else int(f.stat().st_size),
            )
        )
    return data


def normalize_relative_path(value: object) -> str:
    normalized = str(value or "").replace("\\", "/").strip()
    if normalized in {"", ".", "/"}:
        return ""

    parts = [part for part in normalized.split("/") if part and part != "."]
    if any(part == ".." for part in parts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path traversal is not allowed.",
        )
    return "/".join(parts)


def normalize_child_name(value: object) -> str:
    name = str(value or "").strip()
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file or directory name.",
        )
    return name


def _project_meta(project_id: str):
    try:
        return NoneBotProjectManager(project_id=project_id).read()
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project does not exist.",
        ) from err


def _is_path_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def resolve_file_manager_scope(project_dir: Path) -> Tuple[FileManagerScope, str, str]:
    base_dir_text = str(getattr(Config, "base_dir", "") or "").strip()
    if is_docker_runtime() and base_dir_text:
        base_dir = Path(base_dir_text)
        if _is_path_within(project_dir, base_dir):
            return (
                "installed",
                "Docker内实例目录",
                "当前实例安装在 WebUI 所在 Docker 环境内，这里显示实例在容器内的实际项目目录。",
            )

    return (
        "mapped",
        "映射目录",
        "当前实例目录来自 Docker 外部映射或宿主机目录，这里显示映射到运行环境后的实际项目目录。",
    )


def resolve_file_manager_root(
    project_id: str,
) -> Tuple[Path, str, str, FileManagerScope, str, str]:
    meta = _project_meta(project_id)
    project_dir = Path(meta.project_dir).resolve()
    scope, label, description = resolve_file_manager_scope(project_dir)
    return (
        project_dir,
        meta.project_name,
        str(project_dir).replace("\\", "/"),
        scope,
        label,
        description,
    )


def resolve_file_manager_target(
    project_id: str, relative_path: object
) -> Tuple[Path, str, str, FileManagerScope]:
    root_path, project_name, root_text, scope, _, _ = resolve_file_manager_root(project_id)
    normalized_relative = normalize_relative_path(relative_path)
    target = (root_path / PurePosixPath(normalized_relative)).resolve()
    try:
        target.relative_to(root_path)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target path is outside the allowed directory.",
        ) from err
    return target, project_name, root_text, scope


def read_text_content(path: Path) -> Tuple[str, str]:
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Binary files are not supported in the editor.",
        )

    for encoding in TEXT_ENCODINGS:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unable to decode file content.",
    )
