from nb_cli_plugin_webui.app.exceptions import BadRequest, NotFound

from .constants import ErrorCode


class ModuleTypeNotFound(NotFound):
    detail = ErrorCode.MODULE_TYPE_NOT_FOUND


class ModuleIsExisted(NotFound):
    detail = ErrorCode.MODULE_IS_EXISTED


class ModuleNotFound(NotFound):
    detail = ErrorCode.MODULE_NOT_FOUND


class ProjectIsRunning(BadRequest):
    detail = ErrorCode.PROJECT_IS_RUNNING