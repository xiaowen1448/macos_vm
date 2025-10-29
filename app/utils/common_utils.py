import os
import shutil
from .log_utils import logger
from flask import session, request, jsonify, redirect, url_for
from functools import wraps

def clear_sessions_on_startup():
    """启动时清除所有session"""
    try:
        # 清除session文件（如果使用文件session）    
        session_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'flask_session')
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
            os.makedirs(session_dir, exist_ok=True)
            logger.info("已清除所有session文件")
    except Exception as e:
        logger.warning(f"清除session文件失败: {e}")

    logger.info("应用启动，所有session已重置")



# 确保 web/templates/ 目录下有 login.html 和 dashboard.html 文件，否则会报错。
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            # 检查是否是AJAX请求
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get(
                    'Content-Type') == 'application/json':
                return jsonify({
                    'success': False,
                    'message': '请先登录',
                    'redirect': url_for('login')
                }), 401
            else:
                return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function
