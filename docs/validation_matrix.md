# Validation matrix

One source of truth (`app/validation`) powers three layers: HTML5 attributes (`validators.html_attrs`), client-side progressive enhancement (`app/static/js/validation.js`), and server-side WTForms + service checks. The server is always authoritative.

## Account

| Form or endpoint | Field | HTML5 attributes | Client rule (`validation.js`) | Server rule (validator or service) | Message | Test that proves it |
|---|---|---|---|---|---|---|
| `LoginForm` | `email` | `required`, `maxlength=254`, `type=email`, `autocomplete=username` | `required`, `max_length`, `invalid_email` | `DataRequired`, `Email`, `Length(max=254)`, `SafeText` | `Enter a valid email address.` | `test_server_validation_matrix.py` |
| `LoginForm` | `password` | `required`, `maxlength=128`, `type=password`, `autocomplete=current-password` | `required`, `max_length` | `DataRequired`, `Length(max=128)` | `This field is required.` | `test_server_validation_matrix.py` |
| `RegisterForm` | `role` | `required`, `type=radio` | `required` | `DataRequired`, `AnyOf(['student','examiner'])` | `This field is required.` | `test_server_validation_matrix.py` |
| `RegisterForm` / `ProfileForm` / `ExaminerCreateForm` | `full_name` | `required`, `minlength=2`, `maxlength=120`, `autocomplete=name` | `between_length`, `unsafe_characters` | `DataRequired`, `Length(2, 120)`, `SafeText` | `Must be between 2 and 120 characters.` | `test_server_validation_matrix.py` |
| `RegisterForm` / `ExaminerCreateForm` | `email` | `required`, `maxlength=254`, `type=email`, `autocomplete=email` | `required`, `max_length`, `invalid_email` | `DataRequired`, `Email`, `Length(max=254)`, unique check | `An account with this email already exists.` | `test_server_validation_matrix.py` |
| `RegisterForm` / `ChangePasswordForm` | `password` / `new_password` | `required`, `minlength=8`, `maxlength=128`, `autocomplete=new-password` | `password_too_short`, `password_too_long`, `password_no_letter`, `password_no_digit` | `DataRequired`, `StrongPassword(8, 128)` | `Must be at least 8 characters.` | `test_custom_validators.py` |
| `RegisterForm` / `ChangePasswordForm` | `confirm_password` / `confirm_new_password` | `required`, `minlength=8`, `maxlength=128`, `data-rule=match:password` | `passwords_mismatch` | `DataRequired`, `MatchesField` | `Passwords do not match` | `test_custom_validators.py` |
| `RegisterForm` / `ProfileForm` / `ExaminerCreateForm` | `contact_phone` | `maxlength=20`, `pattern=^[0-9+\-\s]+$`, `type=tel`, `autocomplete=tel` | `max_length`, `phone_chars` | `Optional`, `Length(max=20)`, `PhoneChars` | `Use digits, +, - and spaces only.` | `test_custom_validators.py` |
| `RegisterForm` / `ProfileForm` / `ExaminerCreateForm` | `department` | `maxlength=120` | `max_length`, `unsafe_characters` | `Optional`, `Length(max=120)`, `SafeText` | `Must be at most 120 characters.` | `test_server_validation_matrix.py` |
| `ProfileForm` / `ExaminerCreateForm` | `designation` | `maxlength=120` | `max_length`, `unsafe_characters` | `Optional`, `Length(max=120)`, `SafeText` | `Must be at most 120 characters.` | `test_server_validation_matrix.py` |
| `ProfileForm` | `roll_number` | `maxlength=30`, `pattern=^[A-Za-z0-9\-/]+$` | `max_length`, `pattern_mismatch` | `Optional`, `Length(max=30)`, `RollNumber`, unique check | `Use letters, numbers, hyphens, and slashes only.` | `test_custom_validators.py` |
| `ProfileForm` | `program` | `maxlength=120` | `max_length`, `unsafe_characters` | `Optional`, `Length(max=120)`, `SafeText` | `Must be at most 120 characters.` | `test_server_validation_matrix.py` |

## Courses and examinations

