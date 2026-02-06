"""
智能测试机器人 - 动态测试 Supervision Agent

测试机器人使用 DeepSeek，模拟真实用户与 Supervision Agent 的多轮对话。
测试完成后生成详细的测试报告。
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import os

# 禁用代理
os.environ.pop('ALL_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from openai import AsyncOpenAI
from dotenv import load_dotenv

from src.infrastructure.database.session import get_db
from src.core.agent.memory_driven_agent import MemoryDrivenAgent
from src.skills.initialize import initialize_all_tools

load_dotenv()


class TestBot:
    """测试机器人 - 使用 DeepSeek 模拟用户"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        )
        self.conversation_history = []

    async def generate_question(
        self,
        context: str,
        previous_response: str = None,
        round_num: int = 1
    ) -> str:
        """
        根据上下文生成测试问题

        Args:
            context: 测试场景描述
            previous_response: 上一轮的回答
            round_num: 当前轮次
        """
        if round_num == 1:
            # 第一轮：开始任务
            prompt = f"""你是一个测试工程师，正在测试一个监理 AI 助手。

测试场景：{context}

请生成第一个问题，要求监理助手开始分析工作。
问题要具体、清晰，符合真实监理工作场景。

只输出问题，不要其他内容。"""
        else:
            # 后续轮次：根据回答继续提问
            prompt = f"""你是一个测试工程师，正在测试一个监理 AI 助手。

测试场景：{context}

监理助手的上一轮回答：
{previous_response[:500]}...

这是第 {round_num} 轮对话。请根据助手的回答，生成下一个合理的追问或新的任务。

要求：
- 如果助手提到了发现的问题，追问详情
- 如果助手提到了下一步计划，要求执行
- 如果助手完成了某个分析，要求查看其他方面
- 保持对话的连贯性和真实性

只输出问题，不要其他内容。"""

        response = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        question = response.choices[0].message.content.strip()
        return question

    async def analyze_conversation(
        self,
        conversation: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分析整个对话过程，生成测试报告

        Args:
            conversation: 对话历史
        """
        # 构建对话摘要
        dialogue = "\n\n".join([
            f"[轮次 {i+1}]\n用户: {turn['question']}\n助手: {turn['response'][:300]}...\n工具调用: {turn['tool_calls']}"
            for i, turn in enumerate(conversation)
        ])

        prompt = f"""你是一个测试分析师，请分析以下监理 AI 助手的测试对话。

对话记录：
{dialogue}

请从以下维度分析：
1. 工作流程完整性 - 是否按照监理工作流程进行
2. 工具使用合理性 - 工具调用是否恰当
3. 日志记录情况 - 是否记录了工作日志（查看 append_to_file 调用）
4. 专业性 - 回答是否专业、严谨
5. 问题发现能力 - 是否发现了图纸问题

输出 JSON 格式：
{{
  "workflow_score": 0-10,
  "tool_usage_score": 0-10,
  "logging_score": 0-10,
  "professionalism_score": 0-10,
  "problem_detection_score": 0-10,
  "summary": "总体评价",
  "strengths": ["优点1", "优点2"],
  "weaknesses": ["不足1", "不足2"]
}}"""

        response = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        import json
        try:
            analysis = json.loads(response.choices[0].message.content)
        except:
            analysis = {"error": "分析失败", "raw": response.choices[0].message.content}

        return analysis


async def run_supervision_test():
    """
    运行 Supervision Agent 动态测试

    测试流程：
    1. 初始化测试机器人和 Supervision Agent
    2. 进行 3-5 轮对话
    3. 分析对话质量
    4. 生成测试报告
    """
    print("=" * 80)
    print("Supervision Agent 动态测试")
    print("=" * 80)

    # 测试场景
    test_scenario = """
    测试项目：某工业厂房钢结构图纸审核
    图纸位置：workspace/cad_files/
    任务要求：
    1. 分析图纸结构和布局
    2. 检查尺寸标注完整性
    3. 发现潜在设计问题
    4. 记录完整的工作日志
    """

    print(f"\n测试场景：\n{test_scenario}\n")

    # 初始化测试机器人
    test_bot = TestBot()
    conversation_history = []

    # 初始化 Supervision Agent
    print("初始化 Supervision Agent...")
    async for db in get_db():
        agent = MemoryDrivenAgent(
            db=db,
            use_reasoner=False,
            fixed_skill_id="supervision"
        )

        print(f"✓ Agent 初始化完成")
        print(f"  - Skill: supervision")
        print(f"  - 模型将在首次调用时初始化")
        print()

        # 进行多轮对话测试
        max_rounds = 5  # 增加到5轮
        for round_num in range(1, max_rounds + 1):
            print("-" * 80)
            print(f"第 {round_num} 轮对话")
            print("-" * 80)

            # 生成测试问题
            previous_response = conversation_history[-1]["response"] if conversation_history else None
            question = await test_bot.generate_question(
                context=test_scenario,
                previous_response=previous_response,
                round_num=round_num
            )

            print(f"\n[测试机器人] {question}\n")

            # Supervision Agent 处理
            print("[Supervision Agent 工作中...]\n")

            try:
                result = await agent.process_message(
                    user_message=question,
                    session_id=None
                )

                response_text = result.get("text", "")
                tool_calls = result.get("metadata", {}).get("tool_calls", [])

                # 第一轮后打印模型信息
                if round_num == 1 and agent.llm_client:
                    print(f"✓ 模型已初始化: {agent.llm_client.model}")
                    print(f"  Provider: {agent.llm_client.provider}")
                    print(f"  Vision: {agent.llm_client.supports_vision}\n")

                print(f"[Supervision Agent] {response_text[:500]}...")
                print(f"\n工具调用: {len(tool_calls)} 次")
                if tool_calls:
                    for tc in tool_calls[:3]:
                        print(f"  - {tc['name']}")

                # 记录对话
                conversation_history.append({
                    "round": round_num,
                    "question": question,
                    "response": response_text,
                    "tool_calls": [tc["name"] for tc in tool_calls]
                })

            except Exception as e:
                error_msg = str(e)
                print(f"\n❌ 错误: {error_msg}")

                # 如果是网络超时，记录但继续
                if "CancelledError" in error_msg or "timeout" in error_msg.lower():
                    print("  (网络超时，跳过本轮)")
                    continue
                else:
                    import traceback
                    traceback.print_exc()
                    break

            print()

        break  # 退出 db session

    # 分析对话质量
    print("=" * 80)
    print("分析对话质量...")
    print("=" * 80)

    analysis = await test_bot.analyze_conversation(conversation_history)

    # 显示分析结果
    print("\n测试分析结果：")
    print(f"  工作流程完整性: {analysis.get('workflow_score', 'N/A')}/10")
    print(f"  工具使用合理性: {analysis.get('tool_usage_score', 'N/A')}/10")
    print(f"  日志记录情况: {analysis.get('logging_score', 'N/A')}/10")
    print(f"  专业性: {analysis.get('professionalism_score', 'N/A')}/10")
    print(f"  问题发现能力: {analysis.get('problem_detection_score', 'N/A')}/10")
    print(f"\n总体评价: {analysis.get('summary', 'N/A')}")
    print()

    # 生成测试报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"workspace/notes/test_report_{timestamp}.md"

    report_content = f"""# Supervision Agent 测试报告

## 测试信息
- 测试时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- 测试轮次: {len(conversation_history)} 轮
- 测试场景: {test_scenario.strip()}

## 对话记录
"""

    # 添加对话记录
    for turn in conversation_history:
        report_content += f"""
### 第 {turn['round']} 轮

**用户问题**:
{turn['question']}

**Agent 回答**:
{turn['response'][:1000]}...

**工具调用**: {', '.join(turn['tool_calls']) if turn['tool_calls'] else '无'}

---
"""

    # 添加分析结果
    report_content += f"""
## 测试分析

### 评分结果
- 工作流程完整性: {analysis.get('workflow_score', 'N/A')}/10
- 工具使用合理性: {analysis.get('tool_usage_score', 'N/A')}/10
- 日志记录情况: {analysis.get('logging_score', 'N/A')}/10
- 专业性: {analysis.get('professionalism_score', 'N/A')}/10
- 问题发现能力: {analysis.get('problem_detection_score', 'N/A')}/10

### 总体评价
{analysis.get('summary', 'N/A')}

### 优点
"""
    for strength in analysis.get('strengths', []):
        report_content += f"- {strength}\n"

    report_content += "\n### 不足\n"
    for weakness in analysis.get('weaknesses', []):
        report_content += f"- {weakness}\n"

    # 保存报告
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"✓ 测试报告已保存: {report_path}")

    # 检查工作日志
    work_log_path = "workspace/work_log.md"
    if Path(work_log_path).exists():
        print(f"✓ 工作日志已生成: {work_log_path}")
        with open(work_log_path, "r", encoding="utf-8") as f:
            log_content = f.read()
            print(f"  日志长度: {len(log_content)} 字符")
    else:
        print(f"⚠️  工作日志未生成: {work_log_path}")

    return report_path, work_log_path


if __name__ == "__main__":
    asyncio.run(run_supervision_test())
