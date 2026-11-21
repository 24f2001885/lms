#!/usr/bin/env bash
# =====================================================================
# P9.sh - Phase P9: Frontend & Backend Validation (Tier 2, Secondary)
# Course commit message : Milestone-9 EMP-Validation
# Branch                : phase/p9-validation
# Depends on            : P8 (tag p8-done), Gate A (tag tier1-complete)
# Source of truth       : PDR 5.7 (HTML5/JS plus server validation), TDR 7 (T2 JS:
#                         validation.js mirrors server rules, never replaces them),
#                         Design Plan 7-8 (forms, inline errors, a11y),
#                         Master Blueprint 3.2 (P9 row)
# Acceptance            : invalid input is rejected on BOTH client and server with
#                         clear messages; the server rejects it even with JS off.
# This script contains NO application logic: only git/directory setup
# and prompt-only seed files. Files that already hold real code are never
# overwritten; their changes are in docs/seed_updates/P9_update_existing_files.md.
# =====================================================================
set -euo pipefail

PHASE="P9"
BRANCH="phase/p9-validation"
PREV_TAG="p8-done"

[ -d .git ] || { echo "ERROR: run this from the repository root."; exit 1; }
git rev-parse -q --verify "refs/tags/${PREV_TAG}" >/dev/null || { echo "ERROR: tag ${PREV_TAG} not found. Finish and tag P8 first."; exit 1; }
git rev-parse -q --verify "refs/tags/tier1-complete" >/dev/null || { echo "GATE A CLOSED: tag tier1-complete is missing."; exit 1; }
[ -f app/services/chart_data.py ] || { echo "ERROR: app/services/chart_data.py missing (P8 not implemented)."; exit 1; }

# ---------------------------------------------------------------------
# 1. Git branch management
# ---------------------------------------------------------------------
git checkout main
[ -z "$(git status --porcelain)" ] || { echo "ERROR: working tree not clean. Commit or stash first."; exit 1; }
bash scripts/check_gate.sh "$BRANCH" || { echo "ERROR: gate check refused this branch."; exit 1; }
echo "Checking out milestone branch..."
git checkout -b "$BRANCH"

# ---------------------------------------------------------------------
# 2. Directory & Docker setup (only what P9 needs)
# ---------------------------------------------------------------------
mkdir -p app/validation app/static/js
mkdir -p tests/unit tests/integration tests/e2e docs/seed_updates

# ---------------------------------------------------------------------
# 3. File seeding
# ---------------------------------------------------------------------

# ============================ UPDATE PROMPTS =========================

cat << 'EOF' > docs/seed_updates/P9_update_existing_files.md
<!--
FILE PURPOSE: Update prompts for files already implemented in earlier phases that P9 must change. Do NOT regenerate them from scratch; give the LLM the section plus the CURRENT file. Apply the sections in order.

GOLDEN RULES FOR EVERY SECTION
- The numbers (lengths, ranges) and texts move to app/validation but their VALUES do not change, except the new rules listed in section 11.
- Every message text that an earlier phase's test asserts keeps its exact wording ("Passwords do not match", "An account with this email already exists.", "Enter a valid date and time", "End time must be after start time.", "A course with this code already exists.", "Invalid email or password."). Where an earlier phase used a default WTForms text (for example for Length or NumberRange), the catalogue text from messages.py replaces it; update any test that asserted the old default text.
- The service layer stays authoritative; forms and JavaScript only give early feedback.

SECTION 1: app/__init__.py
1. Register a context processor that injects validation_config (the dict from app.validation.client_config(): limits, messages, rule names) into every template.

SECTION 2: app/templates/base.html
1. Before the closing body tag add the JSON block: a script element of type application/json with id validation-config containing {{ validation_config|tojson }} (type application/json is inert, it is data, not executable code), followed by a script tag with defer for url_for static js/validation.js. Load order: the JSON block first, then validation.js. No inline executable script.

SECTION 3: app/templates/macros/forms.html
1. render_field(field, help_text=None): keep the existing behaviour and add: the field id and a stable error container id "<id>-error" (div.invalid-feedback with role="alert" only after a failed submit) and help id "<id>-help"; aria-describedby always lists the help id (when help exists) and the error id; required fields get a visible text marker "(required)" inside the label in addition to the required attribute (not only a colour or asterisk); optional fields are labelled "(optional)". Pass field.render_kw through unchanged so the HTML5 attributes set by the forms appear in the markup.
2. Add macro form_error_summary(form): a div[data-error-summary] with role="alert" and tabindex="-1" that lists server-side errors as links to the fields (empty and hidden when there are none).
3. render_submit(label, css_class="btn btn-primary", once=true): adds data-submit-once when once is true.
4. Add macro char_counter(field, limit) rendering a small span.char-counter with aria-live="polite" next to textareas that have a limit.

