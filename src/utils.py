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

def setup_logging():
    """
    配置日志系统，输出到文件，不输出到控制台
    """
    log_file = LOG_FILE_NAME
    
    # 如果日志文件存在，先清空（可选，或者追加）
    # 这里选择追加模式，但为了每次运行清晰，也可以做分割。
    # 简单起见，使用追加模式。
    
    logging.basicConfig(
        filename=log_file,
        filemode='a',
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        encoding='utf-8'
    )
    
    # 确保未捕获的异常也能记录到日志
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
    
    logging.info("="*50)
    logging.info("DC Data Migration Tool Started")
    logging.info("="*50)

def get_logger():
    return logging.getLogger()
