"""
FILE PURPOSE: Tests for the closing tools: report_facts.py and build_submission.sh.
"""

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from app.extensions import db
from scripts.report_facts import endpoints_table, er_mermaid, libraries_table, main

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def test_libraries_table_parses_pins_and_tiers():
    repo_root = Path(__file__).resolve().parent.parent.parent
    req_files = [
        repo_root / "requirements.txt",
        repo_root / "requirements-tier2.txt",
        repo_root / "requirements-dev.txt",
    ]
    libs = libraries_table(req_files)
    assert len(libs) > 0

    pkg_map = {lib["package"].lower(): lib for lib in libs}
    assert "flask" in pkg_map
    assert pkg_map["flask"]["tier"] == "1"

    assert "flask-login" in pkg_map
    assert pkg_map["flask-login"]["tier"] == "2"

    assert "reportlab" in pkg_map
    assert pkg_map["reportlab"]["tier"] == "2"
    assert pkg_map["reportlab"]["version"] != ""


def test_endpoints_table_contains_known_routes(app):
    eps = endpoints_table(app)
    paths = {e["path"] for e in eps}

    # Should contain key HTML and API routes
    assert any("/student/slots/" in p and "/book" in p for p in paths)
    assert "/api/v1/bookings" in paths
    assert any("/student/bookings/" in p and "/scorecard.pdf" in p for p in paths)


def test_er_mermaid_lists_all_tables_and_foreign_keys(app):
    with app.app_context():
        mmd = er_mermaid(db.metadata)
        assert "erDiagram" in mmd
        assert len(db.metadata.tables) == 13
        for table_name in db.metadata.tables:
            assert table_name in mmd
        assert "||--o{" in mmd


def test_output_deterministic_with_no_date(tmp_path):
    dir1 = tmp_path / "run1"
    dir2 = tmp_path / "run2"

    rc1 = main(["--no-date", "--out-dir", str(dir1)])
    rc2 = main(["--no-date", "--out-dir", str(dir2)])
    assert rc1 == 0
    assert rc2 == 0

    f1_mmd = (dir1 / "er_diagram.mmd").read_text(encoding="utf-8")
    f2_mmd = (dir2 / "er_diagram.mmd").read_text(encoding="utf-8")
    assert f1_mmd == f2_mmd

    f1_facts = (dir1 / "generated_facts.md").read_text(encoding="utf-8")
    f2_facts = (dir2 / "generated_facts.md").read_text(encoding="utf-8")
    assert f1_facts == f2_facts


def test_main_writes_both_files_to_tmp_dir(tmp_path):
    rc = main(["--out-dir", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "er_diagram.mmd").is_file()
    assert (tmp_path / "generated_facts.md").is_file()
    assert (tmp_path / "generated_facts.md").stat().st_size > 0


# --- Shell tests for build_submission.sh ---


@pytest.fixture
def temp_git_repo(tmp_path):
    if not shutil.which("git") or not shutil.which("unzip"):
        pytest.skip("git or unzip not available")

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Initialise git repo
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=repo_dir, check=True)

    # Copy build_submission.sh
    script_source = (
        Path(__file__).resolve().parent.parent.parent / "scripts" / "build_submission.sh"
    )
    scripts_dir = repo_dir / "scripts"
    scripts_dir.mkdir()
    shutil.copy(script_source, scripts_dir / "build_submission.sh")
    (scripts_dir / "build_submission.sh").chmod(0o755)

    # Populate all required files
    required = [
        "README.md",
        "requirements.txt",
        "requirements-tier2.txt",
        "Dockerfile",
        "docker-compose.yml",
        "Makefile",
        ".env.example",
        "app/__init__.py",
        "app/models/user.py",
        "app/services/booking_engine.py",
        "app/blueprints/api_v1/__init__.py",
        "app/services/scorecard.py",
        "tests/test_placeholder.py",
        "docs/ai_llm_declaration.md",
        "docs/er_diagram.mmd",
        "docs/report/report_draft.md",
    ]
    for r in required:
        fp = repo_dir / r
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text("sample content\n", encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True)

    return repo_dir


def test_zip_has_emp_prefix_and_only_tracked_files(temp_git_repo):
    res = subprocess.run(
        ["bash", "scripts/build_submission.sh"], cwd=temp_git_repo, capture_output=True, text=True
    )
    assert res.returncode == 0
    assert "SUBMISSION ZIP OK" in res.stdout

    zip_path = temp_git_repo / "submission_core.zip"
    assert zip_path.is_file()

    unzip_res = subprocess.run(
        ["unzip", "-l", "submission_core.zip"], cwd=temp_git_repo, capture_output=True, text=True
    )
    for line in unzip_res.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0].isdigit() and not parts[3].startswith("-"):
            entry = parts[3]
            assert entry.startswith("emp/"), f"Entry {entry} does not start with emp/"


def test_forbidden_entries_fail_the_script(temp_git_repo):
    # Add a forbidden entry: .env
    forbidden = temp_git_repo / ".env"
    forbidden.write_text("SECRET=123", encoding="utf-8")
    subprocess.run(["git", "add", "-f", ".env"], cwd=temp_git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Add forbidden"], cwd=temp_git_repo, check=True)

    res = subprocess.run(
        ["bash", "scripts/build_submission.sh"], cwd=temp_git_repo, capture_output=True, text=True
    )
    assert res.returncode == 1
    assert "Forbidden entry found" in res.stdout


def test_secret_pattern_fails(temp_git_repo):
    # Add a pyc file
    pyc_file = temp_git_repo / "app" / "bad.pyc"
    pyc_file.write_text("bytecode", encoding="utf-8")
    subprocess.run(["git", "add", "-f", "app/bad.pyc"], cwd=temp_git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Add pyc"], cwd=temp_git_repo, check=True)

    res = subprocess.run(
        ["bash", "scripts/build_submission.sh"], cwd=temp_git_repo, capture_output=True, text=True
    )
    assert res.returncode == 1
    assert "Forbidden entry found" in res.stdout


def test_dirty_tree_refused_without_flag(temp_git_repo):
    (temp_git_repo / "README.md").write_text("dirty edit\n", encoding="utf-8")
    res = subprocess.run(
        ["bash", "scripts/build_submission.sh"], cwd=temp_git_repo, capture_output=True, text=True
    )
    assert res.returncode == 1
    assert "Working tree is dirty" in res.stdout


def test_same_commit_same_sha256(temp_git_repo):
    res1 = subprocess.run(
        ["bash", "scripts/build_submission.sh"], cwd=temp_git_repo, capture_output=True, text=True
    )
    assert res1.returncode == 0
    sha1 = hashlib.sha256((temp_git_repo / "submission_core.zip").read_bytes()).hexdigest()

    (temp_git_repo / "submission_core.zip").unlink()

    res2 = subprocess.run(
        ["bash", "scripts/build_submission.sh"], cwd=temp_git_repo, capture_output=True, text=True
    )
    assert res2.returncode == 0
    sha2 = hashlib.sha256((temp_git_repo / "submission_core.zip").read_bytes()).hexdigest()

    assert sha1 == sha2


def test_missing_required_entry_reported(temp_git_repo):
    subprocess.run(["git", "rm", "README.md"], cwd=temp_git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Remove readme"], cwd=temp_git_repo, check=True)

    res = subprocess.run(
        ["bash", "scripts/build_submission.sh"], cwd=temp_git_repo, capture_output=True, text=True
    )
    assert res.returncode == 1
    assert "Required entry missing" in res.stdout
