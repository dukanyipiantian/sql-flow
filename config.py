import os
from dotenv import load_dotenv


# 加载.env文件
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24).hex())  # 提供fallback
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'  # 自动转换布尔值

    # API配置
    JSON_SORT_KEYS = False  # 禁用JSON键排序
