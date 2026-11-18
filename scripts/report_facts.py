"""
FILE PURPOSE: Generates the factual parts of the final report from the real project:
libraries and versions, API endpoint list and the ER diagram.
Output goes to docs/report/generated_facts.md and docs/er_diagram.mmd.
Offline, no third-party dependency.
"""

import argparse
import importlib.metadata
import os
import sys
from collections.abc import Iterable
from datetime import UTC
from pathlib import Path

PURPOSE_MAP = {
    "flask": "Web framework and routing core",
    "flask-sqlalchemy": "SQLAlchemy ORM integration and session management",
    "sqlalchemy": "Database abstraction and ORM",
    "flask-wtf": "Form handling and CSRF protection",
    "wtforms": "Form validation and rendering engine",
    "flask-login": "User session management and authentication",
    "flask-mail": "SMTP transactional email integration",
    "reportlab": "PDF scorecard document generation",
    "email-validator": "Email address format validation",
    "click": "CLI command integration",
    "werkzeug": "WSGI utilities and password hashing",
    "jinja2": "Template rendering engine",
    "pytest": "Unit and integration test runner",
    "pytest-cov": "Test coverage reporting",
    "pypdf": "PDF text extraction for verification tests",
    "playwright": "End-to-end browser automation",
    "pytest-playwright": "Playwright integration for pytest",
    "ruff": "Fast Python linter",
    "black": "Deterministic code formatter",
    "aiosmtpd": "In-process SMTP test server sink",
}


def libraries_table(requirement_files: Iterable[str | Path]) -> list[dict[str, str]]:
    """
    Parse requirement files to return package metadata rows.
    """
    rows: list[dict[str, str]] = []
    seen = set()

    for rf in requirement_files:
        path = Path(rf)
        if not path.is_file():
            continue

        filename = path.name.lower()
        if "tier2" in filename:
            tier = "2"
        elif "dev" in filename:
            tier = "dev"
        else:
            tier = "1"

        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-r"):
                    continue

                pkg = line
                ver = ""
                if "==" in line:
                    parts = line.split("==", 1)
                    pkg = parts[0].strip()
                    ver = parts[1].strip()
                elif ">=" in line:
                    parts = line.split(">=", 1)
                    pkg = parts[0].strip()
                    ver = ">=" + parts[1].strip()

                norm_name = pkg.lower()
                if norm_name in seen:
                    continue
                seen.add(norm_name)

                purpose = PURPOSE_MAP.get(norm_name, "see documentation")
                licence = ""
                try:
                    meta = importlib.metadata.metadata(pkg)
                    licence = meta.get("License", "") or ""
                except Exception:
                    licence = ""

                rows.append(
                    {
                        "package": pkg,
                        "version": ver,
                        "tier": tier,
                        "purpose": purpose,
                        "licence": licence,
                    }
                )

    return sorted(rows, key=lambda r: (r["tier"], r["package"].lower()))


def endpoints_table(app) -> list[dict[str, str]]:
    """
    Extract HTTP endpoints from app.url_map, excluding static routes.
    """
    routes: list[dict[str, str]] = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static" or rule.rule.startswith("/static"):
            continue

        methods = [m for m in rule.methods if m not in ("HEAD", "OPTIONS")]
        view_func = app.view_functions.get(rule.endpoint)
        doc = ""
        if view_func and view_func.__doc__:
            doc = view_func.__doc__.strip().split("\n")[0].strip()

        bp = rule.endpoint.split(".")[0] if "." in rule.endpoint else ""

        for method in sorted(methods):
            routes.append(
                {
                    "method": method,
                    "path": rule.rule,
                    "endpoint": rule.endpoint,
                    "blueprint": bp,
                    "summary": doc,
                }
            )

    return sorted(routes, key=lambda r: (r["path"], r["method"]))