SECTION 4: forms (one change per file; behaviour and messages unchanged, numbers and texts come from app.validation)
1. app/forms/auth.py: LoginForm (email max EMAIL_MAX, password max PASSWORD_MAX, no strength rule at login); RegisterForm (full_name NAME 2-120, email max 254, password PASSWORD 8-128 with StrongPassword, confirm_password MatchesField with the message "Passwords do not match", department max 120, contact_phone PhoneChars max 20, role choices unchanged); ChangePasswordForm (same password rules plus "must differ from the current password"). Add render_kw via html_attrs: autocomplete username/current-password/new-password/name/tel, inputmode where relevant, data-rule="match:password" on confirm fields.
2. app/forms/profile.py: full_name 2-120, contact_phone, department 120, designation 120, roll_number 30 with RollNumber pattern, program 120.
3. app/forms/course.py: code 2-20 with the existing pattern, name 2-150, description max 2000 (char counter).
4. app/forms/examination.py: name 2-150, description 2000, duration 1-1440, max_marks 1-1000, the five datetime fields use DateTimeLocal; the four window rules move into the ExaminationWindows validator with the SAME message texts as P3; add data-rule attributes (after, not-before) to the matching fields.
5. app/forms/rubric.py: criterion 2-100, description 500, weightage 0-100 step 0.01 with DecimalPlaces(2), max_score at least 0.01 step 0.01, position integer at least 0.
6. app/forms/admin_actions.py: ExaminerCreateForm (names as auth, temporary password with StrongPassword), TemporaryPasswordForm (optional, StrongPassword when given), AdminSearchForm (q max SEARCH_Q_MAX).
7. app/forms/slot.py: capacity 1-500, start/end DateTimeLocal, EndAfterStart with the message "End time must be after start time.", data-rule="after:start_at" on end_at.
8. app/forms/evaluation.py (dynamic form): each score field gets ScoreRange(max_score) and DecimalPlaces(2) with the HTML attributes min=0, max=<criterion maximum>, step=0.01, inputmode="decimal"; comments max 300; remarks max 2000 with the char counter.
9. app/forms/booking_actions.py: reason 3-200 with the char counter; RescheduleForm unchanged.
10. app/forms/common.py: parse_page uses MAX_PAGE_SIZE and DEFAULT_PAGE_SIZE from limits.

SECTION 5: services (import the numbers, change nothing else)
1. app/services/slot_service.py (capacity bounds), catalog_service.py (name, code, duration, marks and rubric bounds), evaluation_service.py (remarks, comment lengths, score decimals), booking_engine.py (reason 3-200), admin_service.py (password strength uses the shared StrongPassword rules), search_service.py (q max length), student_queries.py (no change expected). Error codes and messages are unchanged.

SECTION 6: app/blueprints/api_v1/validation.py
1. EXAMINATION_SCHEMA, SLOT_SCHEMA, CANCEL_SCHEMA take their min/max from app.validation.limits (the numbers already match). A test proves API and forms share the same limits.

SECTION 7: templates that contain forms (add attributes, nothing else)
1. Add data-validate to every POST form that has validators: auth/register, auth/change_password, auth/profile, admin/course_form, admin/examination_form, admin/rubrics (add and edit forms), admin/examiner_form, admin/examiner_detail (temporary password form), admin/slot_change_examiner, admin/reschedule, admin/booking_detail (cancel reason modal), examiner/slot_form, examiner/evaluation_form, examiner/slots_list and slot_students (cancel reason modal), admin/search_results (GET form, no csrf).
2. Add data-submit-once to the submit button of every state-changing form: booking confirm modal, student cancel, admin approve/reject/deactivate/activate, toggles, deletes, publish, reschedule, cancel with reason, evaluation buttons (all three, so only one submission happens), registration and login.
3. Do NOT add the novalidate attribute in HTML: validation.js sets form.noValidate itself, so without JavaScript the browser's native validation (from the same attributes) still runs.
4. Place {{ form_error_summary(form) }} at the top of each form and the char_counter macro next to every textarea with a limit.

SECTION 8: app/static/css/app.css
1. Add .char-counter (small muted text, tabular numbers), .error-summary (border-start danger 4px, padding), .is-invalid + .invalid-feedback visible states using text AND an icon-free "Error:" prefix so colour is never the only signal, .btn[aria-busy="true"] (reduced opacity, cursor progress). No new colours outside the palette.

