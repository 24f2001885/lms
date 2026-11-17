"""
Proves the palette meets WCAG 2.1 AA contrast (4.5:1 text, 3.0:1 non-text) and
that app.css and responsive.css contain the verified tokens (P10).
"""

import pathlib

import pytest

pytestmark = [pytest.mark.a11y, pytest.mark.responsive]


def _srgb_channel(c: int) -> float:
    v = c / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.2126 * _srgb_channel(r) + 0.7152 * _srgb_channel(g) + 0.0722 * _srgb_channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    l1 = relative_luminance(fg)
    l2 = relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


TEXT_PAIRS = [
    ("#212529", "#F5F7FA", "body on page bg"),
    ("#212529", "#FFFFFF", "body on white"),
    ("#5C636A", "#F5F7FA", "muted on page bg"),
    ("#5C636A", "#FFFFFF", "muted on white"),
    ("#1F4E79", "#F5F7FA", "link on page bg"),
    ("#1F4E79", "#FFFFFF", "link on white"),
    ("#FFFFFF", "#1F4E79", "white on primary"),
    ("#FFFFFF", "#173B5C", "white on primary hover"),
    ("#FFFFFF", "#198754", "white on success"),
    ("#FFFFFF", "#DC3545", "white on danger"),
    ("#FFFFFF", "#6C757D", "white on secondary"),
    ("#FFFFFF", "#6F42C1", "white on purple"),
    ("#212529", "#FFC107", "dark on warning"),
    ("#212529", "#FD7E14", "dark on orange badge-full"),
    ("#212529", "#0DCAF0", "dark on info badge"),
    ("#7A5C00", "#FFFFFF", "amber text on white"),
    ("#B02A37", "#F5F7FA", "invalid-feedback on page bg"),
    ("#B02A37", "#FFFFFF", "invalid-feedback on white"),
    ("#146C43", "#FFFFFF", "success text on white"),
    ("#E6EDF3", "#14283B", "sidebar text on sidebar bg"),
    ("#AFC0D0", "#14283B", "sidebar muted on sidebar bg"),
    ("#055160", "#CFF4FC", "alert-info text on bg"),
    ("#664D03", "#FFF3CD", "alert-warning text on bg"),
    ("#842029", "#F8D7DA", "alert-danger text on bg"),
    ("#0F5132", "#D1E7DD", "alert-success text on bg"),
]

NON_TEXT_PAIRS = [
    ("#6C757D", "#FFFFFF", "form control border on white"),
    ("#6C757D", "#F5F7FA", "form control border on page bg"),
    ("#0B5ED7", "#FFFFFF", "focus ring on white"),
    ("#0B5ED7", "#F5F7FA", "focus ring on page bg"),
    ("#FFFFFF", "#14283B", "focus ring on sidebar bg"),
    ("#7A5C00", "#FFFFFF", "outline-badge border on white"),
    ("#FFC107", "#14283B", "sidebar active border on sidebar bg"),
]


@pytest.mark.parametrize("fg,bg,label", TEXT_PAIRS)
def test_text_contrast_meets_wcag_aa(fg, bg, label):
    """Every text colour pair meets at least 4.5:1 contrast."""
    ratio = contrast_ratio(fg, bg)
    assert ratio >= 4.5, f"{label} ({fg} on {bg}) ratio {ratio:.2f} < 4.5"


@pytest.mark.parametrize("fg,bg,label", NON_TEXT_PAIRS)
def test_non_text_contrast_meets_wcag_aa(fg, bg, label):
    """Every non-text border/focus indicator meets at least 3.0:1 contrast."""
    ratio = contrast_ratio(fg, bg)
    assert ratio >= 3.0, f"{label} ({fg} on {bg}) ratio {ratio:.2f} < 3.0"


@pytest.mark.parametrize(
    "fg,bg,threshold",
    [
        ("#6C757D", "#F5F7FA", 4.5),
        ("#FFFFFF", "#FD7E14", 4.5),
        ("#FFFFFF", "#0DCAF0", 4.5),
        ("#DEE2E6", "#FFFFFF", 3.0),
    ],
)
def test_negative_guards_prove_old_values_failed(fg, bg, threshold):
    """Negative guard: proves the pre-P10 colours failed the WCAG threshold."""
    assert contrast_ratio(fg, bg) < threshold


def test_css_files_contain_fixed_tokens_and_no_external_urls():
    """app.css and responsive.css contain the required contrast/responsive tokens."""
    app_css = pathlib.Path("app/static/css/app.css").read_text(encoding="utf-8")
    resp_css = pathlib.Path("app/static/css/responsive.css").read_text(encoding="utf-8")

    for token in ("#5C636A", "#6C757D", "#7A5C00", "#B02A37", "#146C43", ".badge-full"):
        assert token in app_css, f"Missing {token} in app.css"

    for token in (
        "#0B5ED7",
        "prefers-reduced-motion: reduce",
        "forced-colors: active",
        "max-width: 575.98px",
        ".table-stack",
    ):
        assert token in resp_css, f"Missing {token} in responsive.css"

    for css_text in (app_css, resp_css):
        assert "http://" not in css_text
        assert "https://" not in css_text
        assert "@import" not in css_text
