"""
tests/integration/test_admin_access_control.py - Dynamic access control matrix for /admin routes.
"""


def test_admin_routes_reject_non_admins(client, app, make_user, make_admin, login):
    """Verify that all main /admin endpoints strictly reject anonymous and non-admin users."""
    student = make_user(role="student")
    examiner = make_user(role="examiner", approval_status="approved")
    admin = make_admin(must_change_password=False)

    admin_endpoints = [
        "/admin/dashboard",
        "/admin/courses",
        "/admin/examinations",
        "/admin/examiners",
        "/admin/students",
        "/admin/slots",
        "/admin/bookings",
        "/admin/search",
        "/admin/history",
    ]

    for url in admin_endpoints:
        # 1. Anonymous -> 302 to /login
        anon_res = client.get(url, follow_redirects=False)
        assert anon_res.status_code == 302
        assert anon_res.headers["Location"].endswith("/login")

        # 2. Student -> 403 Forbidden
        login(student.email, "Passw0rd123!")
        stu_res = client.get(url)
        assert stu_res.status_code == 403
        client.post("/logout")

        # 3. Examiner -> 403 Forbidden
        login(examiner.email, "Passw0rd123!")
        ex_res = client.get(url)
        assert ex_res.status_code == 403
        client.post("/logout")

        # 4. Admin -> 200 OK
        login(admin.email, "Passw0rd123!")
        adm_res = client.get(url)
        assert adm_res.status_code == 200
        client.post("/logout")
