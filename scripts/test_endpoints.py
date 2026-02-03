"""
测试可能的创建消息端点
"""
import asyncio
import aiohttp


async def test_create_endpoints():
    """测试可能的创建消息端点"""
    base_url = "http://43.139.19.144:1235/api/v1"

    # 可能的端点
    endpoints = [
        "/memories/message",
        "/memories/messages",
        "/memories",
        "/message",
        "/messages",
    ]

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

    print("="*60)
    print("测试不同的端点（POST 方法）")
    print("="*60)

    async with aiohttp.ClientSession() as session:
        for endpoint in endpoints:
            url = f"{base_url}{endpoint}"
            print(f"\nPOST {url}")
            try:
                async with session.post(
                    url,
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    print(f"  状态码: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"  ✅ 成功! 返回: {data}")
                    else:
                        text = await response.text()
                        print(f"  ❌ {text[:200]}")
            except Exception as e:
                print(f"  ❌ 异常: {e}")

    print("\n" + "="*60)
    print("测试不同的端点（PUT 方法）")
    print("="*60)

    async with aiohttp.ClientSession() as session:
        for endpoint in endpoints:
            url = f"{base_url}{endpoint}"
            print(f"\nPUT {url}")
            try:
                async with session.put(
                    url,
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    print(f"  状态码: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"  ✅ 成功! 返回: {data}")
                    else:
                        text = await response.text()
                        print(f"  ❌ {text[:200]}")
            except Exception as e:
                print(f"  ❌ 异常: {e}")


if __name__ == "__main__":
    asyncio.run(test_create_endpoints())
