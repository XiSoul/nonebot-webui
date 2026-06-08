import os
from pathlib import Path
from typing import Callable, Iterable, Optional
from typing_extensions import ParamSpec

from nb_cli.handlers.data import DATA_DIR, CACHE_DIR, CONFIG_DIR

P = ParamSpec("P")

APP_NAME = "nb-cli-plugin-webui"
BASE_CACHE_DIR = (CACHE_DIR / APP_NAME).resolve()
BASE_DATA_DIR = (DATA_DIR / APP_NAME).resolve()
BASE_CONFIG_DIR = (CONFIG_DIR / APP_NAME).resolve()
DEFAULT_DOCKER_DATA_DIR = Path("/data")
LEGACY_DOCKER_APP_DIR = Path(os.getenv("WEBUI_LEGACY_APP_DIR", "/app"))

if "WEBUI_BUILD" in os.environ:
    data_dir = Path(os.getenv("WEBUI_DATA_DIR", str(DEFAULT_DOCKER_DATA_DIR))).expanduser()
    config_dir = Path(os.getenv("WEBUI_CONFIG_DIR", str(data_dir))).expanduser()
    cache_dir = Path(os.getenv("WEBUI_CACHE_DIR", str(data_dir))).expanduser()
    BASE_CACHE_DIR = cache_dir.resolve()
    BASE_DATA_DIR = data_dir.resolve()
    BASE_CONFIG_DIR = config_dir.resolve()


def _ensure_dir(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    elif not path.is_dir():
        raise RuntimeError(f"{path} is not a directory")


def _auto_create_dir(func: Callable[P, Path]) -> Callable[P, Path]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Path:
        path = func(*args, **kwargs)
        _ensure_dir(path)
        return path

    return wrapper


def _candidate_legacy_files(filename: str, legacy_dirs: Iterable[Path]) -> Iterable[Path]:
    for directory in legacy_dirs:
        yield directory / filename


def migrate_legacy_runtime_file(
    filename: str,
    destination: Path,
    *,
    legacy_dirs: Optional[Iterable[Path]] = None,
) -> Optional[Path]:
    """Copy a Docker runtime file from legacy image-local paths into /data.

    Older container instructions persisted /app/config.json and /app/project.json.
    New Docker defaults write all mutable runtime state to /data.  When users
    upgrade or change mounts, preserve existing credentials/registry by copying
    the old file into /data only if the new destination does not already exist.
    """
    if "WEBUI_BUILD" not in os.environ or destination.exists():
        return None

    search_dirs = list(legacy_dirs or (LEGACY_DOCKER_APP_DIR,))
    for legacy_file in _candidate_legacy_files(filename, search_dirs):
        try:
            legacy_file = legacy_file.resolve()
            destination_resolved = destination.resolve()
        except OSError:
            continue
        if legacy_file == destination_resolved or not legacy_file.is_file():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(legacy_file.read_bytes())
        return legacy_file

    return None


@_auto_create_dir
def get_cache_dir() -> Path:
    return BASE_CACHE_DIR


def get_cache_file(filename: str) -> Path:
    return get_cache_dir() / filename


@_auto_create_dir
def get_data_dir() -> Path:
    return BASE_DATA_DIR


def get_data_file(filename: str) -> Path:
    return get_data_dir() / filename


@_auto_create_dir
def get_config_dir() -> Path:
    return BASE_CONFIG_DIR


def get_config_file(filename: str) -> Path:
    return get_config_dir() / filename
