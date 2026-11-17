"""
tests/e2e/test_charts_render.py - End-to-end browser tests for charts rendering and degradation.
"""

import pytest


@pytest.mark.e2e
@pytest.mark.charts
def test_admin_charts_render(live_server, offline_page, make_chart_dataset):
    data = make_chart_dataset()
    page = offline_page

    # Log in as admin
    page.goto(f"{live_server}/login")
    page.fill('input[name="email"]', data.admin.email)
    page.fill('input[name="password"]', "Passw0rd123!")
    page.click('button[type="submit"]')
    page.wait_for_url("**/admin/dashboard")

    # Navigate to charts
    page.goto(f"{live_server}/admin/charts")
    canvases = page.locator("canvas[data-chart-url]")
    assert canvases.count() == 5

    for i in range(canvases.count()):
        canvas = canvases.nth(i)
        page.wait_for_function(
            "el => el.getAttribute('data-chart-state') === 'ready' || el.getAttribute('data-chart-state') === 'empty'",
            arg=canvas.element_handle(),
            timeout=5000,
        )


@pytest.mark.e2e
@pytest.mark.charts
def test_examiner_and_student_pages_render(live_server, offline_page, make_chart_dataset):
    data = make_chart_dataset()
    page = offline_page

    # Log in as examiner
    page.goto(f"{live_server}/login")
    page.fill('input[name="email"]', data.examiner1.email)
    page.fill('input[name="password"]', "Passw0rd123!")
    page.click('button[type="submit"]')
    page.wait_for_url("**/examiner/dashboard")

    page.goto(f"{live_server}/examiner/charts")
    canvases = page.locator("canvas[data-chart-url]")
    assert canvases.count() == 4


@pytest.mark.e2e
@pytest.mark.charts
def test_empty_state_for_new_student(live_server, offline_page, make_student):
    student = make_student()
    page = offline_page

    page.goto(f"{live_server}/login")
    page.fill('input[name="email"]', student.email)
    page.fill('input[name="password"]', "Passw0rd123!")
    page.click('button[type="submit"]')
    page.wait_for_url("**/student/dashboard")

    page.goto(f"{live_server}/student/charts")
    canvases = page.locator("canvas[data-chart-url]")
    assert canvases.count() == 3

    for i in range(canvases.count()):
        canvas = canvases.nth(i)
        page.wait_for_function(
            "el => el.getAttribute('data-chart-state') === 'empty'",
            arg=canvas.element_handle(),
            timeout=5000,
        )
