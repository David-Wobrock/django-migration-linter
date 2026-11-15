from __future__ import annotations

import os
import unittest
import unittest.mock as mock

from django.conf import settings
from django.db.migrations import Migration, RunPython

from django_migration_linter import (
    IgnoreMigration,
    Issue,
    MigrationLinter,
    analyse_sql_statements,
    get_migration_abspath,
)


class OperationsIgnoreMigration(Migration):
    operations = [IgnoreMigration()]


class CacheTestCase(unittest.TestCase):
    def setUp(self):
        self.test_project_path = os.path.dirname(settings.BASE_DIR)

    @mock.patch(
        "django_migration_linter.MigrationLinter._gather_all_migrations",
        return_value=[
            Migration("0001_create_table", "app_add_not_null_column"),
            Migration("0002_add_new_not_null_field", "app_add_not_null_column"),
        ],
    )
    def test_cache_normal(self, *args):
        linter = MigrationLinter(self.test_project_path, database="mysql")
        linter.old_cache.clear()
        linter.old_cache.save()

        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter.lint_all_migrations()
            self.assertEqual(2, analyse_sql_statements_mock.call_count)

        cache = linter.new_cache
        cache.load()

        self.assertEqual("OK", cache["eb6832d34f7ad40903a51a8b053ac13c"]["result"])
        self.assertEqual("ERR", cache["31fa92230495861937bd6fd35b63c4e7"]["result"])
        self.assertListEqual(
            [
                Issue(
                    code="NOT_NULL",
                    message="NOT NULL constraint on columns",
                ),
            ],
            cache["31fa92230495861937bd6fd35b63c4e7"]["errors"],
        )

        # Start the Linter again -> should use cache now.
        linter = MigrationLinter(self.test_project_path, database="mysql")

        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter.lint_all_migrations()
            analyse_sql_statements_mock.assert_not_called()

        self.assertTrue(linter.has_errors)

    @mock.patch(
        "django_migration_linter.MigrationLinter._gather_all_migrations",
        return_value=[
            Migration("0001_create_table", "app_add_not_null_column"),
            Migration("0002_add_new_not_null_field", "app_add_not_null_column"),
        ],
    )
    def test_cache_different_databases(self, *args):
        linter = MigrationLinter(self.test_project_path, database="mysql")
        linter.old_cache.clear()
        linter.old_cache.save()

        linter = MigrationLinter(self.test_project_path, database="sqlite")
        linter.old_cache.clear()
        linter.old_cache.save()

        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter.lint_all_migrations()
            self.assertEqual(2, analyse_sql_statements_mock.call_count)

        cache = linter.new_cache
        cache.load()

        self.assertEqual("OK", cache["eb6832d34f7ad40903a51a8b053ac13c"]["result"])
        self.assertEqual("ERR", cache["31fa92230495861937bd6fd35b63c4e7"]["result"])
        self.assertListEqual(
            [
                Issue(
                    code="NOT_NULL",
                    message="NOT NULL constraint on columns",
                ),
            ],
            cache["31fa92230495861937bd6fd35b63c4e7"]["errors"],
        )

        # Start the Linter again but with different database, should not be the same cache
        linter = MigrationLinter(self.test_project_path, database="mysql")

        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter.lint_all_migrations()
            self.assertEqual(2, analyse_sql_statements_mock.call_count)

        cache = linter.new_cache
        cache.load()

        self.assertEqual("OK", cache["eb6832d34f7ad40903a51a8b053ac13c"]["result"])
        self.assertEqual("ERR", cache["31fa92230495861937bd6fd35b63c4e7"]["result"])
        self.assertListEqual(
            [
                Issue(
                    code="NOT_NULL",
                    message="NOT NULL constraint on columns",
                ),
            ],
            cache["31fa92230495861937bd6fd35b63c4e7"]["errors"],
        )

        self.assertTrue(linter.has_errors)

    @mock.patch(
        "django_migration_linter.MigrationLinter._gather_all_migrations",
        return_value=[
            Migration("0001_initial", "app_ignore_migration"),
            OperationsIgnoreMigration("0002_ignore_migration", "app_ignore_migration"),
        ],
    )
    def test_cache_ignored(self, *args):
        linter = MigrationLinter(self.test_project_path, ignore_name_contains="0001")
        linter.old_cache.clear()
        linter.old_cache.save()

        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter.lint_all_migrations()
            analyse_sql_statements_mock.assert_not_called()

        cache = linter.new_cache
        cache.load()

        self.assertFalse(cache)

    @mock.patch(
        "django_migration_linter.MigrationLinter._gather_all_migrations",
        return_value=[
            Migration("0002_add_new_not_null_field", "app_add_not_null_column")
        ],
    )
    def test_cache_modified(self, *args):
        linter = MigrationLinter(self.test_project_path, database="mysql")
        linter.old_cache.clear()
        linter.old_cache.save()

        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter.lint_all_migrations()
            self.assertEqual(1, analyse_sql_statements_mock.call_count)

        cache = linter.new_cache
        cache.load()

        self.assertEqual("ERR", cache["31fa92230495861937bd6fd35b63c4e7"]["result"])

        # Get the content of the migration file and mock the open call to append
        # some content to change the hash
        migration_path = get_migration_abspath(
            "app_add_not_null_column", "0002_add_new_not_null_field"
        )
        with open(migration_path, "rb") as f:
            file_content = f.read()
        file_content += b"# test comment"

        linter = MigrationLinter(self.test_project_path)
        with mock.patch(
            "django_migration_linter.migration_linter.open",
            mock.mock_open(read_data=file_content),
        ):
            with mock.patch(
                "django_migration_linter.migration_linter.analyse_sql_statements",
                wraps=analyse_sql_statements,
            ) as analyse_sql_statements_mock:
                linter.lint_all_migrations()
                self.assertEqual(1, analyse_sql_statements_mock.call_count)

        cache = linter.new_cache
        cache.load()

        self.assertNotIn("31fa92230495861937bd6fd35b63c4e7", cache)
        self.assertEqual(1, len(cache))
        self.assertEqual("ERR", cache["864f9dc59e9dccd57ef6fa45143f1ef0"]["result"])

    @mock.patch(
        "django_migration_linter.MigrationLinter._gather_all_migrations",
        return_value=[
            Migration("0001_create_table", "app_add_not_null_column"),
            Migration("0002_add_new_not_null_field", "app_add_not_null_column"),
        ],
    )
    def test_ignore_cached_migration(self, *args):
        linter = MigrationLinter(self.test_project_path, database="mysql")
        linter.old_cache.clear()
        linter.old_cache.save()

        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter.lint_all_migrations()
            self.assertEqual(2, analyse_sql_statements_mock.call_count)

        cache = linter.new_cache
        cache.load()

        self.assertEqual("OK", cache["eb6832d34f7ad40903a51a8b053ac13c"]["result"])
        self.assertEqual("ERR", cache["31fa92230495861937bd6fd35b63c4e7"]["result"])
        self.assertListEqual(
            [
                Issue(
                    code="NOT_NULL",
                    message="NOT NULL constraint on columns",
                ),
            ],
            cache["31fa92230495861937bd6fd35b63c4e7"]["errors"],
        )

        # Start the Linter again -> should use cache now but ignore the erroneous
        linter = MigrationLinter(
            self.test_project_path,
            ignore_name_contains="0002_add_new_not_null_field",
            database="mysql",
        )

        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter.lint_all_migrations()
            analyse_sql_statements_mock.assert_not_called()

        self.assertFalse(linter.has_errors)

        cache = linter.new_cache
        cache.load()
        self.assertEqual(1, len(cache))
        self.assertEqual("OK", cache["eb6832d34f7ad40903a51a8b053ac13c"]["result"])

    @mock.patch(
        "django_migration_linter.MigrationLinter._gather_all_migrations",
        return_value=[
            Migration("0001_initial", "app_data_migrations"),
            Migration("0002_missing_reverse", "app_data_migrations"),
        ],
    )
    def test_cache_takes_options_into_account(self, _gather_all_migrations):
        # Faking the 'operations', since the migration file is not read from disk here.
        _gather_all_migrations.return_value[1].operations = [
            RunPython(lambda apps, schema_editor: None),
        ]

        # Create test linters.
        linter_1 = MigrationLinter(self.test_project_path, database="sqlite")
        linter_1.old_cache.clear()
        linter_1.old_cache.save()
        # Start the Linter again, but with an option. The result should not be cached.
        linter_2 = MigrationLinter(
            self.test_project_path,
            database="sqlite",
            warnings_as_errors_tests=["RUNPYTHON_REVERSIBLE"],
        )
        linter_2.old_cache.clear()
        linter_2.old_cache.save()

        # 1 - Not cached.
        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter_1.lint_all_migrations()
            self.assertEqual(2, analyse_sql_statements_mock.call_count)

        cache = linter_1.new_cache
        cache.load()

        self.assertEqual("OK", cache["42ac7f74f6168dbc40b3cb2328d574e3"]["result"])
        self.assertEqual("WARNING", cache["911a42e9584ab70c55ea2875122c37de"]["result"])
        self.assertListEqual(
            [
                Issue(
                    code="RUNPYTHON_REVERSIBLE",
                    message=mock.ANY,
                ),
            ],
            cache["911a42e9584ab70c55ea2875122c37de"]["warnings"],
        )

        self.assertGreater(linter_1.nb_warnings, 0)
        self.assertFalse(linter_1.has_errors)

        # 2 - Not cached.
        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter_2.lint_all_migrations()
            self.assertEqual(2, analyse_sql_statements_mock.call_count)

        self.assertEqual(linter_2.nb_warnings, 0)
        self.assertTrue(linter_2.has_errors)

        # Same as first linter object.
        linter_3 = MigrationLinter(self.test_project_path, database="sqlite")

        # 3 - Cached, because same as 1.
        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter_3.lint_all_migrations()
            analyse_sql_statements_mock.assert_not_called()

        self.assertGreater(linter_3.nb_warnings, 0)
        self.assertFalse(linter_3.has_errors)