| Form or endpoint | Field | HTML5 attributes | Client rule (`validation.js`) | Server rule (validator or service) | Message | Test that proves it |
|---|---|---|---|---|---|---|
| `CourseForm` | `code` | `required`, `minlength=2`, `maxlength=20`, `pattern=^[A-Za-z0-9_-]+$` | `between_length`, `pattern_mismatch` | `DataRequired`, `Length(2, 20)`, `CourseCodeChars`, unique check | `Must be between 2 and 20 characters.` | `test_server_validation_matrix.py` |
| `CourseForm` | `name` | `required`, `minlength=2`, `maxlength=150` | `between_length`, `unsafe_characters` | `DataRequired`, `Length(2, 150)`, `SafeText` | `Must be between 2 and 150 characters.` | `test_server_validation_matrix.py` |
| `CourseForm` / `ExaminationForm` | `description` | `maxlength=2000` | `max_length`, `char_counter`, `unsafe_characters` | `Optional`, `Length(max=2000)`, `SafeText(multiline=True)` | `Must be at most 2000 characters.` | `test_server_validation_matrix.py` |
| `ExaminationForm` / `EXAMINATION_SCHEMA` | `name` | `required`, `minlength=2`, `maxlength=150` | `between_length`, `unsafe_characters` | `DataRequired`, `Length(2, 150)`, `SafeText` | `Must be between 2 and 150 characters.` | `test_server_validation_matrix.py` |
| `ExaminationForm` / `EXAMINATION_SCHEMA` | `duration_minutes` | `required`, `min=1`, `max=1440`, `type=number`, `inputmode=numeric` | `between_value`, `invalid_number` | `DataRequired`, `NumberRange(1, 1440)` | `Must be between 1 and 1440.` | `test_server_validation_matrix.py` |
| `ExaminationForm` / `EXAMINATION_SCHEMA` | `max_marks` | `required`, `min=1`, `max=1000`, `type=number`, `inputmode=numeric` | `between_value`, `invalid_number` | `DataRequired`, `NumberRange(1, 1000)` | `Must be between 1 and 1000.` | `test_server_validation_matrix.py` |
| `ExaminationForm` | `slot_creation_start` | `required`, `type=datetime-local` | `required`, `invalid_datetime` | `DataRequired`, `DateTimeLocal` | `Enter a valid date and time` | `test_custom_validators.py` |
| `ExaminationForm` | `slot_creation_end` | `required`, `type=datetime-local`, `data-rule=after:slot_creation_start\|not-after:booking_start` | `rule_after`, `rule_not_after` | `DataRequired`, `DateTimeLocal`, `ExaminationWindows` | `Slot creation end must be after Slot creation start.` | `test_custom_validators.py` |
| `ExaminationForm` | `booking_start` | `required`, `type=datetime-local` | `required`, `invalid_datetime` | `DataRequired`, `DateTimeLocal`, `ExaminationWindows` | `Enter a valid date and time` | `test_custom_validators.py` |
| `ExaminationForm` | `booking_end` | `required`, `type=datetime-local`, `data-rule=after:booking_start` | `rule_after` | `DataRequired`, `DateTimeLocal`, `ExaminationWindows` | `Booking end must be after Booking start.` | `test_custom_validators.py` |
| `ExaminationForm` | `cancellation_deadline` | `type=datetime-local`, `data-rule=not-before:booking_start` | `rule_not_before` | `Optional`, `DateTimeLocal`, `ExaminationWindows` | `Cancellation deadline must not be before Booking start.` | `test_custom_validators.py` |

## Rubrics, Slots, Bookings, Evaluation & Admin Actions

