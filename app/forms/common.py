"""
FILE PURPOSE: Tiny shared forms used by every role (CSRF-only POST actions and list filters).
DEPENDS ON: flask_wtf, wtforms.
PROMPT FOR LLM IMPLEMENTATION:
1. ConfirmForm(FlaskForm) with no fields: used for every state-changing POST that needs no input (approve, delete, toggle, book, cancel). It exists so each such button is a real form carrying the CSRF token; the view calls form.validate_on_submit().
2. FilterForm base: a FlaskForm subclass with meta csrf = False for GET filter bars, plus helper parse_page(request.args) returning an int >= 1 (default 1) and per_page clamped to 1..100 (default 20). Invalid values fall back to the defaults, never raise.
3. Nothing else; no business rules.
DEBUGGING:
# print(f"[DEBUG] ConfirmForm valid={form.validate_on_submit()} errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- A POST without a CSRF token fails ConfirmForm validation when WTF_CSRF_ENABLED is True.
- parse_page({"page": "abc"}) returns page 1; per_page "500" is clamped to 100; per_page "0" to 1.
"""
