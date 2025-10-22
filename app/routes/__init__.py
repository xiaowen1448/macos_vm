from flask import Blueprint
from .mass_messaging import mass_messaging_bp
from .mupan import mupan_bp
from .icloud_manager import icloud_manager
from .icloud_process import icloud_process_bp

def init_app(app):
    app.register_blueprint(mass_messaging_bp)
    app.register_blueprint(mupan_bp)
    app.register_blueprint(icloud_manager)
    app.register_blueprint(icloud_process_bp)