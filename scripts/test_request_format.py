"""
测试正确的请求格式
"""
import asyncio
import aiohttp


async def test_correct_format():
    """测试正确的请求格式"""
    url = "http://43.139.19.144:1235/api/v1/memories/message"

    # 测试不同的请求体格式
    test_cases = [
        {
            "name": "格式1: message 对象",
            "body": {
                "project_id": "chatbot",
                "message": {
                    "text": "测试消息1",
                    "user_id": "test_user",
                    "run_id": "test_session",
                    "speaker": "user"
                },
                "async_mode": True
            }
        },
        {
            "name": "格式2: memory 字符串",
            "body": {
                "project_id": "chatbot",
                "memory": "测试消息2",
                "async_mode": True
            }
        },
        {
            "name": "格式3: memory 对象",
            "body": {
                "project_id": "chatbot",
                "memory": {
                    "text": "测试消息3",
                    "user_id": "test_user",
                    "run_id": "test_session",
                    "speaker": "user"
                },
                "async_mode": True
            }
        }
    ]

    print("="*60)
    print("测试不同的请求格式")
    print("="*60)

    async with aiohttp.ClientSession() as session:
        for test_case in test_cases:
            print(f"\n{test_case['name']}:")
            print(f"请求体: {test_case['body']}")

            try:
                async with session.put(
                    url,
                    json=test_case['body'],
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    print(f"  状态码: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"  ✅ 成功!")
                        print(f"  返回: {data}")
                    else:
                        text = await response.text()
                        print(f"  ❌ 失败: {text[:300]}")
            except Exception as e:
                print(f"  ❌ 异常: {e}")


if __name__ == "__main__":
    asyncio.run(test_correct_format())
