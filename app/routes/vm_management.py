import os
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template
from functools import wraps
from config import *

# 创建虚拟机信息管理蓝图
vm_management_bp = Blueprint('vm_management', __name__)

# 导入日志工具
from app.utils.log_utils import get_logger

# 获取日志记录器
logger = get_logger(__name__)

# 导入login_required装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 这里应该导入实际的login_required逻辑
        # 由于我们是从主应用移动过来，暂时保持简单
        return f(*args, **kwargs)
    return decorated_function
