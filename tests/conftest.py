import pytest
import sys
from pathlib import Path

# 将项目根目录添加到Python路径
sys.path.append(str(Path(__file__).parent.parent))

from app import create_app


@pytest.fixture
def app():
    """应用fixture"""
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
    })
    yield app

@pytest.fixture
def client(app):
    """测试客户端fixture"""
    return app.test_client()  # 关键点：必须返回Flask测试客户端