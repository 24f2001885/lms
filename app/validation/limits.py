"""
Single source of truth for every length, range, step, and pattern used by forms,
services, the JSON API, and the browser (P9 Validation).
"""

# Account / User (P2 auth & profile forms, P9 PASSWORD_MAX)
NAME_MIN = 2
NAME_MAX = 120
EMAIL_MAX = 254
PASSWORD_MIN = 8
PASSWORD_MAX = 128
PHONE_MAX = 20
DEPARTMENT_MAX = 120
DESIGNATION_MAX = 120
ROLL_MAX = 30
PROGRAM_MAX = 120

# Courses & Examinations (P3 catalog & examination forms)
COURSE_CODE_MIN = 2
COURSE_CODE_MAX = 20
COURSE_NAME_MIN = 2
COURSE_NAME_MAX = 150
DESCRIPTION_MAX = 2000
EXAM_NAME_MIN = 2
EXAM_NAME_MAX = 150
DURATION_MIN = 1
DURATION_MAX = 1440
MAX_MARKS_MIN = 1
MAX_MARKS_MAX = 1000

# Rubrics (P3 rubric form)
CRITERION_MIN = 2
CRITERION_MAX = 100
RUBRIC_DESCRIPTION_MAX = 500
WEIGHTAGE_MIN = 0
WEIGHTAGE_MAX = 100
MAX_SCORE_MIN = "0.01"
DECIMAL_PLACES = 2

# Slots & Bookings (P4 slot form, P6 reason form)
CAPACITY_MIN = 1
CAPACITY_MAX = 500
REASON_MIN = 3
REASON_MAX = 200

# Evaluations & Search (P4 evaluation form, P3 search form)
REMARKS_MAX = 2000
COMMENT_MAX = 300
SEARCH_Q_MAX = 100

# Pagination (P1 config, P3/P7 pagination)
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Regular expression patterns (browser-safe: no lookbehind, no named groups)
COURSE_CODE_PATTERN = r"^[A-Za-z0-9_-]+$"
COURSE_CODE_TITLE = "Use letters, numbers, hyphens, and underscores only."

PHONE_PATTERN = r"^[0-9+\-\s]+$"
PHONE_TITLE = "Use digits, +, - and spaces only."

ROLL_PATTERN = r"^[A-Za-z0-9\-/]+$"
ROLL_TITLE = "Use letters, numbers, hyphens, and slashes only."

LIMITS = {
    "name_min": NAME_MIN,
    "name_max": NAME_MAX,
    "email_max": EMAIL_MAX,
    "password_min": PASSWORD_MIN,
    "password_max": PASSWORD_MAX,
    "phone_max": PHONE_MAX,
    "department_max": DEPARTMENT_MAX,
    "designation_max": DESIGNATION_MAX,
    "roll_max": ROLL_MAX,
    "program_max": PROGRAM_MAX,
    "course_code_min": COURSE_CODE_MIN,
    "course_code_max": COURSE_CODE_MAX,
    "course_name_min": COURSE_NAME_MIN,
    "course_name_max": COURSE_NAME_MAX,
    "description_max": DESCRIPTION_MAX,
    "exam_name_min": EXAM_NAME_MIN,
    "exam_name_max": EXAM_NAME_MAX,
    "duration_min": DURATION_MIN,
    "duration_max": DURATION_MAX,
    "max_marks_min": MAX_MARKS_MIN,
    "max_marks_max": MAX_MARKS_MAX,
    "criterion_min": CRITERION_MIN,
    "criterion_max": CRITERION_MAX,
    "rubric_description_max": RUBRIC_DESCRIPTION_MAX,
    "weightage_min": WEIGHTAGE_MIN,
    "weightage_max": WEIGHTAGE_MAX,
    "max_score_min": MAX_SCORE_MIN,
    "decimal_places": DECIMAL_PLACES,
    "capacity_min": CAPACITY_MIN,
    "capacity_max": CAPACITY_MAX,
    "reason_min": REASON_MIN,
    "reason_max": REASON_MAX,
    "remarks_max": REMARKS_MAX,
    "comment_max": COMMENT_MAX,
    "search_q_max": SEARCH_Q_MAX,
    "default_page_size": DEFAULT_PAGE_SIZE,
    "max_page_size": MAX_PAGE_SIZE,
    "course_code_pattern": COURSE_CODE_PATTERN,
    "course_code_title": COURSE_CODE_TITLE,
    "phone_pattern": PHONE_PATTERN,
    "phone_title": PHONE_TITLE,
    "roll_pattern": ROLL_PATTERN,
    "roll_title": ROLL_TITLE,
}
