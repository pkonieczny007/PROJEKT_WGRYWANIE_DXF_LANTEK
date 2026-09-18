# -*- coding: utf-8 -*-
from flask import Blueprint

bp = Blueprint("dxf", __name__, url_prefix="/dxf", template_folder="../../templates")

from . import routes  # noqa: E402,F401
