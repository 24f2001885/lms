"""
tests/integration/test_chart_pages.py - HTML markup and role access tests for chart pages and widgets.
"""

import pathlib
import re

import pytest


@pytest.mark.charts
def test_admin_page_roles(client, make_admin, make_examiner, make_student, login):
    admin = make_admin()
    examiner = make_examiner()
    student = make_student()

    # Anonymous -> 302
    res_anon = client.get("/admin/charts", follow_redirects=False)
    assert res_anon.status_code == 302
    assert res_anon.headers["Location"].endswith("/login")

    # Examiner -> 403
    login(examiner.email, "Passw0rd123!")
    res_ex = client.get("/admin/charts")
    assert res_ex.status_code == 403
    client.post("/logout")

    # Student -> 403
    login(student.email, "Passw0rd123!")
    res_stu = client.get("/admin/charts")
    assert res_stu.status_code == 403
    client.post("/logout")

    # Admin -> 200
    login(admin.email, "Passw0rd123!")
    res_adm = client.get("/admin/charts")
    assert res_adm.status_code == 200
    client.post("/logout")


@pytest.mark.charts
def test_examiner_page_roles(client, make_admin, make_examiner, make_student, login):
    admin = make_admin()
    approved_ex = make_examiner(approved=True)
    pending_ex = make_examiner(approved=False)
    student = make_student()

    # Approved examiner -> 200
    login(approved_ex.email, "Passw0rd123!")
    res_app = client.get("/examiner/charts")
    assert res_app.status_code == 200
    client.post("/logout")

    # Pending examiner -> 302 to /pending-approval
    login(pending_ex.email, "Passw0rd123!")
    res_pen = client.get("/examiner/charts", follow_redirects=False)
    assert res_pen.status_code == 302
    assert res_pen.headers["Location"].endswith("/pending-approval")
    client.post("/logout")

    # Student -> 403
    login(student.email, "Passw0rd123!")
    assert client.get("/examiner/charts").status_code == 403
    client.post("/logout")

    # Admin -> 403
    login(admin.email, "Passw0rd123!")
    assert client.get("/examiner/charts").status_code == 403
    client.post("/logout")


@pytest.mark.charts
def test_student_page_roles(client, make_admin, make_examiner, make_student, login):
    admin = make_admin()
    examiner = make_examiner()
    student = make_student()

    # Anonymous -> 302
    res_anon = client.get("/student/charts", follow_redirects=False)
    assert res_anon.status_code == 302

    # Student -> 200
    login(student.email, "Passw0rd123!")
    assert client.get("/student/charts").status_code == 200
    client.post("/logout")

    # Admin -> 403
    login(admin.email, "Passw0rd123!")
    assert client.get("/student/charts").status_code == 403
    client.post("/logout")

    # Examiner -> 403
    login(examiner.email, "Passw0rd123!")
    assert client.get("/student/charts").status_code == 403
    client.post("/logout")


@pytest.mark.charts
def test_card_counts(client, make_admin, make_examiner, make_student, login):
    admin = make_admin()
    examiner = make_examiner()
    student = make_student()

    # Admin: 5 cards
    login(admin.email, "Passw0rd123!")
    html_adm = client.get("/admin/charts").get_data(as_text=True)
    assert len(re.findall(r"<figure[^>]*class=[\"'][^\"']*chart-card", html_adm)) == 5
    client.post("/logout")

    # Examiner: 4 cards
    login(examiner.email, "Passw0rd123!")
    html_ex = client.get("/examiner/charts").get_data(as_text=True)
    assert len(re.findall(r"<figure[^>]*class=[\"'][^\"']*chart-card", html_ex)) == 4
    client.post("/logout")

    # Student: 3 cards
    login(student.email, "Passw0rd123!")
    html_stu = client.get("/student/charts").get_data(as_text=True)
    assert len(re.findall(r"<figure[^>]*class=[\"'][^\"']*chart-card", html_stu)) == 3
    client.post("/logout")


@pytest.mark.charts
def test_each_canvas_has_role_img_aria_label_and_data_attributes(client, make_admin, login):
    admin = make_admin()
    login(admin.email, "Passw0rd123!")
    html = client.get("/admin/charts").get_data(as_text=True)
    client.post("/logout")

    canvases = re.findall(r"<canvas[^>]*>", html)
    assert len(canvases) == 5
    for c in canvases:
        assert 'role="img"' in c
        assert 'aria-label="' in c
        assert 'data-chart-url="' in c
        assert 'data-chart-type="' in c
        assert 'aria-describedby="' in c


@pytest.mark.charts
def test_chart_urls_resolve_to_existing_endpoints(app, client, make_admin, login):
    admin = make_admin()
    login(admin.email, "Passw0rd123!")
    html = client.get("/admin/charts").get_data(as_text=True)
    client.post("/logout")

    urls = re.findall(r'data-chart-url="([^"]+)"', html)
    assert len(urls) == 5

    with app.test_request_context():
        for url in urls:
            path = url.split("?")[0]
            # Match path in url_map
            adapter = app.url_map.bind("localhost")
            endpoint, _ = adapter.match(path, method="GET")
            assert endpoint.startswith("api_v1.chart_")