SECTION 9: tests/conftest.py
1. Add helper post_invalid(client, url, data, expect_text=None, expect_status=200) that posts without any JavaScript-related fields, asserts no database change using a snapshot of row counts, and optionally asserts the message text in the HTML.
2. Add fixture forms_catalog: a list of (role, url, method, form_class) tuples for every form page, built by the test module from the url_map plus a manual table for forms that need ids.

SECTION 10: pyproject.toml, Makefile, README.md
1. pyproject.toml: register markers validation and e2e. Makefile: target test-validation (pytest -m validation). README: section "Validation" (shared limits and messages, how to add a field: limit constant, validator, render_kw, test row, matrix row).

SECTION 11: NEW rules introduced in P9 (list them in the README known-issues table and in the decision log)
1. PASSWORD_MAX 128 characters (denial-of-service protection for hashing).
2. SafeText rejects control characters in every free-text field (names, descriptions, reasons, remarks) except line breaks in multi-line fields.
3. All free-text inputs are stripped of leading/trailing spaces before validation.
DEBUGGING:
# print("[DEBUG] applied P9 update section N")
OFFLINE DOCKER TEST CASES:
- After all sections the P0-P8 suite passes (tests that asserted WTForms default texts are updated to the catalogue texts).
- Every form page contains the JSON config block and the validation.js script; no page contains an inline executable script.
- Posting every form with invalid values directly (no browser) is rejected with the same messages the JavaScript shows.
-->
EOF

# ============================ VALIDATION PACKAGE =====================

cat << 'EOF' > app/validation/__init__.py
"""
FILE PURPOSE: Public entry point of the validation package: exposes limits, messages, validators and the client configuration.
DEPENDS ON: app/validation/limits.py, messages.py, validators.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Re-export LIMITS, MESSAGES, the validator classes and html_attrs so other modules write "from app.validation import ...". Keep imports light (no Flask objects at import time, no database access) so services, forms, the API and tests can all import it without cycles.
2. client_config() returns the JSON-safe dict injected into templates: {"limits": LIMITS, "messages": MESSAGES, "rules": ["match", "after", "not-before", "not-after"]}. It contains only constants: no user data, no secrets, no per-request values. Ensure it is serialisable with json.dumps and below 8 KB.
3. Define __all__.
DEBUGGING:
# print(f"[DEBUG] client_config keys={list(client_config())} size={len(json.dumps(client_config()))}")
OFFLINE DOCKER TEST CASES:
- import app.validation works with no application context.
- json.dumps(client_config()) succeeds and is under 8192 bytes.
- No value in client_config() looks like a secret (test scans for the strings key, secret, password hash).
"""
EOF

cat << 'EOF' > app/validation/limits.py
"""
FILE PURPOSE: THE single source of truth for every length, range, step and pattern used by forms, services, the JSON API and the browser (PDR 5.7: HTML5/JS plus server validation share one set of rules).
DEPENDS ON: nothing (constants only).
PROMPT FOR LLM IMPLEMENTATION:
1. Define module-level integer constants with these EXACT values (taken from the Tier 1 and Tier 2 phases): NAME_MIN 2, NAME_MAX 120 (person full name); EMAIL_MAX 254; PASSWORD_MIN 8; PASSWORD_MAX 128 (new in P9); PHONE_MAX 20; DEPARTMENT_MAX 120; DESIGNATION_MAX 120; ROLL_MAX 30; PROGRAM_MAX 120; COURSE_CODE_MIN 2, COURSE_CODE_MAX 20; COURSE_NAME_MIN 2, COURSE_NAME_MAX 150; DESCRIPTION_MAX 2000; EXAM_NAME_MIN 2, EXAM_NAME_MAX 150; DURATION_MIN 1, DURATION_MAX 1440; MAX_MARKS_MIN 1, MAX_MARKS_MAX 1000; CRITERION_MIN 2, CRITERION_MAX 100; RUBRIC_DESCRIPTION_MAX 500; WEIGHTAGE_MIN 0, WEIGHTAGE_MAX 100; MAX_SCORE_MIN as the string "0.01"; DECIMAL_PLACES 2; CAPACITY_MIN 1, CAPACITY_MAX 500; REASON_MIN 3, REASON_MAX 200; REMARKS_MAX 2000; COMMENT_MAX 300; SEARCH_Q_MAX 100; DEFAULT_PAGE_SIZE 20; MAX_PAGE_SIZE 100.
2. Define the regular expressions as strings (so they can be sent to the browser): COURSE_CODE_PATTERN (letters, digits, hyphen, underscore), PHONE_PATTERN (digits, plus, hyphen and spaces only), ROLL_PATTERN (letters, digits, hyphen, slash), plus a title text for each (human explanation used by the HTML title attribute and the pattern-mismatch message).
3. Build LIMITS: a flat, JSON-safe dict of all the numbers and patterns above (keys in lower snake case, for example "name_max") that client_config() exposes. A test asserts that every constant appears in LIMITS and that every min is below its max.
4. Comment every constant with the screen or phase it comes from (for example "P3 course form", "P4 slot capacity").
5. This file must not import Flask, SQLAlchemy or any app module.
DEBUGGING:
# print(f"[DEBUG] LIMITS has {len(LIMITS)} entries; capacity={CAPACITY_MIN}-{CAPACITY_MAX}")
OFFLINE DOCKER TEST CASES:
- Every *_MIN is less than its *_MAX; PASSWORD_MAX is at least 64.
- The regex strings compile with re and also match the HTML pattern syntax used by browsers (no lookbehind, no named groups).
- The numbers equal those used by the Tier 1 forms and the P7 API schemas (comparison test).
"""
EOF

