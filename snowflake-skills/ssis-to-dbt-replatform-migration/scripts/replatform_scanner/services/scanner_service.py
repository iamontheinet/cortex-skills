"""Scans a SnowConvert AI Replatform output directory and builds an inventory."""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..models import (
    ReplatformInventory,
    PackageInfo,
    DbtProjectInfo,
    EtlConfigComponent,
    ValidationIssue,
)


# Regex patterns for parsing orchestration SQL
EXECUTE_DBT_RE = re.compile(
    r"EXECUTE\s+DBT\s+PROJECT\s+(?:[\w]+\.)?(\w+)",
    re.IGNORECASE,
)
CREATE_TASK_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?TASK\s+(?:[\w]+\.)?(\w+)",
    re.IGNORECASE,
)
CREATE_PROCEDURE_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+(?:[\w]+\.)?(\w+)",
    re.IGNORECASE,
)
AFTER_TASK_RE = re.compile(
    r"AFTER\s+(?:[\w]+\.)?(\w+)",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(
    r"<\s*(database|schema|your_\w+|TODO)\s*>|TODO|PLACEHOLDER",
    re.IGNORECASE,
)

# YAML key extraction (simple, avoids full YAML parsing for robustness)
DBT_PROJECT_NAME_RE = re.compile(r"^\s*name:\s*['\"]?(\S+?)['\"]?\s*$", re.MULTILINE)


def _try_read_yaml_name(file_path: Path) -> Optional[str]:
    """Extract the 'name' field from a YAML file without full parsing."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        match = DBT_PROJECT_NAME_RE.search(text)
        if match:
            return match.group(1).strip("'\"")
    except Exception:
        pass
    return None


def _has_placeholders(file_path: Path) -> list[str]:
    """Check if a file contains placeholder values."""
    hits: list[str] = []
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if PLACEHOLDER_RE.search(line):
                hits.append(f"Line {i}: {line.strip()}")
    except Exception:
        pass
    return hits


class ScannerService:
    """Scans a Replatform ETL output directory."""

    def scan(self, etl_dir: str) -> ReplatformInventory:
        root = Path(etl_dir)
        if not root.is_dir():
            raise FileNotFoundError(f"Directory not found: {etl_dir}")

        inventory = ReplatformInventory(
            etl_output_dir=str(root.resolve()),
            scan_timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # 1. Scan etl_configuration/
        etl_config_dir = root / "etl_configuration"
        if etl_config_dir.is_dir():
            self._scan_etl_config(etl_config_dir, inventory)
        else:
            inventory.validation_issues.append(
                ValidationIssue(
                    severity="WARNING",
                    category="MISSING_FILE",
                    file_path=str(etl_config_dir),
                    problem="etl_configuration/ directory not found",
                    suggested_fix="This is expected if the SSIS packages had no variables or shared infrastructure.",
                )
            )

        # 2. Scan each package directory
        for child in sorted(root.iterdir()):
            if child.is_dir() and child.name != "etl_configuration":
                pkg = self._scan_package(child, inventory)
                if pkg:
                    inventory.packages.append(pkg)

        return inventory

    def _scan_etl_config(self, config_dir: Path, inventory: ReplatformInventory) -> None:
        category_map = {"tables": "table", "functions": "function", "procedures": "procedure"}
        for subdir_name, category in category_map.items():
            subdir = config_dir / subdir_name
            if subdir.is_dir():
                for sql_file in sorted(subdir.glob("*.sql")):
                    inventory.etl_config_components.append(
                        EtlConfigComponent(
                            name=sql_file.stem,
                            category=category,
                            file_path=str(sql_file),
                        )
                    )

    def _scan_package(self, pkg_dir: Path, inventory: ReplatformInventory) -> Optional[PackageInfo]:
        pkg_name = pkg_dir.name
        pkg = PackageInfo(name=pkg_name, path=str(pkg_dir))

        # Look for orchestration SQL file
        orch_file = pkg_dir / f"{pkg_name}.sql"
        if orch_file.is_file():
            pkg.orchestration_file = str(orch_file)
            self._parse_orchestration(orch_file, pkg, inventory)
        else:
            # Try case-insensitive match
            sql_files = list(pkg_dir.glob("*.sql"))
            top_level_sql = [f for f in sql_files if f.stem.lower() == pkg_name.lower()]
            if top_level_sql:
                pkg.orchestration_file = str(top_level_sql[0])
                self._parse_orchestration(top_level_sql[0], pkg, inventory)
            else:
                inventory.validation_issues.append(
                    ValidationIssue(
                        severity="WARNING",
                        category="MISSING_FILE",
                        file_path=str(pkg_dir),
                        problem=f"No orchestration SQL file found for package '{pkg_name}'",
                        suggested_fix=f"Expected file: {orch_file}",
                    )
                )

        # Check for script.sql
        script_sql = pkg_dir / "script.sql"
        if script_sql.is_file():
            pkg.has_script_sql = True

        # Scan for dbt projects (subdirectories with dbt_project.yml)
        for child in sorted(pkg_dir.iterdir()):
            if child.is_dir():
                dbt_proj = self._scan_dbt_project(child, pkg_name, inventory)
                if dbt_proj:
                    pkg.dbt_projects.append(dbt_proj)

        if not pkg.dbt_projects and not pkg.orchestration_file:
            return None  # Not a real package

        return pkg

    def _parse_orchestration(self, sql_file: Path, pkg: PackageInfo, inventory: ReplatformInventory) -> None:
        try:
            content = sql_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return

        # Extract EXECUTE DBT PROJECT references
        pkg.execute_dbt_project_refs = [m.group(1) for m in EXECUTE_DBT_RE.finditer(content)]

        # Extract TASK names
        pkg.task_names = [m.group(1) for m in CREATE_TASK_RE.finditer(content)]

        # Determine orchestration type
        has_tasks = bool(pkg.task_names)
        has_procedures = bool(CREATE_PROCEDURE_RE.search(content))

        if has_tasks and not has_procedures:
            pkg.orchestration_type = "TASK"
        elif has_procedures and not has_tasks:
            pkg.orchestration_type = "PROCEDURE"
        elif has_tasks and has_procedures:
            pkg.orchestration_type = "TASK"  # TASKs are the primary pattern
        else:
            pkg.orchestration_type = "UNKNOWN"
            inventory.validation_issues.append(
                ValidationIssue(
                    severity="WARNING",
                    category="MISSING_FILE",
                    file_path=str(sql_file),
                    problem="Could not determine orchestration type (no CREATE TASK or CREATE PROCEDURE found)",
                    suggested_fix="Review the SQL file manually to understand the orchestration pattern.",
                )
            )

        # Check for orphan tasks (tasks that have no AFTER clause and are not the root)
        if pkg.task_names:
            # Build set of tasks that have their own AFTER clause by checking
            # the text block between each CREATE TASK and the next CREATE or EOF
            child_tasks: set[str] = set()
            task_matches = list(CREATE_TASK_RE.finditer(content))
            for idx, m in enumerate(task_matches):
                start = m.end()
                end = task_matches[idx + 1].start() if idx + 1 < len(task_matches) else len(content)
                block = content[start:end]
                if AFTER_TASK_RE.search(block):
                    child_tasks.add(m.group(1).lower())
            # Orphans: not a child (no AFTER) and not the first task (assumed root)
            orphans = [
                t for t in pkg.task_names
                if t.lower() not in child_tasks and t != pkg.task_names[0]
            ]
            for orphan in orphans:
                inventory.validation_issues.append(
                    ValidationIssue(
                        severity="WARNING",
                        category="ORPHAN_TASK",
                        file_path=str(sql_file),
                        problem=f"Task '{orphan}' has no AFTER dependency and may not be the root task",
                        suggested_fix="Review the task DAG to ensure all tasks are properly chained.",
                    )
                )

    def _scan_dbt_project(
        self, proj_dir: Path, package_name: str, inventory: ReplatformInventory
    ) -> Optional[DbtProjectInfo]:
        dbt_project_yml = proj_dir / "dbt_project.yml"
        if not dbt_project_yml.is_file():
            return None  # Not a dbt project

        proj = DbtProjectInfo(
            name=proj_dir.name,
            folder_name=proj_dir.name,
            path=str(proj_dir),
            package_name=package_name,
            has_dbt_project_yml=True,
        )

        # Read project name from dbt_project.yml
        proj.dbt_project_name = _try_read_yaml_name(dbt_project_yml)

        # Check for profiles.yml
        profiles_yml = proj_dir / "profiles.yml"
        proj.has_profiles_yml = profiles_yml.is_file()

        # Check for sources.yml
        models_dir = proj_dir / "models"
        if models_dir.is_dir():
            sources_yml = models_dir / "sources.yml"
            proj.has_sources_yml = sources_yml.is_file()

            # Count models by layer
            staging_dir = models_dir / "staging"
            if staging_dir.is_dir():
                proj.staging_models = [f.stem for f in staging_dir.glob("*.sql")]

            intermediate_dir = models_dir / "intermediate"
            if intermediate_dir.is_dir():
                proj.intermediate_models = [f.stem for f in intermediate_dir.glob("*.sql")]

            marts_dir = models_dir / "marts"
            if marts_dir.is_dir():
                proj.mart_models = [f.stem for f in marts_dir.glob("*.sql")]

            proj.model_count = len(proj.staging_models) + len(proj.intermediate_models) + len(proj.mart_models)

        # Count macros
        macros_dir = proj_dir / "macros"
        if macros_dir.is_dir():
            proj.macro_count = len(list(macros_dir.glob("*.sql")))

        # Count tests
        tests_dir = proj_dir / "tests"
        if tests_dir.is_dir():
            proj.test_count = len(list(tests_dir.glob("*.sql")))

        # Validate: project name matches folder name
        if proj.dbt_project_name and proj.dbt_project_name != proj.folder_name:
            inventory.validation_issues.append(
                ValidationIssue(
                    severity="ERROR",
                    category="NAME_MISMATCH",
                    file_path=str(dbt_project_yml),
                    problem=(
                        f"dbt_project.yml name '{proj.dbt_project_name}' does not match "
                        f"folder name '{proj.folder_name}'"
                    ),
                    suggested_fix=(
                        f"Update the 'name' field in dbt_project.yml to '{proj.folder_name}' "
                        f"(required for EXECUTE DBT PROJECT to work correctly)."
                    ),
                )
            )

        # Validate: sources.yml exists
        if not proj.has_sources_yml:
            inventory.validation_issues.append(
                ValidationIssue(
                    severity="WARNING",
                    category="MISSING_FILE",
                    file_path=str(models_dir / "sources.yml") if models_dir.is_dir() else str(proj_dir),
                    problem=f"sources.yml not found in dbt project '{proj.name}'",
                    suggested_fix="Create a sources.yml with the correct database/schema references.",
                )
            )

        # Validate: check for placeholders in key files
        for check_file in [dbt_project_yml, profiles_yml, models_dir / "sources.yml" if models_dir.is_dir() else None]:
            if check_file and check_file.is_file():
                hits = _has_placeholders(check_file)
                if hits:
                    inventory.validation_issues.append(
                        ValidationIssue(
                            severity="ERROR",
                            category="PLACEHOLDER",
                            file_path=str(check_file),
                            problem=f"Placeholder values found: {'; '.join(hits[:3])}",
                            suggested_fix="Replace placeholder values with actual database/schema/connection details.",
                        )
                    )

        return proj
