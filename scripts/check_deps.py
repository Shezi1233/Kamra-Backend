"""Verify that every third-party import in app/ and api/ is declared.

Run from anywhere:

    python scripts/check_deps.py

The script only uses the standard library so it works in a clean checkout.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LOCAL_PACKAGES = {"app", "api", "scripts"}
IGNORED_IMPORTS = {"__future__"}

# Import name -> PyPI distribution name. Only entries that differ are needed,
# but keeping common runtime packages here makes the output predictable.
IMPORT_TO_DISTRIBUTION = {
    "pydantic_settings": "pydantic-settings",
    "email_validator": "email-validator",
    "python_multipart": "python-multipart",
    "multipart": "python-multipart",
    "dotenv": "python-dotenv",
    "yaml": "pyyaml",
    "PIL": "pillow",
    "jwt": "pyjwt",
    "psycopg2": "psycopg2-binary",
    "psycopg": "psycopg",
    "starlette": "starlette",
    "sqlalchemy": "sqlalchemy",
    "fastapi": "fastapi",
    "httpx": "httpx",
    "openai": "openai",
    "slowapi": "slowapi",
    "bcrypt": "bcrypt",
    "boto3": "boto3",
    "alembic": "alembic",
    "uvicorn": "uvicorn",
    "pydantic": "pydantic",
    "cryptography": "cryptography",
    "pymysql": "pymysql",
}

_REQUIREMENT_NAME = re.compile(r"^([A-Za-z0-9_.-]+)")


def normalize_distribution(name: str) -> str:
    return name.strip().lower().replace("_", "-").replace(".", "-")


def declared_distributions() -> set[str]:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle).get("project", {})
    declared: set[str] = set()
    for requirement in project.get("dependencies", []):
        match = _REQUIREMENT_NAME.match(str(requirement).strip())
        if match:
            declared.add(normalize_distribution(match.group(1)))
    return declared


def imported_modules() -> set[str]:
    modules: set[str] = set()
    for folder in ("app", "api"):
        base = ROOT / folder
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        modules.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        continue
                    if node.module:
                        modules.add(node.module.split(".")[0])
    return modules


def distribution_for(module: str) -> str:
    return IMPORT_TO_DISTRIBUTION.get(module, module)


def main() -> int:
    declared = declared_distributions()
    modules = imported_modules()

    third_party = sorted(
        module
        for module in modules
        if module
        and module not in sys.stdlib_module_names
        and module not in LOCAL_PACKAGES
        and module not in IGNORED_IMPORTS
    )

    missing = sorted(
        {
            f"{module} ({distribution_for(module)})"
            for module in third_party
            if normalize_distribution(distribution_for(module)) not in declared
        }
    )

    print(
        f"Dependency check: {len(third_party)} third-party imports across "
        f"app/ and api/."
    )
    if missing:
        print("Missing from [project].dependencies in pyproject.toml:")
        for item in missing:
            print(f"  - {item}")
        return 1

    print("OK: all direct third-party imports are declared.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
