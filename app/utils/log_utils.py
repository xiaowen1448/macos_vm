import logging
import os
import sys
from datetime import datetime

# 日志级别配置
LOG_LEVEL = logging.INFO

# 日志格式配置
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

def setup_logger(logger_name=None, log_file=None, level=LOG_LEVEL):
    """
    设置日志记录器
    
    Args:
        logger_name: 日志记录器名称
        log_file: 日志文件路径
        level: 日志级别
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    # 创建日志记录器
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 创建格式化器
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 如果指定了日志文件，创建文件处理器
    if log_file:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def get_logger(name=None, log_file=None):
    """
    获取或创建日志记录器
    
    Args:
        name: 日志记录器名称
        log_file: 日志文件路径
        
    Returns:
        logging.Logger: 日志记录器实例
    """
    return setup_logger(name, log_file)

def get_default_logger():
    """
    获取默认日志记录器
    
    Returns:
        logging.Logger: 默认日志记录器
    """
    return get_logger('default')

# 创建全局logger实例，其他模块可以直接导入使用
logger = get_logger('macos_vm')