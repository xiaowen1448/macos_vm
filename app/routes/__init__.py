from flask import Blueprint
from .mass_messaging import mass_messaging_bp
from .mupan import mupan_bp
from .icloud_process import icloud_process_bp
from .process import process_bp
from .script_manager import script_manager_bp


def init_app(app):
    app.register_blueprint(mass_messaging_bp)
    app.register_blueprint(mupan_bp)
    app.register_blueprint(icloud_process_bp)
    app.register_blueprint(process_bp)
    app.register_blueprint(script_manager_bp)
    # proxy_assign相关路由已在app.py中直接注册，不需要在此处注册蓝图