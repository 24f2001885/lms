from flask import Blueprint

examiner_bp = Blueprint("examiner", __name__, url_prefix="/examiner")

# Import route modules to register them on the blueprint
from app.blueprints.examiner import dashboard, evaluations, examinations, slots  # noqa: E402,F401
