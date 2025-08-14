import os
from dotenv import load_dotenv


# 加载.env文件
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')