cat << 'EOF' > app/validation/messages.py
"""
FILE PURPOSE: One catalogue of user-facing validation messages used by the server (WTForms, services) and by the browser (JavaScript receives the same dict), so a rule never shows two different texts.
DEPENDS ON: app/validation/limits.py (for formatted limits only).
PROMPT FOR LLM IMPLEMENTATION:
1. Define MESSAGES as a dict of key -> template string using str.format placeholders ({min}, {max}, {other}). Plain English, short, actionable, no jargon. Required keys: required "This field is required."; min_length "Must be at least {min} characters."; max_length "Must be at most {max} characters."; between_length "Must be between {min} and {max} characters."; min_value "Must be at least {min}."; max_value "Must be at most {max}."; between_value "Must be between {min} and {max}."; invalid_email "Enter a valid email address."; invalid_number "Enter a number."; too_many_decimals "Use at most {places} decimal places."; pattern_mismatch "{title}"; unsafe_characters "Contains characters that are not allowed."; phone_chars "Use digits, +, - and spaces only."; password_too_short "Must be at least {min} characters."; password_too_long "Must be at most {max} characters."; password_no_letter "Must contain a letter."; password_no_digit "Must contain a number."; password_same_as_current "Choose a password that is different from the current one."; invalid_datetime "Enter a valid date and time"; end_after_start "End time must be after start time."; passwords_mismatch "Passwords do not match"; rule_after "{label} must be after {other}."; rule_not_before "{label} must not be before {other}."; rule_not_after "{label} must not be after {other}."; email_taken "An account with this email already exists."; course_code_taken "A course with this code already exists."; login_failed "Invalid email or password."; char_counter "{count} of {max} characters".
2. COMPATIBILITY: the texts "Passwords do not match", "An account with this email already exists.", "Enter a valid date and time", "End time must be after start time.", "A course with this code already exists." and "Invalid email or password." keep their exact characters (earlier phases' tests assert them, including the missing final full stop on two of them).
3. Provide msg(key, **kwargs) that formats a template and raises KeyError with a clear message for unknown keys, and a test hook all_keys().
4. No message contains HTML, markup or a trailing space.
DEBUGGING:
# print(f"[DEBUG] msg({key!r}, {kwargs}) -> {text!r}")
OFFLINE DOCKER TEST CASES:
- msg("between_length", min=2, max=120) == "Must be between 2 and 120 characters."
- The six compatibility texts equal the exact strings above.
- Every key used by validators.py and by validation.js exists in MESSAGES (cross-check test reads the JS file for message keys).
"""
EOF

