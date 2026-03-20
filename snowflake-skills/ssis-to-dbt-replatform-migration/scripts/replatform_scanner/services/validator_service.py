"""Validates a Replatform inventory and detects additional issues."""

import json
import re
from pathlib import Path
from typing import List

import yaml

from ..models import ReplatformInventory, ValidationIssue
from .scanner_service import _strip_sql_comments


SCHEMA_REF_RE = re.compile(r"\bpublic\.\w+", re.IGNORECASE)

# Fields in profiles.yml that `snow dbt deploy` does not support
UNSUPPORTED_PROFILES_FIELDS = {
    "authenticator",
    "private_key_path",
    "private_key_passphrase",
    "token",
    "client_session_keep_alive",
    "connect_retries",
    "connect_timeout",
    "retry_on_database_errors",
    "retry_all",
}

# Fields in profiles.yml that reference the source environment and must be
# updated before `snow dbt deploy`.  Split into two groups:
#
#   CLI-OVERRIDDEN: `snow dbt deploy` replaces these from CLI flags
#   (--database, --schema, --warehouse).  Placeholder values are OK here
#   because the CLI flags win at deploy time.
#
#   USED-VERBATIM: `snow dbt deploy` reads these from profiles.yml and
#   uses them as-is (role) or from the CLI connection (account, user).
#   `role` in particular is NOT overridden — a value like 'placeholder'
#   will cause "Failed to use role placeholder" at deploy time.
#   `password` is handled by the CLI connection's auth mechanism.
PROFILES_CLI_OVERRIDDEN_FIELDS = {"database", "schema", "warehouse"}
PROFILES_VERBATIM_FIELDS = {"account", "user", "role"}
PROFILES_OVERRIDE_FIELDS = (
    PROFILES_CLI_OVERRIDDEN_FIELDS | PROFILES_VERBATIM_FIELDS | {"password"}
)

# Regex to capture schema-qualified EXECUTE DBT PROJECT references.
# Group 1 = schema prefix, Group 2 = project name.
EXECUTE_DBT_QUALIFIED_RE = re.compile(
    r"EXECUTE\s+DBT\s+PROJECT\s+([\w]+)\.([\w]+)",
    re.IGNORECASE,
)

# Regex to capture WAREHOUSE = <name> in orchestration SQL.
ORCH_WAREHOUSE_RE = re.compile(
    r"\bWAREHOUSE\s*=\s*(\w+)",
    re.IGNORECASE,
)

# Regex to detect Jinja var() → ::DATE cast in dbt models/macros.
# SnowConvert often produces `'{{ var("report_month") }}'::DATE` but the
# variable value may be a partial date like '2024-01' (YYYY-MM) which
# Snowflake's ::DATE cast cannot parse.  Should use TO_DATE with a format.
VAR_DATE_CAST_RE = re.compile(
    r"""\{\{\s*var\(\s*["'][^"']+["']\s*\)\s*\}\}['"]?\s*::DATE""",
    re.IGNORECASE,
)

# Regex to detect TASK clause ordering issue: AFTER before WAREHOUSE
# Matches a CREATE TASK block where AFTER appears before WAREHOUSE
TASK_AFTER_BEFORE_WAREHOUSE_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?TASK\s+\S+\s*\n"
    r"(?:.*\n)*?\s+AFTER\s+\S+"
    r"(?:.*\n)*?\s+WAREHOUSE\s*=",
    re.IGNORECASE,
)


