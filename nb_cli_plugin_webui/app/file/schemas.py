from typing import List, Literal

from pydantic import BaseModel

from nb_cli_plugin_webui.app.schemas import GenericResponse


FileManagerScope = Literal["mapped", "installed"]


class SimpleModel(BaseModel):
    name: str
    is_dir: bool
    path: str


class FileInfo(SimpleModel):
    modified_time: str
    absolute_path: str
    size: int = 0


class FileResponse(GenericResponse[List[FileInfo]]):
    pass


class FileManagerRootItem(BaseModel):
    scope: FileManagerScope
    label: str
    description: str = ""
    root_path: str = ""
    available: bool = True
    detail: str = ""


class FileManagerRootsResponse(BaseModel):
    project_id: str
    project_name: str = ""
    roots: List[FileManagerRootItem]


class FileManagerListResponse(BaseModel):
    scope: FileManagerScope
    root_path: str = ""
    current_path: str = ""
    available: bool = True
    detail: str = ""
    items: List[FileInfo]


class FileManagerContentResponse(BaseModel):
    scope: FileManagerScope
    root_path: str = ""
    path: str
    content: str
    encoding: str = "utf-8"
    size: int = 0


class FileManagerWriteRequest(BaseModel):
    project_id: str
    scope: FileManagerScope
    path: str
    content: str = ""
    encoding: str = "utf-8"


class FileManagerCreateRequest(BaseModel):
    project_id: str
    scope: FileManagerScope
    path: str = ""
    name: str
    is_dir: bool


class FileManagerDeleteRequest(BaseModel):
    project_id: str
    scope: FileManagerScope
    path: str
