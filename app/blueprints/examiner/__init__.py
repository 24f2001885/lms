from flask import Blueprint

examiner_bp = Blueprint("examiner", __name__, url_prefix="/examiner")

# Import route modules to register them on the blueprint
from app.blueprints.examiner import (  # noqa: E402, F401
    charts,
    dashboard,
    evaluations,
    examinations,
    slots,
)
