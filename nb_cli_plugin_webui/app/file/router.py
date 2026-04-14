import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from nb_cli_plugin_webui.app.config import Config
from nb_cli_plugin_webui.app.logging import logger as log

from .utils import (
    list_file,
    normalize_child_name,
    normalize_relative_path,
    read_text_content,
    resolve_file_manager_root,
    resolve_file_manager_target,
)
from .schemas import (
    FileManagerContentResponse,
    FileManagerCreateRequest,
    FileManagerDeleteRequest,
    FileManagerListResponse,
    FileManagerRootsResponse,
    FileManagerRootItem,
    FileManagerScope,
    FileManagerWriteRequest,
    SimpleModel,
    FileResponse,
)
from .exceptions import PathIsNotDir, PathIsNotExists

router = APIRouter(tags=["file"])


@router.get("/list", response_model=FileResponse)
async def get_file_list(path: str) -> FileResponse:
    """
    - 根据提供的路径, 基于 base_dir 返回文件列表
    """
    base_dir = Path(Config.base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    working_dir = base_dir / Path(path)
    if not working_dir.exists():
        raise PathIsNotExists()
    if not working_dir.is_dir():
        raise PathIsNotDir()
    result = list_file(working_dir, base_dir)
    return FileResponse(detail=result)


@router.post("/create", response_model=FileResponse)
async def create_file(data: SimpleModel) -> FileResponse:
    """
    - 根据提供的路径, 基于 base_dir 创建文件
    """
    base_dir = Path(Config.base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    working_dir = base_dir / Path(data.path)
    path = working_dir / data.name
    if data.is_dir:
        path.mkdir(parents=True, exist_ok=True)
    else:
        working_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(str(), encoding="utf-8")
    result = list_file(working_dir, base_dir)
    return FileResponse(detail=result)


@router.delete("/delete", response_model=FileResponse)
async def delete_file(path: str) -> FileResponse:
    """
    - 根据提供的路径, 基于 base_dir 删除文件
    """
    base_dir = Path(Config.base_dir)
    working_dir = base_dir / Path(path)
    if not working_dir.exists():
        raise PathIsNotExists()

    try:
        shutil.rmtree(working_dir)
    except OSError as err:
        log.error(f"Delete file failed: {err}")
        log.exception(err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除文件失败 {err=}",
        )

    result = list_file(working_dir.parent, base_dir)
    return FileResponse(detail=result)


@router.get("/manager/roots", response_model=FileManagerRootsResponse)
async def get_file_manager_roots(project_id: str) -> FileManagerRootsResponse:
    roots = []
    project_name = ""
    try:
        _, project_name, root_text, scope, label, description = resolve_file_manager_root(
            project_id
        )
        roots.append(
            FileManagerRootItem(
                scope=scope,
                label=label,
                description=description,
                root_path=root_text,
                available=True,
            )
        )
    except HTTPException as err:
        roots.append(
            FileManagerRootItem(
                scope="mapped",
                label="实例目录",
                description="无法识别当前实例目录。",
                root_path="",
                available=False,
                detail=str(err.detail),
            )
        )

    return FileManagerRootsResponse(
        project_id=project_id,
        project_name=project_name,
        roots=roots,
    )


@router.get("/manager/list", response_model=FileManagerListResponse)
async def get_file_manager_list(
    project_id: str,
    scope: FileManagerScope,
    path: str = "",
) -> FileManagerListResponse:
    target_dir, _, root_text, actual_scope = resolve_file_manager_target(project_id, path)
    if not target_dir.exists():
        raise PathIsNotExists()
    if not target_dir.is_dir():
        raise PathIsNotDir()

    return FileManagerListResponse(
        scope=actual_scope,
        root_path=root_text,
        current_path=normalize_relative_path(path),
        items=list_file(target_dir, resolve_file_manager_root(project_id)[0]),
    )


@router.get("/manager/content", response_model=FileManagerContentResponse)
async def get_file_manager_content(
    project_id: str,
    scope: FileManagerScope,
    path: str,
) -> FileManagerContentResponse:
    target_file, _, root_text, actual_scope = resolve_file_manager_target(project_id, path)
    if not target_file.exists():
        raise PathIsNotExists()
    if target_file.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Directory cannot be opened as a file.",
        )

    content, encoding = read_text_content(target_file)
    return FileManagerContentResponse(
        scope=actual_scope,
        root_path=root_text,
        path=normalize_relative_path(path),
        content=content,
        encoding=encoding,
        size=int(target_file.stat().st_size),
    )


@router.put("/manager/content", response_model=FileManagerContentResponse)
async def update_file_manager_content(
    data: FileManagerWriteRequest,
) -> FileManagerContentResponse:
    target_file, _, root_text, actual_scope = resolve_file_manager_target(
        data.project_id, data.path
    )
    if not target_file.exists():
        raise PathIsNotExists()
    if target_file.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Directory content cannot be edited.",
        )

    encoding = (data.encoding or "utf-8").strip() or "utf-8"
    target_file.write_text(data.content, encoding=encoding)
    return FileManagerContentResponse(
        scope=actual_scope,
        root_path=root_text,
        path=normalize_relative_path(data.path),
        content=data.content,
        encoding=encoding,
        size=len(data.content.encode(encoding, errors="ignore")),
    )


@router.post("/manager/create", response_model=FileManagerListResponse)
async def create_file_manager_entry(
    data: FileManagerCreateRequest,
) -> FileManagerListResponse:
    parent_dir, _, root_text, actual_scope = resolve_file_manager_target(
        data.project_id, data.path
    )
    if not parent_dir.exists():
        raise PathIsNotExists()
    if not parent_dir.is_dir():
        raise PathIsNotDir()

    entry_name = normalize_child_name(data.name)
    target = parent_dir / entry_name
    if target.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target already exists.",
        )

    if data.is_dir:
        target.mkdir(parents=True, exist_ok=False)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")

    return FileManagerListResponse(
        scope=actual_scope,
        root_path=root_text,
        current_path=normalize_relative_path(data.path),
        items=list_file(parent_dir, resolve_file_manager_root(data.project_id)[0]),
    )


@router.delete("/manager/delete", response_model=FileManagerListResponse)
async def delete_file_manager_entry(
    data: FileManagerDeleteRequest,
) -> FileManagerListResponse:
    target, _, root_text, actual_scope = resolve_file_manager_target(
        data.project_id, data.path
    )
    if not target.exists():
        raise PathIsNotExists()

    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    parent_dir = target.parent
    root_dir = resolve_file_manager_root(data.project_id)[0]
    current_path = ""
    if parent_dir != root_dir:
        current_path = str(parent_dir.relative_to(root_dir)).replace("\\", "/")

    return FileManagerListResponse(
        scope=actual_scope,
        root_path=root_text,
        current_path=current_path,
        items=list_file(parent_dir, root_dir),
    )
