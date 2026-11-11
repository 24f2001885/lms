"""
FILE PURPOSE: WTForms for creating and editing an examination (ADM-05) with datetime-local inputs.
DEPENDS ON: flask_wtf, wtforms, app/models/examination.py, app/models/course.py, app/services/windows.py (from_local_input, to_input_value).
PROMPT FOR LLM IMPLEMENTATION:
1. ExaminationForm fields: course_id (SelectField of ACTIVE courses, coerce int), name (DataRequired, Length 2-150), description (Optional TextArea), exam_type (SelectField from EXAM_TYPES with labels Viva, Practical, Project demo, Assessment), duration_minutes (IntegerField, NumberRange 1-1440), max_marks (IntegerField, NumberRange 1-1000), slot_creation_start, slot_creation_end, booking_start, booking_end, cancellation_deadline (StringField rendered as type datetime-local; cancellation_deadline Optional).
2. A method to_service_data() converts the five datetime strings with windows.from_local_input into naive UTC and returns the dict for catalog_service; invalid text produces a field error "Enter a valid date and time".
3. A method populate_from(exam) fills the form for editing using windows.to_input_value.
4. Cross-field validation (mirror of the service, for early feedback; the service remains authoritative): slot creation end after start, booking end after booking start, slot creation end not after booking start, cancellation deadline not before booking start. Each message names the two fields involved.
5. HTML5 attributes (required, min, max) are added in the template; no JavaScript.
DEBUGGING:
# print(f"[DEBUG] ExaminationForm data={form.data} errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- booking_end earlier than booking_start fails with a message naming both fields.
- Submitting local "2030-01-10T10:00" with Asia/Kolkata results in to_service_data()["booking_start"] == 2030-01-10 04:30.
- Blank cancellation_deadline is accepted and the service fills booking_end.
- An inactive course is not offered in the course select.
"""
