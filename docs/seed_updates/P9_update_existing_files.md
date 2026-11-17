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
