import os
import shutil
import fnmatch
import logging
import re
from PyQt6.QtCore import QThread, pyqtSignal


class MigrationWorker(QThread):
    progress_update = pyqtSignal(int, str)  # progress %, message
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, from_path, to_path, migration_rule_file):
        super().__init__()
        self.from_path = from_path
        self.to_path = to_path
        self.migration_rule_file = migration_rule_file
        self.logger = logging.getLogger()
        self.is_running = True

        # Placeholder context for rule patterns.
        self._placeholder_context = self._build_placeholder_context()


    # Placeholders for Rules in data_migration_rules.conf
    # If more needed, add here
    def _build_placeholder_context(self):
        old_version_name = os.path.basename(os.path.normpath(self.from_path)) if self.from_path else ""
        new_version_name = os.path.basename(os.path.normpath(self.to_path)) if self.to_path else ""

        return {
            # NOTE: folder name is treated as the "version name" (e.g. 1.21.11).
            "OLD_VERSION_NAME": old_version_name,
            "NEW_VERSION_NAME": new_version_name,

            "OLD_VERSION_PATH": self.from_path or "",
            "NEW_VERSION_PATH": self.to_path or "",
        }

    _PLACEHOLDER_RE = re.compile(r"\$\{([^}]+)\}")

    def _expand_placeholders(self, text: str) -> str:
        """Expand ${NAME} placeholders in rule patterns.

        Unknown placeholders are left unchanged.
        """

        def repl(match: re.Match) -> str:
            key = match.group(1)
            if key in self._placeholder_context:
                return str(self._placeholder_context[key])
            return match.group(0)

        return self._PLACEHOLDER_RE.sub(repl, text)


    def run(self):
        try:
            self.logger.info(f"Starting migration from [{self.from_path}] to [{self.to_path}]")

            if not os.path.exists(self.from_path):
                raise FileNotFoundError(f"Source path does not exist: {self.from_path}")

            # 1. Parse Rules
            rules = self.parse_rules(self.migration_rule_file)
            self.logger.info(f"Loaded {len(rules)} rules.")

            # 2. Scan Files
            # AI写的答辩。应该写成构建目录树然后按规则剪枝
            # 懒：能跑就不要动
            self.progress_update.emit(0, "正在扫描文件...")
            files_to_copy = self.scan_files(self.from_path, rules)
            total_files = len(files_to_copy)
            self.logger.info(f"Found {total_files} files to migrate.")

            if total_files == 0:
                self.finished.emit(True, "没有发现需要迁移的文件。")
                return

            # 3. Copy Files
            copied_count = 0
            for rel_path in files_to_copy:
                if not self.is_running:
                    break

                src_file = os.path.join(self.from_path, rel_path)
                dst_file = os.path.join(self.to_path, rel_path)

                try:
                    # Ensure destination directory exists
                    os.makedirs(os.path.dirname(dst_file), exist_ok=True)

                    # Copy file (overwrite)
                    shutil.copy2(src_file, dst_file)
                    self.logger.info(f"Copied: {rel_path}")
                except Exception as e:
                    self.logger.error(f"Failed to copy {rel_path}: {e}")

                copied_count += 1
                progress = int((copied_count / total_files) * 100)
                self.progress_update.emit(progress, f"正在迁移: {rel_path}")

            self.finished.emit(True, "数据迁移成功！")

        except Exception as e:
            self.logger.error(f"Migration failed: {e}", exc_info=True)
            self.finished.emit(False, f"迁移失败: {str(e)}")

    def stop(self):
        self.is_running = False

    def parse_rules(self, config_path):
        """Parse the config file.

        Returns a list of tuples: (pattern, is_exclude)
        """
        rules = []
        if not os.path.exists(config_path):
            self.logger.warning("Config file not found, using default empty rules.")
            return rules

        # Use utf-8-sig to gracefully handle UTF-8 BOM
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                # Support full-line comments (allow leading whitespace)
                if not line.strip() or line.lstrip().startswith('#'):
                    continue

                # Support end-of-line comments: treat '#'
                for i, ch in enumerate(line):
                    if ch == '#' and i > 0 and line[i - 1].isspace():
                        line = line[: i - 1]
                        break

                line = line.strip()
                if not line:
                    continue

                is_exclude = False
                if line.startswith('!'):
                    is_exclude = True
                    pattern = line[1:]
                else:
                    pattern = line

                pattern = self._expand_placeholders(pattern)

                # Normalize slashes
                pattern = pattern.replace('\\', '/')
                rules.append((pattern, is_exclude))
        return rules

    def scan_files(self, root_dir, rules):
        """Scan directory and apply rules to determine which files to copy.

        Returns a list of relative paths.
        """
        files_to_copy = []

        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Calculate relative path from root
            rel_dir = os.path.relpath(dirpath, root_dir)
            if rel_dir == '.':
                rel_dir = ''

            # Normalize slashes for consistent matching
            rel_dir = rel_dir.replace('\\', '/')

            for filename in filenames:
                rel_file_path = os.path.join(rel_dir, filename).replace('\\', '/')

                if self.should_copy(rel_file_path, rules):
                    files_to_copy.append(rel_file_path)

        return files_to_copy

    def should_copy(self, rel_path, rules):
        """Determine if a file should be copied based on rules.

        Default is NOT to copy (unless matched by an include rule).
        Bottom rules override top rules.
        """
        decision = False  # Default: Do not copy

        for pattern, is_exclude in rules:
            # Check if pattern matches
            # We need to handle directory matching logic from user request:
            # "saves/" means "saves" dir and everything inside.

            match = False

            if pattern.endswith('/'):
                # Directory match with potential wildcards
                # e.g. "saves/" or "*IAS*/"
                clean_pattern = pattern.rstrip('/')

                # Check if the file itself IS the directory (unlikely in walk, but possible)
                # OR if the file is INSIDE the directory
                # We use fnmatch to support wildcards in the directory name

                # Case 1: Exact match (or wildcard match) of the directory name
                # e.g. rel_path="saves", pattern="saves"
                if fnmatch.fnmatch(rel_path, clean_pattern):
                    match = True

                # Case 2: Inside the directory
                # e.g. rel_path="saves/level.dat", pattern="saves/*"
                # e.g. rel_path="AutoIAS/config.txt", pattern="*IAS*/*"
                elif fnmatch.fnmatch(rel_path, clean_pattern + '/*'):
                    match = True
            else:
                # File match
                if fnmatch.fnmatch(rel_path, pattern):
                    match = True

            if match:
                if is_exclude:
                    decision = False
                else:
                    decision = True

        return decision
