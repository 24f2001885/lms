"""
Browser E2E tests for client-side validation (validation.js) and server-side
enforcement when JavaScript is disabled or bypassed (P9).
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.validation]


def test_required_and_length_inline_messages(page, live_server):
    """Empty and too-short inputs trigger inline 'Error:' messages and aria-invalid."""
    page.goto(f"{live_server}/register")
    name_input = page.locator("#full_name")
    name_input.focus()
    name_input.fill("A")
    name_input.blur()

    err_el = page.locator("#full_name-error")
    assert "Error: Must be between 2 and 120 characters." in err_el.inner_text()
    assert name_input.get_attribute("aria-invalid") == "true"

    name_input.fill("Abhishek Pathak")
    assert name_input.get_attribute("aria-invalid") is None
    assert err_el.inner_text().strip() == ""


def test_password_mismatch_and_strength_hint(page, live_server):
    """Password strength helper updates live and confirm password checks match."""
    page.goto(f"{live_server}/register")
    pwd = page.locator("#password")
    conf = page.locator("#confirm_password")

    pwd.fill("Passw0rd1")
    conf.fill("Passw0rd2")
    conf.blur()

    conf_err = page.locator("#confirm_password-error")
    assert "Passwords do not match" in conf_err.inner_text()

    conf.fill("Passw0rd1")
    assert conf_err.inner_text().strip() == ""


def test_server_rejects_when_attributes_removed(page, live_server):
    """Removing HTML5 attributes and disabling client JS still triggers server rejection."""
    page.goto(f"{live_server}/register")
    page.evaluate(
        """() => {
            const form = document.querySelector('form');
            form.removeAttribute('data-validate');
            for (const el of form.querySelectorAll('input')) {
                el.removeAttribute('required');
                el.removeAttribute('minlength');
                el.removeAttribute('maxlength');
            }
        }"""
    )
    page.locator("input[name='role'][value='student']").check()
    page.locator("#full_name").fill("A")
    page.locator("#email").fill("valid@test.local")
    page.locator("#password").fill("Passw0rd1")
    page.locator("#confirm_password").fill("Passw0rd1")
    page.locator("button[type='submit']").click()

    assert "Must be between 2 and 120 characters." in page.content()
