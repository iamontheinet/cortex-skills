"""CLI for replatform_scanner - scan, validate, and summarize Replatform output."""

import json
import sys
from pathlib import Path

from .services import ScannerService, ValidatorService, load_inventory, save_inventory


def cmd_scan(args: list[str]) -> None:
    """Scan a Replatform output directory and produce inventory JSON."""
    if len(args) < 2:
        print("Usage: scan <etl_output_dir> <output_json>", file=sys.stderr)
        sys.exit(1)

    etl_dir = args[0]
    output_json = args[1]

    scanner = ScannerService()
    inventory = scanner.scan(etl_dir)

    save_inventory(inventory, output_json)
    print(f"Inventory saved to: {output_json}")
    print(f"  Packages: {len(inventory.packages)}")
    print(f"  dbt Projects: {inventory.total_dbt_projects}")
    print(f"  etl_config components: {len(inventory.etl_config_components)}")
    print(f"  Validation issues: {len(inventory.validation_issues)}")


def cmd_summary(args: list[str]) -> None:
    """Print a human-readable summary of the inventory."""
    if len(args) < 1:
        print("Usage: summary <inventory_json>", file=sys.stderr)
        sys.exit(1)

    inventory = load_inventory(args[0])

    print("=" * 60)
    print("REPLATFORM OUTPUT INVENTORY")
    print("=" * 60)
    print(f"Source directory: {inventory.etl_output_dir}")
    print(f"Scanned at: {inventory.scan_timestamp}")
    print()

    print(f"Packages: {len(inventory.packages)}")
    print(f"  TASK-based: {len(inventory.task_based_packages)}")
    print(f"  PROCEDURE-based: {len(inventory.procedure_based_packages)}")
    print(f"dbt Projects: {inventory.total_dbt_projects}")
    print(f"etl_configuration components: {len(inventory.etl_config_components)}")
    print()

    if inventory.packages:
        print("-" * 60)
        print("PACKAGES")
        print("-" * 60)
        for pkg in inventory.packages:
            orch_label = pkg.orchestration_type or "UNKNOWN"
            print(f"  {pkg.name} [{orch_label}]")
            for proj in pkg.dbt_projects:
                model_info = f"{proj.model_count} models"
                name_note = ""
                if proj.dbt_project_name and proj.dbt_project_name != proj.folder_name:
                    name_note = f" (yml name: {proj.dbt_project_name})"
                print(f"    -> {proj.folder_name}{name_note} ({model_info})")
            if pkg.execute_dbt_project_refs:
                print(f"    EXECUTE DBT PROJECT refs: {', '.join(pkg.execute_dbt_project_refs)}")
        print()

    if inventory.etl_config_components:
        print("-" * 60)
        print("ETL CONFIGURATION")
        print("-" * 60)
        for comp in inventory.etl_config_components:
            print(f"  [{comp.category}] {comp.name}")
        print()

    errors = [i for i in inventory.validation_issues if i.severity == "ERROR"]
    warnings = [i for i in inventory.validation_issues if i.severity == "WARNING"]
    infos = [i for i in inventory.validation_issues if i.severity == "INFO"]

    print("-" * 60)
    print(f"VALIDATION ISSUES ({len(inventory.validation_issues)} total)")
    print("-" * 60)
    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for issue in errors:
            print(f"    [{issue.category}] {issue.problem}")
            print(f"      File: {issue.file_path}")
            print(f"      Fix: {issue.suggested_fix}")
    if warnings:
        print(f"\n  WARNINGS ({len(warnings)}):")
        for issue in warnings:
            print(f"    [{issue.category}] {issue.problem}")
            print(f"      File: {issue.file_path}")
    if infos:
        print(f"\n  INFO ({len(infos)}):")
        for issue in infos:
            print(f"    [{issue.category}] {issue.problem}")
    if not inventory.validation_issues:
        print("  No issues found.")


def cmd_validate(args: list[str]) -> None:
    """Run full validation on an existing inventory."""
    if len(args) < 1:
        print("Usage: validate <inventory_json>", file=sys.stderr)
        sys.exit(1)

    json_path = args[0]
    inventory = load_inventory(json_path)

    validator = ValidatorService()
    new_issues = validator.validate(inventory)

    # Save updated inventory
    save_inventory(inventory, json_path)

    print(f"Validation complete. {len(new_issues)} new issues found.")
    for issue in new_issues:
        print(f"  [{issue.severity}] [{issue.category}] {issue.problem}")
        print(f"    File: {issue.file_path}")
        print(f"    Fix: {issue.suggested_fix}")

    total = len(inventory.validation_issues)
    errors = len([i for i in inventory.validation_issues if i.severity == "ERROR"])
    warnings = len([i for i in inventory.validation_issues if i.severity == "WARNING"])
    print(f"\nTotal issues: {total} ({errors} errors, {warnings} warnings)")


def cmd_issues(args: list[str]) -> None:
    """List all validation issues."""
    if len(args) < 1:
        print("Usage: issues <inventory_json>", file=sys.stderr)
        sys.exit(1)

    inventory = load_inventory(args[0])

    if not inventory.validation_issues:
        print("No validation issues found.")
        return

    for i, issue in enumerate(inventory.validation_issues, 1):
        print(f"Issue {i}: [{issue.severity}] [{issue.category}]")
        print(f"  File: {issue.file_path}")
        print(f"  Problem: {issue.problem}")
        print(f"  Fix: {issue.suggested_fix}")
        print()


