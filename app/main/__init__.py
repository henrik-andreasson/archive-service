from flask import Blueprint

bp = Blueprint('archive', __name__)

from app.main import archive
