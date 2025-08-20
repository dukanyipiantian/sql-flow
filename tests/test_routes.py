def test_home_page(client):
    pass


def test_sql_parsing(client):
    # 测试简单SELECT（完整格式）
    test_sql = "SELECT u.id, o.order_date FROM users u LEFT JOIN orders o ON u.id = o.user_id WHERE u.status = 'active';"
    response = client.post(
        "/api/parse",
        json={"sql": test_sql},  # 必须用json参数
        headers={"Content-Type": "application/json"}  # 必须设置请求头
    )

    assert response.status_code == 200, f"状态码非200，实际为{response.status_code}"
    data = response.get_json()
    print(f"解析结果: {data}")

    # 根据你的API实际返回结构调整断言
    assert data["success"] is True, "API返回success应为True"
    assert "users" in data["data"]["tables"], f"解析失败，实际返回: {data}"

    # 测试带别名的表（简化写法）
    test_sql2 = "SELECT u.id FROM users AS u"
    response = client.post("/api/parse",
                           json={"sql": test_sql2},
                           headers={"Content-Type": "application/json"}
                           )
    response_data = response.get_json()
    assert "users" in response_data["data"]["tables"]