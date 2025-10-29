import os
import shutil
from datetime import datetime, timedelta
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
        # 检查是否已登录
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
        
        # 检查session是否超时（默认8小时，从app.py中的配置获取）
        if 'login_time' in session:
            try:
                login_time = datetime.fromisoformat(session['login_time'])
                # 计算当前时间与登录时间的差值
                time_diff = datetime.now() - login_time
                # 检查是否超过8小时（28800秒）
                if time_diff.total_seconds() > 28800:  # 8小时 = 8 * 3600秒
                    logger.info(f"用户 {session.get('username', 'unknown')} session超时")
                    # 清除session
                    session.clear()
                    # 跳转到登录页面
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get(
                            'Content-Type') == 'application/json':
                        return jsonify({
                            'success': False,
                            'message': '登录已超时，请重新登录',
                            'redirect': url_for('login')
                        }), 401
                    else:
                        return redirect(url_for('login'))
            except Exception as e:
                logger.error(f"检查session超时失败: {e}")
                # 出错时清除session并跳转到登录页
                session.clear()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get(
                        'Content-Type') == 'application/json':
                    return jsonify({
                        'success': False,
                        'message': 'session验证失败，请重新登录',
                        'redirect': url_for('login')
                    }), 401
                else:
                    return redirect(url_for('login'))
        
        return f(*args, **kwargs)

    return decorated_function
