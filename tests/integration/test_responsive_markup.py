"""
Structural responsive checks over rendered templates (P10).
"""

import pathlib

import pytest

from scripts.a11y_audit import audit_html

pytestmark = pytest.mark.responsive


def test_base_and_role_templates_have_responsive_wiring():
    """base.html and role base templates include responsive.css, drawer, and navbar togglers."""
    base_html = pathlib.Path("app/templates/base.html").read_text(encoding="utf-8")
    admin_html = pathlib.Path("app/templates/admin/base_admin.html").read_text(encoding="utf-8")
    exam_html = pathlib.Path("app/templates/examiner/base_examiner.html").read_text(
        encoding="utf-8"
    )
    stu_html = pathlib.Path("app/templates/student/base_student.html").read_text(encoding="utf-8")

    assert 'content="width=device-width, initial-scale=1"' in base_html
    assert "css/app.css" in base_html
    assert "css/responsive.css" in base_html
    assert base_html.index("css/app.css") < base_html.index("css/responsive.css")
    assert "Skip to main content" in base_html

    assert 'id="adminSidebar"' in admin_html
    assert "offcanvas-lg" in admin_html
    assert 'data-bs-toggle="offcanvas"' in admin_html
    assert 'aria-controls="adminSidebar"' in admin_html

    for nav_tpl in (exam_html, stu_html):
        assert "navbar-expand-lg" in nav_tpl
        assert "navbar-toggler" in nav_tpl
        assert 'aria-controls="mainNav"' in nav_tpl
        assert 'aria-expanded="false"' in nav_tpl
        assert 'aria-label="Toggle navigation"' in nav_tpl


def test_public_pages_responsive_contract(client):
    """Public pages (/login, /register, /api/v1/docs) pass responsive rules R-01..R-08."""
    for url in ("/login", "/register", "/api/v1/docs"):
        resp = client.get(url)
        if resp.status_code != 200:
            continue
        html = resp.get_data(as_text=True)
        r_issues = [i for i in audit_html(html, page=url) if i.rule.startswith("R-")]
        assert r_issues == [], f"Responsive issues on {url}: {r_issues}"