cat << 'EOF' > app/validation/validators.py
"""
FILE PURPOSE: Reusable server-side validators (WTForms-compatible) plus the html_attrs helper that produces the matching HTML5 attributes, so the browser and the server enforce the same rule from one definition.
DEPENDS ON: wtforms.validators (ValidationError, StopValidation), app/validation/limits.py, messages.py, app/services/windows.py (from_local_input; for datetime parsing only), app/security/auth_helpers.py (validate_password_strength).
PROMPT FOR LLM IMPLEMENTATION:
1. Each validator is a small class with __init__(message=None, ...) and __call__(form, field); the default message comes from messages.py; every validator is a no-op on empty optional values (the Optional/DataRequired validator decides emptiness) and never touches the database.
2. Provide: SafeText(multiline=False) (rejects control characters; allows tab/newline only when multiline; message unsafe_characters); PhoneChars() (PHONE_PATTERN); RollNumber() (ROLL_PATTERN, uppercase normalisation is done in the form filter); StrongPassword() (min and max length, letter, digit; reports the FIRST problem with the matching message; uses validate_password_strength for the letter/digit rules); MatchesField(other_name) (message passwords_mismatch by default); DateTimeLocal() (parses with windows.from_local_input, message invalid_datetime); EndAfterStart(start_field) (end strictly after start, message end_after_start); DecimalPlaces(places=2) (message too_many_decimals); ScoreRange(max_score) (0 <= value <= max_score, message names the maximum); ExaminationWindows() (the four Tier 1 window rules with the SAME texts as P3: creation start before end, booking start before end, creation end not after booking start, cancellation deadline not before booking start).
3. html_attrs(min_len=None, max_len=None, minimum=None, maximum=None, step=None, pattern=None, title=None, inputmode=None, autocomplete=None, rule=None) returns the dict for WTForms render_kw: minlength, maxlength, min, max, step, pattern, title (the human explanation shown by browsers), inputmode, autocomplete and data-rule (for validation.js cross-field rules such as "after:start_at"). None values are omitted. Numbers are rendered as strings. The values MUST come from limits.py constants (callers never type numbers).
4. A function describe(field) used by tests returns the effective constraints of a bound field (validators plus render_kw) so a test can assert that server rules and HTML attributes agree.
5. Validators raise wtforms.ValidationError with the formatted message; they never catch exceptions silently and never log the value.
DEBUGGING:
# print(f"[DEBUG] validator {type(self).__name__} field={field.name} value_len={len(str(field.data or ''))}")
OFFLINE DOCKER TEST CASES:
- SafeText rejects "a\x00b" and "tab\there" (single line) but accepts "line1\nline2" when multiline=True.
- StrongPassword gives password_too_short for "abc1", password_no_digit for "abcdefgh", password_no_letter for "12345678", password_too_long for 129 characters, and passes "Passw0rdOK".
- EndAfterStart fails for equal times and for end before start; DateTimeLocal fails for "2030-13-40T25:61".
- DecimalPlaces(2) rejects 1.234 and accepts 1.23 and 5.
- ExaminationWindows reproduces each of the four P3 messages for the four violating inputs.
- html_attrs(min_len=2, max_len=120) returns {"minlength": "2", "maxlength": "120"}; None values are omitted.
"""
EOF

# ================================ JAVASCRIPT =========================

cat << 'EOF' > app/static/js/validation.js
/*
FILE PURPOSE: Progressive enhancement for client-side validation (TDR 7: small scripts that MIRROR server rules but never replace them). Without JavaScript the browser still validates from the same HTML5 attributes and the server always re-validates.
DEPENDS ON: the JSON block #validation-config (limits and messages from app/validation), HTML5 attributes set by app/validation/validators.html_attrs, Bootstrap classes.
PROMPT FOR LLM IMPLEMENTATION:
1. Plain browser JavaScript in one IIFE, no modules, no libraries, no network requests. Read the config once with JSON.parse(document.getElementById("validation-config").textContent); if it is missing or invalid, do nothing and log one console.warn (the page must keep working).
2. Initialise every form[data-validate]: set form.noValidate = true (so our inline messages replace the browser bubbles ONLY when JavaScript runs), validate a field on blur (after the user has touched it) and on input once it has been marked invalid, and validate all fields on submit.
3. Built-in checks per field, using the field's own attributes and the config messages: required -> "required"; minlength/maxlength measured on the trimmed value (the browser's tooShort flag is unreliable for programmatic values, so measure manually) -> min_length / max_length; type email -> invalid_email; type number: badInput -> invalid_number, min -> min_value, max -> max_value, step with at most N decimals -> too_many_decimals; pattern (anchored) -> the field's title attribute text or pattern_mismatch; datetime-local with a value that does not parse -> invalid_datetime.
4. Cross-field rules from data-rule="NAME:other_field_name" (only when both values are filled): match (equal strings -> passwords_mismatch), after (string compare of two datetime-local values, strictly later -> rule_after, or end_after_start for fields named end_at), not-before (>= -> rule_not_before), not-after (<= -> rule_not_after). datetime-local strings in the same timezone compare correctly as plain strings. Labels for messages come from the label elements. There is NO client-side "not in the past" rule (the browser timezone may differ from APP_TIMEZONE); the server decides that.
5. Error display (WCAG 3.3.1/3.3.3): add class is-invalid, set aria-invalid="true", create or update div.invalid-feedback with id "<id>-error" containing the message prefixed by the visually present word "Error:", and merge that id into aria-describedby (keep the help id). On correction remove them. On a failed submit: preventDefault, fill the form's [data-error-summary] with links to each invalid field, show it, move focus to the summary (it has tabindex -1) and let the user jump to the first field via the link; focus the first invalid field when there is no summary container.
6. Password helper: for inputs with autocomplete="new-password" show a live hint in the element referenced by data-strength-target ("At least 8 characters, a letter and a number") that turns into "Looks good" when all rules pass; announce changes through its aria-live="polite" region without stealing focus. It never blocks anything beyond the same rules the server enforces.
7. Character counters: for textarea/input with maxlength and a .char-counter sibling update "N of M characters" (config char_counter) on input; throttle announcements (aria-live polite) to when the remaining characters cross 20 and 0.
8. Submit-once: for submit buttons with data-submit-once, on the form's FIRST valid submit set disabled, aria-busy="true" and the button text to "Please wait..." (keep the original text in a data attribute), but do NOT disable before the submit event has fired (a disabled button would drop its name/value from the request: the evaluation form's action buttons must still send their action value, so copy the clicked button's name/value into a hidden input first). A second click or Enter keypress while submitting does nothing. On the pageshow event with event.persisted (back/forward cache) restore the buttons.
9. Never mark anything as trusted: no hidden "validated" fields, no skipping of server checks; keep all behaviour reversible by removing the script.
10. Keep the file under 300 lines, one small function per rule, comments in plain English; no use of eval, innerHTML or document.write (use textContent/createElement).
DEBUGGING:
// console.debug("[validation] field", field.name, "state", state);   (leave commented; enable while debugging)
OFFLINE DOCKER TEST CASES:
- A required empty field shows "Error: This field is required." under the field, aria-invalid is true and aria-describedby includes the error id; fixing the value clears all three.
- Typing 1 character into a 2-120 name field and leaving it shows the between_length message with 2 and 120.
- Mismatched passwords show "Passwords do not match"; matching ones clear it.
- Submitting an invalid examination form focuses the error summary, lists each problem as a link and sends nothing to the server.
- A double click on a valid booking confirm button sends exactly one request and the button shows "Please wait...".
- With JavaScript disabled the same invalid input is stopped by the browser (required, minlength, min, max attributes) or rejected by the server with the same message text.
- No request to any host other than 127.0.0.1 and no console errors on any page.
*/
EOF

