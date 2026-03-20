"""Shared fixtures for replatform_scanner tests."""

import sys
from pathlib import Path

import pytest

# Add the scripts directory to sys.path so we can import replatform_scanner
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Helper factories (not fixtures — called directly in tests with tmp_path)
# ---------------------------------------------------------------------------


def make_dbt_project(
    parent: Path,
    name: str,
    *,
    yml_name: str | None = None,
    profiles: bool = True,
    sources: bool = True,
    source_database: str | None = None,
    source_schema: str | None = None,
    staging_models: list[str] | None = None,
    staging_model_contents: dict[str, str] | None = None,
    intermediate_models: list[str] | None = None,
    mart_models: list[str] | None = None,
    macros: list[str] | None = None,
    macro_contents: dict[str, str] | None = None,
    tests: list[str] | None = None,
    placeholder_in: str | None = None,
) -> Path:
    """Create a synthetic dbt project directory.

    Args:
        parent: Parent directory (e.g., the package dir).
        name: Folder name for the project.
        yml_name: 'name' field inside dbt_project.yml. Defaults to *name*.
        profiles: Whether to create profiles.yml.
        sources: Whether to create models/sources.yml.
        source_database: If set, add 'database: <value>' to sources.yml.
        source_schema: If set, add 'schema: <value>' to sources.yml.
        staging_models: List of .sql model names for models/staging/.
        staging_model_contents: Dict of model name -> SQL content for staging models.
        intermediate_models: List of .sql model names for models/intermediate/.
        mart_models: List of .sql model names for models/marts/.
        macros: List of .sql macro file names.
        macro_contents: Dict of macro name -> SQL content for macros.
        tests: List of .sql test file names.
        placeholder_in: If set, inject a placeholder into this file
            ('dbt_project.yml', 'profiles.yml', or 'sources.yml').
    """
    proj_dir = parent / name
    proj_dir.mkdir(parents=True, exist_ok=True)

    effective_name = yml_name if yml_name is not None else name
    dbt_yml_content = f"name: '{effective_name}'\nversion: '1.0.0'\n"
    if placeholder_in == "dbt_project.yml":
        dbt_yml_content += "database: <database>\n"
    (proj_dir / "dbt_project.yml").write_text(dbt_yml_content)

    if profiles:
        profiles_content = "my_profile:\n  target: dev\n  outputs:\n    dev:\n      type: snowflake\n"
        if placeholder_in == "profiles.yml":
            profiles_content += "      account: <your_account>\n"
        (proj_dir / "profiles.yml").write_text(profiles_content)

    models_dir = proj_dir / "models"
    models_dir.mkdir(exist_ok=True)

    if sources:
        sources_content = "version: 2\nsources:\n  - name: raw\n"
        if source_database:
            sources_content += f"    database: {source_database}\n"
        if source_schema:
            sources_content += f"    schema: {source_schema}\n"
        sources_content += "    tables:\n      - name: orders\n"
        if placeholder_in == "sources.yml":
            sources_content += "    database: <database>\n"
        (models_dir / "sources.yml").write_text(sources_content)

    for layer, names in [
        ("staging", staging_models),
        ("intermediate", intermediate_models),
        ("marts", mart_models),
    ]:
        if names:
            layer_dir = models_dir / layer
            layer_dir.mkdir(exist_ok=True)
            for m in names:
                content = f"SELECT 1 AS {m}"
                if layer == "staging" and staging_model_contents and m in staging_model_contents:
                    content = staging_model_contents[m]
                (layer_dir / f"{m}.sql").write_text(content)

    if macros:
        macros_dir = proj_dir / "macros"
        macros_dir.mkdir(exist_ok=True)
        for m in macros:
            content = f"-- macro {m}"
            if macro_contents and m in macro_contents:
                content = macro_contents[m]
            (macros_dir / f"{m}.sql").write_text(content)

    if tests:
        tests_dir = proj_dir / "tests"
        tests_dir.mkdir(exist_ok=True)
        for t in tests:
            (tests_dir / f"{t}.sql").write_text(f"-- test {t}")

    return proj_dir


def make_orchestration_sql(
    pkg_dir: Path,
    name: str,
    *,
    tasks: list[dict] | None = None,
    procedures: list[str] | None = None,
    dbt_refs: list[str] | None = None,
    raw_sql: str | None = None,
) -> Path:
    """Create an orchestration SQL file inside a package directory.

    Args:
        pkg_dir: The package directory.
        name: File name stem (will create {name}.sql).
        tasks: List of dicts with 'name' and optional 'after' key.
            Example: [{'name': 'root_task'}, {'name': 'child', 'after': 'root_task'}]
        procedures: List of procedure names to include CREATE PROCEDURE for.
        dbt_refs: List of dbt project names to include EXECUTE DBT PROJECT for.
        raw_sql: If provided, write this verbatim instead of generating.
    """
    sql_file = pkg_dir / f"{name}.sql"

    if raw_sql is not None:
        sql_file.write_text(raw_sql)
        return sql_file

    lines: list[str] = []

    if tasks:
        for t in tasks:
            after_clause = f"\n  AFTER {t['after']}" if t.get("after") else ""
            ref_clause = ""
            if t.get("ref"):
                ref_clause = f"\nAS\n  EXECUTE DBT PROJECT {t['ref']};"
            elif dbt_refs:
                # Use next available ref
                pass
            lines.append(
                f"CREATE OR REPLACE TASK {t['name']}{after_clause}\n"
                f"  WAREHOUSE = MY_WH\n"
                f"  SCHEDULE = '60 MINUTE'{ref_clause}\n"
            )

    if procedures:
        for p in procedures:
            lines.append(
                f"CREATE OR REPLACE PROCEDURE {p}()\n"
                f"RETURNS STRING\n"
                f"LANGUAGE SQL\n"
                f"AS\n$$\nBEGIN\n  RETURN 'ok';\nEND;\n$$;\n"
            )

    if dbt_refs:
        for ref in dbt_refs:
            # Only add if not already embedded in a task
            if not any(t.get("ref") == ref for t in (tasks or [])):
                lines.append(f"EXECUTE DBT PROJECT {ref};\n")

    sql_file.write_text("\n".join(lines))
    return sql_file


def make_etl_dir(
    tmp_path: Path,
    *,
    etl_config: bool = True,
    tables: list[str] | None = None,
    functions: list[str] | None = None,
    procedures: list[str] | None = None,
) -> Path:
    """Create the top-level ETL output directory with optional etl_configuration.

    Args:
        tmp_path: pytest tmp_path fixture.
        etl_config: Whether to create etl_configuration/ at all.
        tables: SQL file stems for etl_configuration/tables/.
        functions: SQL file stems for etl_configuration/functions/.
        procedures: SQL file stems for etl_configuration/procedures/.

    Returns:
        Path to the ETL output root directory.
    """
    etl_root = tmp_path / "Output" / "ETL"
    etl_root.mkdir(parents=True)

    if etl_config:
        config_dir = etl_root / "etl_configuration"
        config_dir.mkdir()
        for category, names in [
            ("tables", tables),
            ("functions", functions),
            ("procedures", procedures),
        ]:
            if names:
                cat_dir = config_dir / category
                cat_dir.mkdir()
                for n in names:
                    (cat_dir / f"{n}.sql").write_text(f"-- {category}/{n}")

    return etl_root
