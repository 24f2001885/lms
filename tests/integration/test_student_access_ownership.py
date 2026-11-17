"""
FILE PURPOSE: Student routes are role-locked and ownership-scoped (risk R-4).
DEPENDS ON: tests/conftest.py (student_client, factories).
PROMPT FOR LLM IMPLEMENTATION:
1. URL matrix from app.url_map for rules starting /student: anonymous -> 302 /login; admin and examiner -> 403; inactive student -> 302 /account-inactive; student with must_change_password -> 302 /change-password; ready student -> not 403 and not 500. GET on POST-only routes returns 405.
2. Ownership with students A and B: B gets 404 for A's booking detail, cancel and result detail; B's lists never contain A's rows; B cannot book on behalf of A (the route takes no student id; assert there is no such parameter).
3. test_csrf_required_on_book_and_cancel with CSRF enabled.
DEBUGGING:
# print(f"[DEBUG] {method} {url} as {role} -> {response.status_code}")
OFFLINE DOCKER TEST CASES:
- The matrix covers every /student rule at collection time.
"""
"""
FILE PURPOSE: Integration access control and ownership tests for student routes.
"""


def test_anonymous_redirects_to_login(client):
    res = client.get("/student/dashboard")
    assert res.status_code == 302
    assert "/login" in res.headers.get("Location", "")


def test_student_dashboard_access(student_client):
    client, student = student_client
    res = client.get("/student/dashboard")
    assert res.status_code == 200
    assert b"Dashboard" in res.data