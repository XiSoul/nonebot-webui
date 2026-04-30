import os
from pathlib import Path
from subprocess import check_output
from importlib.metadata import PackageNotFoundError, version

_DOCKER_VERSION_FILE = Path("/usr/local/share/nb-cli-plugin-webui/version")


def __get_git_revision(path: Path):
    git_path = path / ".git"
    if not git_path.exists():
        return None
    try:
        revision = check_output(["git", "rev-parse", "HEAD"], cwd=path, env=os.environ)
    except Exception:
        return None
    return revision.decode("utf-8").strip()


def get_revision():
    package_dir = Path(__file__)
    if package_dir.exists():
        return __get_git_revision(package_dir.parent.parent.absolute())


def get_docker_version():
    docker_version = str(os.getenv("WEBUI_VERSION", "")).strip()
    if docker_version:
        return docker_version

    if _DOCKER_VERSION_FILE.is_file():
        file_version = _DOCKER_VERSION_FILE.read_text(encoding="utf-8").strip()
        if file_version:
            return file_version

    # Backward compatibility for old images that wrote the version directly into WEBUI_BUILD.
    legacy_value = str(os.getenv("WEBUI_BUILD", "")).strip()
    if legacy_value and legacy_value not in {"1", "true", "docker"}:
        return legacy_value


def get_version():
    docker_version = get_docker_version()
    if docker_version:
        return docker_version

    if __build__:
        return f"{__version__}+g{__build__[:7]}"
    return __version__

try:
    __version__ = version("nb_cli_plugin_webui")
except PackageNotFoundError:
    # Fallback for source checkout/dev mode before the package is installed.
    __version__ = "0.0.0"
__build__ = get_revision()