# ================================ DOCS ===============================

cat << 'EOF' > docs/validation_matrix.md
<!--
FILE PURPOSE: The field-by-field validation matrix for the report, the viva and the tests: every input, its HTML5 attribute, its JavaScript rule, its server rule and its message in one table.
PROMPT FOR LLM IMPLEMENTATION:
1. Title "Validation matrix" and a short intro: one source of truth (app/validation), three layers (HTML5 attributes, validation.js, server forms and services), the server is authoritative.
2. One table per area (Account, Courses and examinations, Rubrics, Slots and bookings, Evaluation, Admin actions, JSON API) with columns: Form or endpoint, Field, HTML5 attributes, Client rule (validation.js), Server rule (validator or service), Message, Test that proves it. One row per field; the numbers must be taken from app/validation/limits.py (write them out, do not say "see code").
3. A section "Rules that only the server can check" listing: duplicate email, duplicate course code, overlap of slots, duplicate booking, seat availability, window open/closed, rubric total 100, ownership, past start time. Each with the error code and the test that covers it.
4. A section "What happens with JavaScript off" with two sentences and a pointer to tests/e2e/test_client_validation.py.
5. Keep it under 150 lines of plain Markdown tables.
DEBUGGING:
(none: documentation file) Verify with: pytest tests/integration/test_html5_attributes.py (the test cross-checks the numbers).
OFFLINE DOCKER TEST CASES:
- Every field named in the matrix exists in a form class or API schema (a test greps the table).
- The numbers in the table equal LIMITS.
-->
EOF

# ================================ TESTS ==============================

cat << 'EOF' > tests/unit/test_validation_limits_messages.py
"""
FILE PURPOSE: Consistency tests for limits, messages and client_config.
DEPENDS ON: app/validation, app/blueprints/api_v1/validation.py, app/forms, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Limits: test_every_min_below_max, test_limits_dict_contains_all_constants, test_regex_strings_compile_and_are_browser_safe (no lookbehind or named groups), test_password_max_at_least_64.
2. Messages: test_compatibility_texts_exact (the six strings of messages.py rule 2), test_msg_formats_placeholders, test_unknown_key_raises, test_no_message_has_markup_or_trailing_space, test_js_message_keys_exist (parse app/static/js/validation.js for message keys and assert each is in MESSAGES).
3. Client config: test_client_config_json_safe_and_small, test_client_config_has_no_secrets.
4. Parity: test_forms_use_limits (introspect each form field with Length/NumberRange validators and compare to LIMITS), test_api_schemas_use_same_limits (EXAMINATION_SCHEMA, SLOT_SCHEMA, CANCEL_SCHEMA numbers equal the limits), test_services_use_same_limits (slot capacity bounds, remarks length).
DEBUGGING:
# print(f"[DEBUG] parity check {form}.{field}: form={form_value} limits={limit_value}")
OFFLINE DOCKER TEST CASES:
- 17 tests pass offline.
"""
EOF

