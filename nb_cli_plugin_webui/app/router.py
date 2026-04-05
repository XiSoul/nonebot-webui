from fastapi import APIRouter

from .auth.router import router as auth_router
from .file.router import router as file_router
from .store.router import router as store_router
from .status.router import router as status_router
from .process.router import router as process_router
from .project.router import router as project_router
from .system.router import router as system_router

router = APIRouter()


router.include_router(auth_router, prefix="/auth")
router.include_router(file_router, prefix="/file")
router.include_router(store_router, prefix="/store")
router.include_router(status_router, prefix="/status")
router.include_router(process_router, prefix="/process")
router.include_router(project_router, prefix="/project")
router.include_router(system_router, prefix="/system")