@pytest.mark.charts
def test_days_selector_marks_current_and_whitelists(client, make_admin, login):
    admin = make_admin()
    login(admin.email, "Passw0rd123!")

    # Default 30
    html_30 = client.get("/admin/charts").get_data(as_text=True)
    assert 'aria-current="true"' in html_30
    assert 'days=30"' in html_30

    # Explicit 90
    html_90 = client.get("/admin/charts?days=90").get_data(as_text=True)
    assert 'data-chart-url="/api/v1/charts/bookings-by-day?days=90"' in html_90

    # Invalid fallback to 30
    html_inv = client.get("/admin/charts?days=5").get_data(as_text=True)
    assert 'data-chart-url="/api/v1/charts/bookings-by-day?days=30"' in html_inv

    client.post("/logout")


@pytest.mark.charts
def test_noscript_fallback_present(client, make_admin, login):
    admin = make_admin()
    login(admin.email, "Passw0rd123!")
    html = client.get("/admin/charts").get_data(as_text=True)
    client.post("/logout")

    assert "<noscript>" in html
    assert "This chart needs JavaScript." in html


@pytest.mark.charts
def test_scripts_local_and_ordered(client, make_admin, login):
    admin = make_admin()
    login(admin.email, "Passw0rd123!")
    html = client.get("/admin/charts").get_data(as_text=True)
    client.post("/logout")

    idx_chartjs = html.find("chart.umd.min.js")
    idx_charts = html.find("js/charts.js")
    assert idx_chartjs != -1
    assert idx_charts != -1
    assert idx_chartjs < idx_charts
    assert "http://" not in html
    assert "https://" not in html


@pytest.mark.charts
def test_no_external_urls_in_pages(client, make_admin, make_examiner, make_student, login):
    for user_fn, url in [
        (make_admin, "/admin/charts"),
        (make_examiner, "/examiner/charts"),
        (make_student, "/student/charts"),
    ]:
        user = user_fn()
        login(user.email, "Passw0rd123!")
        html = client.get(url).get_data(as_text=True)
        assert "http://" not in html
        assert "https://" not in html
        client.post("/logout")


@pytest.mark.charts
def test_dashboard_widgets_present_for_each_role(
    client, make_admin, make_examiner, make_student, login
):
    admin = make_admin()
    examiner = make_examiner()
    student = make_student()

    login(admin.email, "Passw0rd123!")
    html_adm = client.get("/admin/dashboard").get_data(as_text=True)
    assert 'id="charts-widget"' in html_adm
    assert len(re.findall(r"<canvas[^>]*>", html_adm)) == 2
    assert "chart.umd.min.js" in html_adm
    client.post("/logout")

    login(examiner.email, "Passw0rd123!")
    html_ex = client.get("/examiner/dashboard").get_data(as_text=True)
    assert 'id="charts-widget"' in html_ex
    assert len(re.findall(r"<canvas[^>]*>", html_ex)) == 2
    assert "chart.umd.min.js" in html_ex
    client.post("/logout")

    login(student.email, "Passw0rd123!")
    html_stu = client.get("/student/dashboard").get_data(as_text=True)
    assert 'id="charts-widget"' in html_stu
    assert len(re.findall(r"<canvas[^>]*>", html_stu)) == 2
    assert "chart.umd.min.js" in html_stu
    client.post("/logout")


@pytest.mark.charts
def test_non_chart_pages_have_no_chart_scripts(client, make_admin, login):
    admin = make_admin()
    login(admin.email, "Passw0rd123!")
    html = client.get("/admin/courses").get_data(as_text=True)
    client.post("/logout")
    assert "chart.umd.min.js" not in html
    assert "js/charts.js" not in html


@pytest.mark.charts
def test_admin_sidebar_has_eleven_links_with_charts_under_dashboard(client, make_admin, login):
    admin = make_admin()
    login(admin.email, "Passw0rd123!")
    html = client.get("/admin/dashboard").get_data(as_text=True)
    client.post("/logout")

    # Match sidebar
    sidebar_match = re.search(r'<aside class="admin-sidebar[^"]*">(.*?)</aside>', html, re.DOTALL)
    assert sidebar_match is not None
    sidebar_html = sidebar_match.group(1)

    links = re.findall(r'<a class="nav-link[^"]*"[^>]*href="([^"]+)"', sidebar_html)
    assert len(links) == 11, f"Expected 11 links in admin sidebar, found {len(links)}: {links}"

    # Verify Charts link is directly under Dashboard
    assert links[0].endswith("/admin/dashboard")
    assert links[1].endswith("/admin/charts")


@pytest.mark.charts
def test_vendor_chartjs_file_exists():
    vendor_path = pathlib.Path("app/static/vendor/chartjs/chart.umd.min.js")
    if not vendor_path.exists():
        pytest.skip("Chart.js vendor file has not been downloaded yet.")
    assert vendor_path.stat().st_size > 1000
