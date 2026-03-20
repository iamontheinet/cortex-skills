"""Comprehensive tests for replatform_scanner.

67+ tests across 8 groups + 5 new groups:
  A: ScannerService — Happy Path (5)
  B: ScannerService — Edge Cases (10)
  C: Validation Issue Detection (8)
  D: ValidatorService (5)
  D2: Profiles & TASK Syntax Validation (5)
  D3: Missing Profiles Severity (1)
  D4: Source Schema Mismatch Detection (5)
  D5: Orchestration Schema Prefix Detection (5)
  D6: Orchestration Warehouse Detection (4)
  D7: PROC_EXECUTE_DBT Detection (3)
  D8: PARTIAL_DATE_CAST Detection (3)
  E: Serialization Roundtrip (2)
  F: Regex Patterns (4)
  G: CLI Commands (3)
  H: Regression Tests — Bugs found during end-to-end testing (10)
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import make_dbt_project, make_etl_dir, make_orchestration_sql

from replatform_scanner.services import ScannerService, ValidatorService, load_inventory, save_inventory
from replatform_scanner.services.scanner_service import (
    AFTER_TASK_RE,
    CREATE_PROCEDURE_RE,
    CREATE_TASK_RE,
    EXECUTE_DBT_RE,
    PLACEHOLDER_RE,
    _strip_sql_comments,
)

# ───────────────────────────────────────────────────────────────
# Group A: ScannerService — Happy Path
# ───────────────────────────────────────────────────────────────


class TestScannerHappyPath:
    """Tests that cover the normal, fully-formed Replatform output."""

    def test_scan_full_replatform_output(self, tmp_path):
        """Full realistic fixture: etl_config + 1 package + 2 dbt projects + TASK orchestration."""
        root = make_etl_dir(tmp_path, tables=["control_variables"], functions=["fn_lookup"])

        pkg_dir = root / "MyPackage"
        pkg_dir.mkdir()

        make_dbt_project(
            pkg_dir, "DataFlow1",
            staging_models=["stg_orders", "stg_customers"],
            mart_models=["fct_orders"],
        )
        make_dbt_project(
            pkg_dir, "DataFlow2",
            staging_models=["stg_products"],
        )

        make_orchestration_sql(
            pkg_dir, "MyPackage",
            tasks=[
                {"name": "root_task"},
                {"name": "task_df1", "after": "root_task", "ref": "DataFlow1"},
                {"name": "task_df2", "after": "task_df1", "ref": "DataFlow2"},
            ],
        )

        scanner = ScannerService()
        inv = scanner.scan(str(root))

        assert len(inv.packages) == 1
        assert inv.packages[0].name == "MyPackage"
        assert len(inv.packages[0].dbt_projects) == 2
        assert inv.packages[0].orchestration_type == "TASK"
        assert len(inv.packages[0].task_names) == 3
        assert set(inv.packages[0].execute_dbt_project_refs) == {"DataFlow1", "DataFlow2"}
        assert len(inv.etl_config_components) == 2
        assert inv.total_dbt_projects == 2

    def test_scan_procedure_based_package(self, tmp_path):
        """Orchestration uses CREATE PROCEDURE, no TASKs."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "ProcPkg"
        pkg_dir.mkdir()

        make_dbt_project(pkg_dir, "DFlow", staging_models=["stg_a"])
        make_orchestration_sql(
            pkg_dir, "ProcPkg",
            procedures=["sp_run_all"],
            dbt_refs=["DFlow"],
        )

        inv = ScannerService().scan(str(root))
        assert inv.packages[0].orchestration_type == "PROCEDURE"

    def test_scan_multiple_packages(self, tmp_path):
        """Three package directories are discovered."""
        root = make_etl_dir(tmp_path, etl_config=False)

        for name in ["PkgA", "PkgB", "PkgC"]:
            d = root / name
            d.mkdir()
            make_dbt_project(d, f"df_{name}", staging_models=["stg_x"])
            make_orchestration_sql(
                d, name,
                tasks=[{"name": f"task_{name}"}],
                dbt_refs=[f"df_{name}"],
            )

        inv = ScannerService().scan(str(root))
        assert len(inv.packages) == 3
        pkg_names = {p.name for p in inv.packages}
        assert pkg_names == {"PkgA", "PkgB", "PkgC"}

    def test_scan_clean_project_no_errors(self, tmp_path):
        """A perfectly valid project should produce zero ERROR-level issues from scanning."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "CleanPkg"
        pkg_dir.mkdir()

        make_dbt_project(
            pkg_dir, "clean_flow",
            staging_models=["stg_a"],
            sources=True,
            profiles=True,
        )
        make_orchestration_sql(
            pkg_dir, "CleanPkg",
            tasks=[{"name": "root_task", "ref": "clean_flow"}],
        )

        inv = ScannerService().scan(str(root))
        errors = [i for i in inv.validation_issues if i.severity == "ERROR"]
        assert len(errors) == 0

    def test_scan_with_script_sql(self, tmp_path):
        """Package dir contains script.sql — has_script_sql should be True."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "ScriptPkg"
        pkg_dir.mkdir()

        make_dbt_project(pkg_dir, "df1", staging_models=["stg_a"])
        make_orchestration_sql(pkg_dir, "ScriptPkg", tasks=[{"name": "t1"}])
        (pkg_dir / "script.sql").write_text("-- migration script")

        inv = ScannerService().scan(str(root))
        assert inv.packages[0].has_script_sql is True


# ───────────────────────────────────────────────────────────────
# Group B: ScannerService — Edge Cases
# ───────────────────────────────────────────────────────────────


