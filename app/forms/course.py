"""
FILE PURPOSE: WTForms for creating and editing a course (ADM-03).
DEPENDS ON: flask_wtf, wtforms, app/models/course.py.
PROMPT FOR LLM IMPLEMENTATION:
1. CourseForm fields: code (DataRequired, Length 2-20, filter strip+upper, Regexp letters digits and - _ only), name (DataRequired, Length 2-150), description (Optional, Length max 2000, TextAreaField), status (SelectField choices from COURSE_STATUSES, default "active").
2. A constructor argument course_id lets validate_code skip the course being edited when checking duplicates (case-insensitive). Duplicate message: "A course with this code already exists."
3. Labels match the PDR: "Course code", "Course name", "Description", "Status".
DEBUGGING:
# print(f"[DEBUG] CourseForm errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- Code "cs 101" (space) is invalid; "cs101" is stored as "CS101".
- Editing a course and keeping its own code is valid; using another course's code is not.
"""
