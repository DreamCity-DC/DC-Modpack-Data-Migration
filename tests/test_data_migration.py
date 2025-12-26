import os
import unittest
import tempfile
from pathlib import Path

try:
    from PyQt6.QtCore import QCoreApplication
except Exception:  # pragma: no cover
    QCoreApplication = None

from src.data_migration import MigrationWorker


class TestMigrationWorkerRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure a Qt application exists so signal connections/emits are stable.
        if QCoreApplication is not None and QCoreApplication.instance() is None:
            cls._qt_app = QCoreApplication([])
        else:
            cls._qt_app = None

    def test_parse_rules_supports_comments_bom_inline_and_exclude(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "rules.conf"
            # Include UTF-8 BOM and various comment styles.
            content = (
                "\ufeff# full line comment\n"
                "   # comment with leading whitespace\n"
                "\n"
                "saves/  # copy saves dir\n"
                "!saves/backup/  # exclude backup\n"
                "config\\options.txt\n"
                "!mods/*.jar\n"
            )
            cfg.write_text(content, encoding="utf-8")

            worker = MigrationWorker("from", "to", str(cfg))
            rules = worker.parse_rules(str(cfg))

            self.assertEqual(
                rules,
                [
                    ("saves/", False),
                    ("saves/backup/", True),
                    ("config/options.txt", False),
                    ("mods/*.jar", True),
                ],
            )

    def test_parse_rules_expands_placeholders_old_new_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "rules.conf"
            cfg.write_text(
                "logs/${OLD_VERION_NAME}.log\n"
                "logs/${OLD_VERSION_NAME}.log\n"
                "logs/${NEW_VERSION_NAME}.log\n"
                "keep/${UNKNOWN_PLACEHOLDER}.txt\n",
                encoding="utf-8",
            )

            worker = MigrationWorker(
                "C:/Game/.minecraft/versions/1.20.1",
                "C:/Game/.minecraft/versions/1.21.4",
                str(cfg),
            )
            rules = worker.parse_rules(str(cfg))

            self.assertEqual(
                rules,
                [
                    ("logs/${OLD_VERION_NAME}.log", False),
                    ("logs/1.20.1.log", False),
                    ("logs/1.21.4.log", False),
                    ("keep/${UNKNOWN_PLACEHOLDER}.txt", False),
                ],
            )

    def test_should_copy_default_false_and_bottom_rules_override(self):
        worker = MigrationWorker("from", "to", "cfg")

        rules = [("saves/", False)]
        self.assertTrue(worker.should_copy("saves/level.dat", rules))
        self.assertFalse(worker.should_copy("mods/a.jar", rules))

        # Exclude overrides include when later in file.
        rules = [("saves/", False), ("saves/secret.txt", True)]
        self.assertTrue(worker.should_copy("saves/level.dat", rules))
        self.assertFalse(worker.should_copy("saves/secret.txt", rules))

        # Include overrides exclude when later in file.
        rules = [("saves/", True), ("saves/", False)]
        self.assertTrue(worker.should_copy("saves/level.dat", rules))

    def test_should_copy_directory_patterns_with_wildcards(self):
        worker = MigrationWorker("from", "to", "cfg")

        rules = [("*IAS*/", False)]
        self.assertTrue(worker.should_copy("AutoIAS/config.txt", rules))
        self.assertTrue(worker.should_copy("MyIASStuff/sub/a.txt", rules))
        self.assertFalse(worker.should_copy("Other/mods.txt", rules))


class TestMigrationWorkerScanAndRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if QCoreApplication is not None and QCoreApplication.instance() is None:
            cls._qt_app = QCoreApplication([])
        else:
            cls._qt_app = None

    def test_scan_files_applies_rules_and_returns_relative_posix_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "saves").mkdir()
            (root / "mods").mkdir()

            (root / "saves" / "level.dat").write_text("ok", encoding="utf-8")
            (root / "mods" / "a.jar").write_text("jar", encoding="utf-8")

            worker = MigrationWorker(str(root), "to", "cfg")
            rules = [("saves/", False), ("mods/", True)]
            files = worker.scan_files(str(root), rules)

            self.assertEqual(sorted(files), ["saves/level.dat"])

    def test_run_copies_only_included_files_and_emits_finished_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src = base / "src"
            dst = base / "dst"
            src.mkdir()
            dst.mkdir()

            (src / "saves").mkdir()
            (src / "mods").mkdir()
            (src / "saves" / "level.dat").write_text("LEVEL", encoding="utf-8")
            (src / "mods" / "a.jar").write_text("JAR", encoding="utf-8")

            cfg = base / "rules.conf"
            cfg.write_text("saves/\n!mods/\n", encoding="utf-8")

            worker = MigrationWorker(str(src), str(dst), str(cfg))
            finished_events = []
            progress_events = []

            worker.finished.connect(lambda ok, msg: finished_events.append((ok, msg)))
            worker.progress_update.connect(lambda p, msg: progress_events.append((p, msg)))

            # Run synchronously (avoid multi-thread timing in unit tests)
            worker.run()

            self.assertTrue((dst / "saves" / "level.dat").exists())
            self.assertFalse((dst / "mods" / "a.jar").exists())
            self.assertEqual((dst / "saves" / "level.dat").read_text(encoding="utf-8"), "LEVEL")

            self.assertTrue(finished_events, "finished signal should be emitted")
            self.assertEqual(finished_events[-1][0], True)
            self.assertIn("成功", finished_events[-1][1])
            self.assertTrue(any(msg.startswith("正在扫描") for _, msg in progress_events))

    def test_run_missing_source_emits_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            missing_src = base / "missing"
            dst = base / "dst"
            dst.mkdir()
            cfg = base / "rules.conf"
            cfg.write_text("saves/\n", encoding="utf-8")

            worker = MigrationWorker(str(missing_src), str(dst), str(cfg))
            finished_events = []
            worker.finished.connect(lambda ok, msg: finished_events.append((ok, msg)))

            worker.run()

            self.assertTrue(finished_events)
            ok, msg = finished_events[-1]
            self.assertFalse(ok)
            self.assertIn("Source path does not exist", msg)
