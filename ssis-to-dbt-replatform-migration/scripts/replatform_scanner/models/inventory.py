from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ValidationIssue:
    severity: str  # ERROR, WARNING, INFO
    category: str  # PLACEHOLDER, NAME_MISMATCH, SCHEMA_MISMATCH, SOURCE_SCHEMA_MISMATCH, MISSING_FILE, ORPHAN_TASK, DANGLING_REF, UNSUPPORTED_FIELD, TASK_SYNTAX, ORCH_SCHEMA_PREFIX, ORCH_WAREHOUSE, PROC_EXECUTE_DBT, PARTIAL_DATE_CAST
    file_path: str
    problem: str
    suggested_fix: str

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "category": self.category,
            "file_path": self.file_path,
            "problem": self.problem,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class DbtProjectInfo:
    """Represents a single dbt project generated from a Data Flow Task."""
    name: str
    folder_name: str
    path: str
    package_name: str
    has_dbt_project_yml: bool = False
    has_profiles_yml: bool = False
    has_sources_yml: bool = False
    dbt_project_name: Optional[str] = None  # name field from dbt_project.yml
    model_count: int = 0
    staging_models: List[str] = field(default_factory=list)
    intermediate_models: List[str] = field(default_factory=list)
    mart_models: List[str] = field(default_factory=list)
    macro_count: int = 0
    test_count: int = 0
    deploy_status: str = "PENDING"  # PENDING, DEPLOYED, FAILED

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "folder_name": self.folder_name,
            "path": self.path,
            "package_name": self.package_name,
            "has_dbt_project_yml": self.has_dbt_project_yml,
            "has_profiles_yml": self.has_profiles_yml,
            "has_sources_yml": self.has_sources_yml,
            "dbt_project_name": self.dbt_project_name,
            "model_count": self.model_count,
            "staging_models": self.staging_models,
            "intermediate_models": self.intermediate_models,
            "mart_models": self.mart_models,
            "macro_count": self.macro_count,
            "test_count": self.test_count,
            "deploy_status": self.deploy_status,
        }


@dataclass
class PackageInfo:
    """Represents a converted SSIS package."""
    name: str
    path: str
    orchestration_file: Optional[str] = None
    orchestration_type: Optional[str] = None  # TASK, PROCEDURE, UNKNOWN
    dbt_projects: List[DbtProjectInfo] = field(default_factory=list)
    execute_dbt_project_refs: List[str] = field(default_factory=list)
    task_names: List[str] = field(default_factory=list)
    has_script_sql: bool = False
    deploy_status: str = "PENDING"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "orchestration_file": self.orchestration_file,
            "orchestration_type": self.orchestration_type,
            "dbt_projects": [p.to_dict() for p in self.dbt_projects],
            "execute_dbt_project_refs": self.execute_dbt_project_refs,
            "task_names": self.task_names,
            "has_script_sql": self.has_script_sql,
            "deploy_status": self.deploy_status,
        }


@dataclass
class EtlConfigComponent:
    """Represents a component in etl_configuration/."""
    name: str
    category: str  # table, function, procedure
    file_path: str
    deploy_status: str = "PENDING"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "file_path": self.file_path,
            "deploy_status": self.deploy_status,
        }


@dataclass
class ReplatformInventory:
    """Complete inventory of a Replatform output directory."""
    etl_output_dir: str
    etl_config_components: List[EtlConfigComponent] = field(default_factory=list)
    packages: List[PackageInfo] = field(default_factory=list)
    validation_issues: List[ValidationIssue] = field(default_factory=list)
    scan_timestamp: Optional[str] = None

    @property
    def total_dbt_projects(self) -> int:
        return sum(len(p.dbt_projects) for p in self.packages)

    @property
    def task_based_packages(self) -> List[PackageInfo]:
        return [p for p in self.packages if p.orchestration_type == "TASK"]

    @property
    def procedure_based_packages(self) -> List[PackageInfo]:
        return [p for p in self.packages if p.orchestration_type == "PROCEDURE"]

    @property
    def all_execute_dbt_refs(self) -> List[str]:
        refs = []
        for pkg in self.packages:
            refs.extend(pkg.execute_dbt_project_refs)
        return refs

    @property
    def all_dbt_project_names(self) -> List[str]:
        names = []
        for pkg in self.packages:
            for proj in pkg.dbt_projects:
                names.append(proj.dbt_project_name or proj.folder_name)
        return names

    def to_dict(self) -> dict:
        return {
            "etl_output_dir": self.etl_output_dir,
            "scan_timestamp": self.scan_timestamp,
            "etl_config_components": [c.to_dict() for c in self.etl_config_components],
            "packages": [p.to_dict() for p in self.packages],
            "validation_issues": [i.to_dict() for i in self.validation_issues],
            "summary": {
                "total_packages": len(self.packages),
                "total_dbt_projects": self.total_dbt_projects,
                "task_based_count": len(self.task_based_packages),
                "procedure_based_count": len(self.procedure_based_packages),
                "etl_config_count": len(self.etl_config_components),
                "issue_count": len(self.validation_issues),
                "error_count": len([i for i in self.validation_issues if i.severity == "ERROR"]),
                "warning_count": len([i for i in self.validation_issues if i.severity == "WARNING"]),
            },
        }
