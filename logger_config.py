import logging
import sys
import os

def setup_logging():
    """设置系统日志和用户日志配置"""

    # 创建用户日志处理器 - 输出到stdout，用于前台显示
    user_handler = logging.StreamHandler(sys.stdout)
    user_handler.setLevel(logging.INFO)
    user_formatter = logging.Formatter('%(message)s')
    user_handler.setFormatter(user_formatter)

    # 创建系统日志处理器 - 输出到文件，用于调试
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    system_handler = logging.FileHandler(os.path.join(log_dir, "system.log"))
    system_handler.setLevel(logging.DEBUG)
    system_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    system_handler.setFormatter(system_formatter)

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # 添加处理器
    root_logger.addHandler(user_handler)
    root_logger.addHandler(system_handler)

    # 创建专门的用户日志记录器
    user_logger = logging.getLogger('user')
    user_logger.addHandler(user_handler)
    user_logger.propagate = False  # 防止重复输出

    # 创建专门的系统日志记录器
    system_logger = logging.getLogger('system')
    system_logger.addHandler(system_handler)
    system_logger.propagate = False

    return user_logger, system_logger

# 全局日志记录器
user_logger, system_logger = setup_logging()

# 便捷函数
def user_print(*args, **kwargs):
    """用户前台输出函数"""
    print(*args, **kwargs)

def debug_print(*args, **kwargs):
    """调试输出函数"""
    system_logger.debug(" ".join(str(arg) for arg in args))

def info_print(*args, **kwargs):
    """普通信息输出"""
    system_logger.info(" ".join(str(arg) for arg in args))

def error_print(*args, **kwargs):
    """错误输出"""
    system_logger.error(" ".join(str(arg) for arg in args))

def warn_print(*args, **kwargs):
    """警告输出"""
    system_logger.warning(" ".join(str(arg) for arg in args))
