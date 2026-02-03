"""
测试存储消息接口的不同 HTTP 方法
"""
import asyncio
import aiohttp


async def test_store_methods():
    """测试不同的 HTTP 方法"""
    url = "http://43.139.19.144:1235/api/v1/memories/message"

    body = {
        "project_id": "chatbot",
        "message": {
            "text": "测试消息",
            "user_id": "test_user",
            "run_id": "test_session",
            "speaker": "user"
        },
        "async_mode": True
    }

    methods = ["POST", "PUT", "PATCH"]

    print("="*60)
    print(f"测试 {url}")
    print("="*60)

    async with aiohttp.ClientSession() as session:
        for method in methods:
            print(f"\n测试 {method} 方法:")
            try:
                async with session.request(
                    method,
                    url,
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    print(f"  状态码: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"  ✅ 成功!")
                        print(f"  返回数据: {data}")
                        return
                    else:
                        text = await response.text()
                        print(f"  ❌ 失败: {text[:200]}")
            except Exception as e:
                print(f"  ❌ 异常: {e}")


if __name__ == "__main__":
    asyncio.run(test_store_methods())
