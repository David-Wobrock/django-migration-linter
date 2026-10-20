from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from django.conf import settings
from django.db import ProgrammingError

from django_migration_linter import MigrationLinter
from django_migration_linter.cache import Cache


class CacheOptionsTestCase(unittest.TestCase):
    def setUp(self):
        self.cache_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.cache_directory.cleanup)
        self.project_path = os.path.dirname(settings.BASE_DIR)

    def lint(self, app, name, **options):
        linter = MigrationLinter(
            self.project_path,
            cache_path=self.cache_directory.name,
            no_output=True,
            **options,
        )
        migration = linter.migration_loader.get_migration(app, name)
        linter.lint_migration(migration)
        linter.new_cache.save()
        return linter

    def test_excluded_checks_are_recomputed(self):
        app, name = "app_drop_table", "0002_delete_a"
        self.assertTrue(self.lint(app, name).has_errors)
        self.assertFalse(
            self.lint(app, name, exclude_migration_tests=["DROP_TABLE"]).has_errors
        )
        self.assertTrue(self.lint(app, name).has_errors)

        # Unchanged options still avoid generating SQL on the following run.
        with patch.object(MigrationLinter, "get_sql") as get_sql:
            self.assertTrue(self.lint(app, name).has_errors)
        get_sql.assert_not_called()

    def test_warning_options_are_recomputed(self):
        app, name = "app_data_migrations", "0002_missing_reverse"
        self.assertEqual(1, self.lint(app, name).nb_warnings)
        self.assertTrue(
            self.lint(
                app, name, warnings_as_errors_tests=["RUNPYTHON_REVERSIBLE"]
            ).has_errors
        )
        self.assertEqual(1, self.lint(app, name).nb_warnings)
        self.assertTrue(self.lint(app, name, all_warnings_as_errors=True).has_errors)
        self.assertEqual(
            1,
            self.lint(
                app, name, exclude_migration_tests=["RUNPYTHON_REVERSIBLE"]
            ).nb_valid,
        )

    def test_sqlmigrate_error_option_is_recomputed(self):
        with patch.object(MigrationLinter, "get_sql", side_effect=ProgrammingError):
            app, name = "app_drop_table", "0002_delete_a"
            self.assertTrue(self.lint(app, name).has_errors)
            ignored = self.lint(app, name, ignore_sqlmigrate_errors=True)
        self.assertFalse(ignored.has_errors)
        self.assertEqual(1, ignored.nb_ignored)

    def test_cache_without_option_metadata_is_not_reused(self):
        app, name = "app_drop_table", "0002_delete_a"
        cache = Cache(self.project_path, "default", self.cache_directory.name)
        cache[MigrationLinter.get_migration_hash(app, name)] = {"result": "OK"}
        cache.save()
        self.assertTrue(self.lint(app, name).has_errors)

    def test_equivalent_option_orders_reuse_cache(self):
        app, name = "app_drop_table", "0002_delete_a"
        self.lint(app, name, exclude_migration_tests=["DROP_TABLE", "DROP_COLUMN"])
        with patch.object(MigrationLinter, "get_sql") as get_sql:
            result = self.lint(
                app, name, exclude_migration_tests=["DROP_COLUMN", "DROP_TABLE"]
            )
        self.assertFalse(result.has_errors)
        get_sql.assert_not_called()