cat << 'EOF' > tests/unit/test_custom_validators.py
"""
FILE PURPOSE: Unit tests for every custom validator and html_attrs.
DEPENDS ON: app/validation/validators.py, wtforms test helpers (a tiny form class per test).
PROMPT FOR LLM IMPLEMENTATION:
1. SafeText: test_rejects_control_chars, test_multiline_allows_newlines, test_unicode_letters_allowed.
2. Passwords: test_strong_password_each_message (short, no letter, no digit, too long, ok), test_matches_field_exact_message_text.
3. Dates: test_datetime_local_valid_invalid, test_end_after_start_equal_and_reversed, test_examination_windows_four_messages_unchanged.
4. Numbers: test_decimal_places_boundaries, test_score_range_boundaries_and_message_names_max, test_capacity_range_via_numberrange.
5. Text patterns: test_phone_chars, test_roll_number_pattern, test_course_code_pattern.
6. html_attrs: test_html_attrs_omits_none, test_html_attrs_strings, test_describe_matches_render_kw.
7. All boundary tests use min-1, min, max, max+1.
DEBUGGING:
# print(f"[DEBUG] validator case {name}: errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- 26 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_server_validation_matrix.py
"""
FILE PURPOSE: THE acceptance test for backend validation: every form and API endpoint rejects invalid input DIRECTLY (no browser, no JavaScript) with the catalogue message and without changing the database.
DEPENDS ON: tests/conftest.py (post_invalid, factories, api fixture), app/validation.
PROMPT FOR LLM IMPLEMENTATION:
1. A single parametrised table VALIDATION_CASES of (role, method, url, valid_payload, field, invalid_value, expected_text) built from LIMITS so numbers are never retyped: for every text/number field test min-1, min, max and max+1 where applicable (name, email, password, course code and name, description, examination name, duration, max marks, criterion, weightage, max score, capacity, reason, remarks, comment, search q, phone, roll number, program, department, designation).
2. Dates and timelines: examination windows (creation end after booking start, booking end before start, deadline before booking start, bad datetime text), slot end not after start, slot start in the past (service code slot_in_past), capacity 0 and 501.
3. Marks: score above the criterion maximum, negative score, three decimals, total above the examination maximum (service total_exceeds_max).
4. Accounts: mismatched passwords ("Passwords do not match"), weak passwords, duplicate email (case-insensitive), tampered role, over-long password (129 characters).
5. Server-only rules through forged POSTs: duplicate booking, full slot, closed window, foreign ids (404), reschedule to a tampered slot id.
6. JSON API parity: the same limits produce 422 validation_error with the same boundary values (name 1 and 151 characters, capacity 0 and 501, duration 0 and 1441).
7. For each case assert: status code, the exact message text in the HTML (or JSON "fields"), and that table row counts are unchanged (snapshot before and after). Also assert that valid boundary values (min and max) are ACCEPTED.
8. test_js_is_never_required: the valid payloads contain no JavaScript-added fields and succeed; test_only_expected_fields_mass_assignment (extra fields like role, approval_status, is_active are ignored or rejected).
DEBUGGING:
# print(f"[DEBUG] case {role} {url} {field}={invalid_value!r} -> {response.status_code} {matched_text!r}")
OFFLINE DOCKER TEST CASES:
- About 200 parametrised cases pass offline in under 40 seconds; lowering any limit in limits.py makes the matching boundary cases fail.
"""
EOF

cat << 'EOF' > tests/integration/test_html5_attributes.py
"""
FILE PURPOSE: Proves the HTML5 attributes rendered by every form agree with the server validators, and that the validation script and config are wired on every page.
DEPENDS ON: tests/conftest.py (forms_catalog), app/validation/validators.py (describe), app/templates.
PROMPT FOR LLM IMPLEMENTATION:
1. For every form page of every role render the page and parse it with the standard html.parser; for each input/select/textarea compare the attributes with describe(field) of the bound WTForms field: required iff DataRequired/InputRequired; minlength/maxlength equal Length bounds; min/max/step equal NumberRange/Decimal bounds; pattern and title equal the validator pattern; type is email for email fields, number for numeric, datetime-local for date-times, password for passwords, tel for phones.
2. Accessibility attributes: autocomplete values (username, current-password, new-password, email, name, tel), inputmode numeric/decimal on number fields, every control has a label for= match, aria-describedby references ids that exist.
3. Wiring: every page contains exactly one script element of type application/json with id validation-config whose JSON parses and whose limits equal app.validation.LIMITS; the validation.js script tag appears after it with defer; no page contains an inline executable script and no form has the novalidate attribute.
4. Forms: every POST form that has validators has data-validate; every state-changing form's submit button has data-submit-once; every textarea with a limit has a .char-counter; each form page has a [data-error-summary] container.
5. Matrix doc check: every field named in docs/validation_matrix.md exists in a form or schema (parse the table).
DEBUGGING:
# print(f"[DEBUG] attr check {page_url} {field.name}: html={html_attrs} expected={expected}")
OFFLINE DOCKER TEST CASES:
- All form pages (about 25) pass; removing render_kw from any field makes a mismatch test fail.
"""
EOF

cat << 'EOF' > tests/e2e/test_client_validation.py
"""
FILE PURPOSE: Browser tests of the client-side validation behaviour, and proof that the server protects the application when JavaScript is off or bypassed.
DEPENDS ON: tests/e2e/conftest.py (live_server, browser fixtures), app/validation.messages.
PROMPT FOR LLM IMPLEMENTATION:
1. Mark @pytest.mark.e2e and @pytest.mark.validation. With JavaScript ON:
   - test_required_and_length_inline_messages (registration: empty and one-character name show "Error:" plus the catalogue text, aria-invalid true, aria-describedby includes the error id, fixing clears them),
   - test_password_mismatch_and_strength_hint (live hint text changes, mismatch text equals "Passwords do not match"),
   - test_examination_window_rules (change booking_end earlier than booking_start: message names both labels; submit is blocked, focus lands on the error summary, a link jumps to the field),
   - test_slot_end_before_start ("End time must be after start time."),
   - test_evaluation_score_above_max (message names the maximum; the three action buttons still send their action when the form is valid),
   - test_char_counter_updates_and_announces,
   - test_submit_once_double_click_creates_one_booking (double-click the booking confirm button and assert exactly one booking row and one request),
   - test_no_console_errors_and_no_external_requests.
