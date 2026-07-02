import unittest

from src.utils import find_max_version


class TestVersionHelpers(unittest.TestCase):
    def test_find_max_version_extracts_numbers_from_prefixed_folder_names(self):
        versions = [
            "【DreamCity】生存服26.2",
            "【DreamCity】生存服1.21.11",
        ]

        self.assertEqual(find_max_version(versions), "【DreamCity】生存服26.2")

    def test_find_max_version_keeps_plain_dotted_version_behavior(self):
        versions = ["1.20.1", "1.21.4", "1.21.11"]

        self.assertEqual(find_max_version(versions), "1.21.11")
