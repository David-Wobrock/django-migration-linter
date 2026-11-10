from __future__ import annotations

import os
import tempfile
import unittest

from django_migration_linter.cache import Cache


class CacheCorruptFileTestCase(unittest.TestCase):
    def test_load_corrupt_cache_file_starts_empty(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            cache = Cache("test_folder", "default", cache_dir)
            with open(cache.filename, "wb") as f:
                f.write(b"\x80Xthis-is-not-a-valid-pickle-payload")
            fresh = Cache("test_folder", "default", cache_dir)
            fresh.load()
            self.assertEqual(len(fresh), 0)

    def test_load_empty_cache_file_starts_empty(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            cache = Cache("test_folder", "default", cache_dir)
            with open(cache.filename, "wb") as f:
                f.write(b"")
            fresh = Cache("test_folder", "default", cache_dir)
            fresh.load()
            self.assertEqual(len(fresh), 0)

    def test_load_missing_cache_file_starts_empty(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            cache = Cache("test_folder", "default", cache_dir)
            if os.path.exists(cache.filename):
                os.remove(cache.filename)
            cache.load()
            self.assertEqual(len(cache), 0)