def cmd_packages(args: list[str]) -> None:
    """List all packages with orchestration type."""
    if len(args) < 1:
        print("Usage: packages <inventory_json>", file=sys.stderr)
        sys.exit(1)

    inventory = load_inventory(args[0])

    for pkg in inventory.packages:
        print(f"{pkg.name} | Type: {pkg.orchestration_type or 'UNKNOWN'} | "
              f"dbt projects: {len(pkg.dbt_projects)} | "
              f"Status: {pkg.deploy_status}")


def cmd_dbt_projects(args: list[str]) -> None:
    """List all dbt projects with deployment names."""
    if len(args) < 1:
        print("Usage: dbt-projects <inventory_json>", file=sys.stderr)
        sys.exit(1)

    inventory = load_inventory(args[0])

    for pkg in inventory.packages:
        for proj in pkg.dbt_projects:
            deploy_name = proj.dbt_project_name or proj.folder_name
            mismatch = " [NAME MISMATCH]" if (
                proj.dbt_project_name and proj.dbt_project_name != proj.folder_name
            ) else ""
            print(
                f"{pkg.name}/{proj.folder_name} -> deploy as '{deploy_name}'"
                f" | {proj.model_count} models{mismatch}"
            )


def cmd_deploy_order(args: list[str]) -> None:
    """Show recommended deployment order."""
    if len(args) < 1:
        print("Usage: deploy-order <inventory_json>", file=sys.stderr)
        sys.exit(1)

    inventory = load_inventory(args[0])

    step = 1

    if inventory.etl_config_components:
        print(f"Step {step}: Deploy etl_configuration objects")
        for comp in inventory.etl_config_components:
            print(f"  {step}.{inventory.etl_config_components.index(comp)+1} "
                  f"[{comp.category}] {comp.name} <- {comp.file_path}")
        step += 1

    if inventory.packages:
        # dbt projects first
        print(f"\nStep {step}: Deploy dbt projects (via snow dbt deploy)")
        for pkg in inventory.packages:
            for proj in pkg.dbt_projects:
                deploy_name = proj.dbt_project_name or proj.folder_name
                print(f"  snow dbt deploy --schema <SCHEMA> --database <DATABASE> "
                      f"--force {deploy_name}")
        step += 1

        # Then orchestration
        print(f"\nStep {step}: Deploy orchestration SQL")
        for pkg in inventory.packages:
            if pkg.orchestration_file:
                print(f"  Execute: {pkg.orchestration_file} [{pkg.orchestration_type}]")
        step += 1


def cmd_stats(args: list[str]) -> None:
    """Show summary statistics."""
    if len(args) < 1:
        print("Usage: stats <inventory_json>", file=sys.stderr)
        sys.exit(1)

    inventory = load_inventory(args[0])

    total_models = sum(
        proj.model_count
        for pkg in inventory.packages
        for proj in pkg.dbt_projects
    )
    total_macros = sum(
        proj.macro_count
        for pkg in inventory.packages
        for proj in pkg.dbt_projects
    )

    print(f"Packages: {len(inventory.packages)}")
    print(f"  TASK-based: {len(inventory.task_based_packages)}")
    print(f"  PROCEDURE-based: {len(inventory.procedure_based_packages)}")
    print(f"dbt Projects: {inventory.total_dbt_projects}")
    print(f"Total Models: {total_models}")
    print(f"Total Macros: {total_macros}")
    print(f"etl_config Components: {len(inventory.etl_config_components)}")
    print(f"EXECUTE DBT PROJECT refs: {len(inventory.all_execute_dbt_refs)}")
    print(f"Validation Issues: {len(inventory.validation_issues)}")
    print(f"  Errors: {len([i for i in inventory.validation_issues if i.severity == 'ERROR'])}")
    print(f"  Warnings: {len([i for i in inventory.validation_issues if i.severity == 'WARNING'])}")
    print(f"  Info: {len([i for i in inventory.validation_issues if i.severity == 'INFO'])}")


COMMANDS = {
    "scan": cmd_scan,
    "summary": cmd_summary,
    "validate": cmd_validate,
    "issues": cmd_issues,
    "packages": cmd_packages,
    "dbt-projects": cmd_dbt_projects,
    "deploy-order": cmd_deploy_order,
    "stats": cmd_stats,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: python -m replatform_scanner <command> [args]")
        print()
        print("Commands:")
        print("  scan <etl_dir> <output_json>   Scan Replatform output directory")
        print("  summary <json>                 Print human-readable summary")
        print("  validate <json>                Run validation checks")
        print("  issues <json>                  List all validation issues")
        print("  packages <json>                List packages with orchestration type")
        print("  dbt-projects <json>            List dbt projects with deploy names")
        print("  deploy-order <json>            Show recommended deployment order")
        print("  stats <json>                   Show statistics")
        sys.exit(0)

    command = sys.argv[1]
    if command not in COMMANDS:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(f"Available commands: {', '.join(COMMANDS.keys())}", file=sys.stderr)
        sys.exit(1)

    try:
        COMMANDS[command](sys.argv[2:])
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