def er_mermaid(metadata) -> str:
    """
    Generate deterministic Mermaid erDiagram from SQLAlchemy metadata.
    """
    lines = ["erDiagram"]
    tables = sorted(metadata.tables.values(), key=lambda t: t.name)

    # Entities and columns
    for table in tables:
        lines.append(f"    {table.name} {{")
        for col in table.columns:
            col_type = str(col.type).split("(")[0].upper()
            keys = []
            if col.primary_key:
                keys.append("PK")
            if col.foreign_keys:
                keys.append("FK")
            if col.unique:
                keys.append("UK")
            key_str = f" {','.join(keys)}" if keys else ""
            lines.append(f"        {col_type} {col.name}{key_str}")
        lines.append("    }")

    # Relationships
    relationships = []
    for table in tables:
        for fk in table.foreign_keys:
            parent_table = fk.column.table.name
            child_table = table.name
            relationships.append(f'    {parent_table} ||--o{{ {child_table} : "{fk.parent.name}"')

    for rel in sorted(relationships):
        lines.append(rel)

    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate report factual artifacts.")
    parser.add_argument(
        "--no-date", action="store_true", help="Omit generation timestamp for deterministic output"
    )
    parser.add_argument("--out-dir", default=None, help="Output directory")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    out_dir = Path(args.out_dir) if args.out_dir else repo_root / "docs"

    req_files = [
        repo_root / "requirements.txt",
        repo_root / "requirements-tier2.txt",
        repo_root / "requirements-dev.txt",
    ]
    libs = libraries_table(req_files)

    os.environ["FLASK_CONFIG"] = "testing"
    from app import create_app
    from app.extensions import db

    app = create_app("testing", test_config={"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})

    with app.app_context():
        db.create_all()
        eps = endpoints_table(app)
        er_mmd = er_mermaid(db.metadata)
        table_count = len(db.metadata.tables)

    # Write docs/er_diagram.mmd
    er_path = out_dir / "er_diagram.mmd"
    er_path.parent.mkdir(parents=True, exist_ok=True)
    with open(er_path, "w", encoding="utf-8") as f:
        f.write(er_mmd)

    # Separate endpoints
    html_eps = [e for e in eps if not e["path"].startswith("/api/v1")]
    api_eps = [e for e in eps if e["path"].startswith("/api/v1")]

    # Write docs/report/generated_facts.md
    facts_path = (
        (out_dir / "report" / "generated_facts.md")
        if not args.out_dir
        else (out_dir / "generated_facts.md")
    )
    facts_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# System Facts and Architecture")
    lines.append("")
    if not args.no_date:
        from datetime import datetime

        lines.append(f"*Generated on {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}*")
        lines.append("")

    lines.append("## 1. Libraries and Dependencies")
    lines.append("")
    lines.append("| Package | Version | Tier | Purpose | Licence |")
    lines.append("| :--- | :--- | :--- | :--- | :--- |")
    for lib in libs:
        lines.append(
            f"| {lib['package']} | {lib['version']} | {lib['tier']} | {lib['purpose']} | {lib['licence']} |"
        )
    lines.append("")

    lines.append("## 2. Endpoints")
    lines.append("")
    lines.append("### Tier 1 HTML Routes")
    lines.append("")
    lines.append("| Method | Path | Endpoint | Blueprint | Summary |")
    lines.append("| :--- | :--- | :--- | :--- | :--- |")
    for ep in html_eps:
        lines.append(
            f"| {ep['method']} | {ep['path']} | {ep['endpoint']} | {ep['blueprint']} | {ep['summary']} |"
        )
    lines.append("")

    lines.append("### Tier 2 API Routes")
    lines.append("")
    lines.append("| Method | Path | Endpoint | Blueprint | Summary |")
    lines.append("| :--- | :--- | :--- | :--- | :--- |")
    for ep in api_eps:
        lines.append(
            f"| {ep['method']} | {ep['path']} | {ep['endpoint']} | {ep['blueprint']} | {ep['summary']} |"
        )
    lines.append("")

    lines.append("## 3. Entity-Relationship Diagram")
    lines.append("")
    lines.append(f"Total tables: {table_count}")
    lines.append("")
    lines.append("```mermaid")
    lines.append(er_mmd.strip())
    lines.append("```")
    lines.append("")

    with open(facts_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Generated: {er_path}")
    print(f"Generated: {facts_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