class ValidatorService:
    """Runs validation checks on a Replatform inventory."""

    def validate(self, inventory: ReplatformInventory) -> List[ValidationIssue]:
        """Run all validation checks and return new issues found."""
        new_issues: List[ValidationIssue] = []

        new_issues.extend(self._check_dangling_refs(inventory))
        new_issues.extend(self._check_etl_config_schema_refs(inventory))
        new_issues.extend(self._check_dbt_project_completeness(inventory))
        new_issues.extend(self._check_profiles_yml_fields(inventory))
        new_issues.extend(self._check_profiles_override_fields(inventory))
        new_issues.extend(self._check_task_clause_ordering(inventory))
        new_issues.extend(self._check_source_schema_refs(inventory))
        new_issues.extend(self._check_orchestration_schema_prefix(inventory))
        new_issues.extend(self._check_orchestration_warehouse(inventory))
        new_issues.extend(self._check_procedure_execute_dbt(inventory))
        new_issues.extend(self._check_partial_date_cast(inventory))

        # Append to inventory
        inventory.validation_issues.extend(new_issues)
        return new_issues

    def _check_dangling_refs(self, inventory: ReplatformInventory) -> List[ValidationIssue]:
        """Check that EXECUTE DBT PROJECT references point to existing projects."""
        issues = []
        known_projects = set()
        for pkg in inventory.packages:
            for proj in pkg.dbt_projects:
                known_projects.add((proj.dbt_project_name or proj.folder_name).lower())
                known_projects.add(proj.folder_name.lower())

        for pkg in inventory.packages:
            for ref in pkg.execute_dbt_project_refs:
                if ref.lower() not in known_projects:
                    issues.append(
                        ValidationIssue(
                            severity="ERROR",
                            category="DANGLING_REF",
                            file_path=pkg.orchestration_file or pkg.path,
                            problem=(
                                f"EXECUTE DBT PROJECT references '{ref}' but no matching "
                                f"dbt project folder found"
                            ),
                            suggested_fix=(
                                f"Ensure a dbt project with name '{ref}' exists, or update "
                                f"the orchestration SQL to use the correct project name."
                            ),
                        )
                    )

        return issues

    def _check_etl_config_schema_refs(self, inventory: ReplatformInventory) -> List[ValidationIssue]:
        """Check etl_configuration files for hardcoded 'public' schema references."""
        issues = []
        for component in inventory.etl_config_components:
            file_path = Path(component.file_path)
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                matches = SCHEMA_REF_RE.findall(content)
                if matches:
                    issues.append(
                        ValidationIssue(
                            severity="INFO",
                            category="SCHEMA_MISMATCH",
                            file_path=str(file_path),
                            problem=(
                                f"Hardcoded 'public' schema references found: "
                                f"{', '.join(set(matches[:5]))}"
                            ),
                            suggested_fix=(
                                "If deploying to a schema other than 'public', update these "
                                "references to match the target schema."
                            ),
                        )
                    )
            except Exception:
                pass

        return issues

    def _check_dbt_project_completeness(self, inventory: ReplatformInventory) -> List[ValidationIssue]:
        """Check each dbt project has minimum required files."""
        issues = []
        for pkg in inventory.packages:
            for proj in pkg.dbt_projects:
                if not proj.has_profiles_yml:
                    issues.append(
                        ValidationIssue(
                            severity="ERROR",
                            category="MISSING_FILE",
                            file_path=proj.path,
                            problem=f"profiles.yml missing in dbt project '{proj.name}'",
                            suggested_fix=(
                                "Create a profiles.yml with your Snowflake connection details. "
                                "`snow dbt deploy` requires profiles.yml to exist."
                            ),
                        )
                    )

                if proj.model_count == 0:
                    issues.append(
                        ValidationIssue(
                            severity="WARNING",
                            category="MISSING_FILE",
                            file_path=proj.path,
                            problem=f"No SQL models found in dbt project '{proj.name}'",
                            suggested_fix="Check if models were generated correctly.",
                        )
                    )

        return issues

    def _check_profiles_yml_fields(self, inventory: ReplatformInventory) -> List[ValidationIssue]:
        """Check profiles.yml for fields unsupported by `snow dbt deploy`."""
        issues = []
        for pkg in inventory.packages:
            for proj in pkg.dbt_projects:
                profiles_path = Path(proj.path) / "profiles.yml"
                if not profiles_path.is_file():
                    continue
                try:
                    content = profiles_path.read_text(encoding="utf-8", errors="replace")
                    parsed = yaml.safe_load(content)
                    if not isinstance(parsed, dict):
                        continue
                    # Walk profile -> outputs -> target -> fields
                    for profile_name, profile_val in parsed.items():
                        if not isinstance(profile_val, dict):
                            continue
                        outputs = profile_val.get("outputs", {})
                        if not isinstance(outputs, dict):
                            continue
                        for target_name, target_val in outputs.items():
                            if not isinstance(target_val, dict):
                                continue
                            bad_fields = set(target_val.keys()) & UNSUPPORTED_PROFILES_FIELDS
                            if bad_fields:
                                issues.append(
                                    ValidationIssue(
                                        severity="ERROR",
                                        category="UNSUPPORTED_FIELD",
                                        file_path=str(profiles_path),
                                        problem=(
                                            f"profiles.yml contains fields unsupported by "
                                            f"`snow dbt deploy` in target '{target_name}': "
                                            f"{', '.join(sorted(bad_fields))}"
                                        ),
                                        suggested_fix=(
                                            f"Remove unsupported fields ({', '.join(sorted(bad_fields))}) "
                                            f"from profiles.yml. `snow dbt deploy` uses the CLI "
                                            f"connection configuration, not profiles.yml authentication."
                                        ),
                                    )
                                )
                except Exception:
                    pass
        return issues

    def _check_profiles_override_fields(self, inventory: ReplatformInventory) -> List[ValidationIssue]:
        """Flag profiles.yml fields that snow dbt deploy overrides from the CLI connection.

        Hardcoded account/user/role/database/schema/warehouse values reference
        the original source environment and cause 'Object does not exist' errors
        when the --database/--schema flags differ.  Only `type` and `threads`
        are needed.
        """
        issues = []
        for pkg in inventory.packages:
            for proj in pkg.dbt_projects:
                profiles_path = Path(proj.path) / "profiles.yml"
                if not profiles_path.is_file():
                    continue
                try:
                    content = profiles_path.read_text(encoding="utf-8", errors="replace")
                    parsed = yaml.safe_load(content)
                    if not isinstance(parsed, dict):
                        continue
                    for profile_name, profile_val in parsed.items():
                        if not isinstance(profile_val, dict):
                            continue
                        outputs = profile_val.get("outputs", {})
                        if not isinstance(outputs, dict):
                            continue
                        for target_name, target_val in outputs.items():
                            if not isinstance(target_val, dict):
                                continue
                            override_fields = set(target_val.keys()) & PROFILES_OVERRIDE_FIELDS
                            if override_fields:
                                issues.append(
                                    ValidationIssue(
                                        severity="WARNING",
                                        category="PROFILES_OVERRIDE",
                                        file_path=str(profiles_path),
                                        problem=(
                                            f"profiles.yml target '{target_name}' has connection "
                                            f"fields that `snow dbt deploy` overrides from the CLI "
                                            f"connection: {', '.join(sorted(override_fields))}. "
                                            f"These reference the original environment and may "
                                            f"cause 'Object does not exist' errors."
                                        ),
                                    suggested_fix=(
                                        f"Replace source-environment values for "
                                        f"{', '.join(sorted(override_fields))} in "
                                        f"profiles.yml with target-environment "
                                        f"values. **`role`, `account`, and `user` "
                                        f"are used verbatim by `snow dbt deploy`** "
                                        f"— they MUST be set to real target values "
                                        f"(e.g. the role from your Snowflake "
                                        f"connection), NOT 'placeholder'. "
                                        f"`database`, `schema`, and `warehouse` "
                                        f"are overridden by CLI flags so placeholder "
                                        f"values are acceptable for those three."
                                    ),
                                    )
                                )
                except Exception:
                    pass
        return issues

    def _check_task_clause_ordering(self, inventory: ReplatformInventory) -> List[ValidationIssue]:
        """Check CREATE TASK statements have WAREHOUSE before AFTER (Snowflake syntax requirement)."""
        issues = []
        for pkg in inventory.packages:
            if pkg.orchestration_type != "TASK" or not pkg.orchestration_file:
                continue
            orch_path = Path(pkg.orchestration_file)
            if not orch_path.is_file():
                continue
            try:
                content = orch_path.read_text(encoding="utf-8", errors="replace")
                active_content = _strip_sql_comments(content)
                # Check each CREATE TASK block individually
                task_re = re.compile(
                    r"CREATE\s+(?:OR\s+REPLACE\s+)?TASK\s+(\S+)",
                    re.IGNORECASE,
                )
                for match in task_re.finditer(active_content):
                    task_name = match.group(1)
                    start = match.start()
                    # Find the end of this task block (next CREATE or EOF)
                    next_create = re.search(r"\nCREATE\s", active_content[match.end():], re.IGNORECASE)
                    end = match.end() + next_create.start() if next_create else len(active_content)
                    block = active_content[start:end]
                    # Check if AFTER appears before WAREHOUSE in this block
                    after_pos = re.search(r"\bAFTER\b", block, re.IGNORECASE)
                    warehouse_pos = re.search(r"\bWAREHOUSE\b", block, re.IGNORECASE)
                    if after_pos and warehouse_pos and after_pos.start() < warehouse_pos.start():
                        issues.append(
                            ValidationIssue(
                                severity="ERROR",
                                category="TASK_SYNTAX",
                                file_path=str(orch_path),
                                problem=(
                                    f"CREATE TASK {task_name}: AFTER clause appears before "
                                    f"WAREHOUSE clause. Snowflake requires WAREHOUSE before AFTER."
                                ),
                                suggested_fix=(
                                    f"Reorder the clauses so WAREHOUSE comes before AFTER in "
                                    f"the CREATE TASK statement for '{task_name}'."
                                ),
                            )
                        )
            except Exception:
                pass
        return issues


    def _check_source_schema_refs(self, inventory: ReplatformInventory) -> List[ValidationIssue]:
        """Check sources.yml for hardcoded database/schema that may not exist in the target."""
        issues = []
        for pkg in inventory.packages:
            for proj in pkg.dbt_projects:
                sources_path = Path(proj.path) / "models" / "sources.yml"
                if not sources_path.is_file():
                    continue
                try:
                    content = sources_path.read_text(encoding="utf-8", errors="replace")
                    parsed = yaml.safe_load(content)
                    if not isinstance(parsed, dict):
                        continue
                    sources_list = parsed.get("sources", [])
                    if not isinstance(sources_list, list):
                        continue
                    for source in sources_list:
                        if not isinstance(source, dict):
                            continue
                        src_name = source.get("name", "<unknown>")
                        src_db = source.get("database")
                        # Only flag when database is explicitly set — that's the
                        # field that points at the original source environment.
                        # schema alone (e.g. schema: PUBLIC) is fine; dbt uses
                        # the source name as schema when it's omitted, so an
                        # explicit schema is often intentional/correct.
                        if not src_db:
                            continue
                        src_schema = source.get("schema")
                        refs = [f"database: {src_db}"]
                        if src_schema:
                            refs.append(f"schema: {src_schema}")
                        issues.append(
                            ValidationIssue(
                                severity="WARNING",
                                category="SOURCE_SCHEMA_MISMATCH",
                                file_path=str(sources_path),
                                problem=(
                                    f"Source '{src_name}' has hardcoded {', '.join(refs)}. "
                                    f"These reference the original source environment and may "
                                    f"not exist in the target Snowflake account."
                                ),
                                suggested_fix=(
                                    f"Remove the database field in sources.yml for source "
                                    f"'{src_name}' so dbt uses the project's target database, "
                                    f"and set schema to the target schema (e.g. PUBLIC)."
                                ),
                            )
                        )
                except Exception:
                    pass
        return issues

    def _check_orchestration_schema_prefix(self, inventory: ReplatformInventory) -> List[ValidationIssue]:
        """Flag schema-qualified EXECUTE DBT PROJECT references in orchestration SQL.

        SnowConvert carries over the source-environment schema (e.g. ``ETL``)
        in ``EXECUTE DBT PROJECT ETL.LoadOrders``.  After ``snow dbt deploy
        --schema PUBLIC`` the project lives under ``PUBLIC``, so the hardcoded
        ``ETL.`` prefix will cause an "Object does not exist" error.
        """
        issues: List[ValidationIssue] = []
        for pkg in inventory.packages:
            if not pkg.orchestration_file:
                continue
            orch_path = Path(pkg.orchestration_file)
            if not orch_path.is_file():
                continue
            try:
                content = orch_path.read_text(encoding="utf-8", errors="replace")
                active_content = _strip_sql_comments(content)
                matches = EXECUTE_DBT_QUALIFIED_RE.findall(active_content)
                if not matches:
                    continue
                # matches is a list of (schema, project) tuples
                seen: set[str] = set()
                for schema, project in matches:
                    key = f"{schema}.{project}"
                    if key.lower() in seen:
                        continue
                    seen.add(key.lower())
                    issues.append(
                        ValidationIssue(
                            severity="ERROR",
                            category="ORCH_SCHEMA_PREFIX",
                            file_path=str(orch_path),
                            problem=(
                                f"EXECUTE DBT PROJECT {schema}.{project} has hardcoded "
                                f"schema prefix '{schema}'. After `snow dbt deploy "
                                f"--schema <target>`, the project lives under the "
                                f"target schema, not '{schema}'."
                            ),
                            suggested_fix=(
                                f"Change '{schema}.{project}' to "
                                f"'<target_schema>.{project}' (e.g. 'PUBLIC.{project}') "
                                f"to match the schema used in `snow dbt deploy --schema`."
                            ),
                        )
                    )
            except Exception:
                pass
        return issues

    def _check_orchestration_warehouse(self, inventory: ReplatformInventory) -> List[ValidationIssue]:
        """Flag hardcoded warehouse names in orchestration SQL.

        SnowConvert carries over the source-environment warehouse names
        (e.g. ``ETL_WH``, ``REPORT_WH``).  These warehouses may not exist in
        the target Snowflake account.
        """
        issues: List[ValidationIssue] = []
        for pkg in inventory.packages:
            if not pkg.orchestration_file:
                continue
            orch_path = Path(pkg.orchestration_file)
            if not orch_path.is_file():
                continue
            try:
                content = orch_path.read_text(encoding="utf-8", errors="replace")
                active_content = _strip_sql_comments(content)
                warehouse_names = ORCH_WAREHOUSE_RE.findall(active_content)
                if not warehouse_names:
                    continue
                unique_names = sorted(set(wh.upper() for wh in warehouse_names))
                issues.append(
                    ValidationIssue(
                        severity="WARNING",
                        category="ORCH_WAREHOUSE",
                        file_path=str(orch_path),
                        problem=(
                            f"Orchestration SQL references warehouse(s): "
                            f"{', '.join(unique_names)}. These are hardcoded from "
                            f"the source environment and may not exist in the "
                            f"target Snowflake account."
                        ),
                        suggested_fix=(
                            f"Update WAREHOUSE = references to use the target "
                            f"warehouse (e.g. COMPUTE_WH), or confirm that "
                            f"{', '.join(unique_names)} exist in the target account."
                        ),
                    )
                )
            except Exception:
                pass
        return issues

    def _check_procedure_execute_dbt(self, inventory: ReplatformInventory) -> List[ValidationIssue]:
        """Flag PROCEDURE-based orchestration that uses EXECUTE DBT PROJECT.

        ``EXECUTE DBT PROJECT`` cannot run inside a SQL stored procedure
        (LANGUAGE SQL BEGIN…END).  Snowflake rejects it with
        "Unsupported statement type 'SHOW PARAMETER'".  The orchestration
        must be converted to a TASK-based DAG instead.
        """
        issues: List[ValidationIssue] = []
        for pkg in inventory.packages:
            if pkg.orchestration_type != "PROCEDURE":
                continue
            if not pkg.execute_dbt_project_refs:
                continue
            refs = ", ".join(pkg.execute_dbt_project_refs)
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    category="PROC_EXECUTE_DBT",
                    file_path=pkg.orchestration_file or pkg.path,
                    problem=(
                        f"EXECUTE DBT PROJECT cannot run inside a SQL stored "
                        f"procedure (LANGUAGE SQL). Snowflake will fail with "
                        f"'Unsupported statement type'. Referenced projects: {refs}"
                    ),
                    suggested_fix=(
                        f"Convert this PROCEDURE-based orchestration to a "
                        f"TASK-based DAG. Each EXECUTE DBT PROJECT call "
                        f"becomes a child task with an AFTER dependency."
                    ),
                )
            )
        return issues

    def _check_partial_date_cast(self, inventory: ReplatformInventory) -> List[ValidationIssue]:
        """Flag ``'{{ var(...) }}'::DATE`` patterns in dbt models and macros.

        SnowConvert often generates ``'{{ var("report_month") }}'::DATE``
        but the variable value may be a partial date like ``'2024-01'``
        (YYYY-MM format) which Snowflake's ``::DATE`` cast cannot parse.
        The fix is to use ``TO_DATE('{{ var(...) }}', 'YYYY-MM')`` with an
        explicit format string.
        """
        issues: List[ValidationIssue] = []
        for pkg in inventory.packages:
            for proj in pkg.dbt_projects:
                proj_path = Path(proj.path)
                # Scan models/ and macros/ directories for SQL files
                for subdir in ["models", "macros"]:
                    scan_dir = proj_path / subdir
                    if not scan_dir.is_dir():
                        continue
                    for sql_file in scan_dir.rglob("*.sql"):
                        try:
                            content = sql_file.read_text(encoding="utf-8", errors="replace")
                            matches = VAR_DATE_CAST_RE.findall(content)
                            if matches:
                                issues.append(
                                    ValidationIssue(
                                        severity="WARNING",
                                        category="PARTIAL_DATE_CAST",
                                        file_path=str(sql_file),
                                        problem=(
                                            f"Found '{{{{ var(...) }}}}::DATE' cast pattern "
                                            f"({len(matches)} occurrence(s)). If the variable "
                                            f"value is a partial date like 'YYYY-MM', "
                                            f"Snowflake's ::DATE cast will fail."
                                        ),
                                        suggested_fix=(
                                            "Replace `'{{ var(\"...\") }}'::DATE` with "
                                            "`TO_DATE('{{ var(\"...\") }}', 'YYYY-MM')` "
                                            "(using the appropriate format string for the "
                                            "variable's expected value)."
                                        ),
                                    )
                                )
                        except Exception:
                            pass
        return issues


def load_inventory(json_path: str) -> ReplatformInventory:
    """Load an inventory from a JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    from ..models import PackageInfo, DbtProjectInfo, EtlConfigComponent

    inventory = ReplatformInventory(
        etl_output_dir=data["etl_output_dir"],
        scan_timestamp=data.get("scan_timestamp"),
    )

    for comp_data in data.get("etl_config_components", []):
        inventory.etl_config_components.append(
            EtlConfigComponent(**comp_data)
        )

    for pkg_data in data.get("packages", []):
        dbt_projects = []
        for proj_data in pkg_data.pop("dbt_projects", []):
            dbt_projects.append(DbtProjectInfo(**proj_data))
        pkg = PackageInfo(**pkg_data, dbt_projects=dbt_projects)
        inventory.packages.append(pkg)

    for issue_data in data.get("validation_issues", []):
        inventory.validation_issues.append(ValidationIssue(**issue_data))

    return inventory


def save_inventory(inventory: ReplatformInventory, json_path: str) -> None:
    """Save an inventory to a JSON file."""
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(inventory.to_dict(), f, indent=2, default=str)
