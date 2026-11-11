"""
FILE PURPOSE: WTForms for adding and editing a rubric criterion (ADM-07).
DEPENDS ON: flask_wtf, wtforms.
PROMPT FOR LLM IMPLEMENTATION:
1. RubricForm fields: criterion_name (DataRequired, Length 2-100, strip), description (Optional, Length max 500), weightage (DecimalField places 2, NumberRange 0-100), max_score (DecimalField places 2, NumberRange min 0.01), position (IntegerField Optional, default next position).
2. Labels: "Criterion", "Description", "Weightage (%)", "Maximum score".
3. No cross-criterion logic here (total-100 and uniqueness are service rules).
DEBUGGING:
# print(f"[DEBUG] RubricForm errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- weightage 100.01 and -1 are rejected; max_score 0 is rejected; 12.5 is accepted.
"""
