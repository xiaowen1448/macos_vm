from flask import Blueprint
from .mass_messaging import mass_messaging_bp
from .mupan import mupan_bp
from .icloud_process import icloud_process_bp
from .process import process_bp
# 重新导入proxy_assign模块以使用其中的API函数，但不注册蓝图
from . import proxy_assign


def init_app(app):
    app.register_blueprint(mass_messaging_bp)
    app.register_blueprint(mupan_bp)
    app.register_blueprint(icloud_process_bp)
    app.register_blueprint(process_bp)
    # 不注册proxy_assign_bp蓝图，避免与app.py中的proxy_assign_page冲突
    # 但保留模块导入以使用其中的函数