class TestScannerEdgeCases:

    def test_scan_nonexistent_directory(self):
        """Scanning a directory that doesn't exist raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ScannerService().scan("/nonexistent/path/xyz")

    def test_scan_empty_directory(self, tmp_path):
        """Empty dir: no etl_configuration, no packages — one WARNING, zero packages."""
        root = tmp_path / "empty"
        root.mkdir()

        inv = ScannerService().scan(str(root))
        assert len(inv.packages) == 0
        warnings = [i for i in inv.validation_issues if i.category == "MISSING_FILE"]
        assert any("etl_configuration" in w.problem for w in warnings)

    def test_scan_missing_etl_configuration(self, tmp_path):
        """Packages exist but no etl_configuration/ — warning issued."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "df1", staging_models=["stg_a"])
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        missing_config = [
            i for i in inv.validation_issues
            if "etl_configuration" in i.problem
        ]
        assert len(missing_config) == 1

    def test_scan_partial_etl_configuration(self, tmp_path):
        """Only tables/ exists, no functions/ or procedures/ — no crash."""
        root = make_etl_dir(tmp_path, tables=["tbl_a"])

        inv = ScannerService().scan(str(root))
        assert len(inv.etl_config_components) == 1
        assert inv.etl_config_components[0].category == "table"

    def test_scan_orchestration_case_insensitive(self, tmp_path):
        """Package 'MyPackage' with file 'mypackage.sql' (case mismatch) — found via fallback."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "MyPackage"
        pkg_dir.mkdir()

        make_dbt_project(pkg_dir, "df1", staging_models=["stg_a"])
        # Write the SQL file with lowercase name
        make_orchestration_sql(
            pkg_dir, "mypackage",
            tasks=[{"name": "root_task"}],
        )

        inv = ScannerService().scan(str(root))
        assert inv.packages[0].orchestration_file is not None
        assert inv.packages[0].orchestration_type == "TASK"

    def test_scan_no_orchestration_sql(self, tmp_path):
        """Package dir with dbt projects but no .sql file — WARNING, package still returned."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "NoOrch"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "df1", staging_models=["stg_a"])

        inv = ScannerService().scan(str(root))
        assert len(inv.packages) == 1
        assert inv.packages[0].orchestration_file is None
        missing_orch = [
            i for i in inv.validation_issues
            if "orchestration SQL" in i.problem
        ]
        assert len(missing_orch) == 1

    def test_scan_unknown_orchestration_type(self, tmp_path):
        """SQL file with neither CREATE TASK nor CREATE PROCEDURE — UNKNOWN type, WARNING."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "WeirdPkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "df1", staging_models=["stg_a"])
        make_orchestration_sql(
            pkg_dir, "WeirdPkg",
            raw_sql="-- Just a comment\nSELECT 1;\n",
        )

        inv = ScannerService().scan(str(root))
        assert inv.packages[0].orchestration_type == "UNKNOWN"
        unknown_warn = [
            i for i in inv.validation_issues
            if "orchestration type" in i.problem
        ]
        assert len(unknown_warn) == 1

    def test_scan_both_task_and_procedure(self, tmp_path):
        """SQL file with both CREATE TASK and CREATE PROCEDURE — TASK wins."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "BothPkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "df1", staging_models=["stg_a"])
        make_orchestration_sql(
            pkg_dir, "BothPkg",
            tasks=[{"name": "task1"}],
            procedures=["sp_helper"],
        )

        inv = ScannerService().scan(str(root))
        assert inv.packages[0].orchestration_type == "TASK"

    def test_scan_subdir_without_dbt_project_yml(self, tmp_path):
        """Subdirectory without dbt_project.yml — ignored, not in dbt_projects list."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()

        # Real dbt project
        make_dbt_project(pkg_dir, "real_project", staging_models=["stg_a"])
        # Not a dbt project — just a random directory
        random_dir = pkg_dir / "random_stuff"
        random_dir.mkdir()
        (random_dir / "notes.txt").write_text("not a dbt project")

        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        assert len(inv.packages[0].dbt_projects) == 1
        assert inv.packages[0].dbt_projects[0].folder_name == "real_project"

    def test_scan_package_no_dbt_no_orch_returns_none(self, tmp_path):
        """Directory with only random files — not added to packages list."""
        root = make_etl_dir(tmp_path, etl_config=False)
        junk_dir = root / "JunkDir"
        junk_dir.mkdir()
        (junk_dir / "readme.txt").write_text("nothing here")

        inv = ScannerService().scan(str(root))
        assert len(inv.packages) == 0


# ───────────────────────────────────────────────────────────────
# Group C: Validation Issue Detection (during scan)
# ───────────────────────────────────────────────────────────────


class TestValidationIssueDetection:

    def test_detect_placeholder_in_profiles_yml(self, tmp_path):
        """<your_account> in profiles.yml → ERROR/PLACEHOLDER."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(
            pkg_dir, "df1",
            staging_models=["stg_a"],
            placeholder_in="profiles.yml",
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        placeholders = [
            i for i in inv.validation_issues
            if i.category == "PLACEHOLDER" and "profiles.yml" in i.file_path
        ]
        assert len(placeholders) == 1
        assert placeholders[0].severity == "ERROR"

    def test_detect_placeholder_in_sources_yml(self, tmp_path):
        """<database> in sources.yml → ERROR/PLACEHOLDER."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(
            pkg_dir, "df1",
            staging_models=["stg_a"],
            placeholder_in="sources.yml",
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        placeholders = [
            i for i in inv.validation_issues
            if i.category == "PLACEHOLDER" and "sources.yml" in i.file_path
        ]
        assert len(placeholders) == 1

    def test_detect_placeholder_todo_keyword(self, tmp_path):
        """TODO in dbt_project.yml → ERROR/PLACEHOLDER."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()

        proj_dir = pkg_dir / "df1"
        proj_dir.mkdir()
        (proj_dir / "dbt_project.yml").write_text("name: 'df1'\nversion: '1.0.0'\n# TODO: fix this\n")
        (proj_dir / "profiles.yml").write_text("p:\n  target: dev\n")
        models_dir = proj_dir / "models"
        models_dir.mkdir()
        (models_dir / "sources.yml").write_text("version: 2\n")
        staging = models_dir / "staging"
        staging.mkdir()
        (staging / "stg_a.sql").write_text("SELECT 1")

        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        placeholders = [
            i for i in inv.validation_issues
            if i.category == "PLACEHOLDER" and "dbt_project.yml" in i.file_path
        ]
        assert len(placeholders) == 1

    def test_detect_name_mismatch(self, tmp_path):
        """dbt_project.yml name 'wrong_name' in folder 'correct_name' → ERROR/NAME_MISMATCH."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(
            pkg_dir, "correct_name",
            yml_name="wrong_name",
            staging_models=["stg_a"],
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        mismatches = [i for i in inv.validation_issues if i.category == "NAME_MISMATCH"]
        assert len(mismatches) == 1
        assert "wrong_name" in mismatches[0].problem
        assert "correct_name" in mismatches[0].problem

    def test_detect_missing_sources_yml(self, tmp_path):
        """No sources.yml in models/ → WARNING/MISSING_FILE."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(
            pkg_dir, "df1",
            sources=False,
            staging_models=["stg_a"],
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        missing_src = [
            i for i in inv.validation_issues
            if i.category == "MISSING_FILE" and "sources.yml" in i.problem
        ]
        assert len(missing_src) == 1

    def test_detect_orphan_task(self, tmp_path):
        """3 tasks: A (root), B (AFTER A), C (no AFTER, not first) → ORPHAN_TASK for C."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "df1", staging_models=["stg_a"])

        sql = (
            "CREATE OR REPLACE TASK task_a\n"
            "  WAREHOUSE = WH\n"
            "  SCHEDULE = '60 MINUTE'\n"
            "AS SELECT 1;\n\n"
            "CREATE OR REPLACE TASK task_b\n"
            "  AFTER task_a\n"
            "  WAREHOUSE = WH\n"
            "AS SELECT 2;\n\n"
            "CREATE OR REPLACE TASK task_c\n"
            "  WAREHOUSE = WH\n"
            "AS SELECT 3;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        orphans = [i for i in inv.validation_issues if i.category == "ORPHAN_TASK"]
        assert len(orphans) == 1
        assert "task_c" in orphans[0].problem

    def test_no_orphan_when_all_chained(self, tmp_path):
        """3 tasks all properly chained → no ORPHAN_TASK issues."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "df1", staging_models=["stg_a"])

        make_orchestration_sql(
            pkg_dir, "Pkg",
            tasks=[
                {"name": "root_task"},
                {"name": "child1", "after": "root_task"},
                {"name": "child2", "after": "child1"},
            ],
        )

        inv = ScannerService().scan(str(root))
        orphans = [i for i in inv.validation_issues if i.category == "ORPHAN_TASK"]
        assert len(orphans) == 0

    def test_detect_missing_profiles_yml(self, tmp_path):
        """dbt project with no profiles.yml → has_profiles_yml=False."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(
            pkg_dir, "df1",
            profiles=False,
            staging_models=["stg_a"],
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        assert inv.packages[0].dbt_projects[0].has_profiles_yml is False


# ───────────────────────────────────────────────────────────────
# Group D: ValidatorService
# ───────────────────────────────────────────────────────────────


class TestValidatorService:

    def test_validate_dangling_ref(self, tmp_path):
        """Orchestration references 'nonexistent_project' → ERROR/DANGLING_REF."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "real_project", staging_models=["stg_a"])
        make_orchestration_sql(
            pkg_dir, "Pkg",
            tasks=[{"name": "t1"}],
            dbt_refs=["nonexistent_project"],
        )

        scanner = ScannerService()
        inv = scanner.scan(str(root))

        validator = ValidatorService()
        new_issues = validator.validate(inv)

        dangling = [i for i in new_issues if i.category == "DANGLING_REF"]
        assert len(dangling) == 1
        assert "nonexistent_project" in dangling[0].problem

    def test_validate_ref_matches_by_folder_name(self, tmp_path):
        """Ref matches folder_name (case-insensitive) → no DANGLING_REF."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "MyFlow", staging_models=["stg_a"])
        make_orchestration_sql(
            pkg_dir, "Pkg",
            tasks=[{"name": "t1"}],
            dbt_refs=["myflow"],  # lowercase — should match case-insensitively
        )

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        dangling = [i for i in new_issues if i.category == "DANGLING_REF"]
        assert len(dangling) == 0

    def test_validate_ref_matches_by_dbt_project_name(self, tmp_path):
        """Ref matches dbt_project_name even though folder_name differs."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        # Folder is "FolderName" but dbt_project.yml has name: 'actual_name'
        make_dbt_project(
            pkg_dir, "FolderName",
            yml_name="actual_name",
            staging_models=["stg_a"],
        )
        make_orchestration_sql(
            pkg_dir, "Pkg",
            tasks=[{"name": "t1"}],
            dbt_refs=["actual_name"],
        )

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        dangling = [i for i in new_issues if i.category == "DANGLING_REF"]
        assert len(dangling) == 0

    def test_validate_schema_mismatch_in_etl_config(self, tmp_path):
        """etl_config SQL with 'public.control_variables' → INFO/SCHEMA_MISMATCH."""
        root = make_etl_dir(tmp_path, tables=["ctrl_vars"])
        # Overwrite the table SQL file with a public schema reference
        tbl_file = root / "etl_configuration" / "tables" / "ctrl_vars.sql"
        tbl_file.write_text("CREATE TABLE public.control_variables (id INT);")

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        schema_issues = [i for i in new_issues if i.category == "SCHEMA_MISMATCH"]
        assert len(schema_issues) == 1
        assert schema_issues[0].severity == "INFO"

    def test_validate_completeness_no_models(self, tmp_path):
        """dbt project with 0 SQL models → WARNING about no models."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        # Create a dbt project with no models (no staging_models, etc.)
        make_dbt_project(pkg_dir, "empty_proj")
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        no_models = [
            i for i in new_issues
            if "No SQL models" in i.problem
        ]
        assert len(no_models) == 1


# ───────────────────────────────────────────────────────────────
# Group D2: New Validator Checks (profiles.yml fields, TASK syntax)
# ───────────────────────────────────────────────────────────────


class TestProfilesYmlFieldValidation:

    def test_unsupported_field_detected(self, tmp_path):
        """profiles.yml with 'authenticator' → ERROR/UNSUPPORTED_FIELD."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        proj = make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])
        # Overwrite profiles.yml with unsupported fields
        (proj / "profiles.yml").write_text(
            "my_profile:\n"
            "  target: dev\n"
            "  outputs:\n"
            "    dev:\n"
            "      type: snowflake\n"
            "      authenticator: externalbrowser\n"
            "      private_key_path: /path/to/key.p8\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        unsupported = [i for i in new_issues if i.category == "UNSUPPORTED_FIELD"]
        assert len(unsupported) == 1
        assert unsupported[0].severity == "ERROR"
        assert "authenticator" in unsupported[0].problem
        assert "private_key_path" in unsupported[0].problem

    def test_no_unsupported_field_when_clean(self, tmp_path):
        """profiles.yml without unsupported fields → no UNSUPPORTED_FIELD issues."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        unsupported = [i for i in new_issues if i.category == "UNSUPPORTED_FIELD"]
        assert len(unsupported) == 0

    def test_unsupported_field_multiple_targets(self, tmp_path):
        """Multiple targets with unsupported fields → one issue per target."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        proj = make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])
        (proj / "profiles.yml").write_text(
            "my_profile:\n"
            "  target: dev\n"
            "  outputs:\n"
            "    dev:\n"
            "      type: snowflake\n"
            "      authenticator: externalbrowser\n"
            "    prod:\n"
            "      type: snowflake\n"
            "      private_key_path: /path/to/key.p8\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        unsupported = [i for i in new_issues if i.category == "UNSUPPORTED_FIELD"]
        assert len(unsupported) == 2


class TestTaskClauseOrdering:

    def test_after_before_warehouse_detected(self, tmp_path):
        """AFTER clause before WAREHOUSE → ERROR/TASK_SYNTAX."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])

        sql = (
            "CREATE OR REPLACE TASK root_task\n"
            "  WAREHOUSE = WH\n"
            "  SCHEDULE = '60 MINUTE'\n"
            "AS SELECT 1;\n\n"
            "CREATE OR REPLACE TASK child_task\n"
            "  AFTER root_task\n"
            "  WAREHOUSE = WH\n"
            "AS SELECT 2;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        task_issues = [i for i in new_issues if i.category == "TASK_SYNTAX"]
        assert len(task_issues) == 1
        assert task_issues[0].severity == "ERROR"
        assert "child_task" in task_issues[0].problem

    def test_warehouse_before_after_is_ok(self, tmp_path):
        """WAREHOUSE before AFTER (correct order) → no TASK_SYNTAX issues."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])

        sql = (
            "CREATE OR REPLACE TASK root_task\n"
            "  WAREHOUSE = WH\n"
            "  SCHEDULE = '60 MINUTE'\n"
            "AS SELECT 1;\n\n"
            "CREATE OR REPLACE TASK child_task\n"
            "  WAREHOUSE = WH\n"
            "  AFTER root_task\n"
            "AS SELECT 2;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        task_issues = [i for i in new_issues if i.category == "TASK_SYNTAX"]
        assert len(task_issues) == 0

    def test_procedure_orchestration_skipped(self, tmp_path):
        """Procedure-based orchestration → no TASK_SYNTAX check needed."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])
        make_orchestration_sql(
            pkg_dir, "Pkg",
            procedures=["main_proc"],
            dbt_refs=["proj1"],
        )

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        task_issues = [i for i in new_issues if i.category == "TASK_SYNTAX"]
        assert len(task_issues) == 0


class TestMissingProfilesSeverity:

    def test_missing_profiles_is_error(self, tmp_path):
        """Missing profiles.yml → ERROR (not WARNING)."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "proj1", profiles=False, staging_models=["stg_a"])
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        missing = [
            i for i in new_issues
            if i.category == "MISSING_FILE" and "profiles.yml" in i.problem
        ]
        assert len(missing) == 1
        assert missing[0].severity == "ERROR"


# ───────────────────────────────────────────────────────────────
# Group D4: Source Schema Mismatch Detection
# ───────────────────────────────────────────────────────────────


class TestSourceSchemaMismatch:

    def test_hardcoded_database_detected(self, tmp_path):
        """sources.yml with database: CONTOSO_OLTP → WARNING/SOURCE_SCHEMA_MISMATCH."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(
            pkg_dir, "proj1",
            staging_models=["stg_a"],
            source_database="CONTOSO_OLTP",
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        src_issues = [i for i in new_issues if i.category == "SOURCE_SCHEMA_MISMATCH"]
        assert len(src_issues) == 1
        assert src_issues[0].severity == "WARNING"
        assert "CONTOSO_OLTP" in src_issues[0].problem

    def test_schema_only_not_flagged(self, tmp_path):
        """sources.yml with schema: dbo but no database → no SOURCE_SCHEMA_MISMATCH.

        Schema-only is not flagged because the real problem is a hardcoded
        database pointing at the original source environment.  Schema alone
        (even a non-PUBLIC value) is often intentional after remapping.
        """
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(
            pkg_dir, "proj1",
            staging_models=["stg_a"],
            source_schema="dbo",
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        src_issues = [i for i in new_issues if i.category == "SOURCE_SCHEMA_MISMATCH"]
        assert len(src_issues) == 0

    def test_hardcoded_database_and_schema_detected(self, tmp_path):
        """sources.yml with both database and schema → single WARNING with both refs."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(
            pkg_dir, "proj1",
            staging_models=["stg_a"],
            source_database="CONTOSO_DW",
            source_schema="ANALYTICS",
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        src_issues = [i for i in new_issues if i.category == "SOURCE_SCHEMA_MISMATCH"]
        assert len(src_issues) == 1
        assert "CONTOSO_DW" in src_issues[0].problem
        assert "ANALYTICS" in src_issues[0].problem

    def test_no_issue_when_no_database_or_schema(self, tmp_path):
        """sources.yml without database/schema fields → no SOURCE_SCHEMA_MISMATCH."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        src_issues = [i for i in new_issues if i.category == "SOURCE_SCHEMA_MISMATCH"]
        assert len(src_issues) == 0

    def test_schema_public_not_flagged(self, tmp_path):
        """sources.yml with schema: PUBLIC but no database → no false positive."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(
            pkg_dir, "proj1",
            staging_models=["stg_a"],
            source_schema="PUBLIC",
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        src_issues = [i for i in new_issues if i.category == "SOURCE_SCHEMA_MISMATCH"]
        assert len(src_issues) == 0

    def test_multiple_sources_multiple_issues(self, tmp_path):
        """Two dbt projects with hardcoded sources → one issue per source."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(
            pkg_dir, "proj1",
            staging_models=["stg_a"],
            source_database="DB_ONE",
        )
        make_dbt_project(
            pkg_dir, "proj2",
            staging_models=["stg_b"],
            source_database="DB_TWO",
            source_schema="raw",
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        src_issues = [i for i in new_issues if i.category == "SOURCE_SCHEMA_MISMATCH"]
        assert len(src_issues) == 2
        problems = " ".join(i.problem for i in src_issues)
        assert "DB_ONE" in problems
        assert "DB_TWO" in problems


# ───────────────────────────────────────────────────────────────
# Group D5: Orchestration Schema Prefix Detection
# ───────────────────────────────────────────────────────────────


class TestOrchSchemaPrefix:
    """Tests for ORCH_SCHEMA_PREFIX validator — flags schema-qualified
    EXECUTE DBT PROJECT references (e.g. ETL.LoadOrders)."""

    def test_schema_prefix_detected(self, tmp_path):
        """EXECUTE DBT PROJECT ETL.LoadOrders → ERROR/ORCH_SCHEMA_PREFIX."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "LoadOrders", staging_models=["stg_a"])

        sql = (
            "CREATE OR REPLACE TASK root_task\n"
            "  WAREHOUSE = WH\n"
            "  SCHEDULE = '60 MINUTE'\n"
            "AS\n"
            "  EXECUTE DBT PROJECT ETL.LoadOrders;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        prefix_issues = [i for i in new_issues if i.category == "ORCH_SCHEMA_PREFIX"]
        assert len(prefix_issues) == 1
        assert prefix_issues[0].severity == "ERROR"
        assert "ETL" in prefix_issues[0].problem
        assert "LoadOrders" in prefix_issues[0].problem

    def test_no_schema_prefix_no_issue(self, tmp_path):
        """EXECUTE DBT PROJECT LoadOrders (no prefix) → no ORCH_SCHEMA_PREFIX."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "LoadOrders", staging_models=["stg_a"])

        sql = (
            "CREATE OR REPLACE TASK root_task\n"
            "  WAREHOUSE = WH\n"
            "  SCHEDULE = '60 MINUTE'\n"
            "AS\n"
            "  EXECUTE DBT PROJECT LoadOrders;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        prefix_issues = [i for i in new_issues if i.category == "ORCH_SCHEMA_PREFIX"]
        assert len(prefix_issues) == 0

    def test_multiple_prefixed_refs(self, tmp_path):
        """Three schema-qualified refs → three ORCH_SCHEMA_PREFIX issues."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "ProjA", staging_models=["stg_a"])
        make_dbt_project(pkg_dir, "ProjB", staging_models=["stg_b"])
        make_dbt_project(pkg_dir, "ProjC", staging_models=["stg_c"])

        sql = (
            "CREATE OR REPLACE TASK t1\n"
            "  WAREHOUSE = WH\n"
            "  SCHEDULE = '60 MINUTE'\n"
            "AS\n  EXECUTE DBT PROJECT ETL.ProjA;\n\n"
            "CREATE OR REPLACE TASK t2\n"
            "  WAREHOUSE = WH\n"
            "  AFTER t1\n"
            "AS\n  EXECUTE DBT PROJECT ETL.ProjB;\n\n"
            "CREATE OR REPLACE TASK t3\n"
            "  WAREHOUSE = WH\n"
            "  AFTER t2\n"
            "AS\n  EXECUTE DBT PROJECT STAGING.ProjC;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        prefix_issues = [i for i in new_issues if i.category == "ORCH_SCHEMA_PREFIX"]
        assert len(prefix_issues) == 3
        problems = " ".join(i.problem for i in prefix_issues)
        assert "ETL" in problems
        assert "STAGING" in problems

    def test_duplicate_ref_not_double_counted(self, tmp_path):
        """Same schema.project appearing twice → only one issue."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "LoadOrders", staging_models=["stg_a"])

        sql = (
            "CREATE OR REPLACE TASK t1\n"
            "  WAREHOUSE = WH\n"
            "  SCHEDULE = '60 MINUTE'\n"
            "AS\n  EXECUTE DBT PROJECT ETL.LoadOrders;\n\n"
            "-- retry logic\n"
            "EXECUTE DBT PROJECT ETL.LoadOrders;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        prefix_issues = [i for i in new_issues if i.category == "ORCH_SCHEMA_PREFIX"]
        assert len(prefix_issues) == 1

    def test_procedure_based_also_checked(self, tmp_path):
        """Procedure-based orchestration with schema prefix → also flagged."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "SyncData", staging_models=["stg_a"])

        sql = (
            "CREATE OR REPLACE PROCEDURE sp_run()\n"
            "RETURNS STRING\n"
            "LANGUAGE SQL\n"
            "AS\n$$\nBEGIN\n"
            "  EXECUTE DBT PROJECT DBO.SyncData;\n"
            "  RETURN 'ok';\nEND;\n$$;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        prefix_issues = [i for i in new_issues if i.category == "ORCH_SCHEMA_PREFIX"]
        assert len(prefix_issues) == 1
        assert "DBO" in prefix_issues[0].problem


# ───────────────────────────────────────────────────────────────
# Group D6: Orchestration Warehouse Detection
# ───────────────────────────────────────────────────────────────


class TestOrchWarehouse:
    """Tests for ORCH_WAREHOUSE validator — flags hardcoded warehouse names
    in orchestration SQL."""

    def test_warehouse_detected(self, tmp_path):
        """WAREHOUSE = ETL_WH → WARNING/ORCH_WAREHOUSE."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])

        sql = (
            "CREATE OR REPLACE TASK root_task\n"
            "  WAREHOUSE = ETL_WH\n"
            "  SCHEDULE = '60 MINUTE'\n"
            "AS SELECT 1;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        wh_issues = [i for i in new_issues if i.category == "ORCH_WAREHOUSE"]
        assert len(wh_issues) == 1
        assert wh_issues[0].severity == "WARNING"
        assert "ETL_WH" in wh_issues[0].problem

    def test_multiple_warehouses_single_issue(self, tmp_path):
        """Multiple WAREHOUSE = refs with different names → single issue listing all."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])

        sql = (
            "CREATE OR REPLACE TASK t1\n"
            "  WAREHOUSE = ETL_WH\n"
            "  SCHEDULE = '60 MINUTE'\n"
            "AS SELECT 1;\n\n"
            "CREATE OR REPLACE TASK t2\n"
            "  WAREHOUSE = REPORT_WH\n"
            "  AFTER t1\n"
            "AS SELECT 2;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        wh_issues = [i for i in new_issues if i.category == "ORCH_WAREHOUSE"]
        assert len(wh_issues) == 1
        assert "ETL_WH" in wh_issues[0].problem
        assert "REPORT_WH" in wh_issues[0].problem

    def test_no_warehouse_no_issue(self, tmp_path):
        """Procedure-based orchestration with no WAREHOUSE clause → no ORCH_WAREHOUSE."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])

        sql = (
            "CREATE OR REPLACE PROCEDURE sp_run()\n"
            "RETURNS STRING\n"
            "LANGUAGE SQL\n"
            "AS\n$$\nBEGIN\n"
            "  EXECUTE DBT PROJECT proj1;\n"
            "  RETURN 'ok';\nEND;\n$$;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        wh_issues = [i for i in new_issues if i.category == "ORCH_WAREHOUSE"]
        assert len(wh_issues) == 0

    def test_no_orchestration_file_no_crash(self, tmp_path):
        """Package with no orchestration file → no ORCH_WAREHOUSE (and no crash)."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])
        # No orchestration SQL

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        wh_issues = [i for i in new_issues if i.category == "ORCH_WAREHOUSE"]
        assert len(wh_issues) == 0


# ───────────────────────────────────────────────────────────────
# Group D7: PROC_EXECUTE_DBT Detection
# ───────────────────────────────────────────────────────────────


class TestProcExecuteDbt:
    """Tests for PROC_EXECUTE_DBT validator — flags PROCEDURE-based
    orchestration that uses EXECUTE DBT PROJECT (unsupported by Snowflake)."""

    def test_procedure_with_execute_dbt_detected(self, tmp_path):
        """PROCEDURE orchestration with EXECUTE DBT PROJECT refs → ERROR/PROC_EXECUTE_DBT."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "SyncData", staging_models=["stg_a"])

        sql = (
            "CREATE OR REPLACE PROCEDURE sp_run()\n"
            "RETURNS STRING\n"
            "LANGUAGE SQL\n"
            "AS\n$$\nBEGIN\n"
            "  EXECUTE DBT PROJECT SyncData;\n"
            "  RETURN 'ok';\nEND;\n$$;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        proc_issues = [i for i in new_issues if i.category == "PROC_EXECUTE_DBT"]
        assert len(proc_issues) == 1
        assert proc_issues[0].severity == "ERROR"
        assert "SyncData" in proc_issues[0].problem
        assert "TASK" in proc_issues[0].suggested_fix

    def test_task_with_execute_dbt_not_flagged(self, tmp_path):
        """TASK orchestration with EXECUTE DBT PROJECT refs → no PROC_EXECUTE_DBT."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "LoadOrders", staging_models=["stg_a"])

        sql = (
            "CREATE OR REPLACE TASK root_task\n"
            "  WAREHOUSE = WH\n"
            "  SCHEDULE = '60 MINUTE'\n"
            "AS\n"
            "  EXECUTE DBT PROJECT LoadOrders;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        proc_issues = [i for i in new_issues if i.category == "PROC_EXECUTE_DBT"]
        assert len(proc_issues) == 0

    def test_procedure_without_execute_dbt_not_flagged(self, tmp_path):
        """PROCEDURE orchestration with no EXECUTE DBT PROJECT refs → no issue."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])

        sql = (
            "CREATE OR REPLACE PROCEDURE sp_run()\n"
            "RETURNS STRING\n"
            "LANGUAGE SQL\n"
            "AS\n$$\nBEGIN\n"
            "  CALL some_other_proc();\n"
            "  RETURN 'ok';\nEND;\n$$;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        proc_issues = [i for i in new_issues if i.category == "PROC_EXECUTE_DBT"]
        assert len(proc_issues) == 0


# ───────────────────────────────────────────────────────────────
# Group D8: PARTIAL_DATE_CAST Detection
# ───────────────────────────────────────────────────────────────


class TestPartialDateCast:
    """Tests for PARTIAL_DATE_CAST validator — flags '{{ var(...) }}'::DATE
    patterns in dbt models/macros that may fail on partial dates."""

    def test_var_date_cast_in_model_detected(self, tmp_path):
        """Model SQL with '{{ var("x") }}'::DATE → WARNING/PARTIAL_DATE_CAST."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(
            pkg_dir, "proj1",
            staging_models=["stg_txn"],
            staging_model_contents={
                "stg_txn": (
                    "SELECT * FROM {{ source('raw', 'orders') }}\n"
                    "WHERE order_date >= DATE_TRUNC('month', '{{ var(\"report_month\") }}'::DATE)\n"
                ),
            },
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        cast_issues = [i for i in new_issues if i.category == "PARTIAL_DATE_CAST"]
        assert len(cast_issues) == 1
        assert cast_issues[0].severity == "WARNING"
        assert "stg_txn" in cast_issues[0].file_path

    def test_var_date_cast_in_macro_detected(self, tmp_path):
        """Macro SQL with '{{ var("x") }}'::DATE → WARNING/PARTIAL_DATE_CAST."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(
            pkg_dir, "proj1",
            staging_models=["stg_a"],
            macros=["m_date_helpers"],
            macro_contents={
                "m_date_helpers": (
                    "{% macro get_month_start() %}\n"
                    "    DATE_TRUNC('month', '{{ var(\"report_month\") }}'::DATE)\n"
                    "{% endmacro %}\n"
                ),
            },
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        cast_issues = [i for i in new_issues if i.category == "PARTIAL_DATE_CAST"]
        assert len(cast_issues) == 1
        assert "m_date_helpers" in cast_issues[0].file_path

    def test_proper_to_date_not_flagged(self, tmp_path):
        """Model using TO_DATE('{{ var("x") }}', 'YYYY-MM') → no PARTIAL_DATE_CAST."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(
            pkg_dir, "proj1",
            staging_models=["stg_txn"],
            staging_model_contents={
                "stg_txn": (
                    "SELECT * FROM {{ source('raw', 'orders') }}\n"
                    "WHERE order_date >= DATE_TRUNC('month', "
                    "TO_DATE('{{ var(\"report_month\") }}', 'YYYY-MM'))\n"
                ),
            },
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        cast_issues = [i for i in new_issues if i.category == "PARTIAL_DATE_CAST"]
        assert len(cast_issues) == 0


# ───────────────────────────────────────────────────────────────
# Group E: Serialization Roundtrip
# ───────────────────────────────────────────────────────────────


class TestProfilesOverrideFields:
    """Tests for PROFILES_OVERRIDE validator — flags connection fields that
    snow dbt deploy overrides from the CLI connection."""

    def test_override_fields_detected(self, tmp_path):
        """profiles.yml with account/database/schema/etc → WARNING/PROFILES_OVERRIDE."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        proj = make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])
        (proj / "profiles.yml").write_text(
            "my_profile:\n"
            "  target: dev\n"
            "  outputs:\n"
            "    dev:\n"
            "      type: snowflake\n"
            "      account: contoso.us-east-1\n"
            "      user: ETL_SERVICE_ACCOUNT\n"
            "      role: ACCOUNTADMIN\n"
            "      warehouse: COMPUTE_WH\n"
            "      database: ETL_DB\n"
            "      schema: ETL\n"
            "      threads: 4\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        override = [i for i in new_issues if i.category == "PROFILES_OVERRIDE"]
        assert len(override) == 1
        assert override[0].severity == "WARNING"
        assert "database" in override[0].problem
        assert "account" in override[0].problem
        assert "schema" in override[0].problem
        assert "Replace" in override[0].suggested_fix

    def test_minimal_profiles_no_override_warning(self, tmp_path):
        """profiles.yml with only type + threads → no PROFILES_OVERRIDE."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        proj = make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])
        (proj / "profiles.yml").write_text(
            "my_profile:\n"
            "  target: dev\n"
            "  outputs:\n"
            "    dev:\n"
            "      type: snowflake\n"
            "      threads: 4\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        override = [i for i in new_issues if i.category == "PROFILES_OVERRIDE"]
        assert len(override) == 0

    def test_database_only_still_flagged(self, tmp_path):
        """profiles.yml with just database → still flagged as PROFILES_OVERRIDE."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        proj = make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])
        (proj / "profiles.yml").write_text(
            "my_profile:\n"
            "  target: dev\n"
            "  outputs:\n"
            "    dev:\n"
            "      type: snowflake\n"
            "      database: CONTOSO_DW\n"
            "      threads: 4\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        override = [i for i in new_issues if i.category == "PROFILES_OVERRIDE"]
        assert len(override) == 1
        assert "database" in override[0].problem

    def test_multiple_projects_each_flagged(self, tmp_path):
        """Each project with override fields gets its own warning."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        for name in ["proj1", "proj2"]:
            proj = make_dbt_project(pkg_dir, name, staging_models=["stg_a"])
            (proj / "profiles.yml").write_text(
                "my_profile:\n"
                "  target: dev\n"
                "  outputs:\n"
                "    dev:\n"
                "      type: snowflake\n"
                "      database: ETL_DB\n"
                "      warehouse: WH\n"
            )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        override = [i for i in new_issues if i.category == "PROFILES_OVERRIDE"]
        assert len(override) == 2


class TestSerialization:

    def test_save_load_roundtrip(self, tmp_path):
        """Scan → save → load roundtrip preserves all fields."""
        root = make_etl_dir(tmp_path, tables=["tbl_a"])
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(
            pkg_dir, "df1",
            staging_models=["stg_a", "stg_b"],
            macros=["macro_clean"],
        )
        make_orchestration_sql(
            pkg_dir, "Pkg",
            tasks=[{"name": "root", "ref": "df1"}],
        )

        scanner = ScannerService()
        inv = scanner.scan(str(root))

        json_path = str(tmp_path / "inventory.json")
        save_inventory(inv, json_path)

        loaded = load_inventory(json_path)

        assert loaded.etl_output_dir == inv.etl_output_dir
        assert loaded.scan_timestamp == inv.scan_timestamp
        assert len(loaded.packages) == len(inv.packages)
        assert len(loaded.etl_config_components) == len(inv.etl_config_components)
        assert len(loaded.validation_issues) == len(inv.validation_issues)

        # Check nested dbt projects
        assert len(loaded.packages[0].dbt_projects) == len(inv.packages[0].dbt_projects)
        orig_proj = inv.packages[0].dbt_projects[0]
        loaded_proj = loaded.packages[0].dbt_projects[0]
        assert loaded_proj.folder_name == orig_proj.folder_name
        assert loaded_proj.model_count == orig_proj.model_count
        assert loaded_proj.staging_models == orig_proj.staging_models
        assert loaded_proj.macro_count == orig_proj.macro_count

    def test_load_invalid_json(self, tmp_path):
        """Non-JSON file → raises json.JSONDecodeError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("this is not json {{{")

        with pytest.raises(json.JSONDecodeError):
            load_inventory(str(bad_file))


# ───────────────────────────────────────────────────────────────
# Group F: Regex Patterns
# ───────────────────────────────────────────────────────────────


class TestRegexPatterns:

    def test_regex_execute_dbt_with_schema_prefix(self):
        """EXECUTE DBT PROJECT public.my_proj → extracts 'my_proj'."""
        match = EXECUTE_DBT_RE.search("EXECUTE DBT PROJECT public.my_proj")
        assert match is not None
        assert match.group(1) == "my_proj"

    def test_regex_execute_dbt_without_prefix(self):
        """EXECUTE DBT PROJECT my_proj → extracts 'my_proj'."""
        match = EXECUTE_DBT_RE.search("EXECUTE DBT PROJECT my_proj")
        assert match is not None
        assert match.group(1) == "my_proj"

    def test_regex_create_or_replace_task(self):
        """CREATE OR REPLACE TASK my_task → extracts 'my_task'."""
        match = CREATE_TASK_RE.search("CREATE OR REPLACE TASK my_task")
        assert match is not None
        assert match.group(1) == "my_task"

        # Also test without OR REPLACE
        match2 = CREATE_TASK_RE.search("CREATE TASK simple_task")
        assert match2 is not None
        assert match2.group(1) == "simple_task"

    def test_regex_placeholder_variants(self):
        """All placeholder forms are detected."""
        test_cases = [
            ("<database>", True),
            ("<schema>", True),
            ("<your_account>", True),
            ("< TODO >", True),
            ("TODO", True),
            ("PLACEHOLDER", True),
            ("my_database", False),
            ("actual_schema", False),
        ]
        for text, should_match in test_cases:
            result = PLACEHOLDER_RE.search(text)
            assert bool(result) == should_match, f"PLACEHOLDER_RE on '{text}': expected {should_match}"


# ───────────────────────────────────────────────────────────────
# Group G: CLI Commands (subprocess-based end-to-end)
# ───────────────────────────────────────────────────────────────


SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"


class TestCLI:

    def _run_cli(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        """Run the CLI via python -m replatform_scanner."""
        return subprocess.run(
            [sys.executable, "-m", "replatform_scanner", *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            env={**__import__("os").environ, "PYTHONPATH": str(SCRIPTS_DIR)},
        )

    def test_cli_scan_and_summary(self, tmp_path):
        """End-to-end: scan fixture, then run summary — exit 0, key strings."""
        root = make_etl_dir(tmp_path, tables=["tbl_a"])
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "df1", staging_models=["stg_x"])
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1", "ref": "df1"}])

        json_out = str(tmp_path / "inv.json")

        # Scan
        result = self._run_cli("scan", str(root), json_out)
        assert result.returncode == 0, f"scan failed: {result.stderr}"
        assert "Inventory saved" in result.stdout

        # Summary
        result = self._run_cli("summary", json_out)
        assert result.returncode == 0, f"summary failed: {result.stderr}"
        assert "REPLATFORM OUTPUT INVENTORY" in result.stdout
        assert "Packages:" in result.stdout

    def test_cli_validate(self, tmp_path):
        """Scan then validate — new issues are appended and reported."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        # Project with no models and no profiles → validator will find issues
        make_dbt_project(pkg_dir, "empty_proj", profiles=False)
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        json_out = str(tmp_path / "inv.json")

        # Scan
        self._run_cli("scan", str(root), json_out)

        # Validate
        result = self._run_cli("validate", json_out)
        assert result.returncode == 0, f"validate failed: {result.stderr}"
        assert "Validation complete" in result.stdout

    def test_cli_unknown_command(self):
        """Unknown command → exit 1 and error message."""
        result = self._run_cli("nonexistent_cmd")
        assert result.returncode == 1
        assert "Unknown command" in result.stderr


# ───────────────────────────────────────────────────────────────
# Group H: Regression Tests — Bugs found during end-to-end testing
# ───────────────────────────────────────────────────────────────


class TestRegressionBugs:
    """Regression tests for bugs discovered during the Phase 0-3 end-to-end
    test of the replatform skill.  These ensure the fixes are permanent and
    cannot silently regress."""

    # -- Bug 1: PROFILES_OVERRIDE suggested_fix must NOT tell users to
    #    remove/strip fields that `snow dbt deploy` requires. ----------------

    def test_profiles_override_fix_says_replace_not_remove(self, tmp_path):
        """PROFILES_OVERRIDE suggested_fix should say 'Replace', NOT 'Remove' or 'Keep only type'."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        proj = make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])
        (proj / "profiles.yml").write_text(
            "my_profile:\n"
            "  target: dev\n"
            "  outputs:\n"
            "    dev:\n"
            "      type: snowflake\n"
            "      account: old.us-east-1\n"
            "      role: OLD_ROLE\n"
            "      database: OLD_DB\n"
            "      schema: OLD_SCHEMA\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        override = [i for i in new_issues if i.category == "PROFILES_OVERRIDE"]
        assert len(override) == 1
        fix_text = override[0].suggested_fix
        # Must say "Replace" (correct guidance)
        assert "Replace" in fix_text, f"suggested_fix should say 'Replace': {fix_text}"
        # Must NOT say "Remove" or "Keep only" (old broken guidance)
        assert "Remove" not in fix_text, f"suggested_fix should NOT say 'Remove': {fix_text}"
        assert "Keep only" not in fix_text, f"suggested_fix should NOT say 'Keep only': {fix_text}"
        # Must warn that role/account/user are used verbatim (Bug 5)
        assert "role" in fix_text.lower(), f"suggested_fix should warn about role: {fix_text}"
        assert "verbatim" in fix_text.lower(), f"suggested_fix should say 'verbatim': {fix_text}"
        assert "placeholder" in fix_text.lower(), f"suggested_fix should warn against placeholder: {fix_text}"

    # -- Bug 2: DANGLING_REF must NOT match inside SQL comments. -------------

    def test_dangling_ref_ignores_commented_out_execute_dbt(self, tmp_path):
        """Commented-out EXECUTE DBT PROJECT lines must not produce DANGLING_REF."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "ActiveProj", staging_models=["stg_a"])
        # ArchiveData is commented out — should NOT be picked up as a ref
        sql = (
            "CREATE OR REPLACE TASK root_task\n"
            "  WAREHOUSE = COMPUTE_WH\n"
            "  SCHEDULE = '60 MINUTE'\n"
            "AS\n"
            "  EXECUTE DBT PROJECT ActiveProj;\n"
            "\n"
            "-- NOTE: ArchiveData disabled pending review\n"
            "-- EXECUTE DBT PROJECT ArchiveData;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        dangling = [i for i in inv.validation_issues + new_issues if i.category == "DANGLING_REF"]
        # ArchiveData is commented out, so no DANGLING_REF for it
        for issue in dangling:
            assert "ArchiveData" not in issue.problem, (
                f"DANGLING_REF falsely matched commented-out ArchiveData: {issue.problem}"
            )

    def test_dangling_ref_ignores_note_comments(self, tmp_path):
        """Words inside -- NOTE comments must not be parsed as dbt project refs."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "RealProj", staging_models=["stg_a"])
        sql = (
            "CREATE OR REPLACE TASK root_task\n"
            "  WAREHOUSE = COMPUTE_WH\n"
            "  SCHEDULE = '60 MINUTE'\n"
            "AS\n"
            "  EXECUTE DBT PROJECT RealProj;\n"
            "\n"
            "-- This task runs inside the daily pipeline\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        dangling = [i for i in inv.validation_issues + new_issues if i.category == "DANGLING_REF"]
        for issue in dangling:
            assert "inside" not in issue.problem.lower(), (
                f"DANGLING_REF falsely matched word from comment: {issue.problem}"
            )

    # -- Bug 3: ORCH_SCHEMA_PREFIX must NOT match inside SQL comments. -------

    def test_orch_schema_prefix_ignores_commented_out_lines(self, tmp_path):
        """Commented-out EXECUTE DBT PROJECT ETL.X must not produce ORCH_SCHEMA_PREFIX."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "LoadOrders", staging_models=["stg_a"])
        sql = (
            "CREATE OR REPLACE TASK root_task\n"
            "  WAREHOUSE = COMPUTE_WH\n"
            "  SCHEDULE = '60 MINUTE'\n"
            "AS\n"
            "  EXECUTE DBT PROJECT LoadOrders;\n"
            "\n"
            "-- Old reference: EXECUTE DBT PROJECT ETL.ArchiveData;\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        prefix_issues = [i for i in new_issues if i.category == "ORCH_SCHEMA_PREFIX"]
        assert len(prefix_issues) == 0, (
            f"ORCH_SCHEMA_PREFIX falsely matched inside comment: {prefix_issues}"
        )

    # -- Bug 3b: ORCH_WAREHOUSE must NOT match inside SQL comments. ----------

    def test_orch_warehouse_ignores_commented_out_lines(self, tmp_path):
        """Commented-out WAREHOUSE = OLD_WH must not produce ORCH_WAREHOUSE."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "Proj1", staging_models=["stg_a"])
        sql = (
            "CREATE OR REPLACE TASK root_task\n"
            "  WAREHOUSE = COMPUTE_WH\n"
            "  SCHEDULE = '60 MINUTE'\n"
            "AS\n"
            "  EXECUTE DBT PROJECT Proj1;\n"
            "\n"
            "-- Previously used: WAREHOUSE = OLD_ETL_WH\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=sql)

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        wh_issues = [i for i in new_issues if i.category == "ORCH_WAREHOUSE"]
        # Should only find COMPUTE_WH, not OLD_ETL_WH from the comment
        for issue in wh_issues:
            assert "OLD_ETL_WH" not in issue.problem, (
                f"ORCH_WAREHOUSE falsely matched inside comment: {issue.problem}"
            )

    # -- _strip_sql_comments unit test ---------------------------------------

    def test_strip_sql_comments_preserves_active_lines(self):
        """_strip_sql_comments blanks comment lines, keeps active lines intact."""
        text = (
            "CREATE TASK root_task\n"
            "  WAREHOUSE = WH\n"
            "-- This is a comment\n"
            "  EXECUTE DBT PROJECT MyProj;\n"
            "  -- another comment with EXECUTE DBT PROJECT Fake;\n"
            "END;\n"
        )
        result = _strip_sql_comments(text)
        lines = result.split("\n")
        assert lines[0] == "CREATE TASK root_task"
        assert lines[1] == "  WAREHOUSE = WH"
        assert lines[2] == ""  # comment stripped
        assert lines[3] == "  EXECUTE DBT PROJECT MyProj;"
        assert lines[4] == ""  # indented comment stripped
        assert lines[5] == "END;"

    # -- Bug 4: SKILL.md must instruct task creation in dependency order ------
    #    (root/parent first, then children).  We verify the scanner correctly
    #    parses all task names in a DAG, which the skill needs to reorder.

    def test_scanner_detects_task_parent_child_structure(self, tmp_path):
        """Scanner must parse all task names (root + children) so the skill can order them."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        make_dbt_project(pkg_dir, "ProjA", staging_models=["stg_a"])
        # Orchestration with root + child tasks (child references root via AFTER)
        make_orchestration_sql(pkg_dir, "Pkg", raw_sql=(
            "CREATE OR REPLACE TASK DailyLoad_ROOT\n"
            "  WAREHOUSE = COMPUTE_WH\n"
            "  SCHEDULE = 'USING CRON 0 5 * * * UTC'\n"
            "AS SELECT 1;\n\n"
            "CREATE OR REPLACE TASK DailyLoad_Child\n"
            "  WAREHOUSE = COMPUTE_WH\n"
            "  AFTER DailyLoad_ROOT\n"
            "AS EXECUTE DBT PROJECT DB.SCHEMA.ProjA\n"
            "   ARGS = 'build';\n"
        ))

        inv = ScannerService().scan(str(root))
        pkg = inv.packages[0]
        # Verify both tasks are found via task_names
        assert "DailyLoad_ROOT" in pkg.task_names, f"Root task not found: {pkg.task_names}"
        assert "DailyLoad_Child" in pkg.task_names, f"Child task not found: {pkg.task_names}"
        # Root should be first in task_names (parse order = file order)
        assert pkg.task_names[0] == "DailyLoad_ROOT", (
            f"Root task should appear first in task_names: {pkg.task_names}"
        )

    # -- Bug 5: PROFILES_OVERRIDE must warn that `role` is used verbatim ------
    #    and cannot be 'placeholder'.

    def test_profiles_override_fix_warns_role_not_placeholder(self, tmp_path):
        """suggested_fix must specifically warn that role is NOT overridden by CLI."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        proj = make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])
        (proj / "profiles.yml").write_text(
            "my_profile:\n"
            "  target: dev\n"
            "  outputs:\n"
            "    dev:\n"
            "      type: snowflake\n"
            "      role: placeholder\n"
            "      database: placeholder\n"
            "      schema: placeholder\n"
            "      warehouse: placeholder\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        override = [i for i in new_issues if i.category == "PROFILES_OVERRIDE"]
        assert len(override) == 1
        fix_text = override[0].suggested_fix
        # Must distinguish role (verbatim) from database/schema/warehouse (CLI-overridden)
        assert "role" in fix_text.lower()
        assert "verbatim" in fix_text.lower()
        # Must NOT tell users that ALL fields can be placeholder
        assert "NOT 'placeholder'" in fix_text or "NOT 'placeholder'" in fix_text.replace("\u2018", "'").replace("\u2019", "'"), (
            f"suggested_fix should explicitly warn against placeholder for role: {fix_text}"
        )

    def test_profiles_override_fix_says_db_schema_wh_overridden(self, tmp_path):
        """suggested_fix must say database/schema/warehouse ARE overridden by CLI flags."""
        root = make_etl_dir(tmp_path, etl_config=False)
        pkg_dir = root / "Pkg"
        pkg_dir.mkdir()
        proj = make_dbt_project(pkg_dir, "proj1", staging_models=["stg_a"])
        (proj / "profiles.yml").write_text(
            "my_profile:\n"
            "  target: dev\n"
            "  outputs:\n"
            "    dev:\n"
            "      type: snowflake\n"
            "      database: OLD_DB\n"
            "      schema: OLD_SCHEMA\n"
            "      warehouse: OLD_WH\n"
        )
        make_orchestration_sql(pkg_dir, "Pkg", tasks=[{"name": "t1"}])

        inv = ScannerService().scan(str(root))
        new_issues = ValidatorService().validate(inv)

        override = [i for i in new_issues if i.category == "PROFILES_OVERRIDE"]
        assert len(override) == 1
        fix_text = override[0].suggested_fix.lower()
        # Must say that database/schema/warehouse are overridden by CLI
        assert "overridden" in fix_text or "override" in fix_text, (
            f"suggested_fix should mention CLI override for db/schema/wh: {fix_text}"
        )
        assert "placeholder" in fix_text, (
            f"suggested_fix should say placeholders are OK for CLI-overridden fields: {fix_text}"
        )
