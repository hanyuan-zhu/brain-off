"""
调试线上记忆 API 接口

测试不同的 URL 路径组合
"""
import asyncio
import aiohttp


async def test_endpoints():
    """测试不同的端点"""
    base_url = "http://43.139.19.144:1235"

    # 测试不同的 URL 组合
    test_cases = [
        # 存储消息的可能路径
        f"{base_url}/api/v1/memories/message",
        f"{base_url}/memories/message",
        f"{base_url}/api/v1/message",

        # 搜索的可能路径
        f"{base_url}/api/v1/memories/search/bundle",
        f"{base_url}/memories/search/bundle",
        f"{base_url}/api/v1/search/bundle",
    ]

    # 测试请求体
    store_body = {
        "project_id": "chatbot",
        "message": {
            "text": "测试消息",
            "user_id": "test_user",
            "run_id": "test_session",
            "speaker": "user"
        },
        "async_mode": True
    }

    search_body = {
        "project_id": "chatbot",
        "query": "测试",
        "top_k": 3
    }

    print("="*60)
    print("测试存储消息接口")
    print("="*60)

    async with aiohttp.ClientSession() as session:
        for url in test_cases[:3]:
            print(f"\n测试 POST {url}")
            try:
                async with session.post(
                    url,
                    json=store_body,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    print(f"  状态码: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"  ✅ 成功: {data}")
                    else:
                        text = await response.text()
                        print(f"  ❌ 失败: {text[:200]}")
            except Exception as e:
                print(f"  ❌ 异常: {e}")

    print("\n" + "="*60)
    print("测试搜索接口")
    print("="*60)

    async with aiohttp.ClientSession() as session:
        for url in test_cases[3:]:
            print(f"\n测试 POST {url}")
            try:
                async with session.post(
                    url,
                    json=search_body,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    print(f"  状态码: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"  ✅ 成功，返回数据键: {list(data.keys())}")
                    else:
                        text = await response.text()
                        print(f"  ❌ 失败: {text[:200]}")
            except Exception as e:
                print(f"  ❌ 异常: {e}")


if __name__ == "__main__":
    asyncio.run(test_endpoints())
