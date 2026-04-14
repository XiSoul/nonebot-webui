from fastapi import HTTPException, status

from nb_cli_plugin_webui.app.exceptions import NotFound, BadRequest

from .constants import ErrorCode


class NoneBotProjectNotFound(NotFound):
    detail = ErrorCode.PROJECT_NOT_FOUND


class ProjectDirIsNotDir(BadRequest):
    detail = ErrorCode.PROJECT_DIR_NOT_DIR


class ProjectDeleteFailed(BadRequest):
    detail = ErrorCode.PROJECT_DELETE_FAILED


class WriteNoneBotProjectProfileFailed(BadRequest):
    detail = ErrorCode.PROJECT_WRITE_PROFILE_FAILED


class ProjectTomlNotFound(BadRequest):
    detail = ErrorCode.PROJECT_TOML_NOT_FOUND


class ProjectNameAlreadyExists(BadRequest):
    detail = "实例名称已存在"

    def __init__(self, project_name: str = "") -> None:
        detail = self.detail
        if project_name:
            detail = f'实例名称 "{project_name}" 已存在，请更换后再试'
        HTTPException.__init__(
            self, status_code=status.HTTP_400_BAD_REQUEST, detail=detail
        )


class ProjectPortAlreadyExists(BadRequest):
    detail = "实例端口已存在"

    def __init__(self, port: int, project_name: str = "") -> None:
        detail = f"端口 {port} 已被其他实例使用，请换一个端口"
        if project_name:
            detail = f"端口 {port} 已被实例 {project_name} 使用，请换一个端口"
        HTTPException.__init__(
            self, status_code=status.HTTP_400_BAD_REQUEST, detail=detail
        )


class ProjectDirectoryAlreadyExists(BadRequest):
    detail = "实例目录已存在"

    def __init__(self, project_dir: str = "", project_name: str = "") -> None:
        detail = self.detail
        if project_dir and project_name:
            detail = f'目录 "{project_dir}" 已被实例 "{project_name}" 使用，请更换目录后再试'
        elif project_dir:
            detail = f'目录 "{project_dir}" 已被其他实例使用，请更换目录后再试'
        HTTPException.__init__(
            self, status_code=status.HTTP_400_BAD_REQUEST, detail=detail
        )
