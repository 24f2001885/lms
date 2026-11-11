"""
FILE PURPOSE: Proves EVERY /admin route is closed to everyone but a ready Admin (risk R-4).
DEPENDS ON: tests/conftest.py, app/__init__.py (url_map).
PROMPT FOR LLM IMPLEMENTATION:
1. Build the list of admin URLs by iterating app.url_map.iter_rules() for rules starting with /admin, filling path variables with the id of a real fixture row (use a converter map: <int:id> -> 1). Keep GET and POST separate.
2. Parametrised tests: anonymous -> 302 to /login for every URL and method; student -> 403; approved examiner -> 403; pending examiner -> 403 (role mismatch comes before the pending redirect); admin with must_change_password True -> 302 to /change-password; admin ready -> never 403 or 500 (200/302/404 allowed for POST with empty data).
3. test_admin_post_without_csrf_rejected (CSRF enabled app) for three representative POST routes.
4. test_no_admin_route_missing_decorator: fail if any /admin rule's view function is not wrapped (check the wrapped marker set by the decorators).
DEBUGGING:
# print(f"[DEBUG] {method} {url} as {role} -> {response.status_code}")
OFFLINE DOCKER TEST CASES:
- The parametrised matrix covers every admin rule found at collection time; adding a new admin route automatically adds cases.
"""
