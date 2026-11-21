"""
Security response headers and a strict Content-Security-Policy (P11).
"""

from flask import request
from flask_login import current_user

_EXTRA_CSP_SOURCES: dict[str, set[str]] = {}


def add_csp_source(directive: str, source: str) -> None:
    """Register an extra source for a CSP directive (idempotent)."""
    valid_directives = {
        "default-src",
        "script-src",
        "style-src",
        "style-src-attr",
        "img-src",
        "font-src",
        "connect-src",
        "object-src",
        "base-uri",
        "form-action",
        "frame-ancestors",
    }
    if directive not in valid_directives:
        raise ValueError(f"Unknown CSP directive: {directive}")
    if not (source.startswith("https://") or (source.startswith("'") and source.endswith("'"))):
        raise ValueError("Source must be an https origin or a quoted keyword.")

    if directive not in _EXTRA_CSP_SOURCES:
        _EXTRA_CSP_SOURCES[directive] = set()
    _EXTRA_CSP_SOURCES[directive].add(source)


def build_csp(extra: dict[str, list[str]] | None = None) -> str:
    """Build the Content-Security-Policy string."""
    base = {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'"],
        "style-src-attr": ["'unsafe-inline'"],
        "img-src": ["'self'", "data:"],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
        "frame-ancestors": ["'none'"],
    }

    merged = {k: list(v) for k, v in base.items()}

    for d, srcs in _EXTRA_CSP_SOURCES.items():
        if d in merged:
            for s in srcs:
                if s not in merged[d]:
                    merged[d].append(s)

    if extra:
        for d, srcs in extra.items():
            if d in merged:
                for s in srcs:
                    if s not in merged[d]:
                        merged[d].append(s)

    parts = []
    for k, v in merged.items():
        parts.append(f"{k} {' '.join(v)}")
    return "; ".join(parts)


def register_security_headers(app):
    if not app.config.get("SECURITY_HEADERS_ENABLED", True):
        return

    @app.after_request
    def set_headers(response):
        csp_header = (
            "Content-Security-Policy-Report-Only"
            if app.config.get("CSP_REPORT_ONLY", False)
            else "Content-Security-Policy"
        )
        extra = {"style-src": ["'unsafe-inline'"]} if app.config.get("TESTING") else None
        response.headers[csp_header] = build_csp(extra=extra)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"

        if current_user.is_authenticated and not request.path.startswith("/static/"):
            ctype = response.headers.get("Content-Type", "")
            if "text/html" in ctype or "application/json" in ctype:
                if "Cache-Control" not in response.headers:
                    response.headers["Cache-Control"] = "no-store"
                vary = response.headers.get("Vary", "")
                if "Cookie" not in vary:
                    response.headers["Vary"] = (vary + ", Cookie").strip(", ")

        return response
