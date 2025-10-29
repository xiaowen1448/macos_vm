import os
import shutil
from .log_utils import logger

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