| Form or endpoint | Field | HTML5 attributes | Client rule (`validation.js`) | Server rule (validator or service) | Message | Test that proves it |
|---|---|---|---|---|---|---|
| `RubricForm` | `criterion_name` | `required`, `minlength=2`, `maxlength=100` | `between_length`, `unsafe_characters` | `DataRequired`, `Length(2, 100)`, `SafeText` | `Must be between 2 and 100 characters.` | `test_server_validation_matrix.py` |
| `RubricForm` | `description` | `maxlength=500` | `max_length`, `char_counter` | `Optional`, `Length(max=500)`, `SafeText(multiline=True)` | `Must be at most 500 characters.` | `test_server_validation_matrix.py` |
| `RubricForm` | `weightage` | `required`, `min=0`, `max=100`, `step=0.01`, `inputmode=decimal` | `between_value`, `too_many_decimals` | `InputRequired`, `NumberRange(0, 100)`, `DecimalPlaces(2)` | `Must be between 0 and 100.` | `test_server_validation_matrix.py` |
| `RubricForm` | `max_score` | `required`, `min=0.01`, `step=0.01`, `inputmode=decimal` | `min_value`, `too_many_decimals` | `DataRequired`, `NumberRange(min=0.01)`, `DecimalPlaces(2)` | `Must be at least 0.01.` | `test_server_validation_matrix.py` |
| `SlotForm` / `SLOT_SCHEMA` | `start_at` | `required`, `type=datetime-local` | `required`, `invalid_datetime` | `DataRequired`, `DateTimeLocal` | `Enter a valid date and time` | `test_server_validation_matrix.py` |
| `SlotForm` / `SLOT_SCHEMA` | `end_at` | `required`, `type=datetime-local`, `data-rule=after:start_at` | `end_after_start` | `DataRequired`, `DateTimeLocal`, `EndAfterStart` | `End time must be after start time.` | `test_custom_validators.py` |
| `SlotForm` / `SLOT_SCHEMA` | `max_capacity` | `required`, `min=1`, `max=500`, `type=number`, `inputmode=numeric` | `between_value` | `DataRequired`, `NumberRange(1, 500)` | `Must be between 1 and 500.` | `test_server_validation_matrix.py` |
| `EvaluationForm` | `score_<id>` | `min=0`, `max=<criterion.max_score>`, `step=0.01`, `inputmode=decimal` | `between_value`, `too_many_decimals` | `Optional`, `ScoreRange`, `DecimalPlaces(2)` | `Score for <criterion> must be between 0 and <max>.` | `test_custom_validators.py` |
| `EvaluationForm` | `comment_<id>` | `maxlength=300` | `max_length`, `unsafe_characters` | `Optional`, `Length(max=300)`, `SafeText` | `Must be at most 300 characters.` | `test_server_validation_matrix.py` |
| `EvaluationForm` | `remarks` | `maxlength=2000` | `max_length`, `char_counter` | `Optional`, `Length(max=2000)`, `SafeText(multiline=True)` | `Must be at most 2000 characters.` | `test_server_validation_matrix.py` |
| `ReasonForm` / `CANCEL_SCHEMA` | `reason` | `required`, `minlength=3`, `maxlength=200` | `between_length`, `char_counter` | `DataRequired`, `Length(3, 200)`, `SafeText(multiline=True)` | `Must be between 3 and 200 characters.` | `test_server_validation_matrix.py` |
| `AdminSearchForm` | `q` | `maxlength=100` | `max_length` | `Optional`, `Length(max=100)`, `SafeText` | `Must be at most 100 characters.` | `test_server_validation_matrix.py` |

## Rules that only the server can check

- **Duplicate email (`email_taken`)**: Checked case-insensitively in `RegisterForm`, `ExaminerCreateForm`, and `users` table constraint (`test_server_validation_matrix.py`).
- **Duplicate course code (`duplicate_course_code`)**: Checked in `CourseForm` and `catalog_service.create_course` (`test_catalog_and_admin_rules.py`).
- **Overlap of slots (`examiner_overlap`)**: Checked across all non-cancelled slots of the examiner via `slot_rules.has_overlap` (`test_slot_service.py`).
- **Duplicate booking (`duplicate_booking`)**: Checked in `booking_engine.book_slot` and enforced by partial unique index `uq_bookings_active_student_exam` (`test_booking_engine_rules.py`).
- **Seat availability (`slot_full` / `slot_not_available`)**: Guarded `UPDATE` and `CHECK` constraint inside `BEGIN IMMEDIATE` transaction (`test_booking_engine_concurrency.py`).
- **Window open/closed (`booking_closed`, `slot_creation_closed`, `slot_edit_locked`, `cancel_deadline_passed`)**: Evaluated against `windows.now_utc()` (`test_windows.py`).
- **Rubric total 100 (`rubric_total_not_100`, `weightage_over_100`)**: Enforced in `catalog_service` (`test_catalog_and_admin_rules.py`).
- **Ownership (`slot_not_found`, `booking_not_found`, `examination_not_found`)**: Enforced in service queries returning 404 (`test_role_scoped_visibility.py`).
- **Past start time (`slot_in_past`)**: Checked in `slot_service.create_slot` against `windows.now_utc()` (`test_slot_service.py`).

## What happens with JavaScript off

Because `novalidate` is never placed in HTML templates and is only attached at runtime by `validation.js`, browsers with JavaScript disabled still enforce native HTML5 attributes (`required`, `minlength`, `maxlength`, `min`, `max`, `step`, `pattern`, `type`). Any input that bypasses or passes native browser checks is validated identically on the server by `app/validation` and the service layer, proven end-to-end in `tests/e2e/test_client_validation.py`.