2. With JavaScript OFF (new context with java_script_enabled=False): test_native_validation_blocks_required_and_length (the browser refuses to submit, nothing reaches the server: assert no request), test_server_message_shown_when_native_checks_pass (submit a value the browser accepts but the server rejects, for example a duplicate email or a past start time, and assert the server message in the page).
3. Bypass: test_removed_attributes_still_rejected_by_server (remove required/min/max attributes via page.evaluate, submit invalid values, assert the same server messages and no database change) and test_forged_post_with_request_context (page.request.post with the CSRF token and invalid data returns the rejection).
4. Take a screenshot into test-results/ on failure.
DEBUGGING:
# print(f"[DEBUG] e2e validation step={step} url={page.url} invalid={invalid_count}")
OFFLINE DOCKER TEST CASES:
- All tests pass with the network disabled; the double-click test fails if data-submit-once is removed.
"""
EOF

# --- keep empty folders in Git ---
find app tests docs -type d -empty -exec touch {}/.gitkeep \;

# ---------------------------------------------------------------------
# 4. Phase completion echo
# ---------------------------------------------------------------------
echo "====================================================="
echo "Milestone P9 Seeded Successfully!"
echo "NEXT STEPS:"
echo "1. Provide the seeded files to your LLM to generate the code. Apply docs/seed_updates/P9_update_existing_files.md in ORDER (sections 1 to 3 first, then forms, services, templates) with the CURRENT files, then run the whole suite and fix tests that asserted old default WTForms texts."
echo "2. Run 'docker compose --profile test run --rm test' (or 'make test-core' and 'make test-validation'), then try every form with bad input in the browser, once with JavaScript on and once off."
echo "3. Run 'git add . && git commit -m \"wip: P9 validation\"'  (wip: commits are free-form)."
echo "4. When green: 'git checkout main && git merge --squash phase/p9-validation && git commit -m \"Milestone-9 EMP-Validation\" && git tag p9-done && git push origin main --tags'."
echo "5. Decisions to confirm: new rules PASSWORD_MAX 128, control-character rejection and trimming of free text; messages for Length/NumberRange replaced by the catalogue texts; no client-side past-date rule (server decides)."
echo "6. Execute P10.sh"
echo "====================================================="
