import logging
import os
import sys
from src.constants import LOG_FILE_NAME


def get_resource_path(*parts: str) -> str:
    """Return absolute path to a bundled resource.

    Works for both source runs and PyInstaller (onefile/onedir) builds.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = getattr(sys, '_MEIPASS')
    else:
        # utils.py lives in src/, project root is one level up
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    return os.path.join(base_path, *parts)


def get_dependence_path(file_name: str) -> str:
    """Resolve a dependency file path.

    Search order:
    1) Current working directory
    2) Next to the executable (PyInstaller)
    3) Bundled internal path (PyInstaller)

    If none exist, return the cwd path (so callers can still pass it through
    and let downstream code decide how to handle a missing file).
    """

    cwd_path = os.path.join(os.getcwd(), file_name)
    if os.path.exists(cwd_path):
        return cwd_path

    if getattr(sys, 'frozen', False):
        exe_dir_path = os.path.join(os.path.dirname(sys.executable), file_name)
        if os.path.exists(exe_dir_path):
            return exe_dir_path

        internal_path = get_resource_path(file_name)
        if os.path.exists(internal_path):
            return internal_path

    return cwd_path


def get_versions(base_path):
    """Get list of version folders in .minecraft/versions."""
    versions_path = os.path.join(base_path, '.minecraft', 'versions')
    if not os.path.exists(versions_path):
        return []

    versions = []
    for item in os.listdir(versions_path):
        full_path = os.path.join(versions_path, item)
        if os.path.isdir(full_path):
            versions.append(item)
    return sorted(versions)


def find_max_version(versions):
    """Find the 'largest' version string.

    Simple heuristic: split by dots, compare integers.
    """
    if not versions:
        return None

    def version_key(v):
        # Extract numbers from string, e.g. "1.21.11" -> [1, 21, 11]
        # Handle non-numeric parts gracefully
        parts = []
        for part in v.replace('-', '.').split('.'):
            if part.isdigit():
                parts.append(int(part))
            else:
                parts.append(0)
        return parts

    return max(versions, key=version_key)


def setup_logging(target_version_path: str):
    """配置日志系统。

    日志输出到目标版本目录下的 logs 文件夹：
    `.minecraft\\versions\\<目标版本>\\logs\\{LOG_FILE_NAME}`

    之所以延迟初始化，是因为在用户尚未选择目标版本并开始迁移之前，
    该 logs 目录并不存在（也不应该生成/写入日志）。
    """

    if not target_version_path:
        raise ValueError("target_version_path is required")

    logs_dir = os.path.join(target_version_path, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, LOG_FILE_NAME)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Reset handlers to avoid duplicate logs across multiple migrations.
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(file_handler)

    # Ensure uncaught exceptions are written once logging is initialized.
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception

    root_logger.info("=" * 50)
    root_logger.info("DC Data Migration Tool Started")
    root_logger.info("Log file: %s", log_file)
    root_logger.info("=" * 50)


def setup_null_logging():
    """在用户开始迁移前禁用日志输出。

    目标：在没有日志目录（目标版本 logs）之前，不写文件、也不输出到控制台。
    """
    root_logger = logging.getLogger()
    # Reset handlers to avoid inheriting environment defaults.
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
    root_logger.addHandler(logging.NullHandler())


def get_logger():
    return logging.getLogger()
