"""
Unit tests for scripts/a11y_audit.py: verifies GOOD_PAGE passes with zero issues
and each rule A11Y-01..22 and R-01..08 triggers when broken (P10).
"""

import pytest

from scripts.a11y_audit import audit_html

pytestmark = [pytest.mark.a11y, pytest.mark.responsive]

GOOD_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EMP Test Page</title>
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to main content</a>
  <header>
    <nav class="navbar navbar-expand-lg" aria-label="Main">
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#mainNav" aria-controls="mainNav" aria-expanded="false" aria-label="Toggle navigation"></button>
      <div id="mainNav" class="collapse navbar-collapse">
        <a class="nav-link" href="/dashboard">Dashboard</a>
      </div>
    </nav>
  </header>
  <main id="main-content" tabindex="-1">
    <h1>Page Heading</h1>
    <div aria-live="polite">
      <div class="alert alert-success" role="alert">Saved!</div>
    </div>
    <form method="post">
      <label for="email">Email (required)</label>
      <input id="email" name="email" type="email" autocomplete="email" aria-describedby="email-help">
      <div id="email-help">Enter your institutional email.</div>
      <button type="submit" class="btn btn-primary btn-xs-block">Save</button>
    </form>
    <div class="table-responsive">
      <table class="table table-stack" role="table">
        <caption>Courses</caption>
        <thead role="rowgroup">
          <tr role="row">
            <th scope="col" role="columnheader">Code</th>
            <th scope="col" role="columnheader">Actions</th>
          </tr>
        </thead>
        <tbody role="rowgroup">
          <tr role="row">
            <td role="cell" data-label="Code"><span class="badge text-bg-success">Active</span></td>
            <td role="cell" data-label="Actions" class="td-actions">
              <button type="button" class="btn btn-sm btn-primary btn-xs-block">Edit</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="modal" id="confirmModal" role="dialog" aria-labelledby="modalTitle">
      <h2 id="modalTitle">Confirm</h2>
      <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
    </div>
  </main>
  <footer>EMP Footer</footer>
</body>
</html>
"""


def test_good_page_has_zero_issues():
    """GOOD_PAGE triggers zero accessibility or responsive issues."""
    assert audit_html(GOOD_PAGE) == []


@pytest.mark.parametrize(
    "rule_id,mutator",
    [
        ("A11Y-01", lambda s: s.replace('lang="en"', "")),
        ("A11Y-02", lambda s: s.replace("<title>EMP Test Page</title>", "<title></title>")),
        ("A11Y-03", lambda s: s.replace("<h1>Page Heading</h1>", "<h1>One</h1><h1>Two</h1>")),
        (
            "A11Y-04",
            lambda s: s.replace(
                "<h1>Page Heading</h1>", "<h1>Page Heading</h1><h3>Skipped H2</h3>"
            ),
        ),
        ("A11Y-05", lambda s: s.replace("<footer", "<div").replace("</footer>", "</div>")),
        ("A11Y-06", lambda s: s.replace('href="#main-content"', 'href="#missing-target"')),
        ("A11Y-07", lambda s: s.replace('<label for="email">Email (required)</label>', "")),
        ("A11Y-08", lambda s: s.replace(">Save</button>", ' title="Save"></button>')),
        (
            "A11Y-09",
            lambda s: s.replace("<h1>Page Heading</h1>", '<h1>Page Heading</h1><img src="x.png">'),
        ),
        ("A11Y-10", lambda s: s.replace('id="email-help"', 'id="email"')),
        (
            "A11Y-11",
            lambda s: s.replace('aria-describedby="email-help"', 'aria-describedby="ghost-id"'),
        ),
        ("A11Y-12", lambda s: s.replace('scope="col"', "")),
        ("A11Y-13", lambda s: s.replace('tabindex="-1"', 'tabindex="3"')),
        (
            "A11Y-14",
            lambda s: s.replace('href="/dashboard"', 'href="https://example.com" target="_blank"'),
        ),
        ("A11Y-15", lambda s: s.replace("initial-scale=1", "initial-scale=1, user-scalable=no")),
        ("A11Y-16", lambda s: s.replace('autocomplete="email"', "")),
        (
            "A11Y-17",
            lambda s: s.replace(
                "<h1>Page Heading</h1>", "<h1>Page Heading</h1><iframe src='about:blank'></iframe>"
            ),
        ),
        ("A11Y-18", lambda s: s.replace('role="dialog"', "")),
        ("A11Y-19", lambda s: s.replace('aria-live="polite"', "")),
        ("A11Y-20", lambda s: s.replace('aria-expanded="false"', "")),
        ("A11Y-21", lambda s: s.replace(">Active</span>", "></span>")),
        (
            "A11Y-22",
            lambda s: s.replace(
                ">Active</span>", ">Active</span><input type='text' name='unlabeled'>"
            ),
        ),
        ("R-01", lambda s: s.replace('name="viewport"', 'name="other"')),
        ("R-02", lambda s: s.replace('data-label="Code"', "")),
        ("R-03", lambda s: s.replace('class="table-responsive"', 'class="plain-wrapper"')),
        (
            "R-04",
            lambda s: s.replace(
                "<h1>Page Heading</h1>", '<h1 style="width: 600px">Page Heading</h1>'
            ),
        ),
        (
            "R-05",
            lambda s: s.replace(
                'class="btn btn-sm btn-primary btn-xs-block"', 'class="btn btn-sm btn-primary"'
            ),
        ),
        ("R-07", lambda s: s.replace('aria-controls="mainNav"', "")),
        ("R-08", lambda s: s.replace('role="columnheader"', 'role="columnheader" class="d-none"')),
    ],
)
def test_each_rule_fires_when_mutated(rule_id, mutator):
    """Mutating GOOD_PAGE to violate a single rule triggers that rule ID."""
    bad_html = mutator(GOOD_PAGE)
    issues = audit_html(bad_html)
    triggered = {i.rule for i in issues}
    assert rule_id in triggered, f"Expected {rule_id} in {triggered}"


def test_r06_admin_sidebar_rule():
    """Admin pages without #adminSidebar.offcanvas-lg trigger R-06."""
    issues = audit_html(GOOD_PAGE, page="/admin/dashboard")
    assert any(i.rule == "R-06" for i in issues)


def test_issue_ordering_is_deterministic():
    """audit_html returns issues in deterministic sorted order."""
    bad = GOOD_PAGE.replace('lang="en"', "").replace('scope="col"', "")
    assert audit_html(bad) == audit_html(bad)
