"""
Interactive CLI chat interface for the AI Task Manager.

Usage:
    python chat.py

Commands:
    /help    - Show available commands
    /clear   - Clear conversation history
    /stats   - Show session statistics
    /exit    - Exit the chat
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional
from uuid import UUID

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.database.session import get_db
from src.core.agent.memory_driven_agent import MemoryDrivenAgent
from src.infrastructure.utils.cli_colors import (
    format_assistant_prefix, format_thinking_prefix,
    format_tool_call, format_tool_success, format_tool_error,
    Colors, dim, draw_separator
)
from src.skills.initialize import initialize_all_tools


class ChatInterface:
    """Interactive chat interface for the agent."""

    def __init__(self, use_reasoner: bool = False, fixed_skill_id: Optional[str] = None):
        """
        Initialize chat interface.

        Args:
            use_reasoner: If True, use deepseek-reasoner (shows thinking).
                         If False, use deepseek-chat (faster, no thinking).
            fixed_skill_id: If provided, always use this skill ID instead of LLM selection.
        """
        self.session_id = None
        self.message_count = 0
        self.db = None
        self.agent = None
        self.use_reasoner = use_reasoner
        self.fixed_skill_id = fixed_skill_id

        # Initialize prompt_toolkit session
        self.prompt_session = PromptSession()
        self.key_bindings = self._setup_key_bindings()

    def _setup_key_bindings(self):
        """Setup key bindings for multi-line input."""
        bindings = KeyBindings()

        @bindings.add('enter')
        def _(event):
            # Enter submits the input
            event.current_buffer.validate_and_handle()

        return bindings

    def print_welcome(self):
        """Print welcome message with GauzAssist logo."""
        # Clear screen effect with some spacing
        print("\n" * 2)

        # GauzAssist ASCII logo with gradient colors
        print(f"{Colors.BRIGHT_MAGENTA}   ██████{Colors.BRIGHT_CYAN}╗ {Colors.BRIGHT_MAGENTA} █████{Colors.BRIGHT_CYAN}╗ {Colors.BRIGHT_MAGENTA}██{Colors.BRIGHT_CYAN}╗   {Colors.BRIGHT_MAGENTA}██{Colors.BRIGHT_CYAN}╗{Colors.BRIGHT_MAGENTA}███████{Colors.BRIGHT_CYAN}╗ {Colors.RESET}")
        print(f"{Colors.BRIGHT_MAGENTA}  ██{Colors.BRIGHT_CYAN}╔════╝ {Colors.BRIGHT_MAGENTA}██{Colors.BRIGHT_CYAN}╔══{Colors.BRIGHT_MAGENTA}██{Colors.BRIGHT_CYAN}╗{Colors.BRIGHT_MAGENTA}██{Colors.BRIGHT_CYAN}║   {Colors.BRIGHT_MAGENTA}██{Colors.BRIGHT_CYAN}║{Colors.BRIGHT_MAGENTA}╚══███{Colors.BRIGHT_CYAN}╔╝{Colors.RESET}")
        print(f"{Colors.BRIGHT_CYAN}  ██{Colors.BRIGHT_BLUE}║  {Colors.BRIGHT_CYAN}███{Colors.BRIGHT_BLUE}╗{Colors.BRIGHT_CYAN}███████{Colors.BRIGHT_BLUE}║{Colors.BRIGHT_CYAN}██{Colors.BRIGHT_BLUE}║   {Colors.BRIGHT_CYAN}██{Colors.BRIGHT_BLUE}║  {Colors.BRIGHT_CYAN}███{Colors.BRIGHT_BLUE}╔╝ {Colors.RESET}")
        print(f"{Colors.BRIGHT_CYAN}  ██{Colors.BRIGHT_BLUE}║   {Colors.BRIGHT_CYAN}██{Colors.BRIGHT_BLUE}║{Colors.BRIGHT_CYAN}██{Colors.BRIGHT_BLUE}╔══{Colors.BRIGHT_CYAN}██{Colors.BRIGHT_BLUE}║{Colors.BRIGHT_CYAN}██{Colors.BRIGHT_BLUE}║   {Colors.BRIGHT_CYAN}██{Colors.BRIGHT_BLUE}║ {Colors.BRIGHT_CYAN}███{Colors.BRIGHT_BLUE}╔╝  {Colors.RESET}")
        print(f"{Colors.BRIGHT_BLUE}  ╚██████{Colors.BLUE}╔╝{Colors.BRIGHT_BLUE}██{Colors.BLUE}║  {Colors.BRIGHT_BLUE}██{Colors.BLUE}║{Colors.BRIGHT_BLUE}╚██████{Colors.BLUE}╔╝{Colors.BRIGHT_BLUE}███████{Colors.BLUE}╗{Colors.RESET}")
        print(f"{Colors.BLUE}   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝{Colors.RESET}")

        # Subtitle with mode indicator
        mode_text = "Reasoner" if self.use_reasoner else "Chat"
        mode_color = Colors.BRIGHT_YELLOW if self.use_reasoner else Colors.BRIGHT_GREEN
        print(f"\n{Colors.BRIGHT_WHITE}        A S S I S T{Colors.RESET}  {dim('|')}  {mode_color}{mode_text}{Colors.RESET} {dim('Mode')}")

        # Show fixed skill mode if enabled
        if self.fixed_skill_id:
            print(f"\n{Colors.BRIGHT_CYAN}[固定 Skill 模式]{Colors.RESET} 使用 skill: {Colors.BRIGHT_WHITE}{self.fixed_skill_id}{Colors.RESET}")
            print(f"{dim('跳过 LLM 自动选择，所有对话使用此 skill')}")

        # Separator
        print(f"\n{dim('─' * 60)}\n")

    def print_help(self):
        """Print help message."""
        print("\n可用命令：")
        print("  /help    - 显示此帮助信息")
        print("  /clear   - 清除对话历史")
        print("  /stats   - 显示会话统计")
        print("  /exit    - 退出聊天")
        print("\n多行输入：")
        print("  • 按 Enter 键提交消息")
        print("  • 粘贴多行文本会完整保留所有换行")
        print("\n示例对话：")
        print("  • 我想做一个个人财务管理工具")
        print("  • 找一下关于学习的想法")
        print("  • 帮我整理最近的想法")
        print()

    def print_stats(self):
        """Print session statistics."""
        print(f"\n📊 会话统计：")
        print(f"  会话 ID: {str(self.session_id)[:8]}..." if self.session_id else "  会话 ID: 未创建")
        print(f"  消息数量: {self.message_count}")
        print()

    async def process_command(self, command: str) -> bool:
        """
        Process special commands.

        Returns:
            True if should continue, False if should exit
        """
        if command == "/help":
            self.print_help()
            return True

        elif command == "/clear":
            self.session_id = None
            self.message_count = 0
            print("\n✓ 对话历史已清除\n")
            return True

        elif command == "/stats":
            self.print_stats()
            return True

        elif command == "/exit":
            print("\n👋 再见！\n")
            return False

        else:
            print(f"\n❌ 未知命令: {command}")
            print("输入 /help 查看可用命令\n")
            return True

    async def chat_loop(self):
        """Main chat loop."""
        self.print_welcome()

        # Initialize database and agent
        async for db in get_db():
            self.db = db
            self.agent = MemoryDrivenAgent(
                db,
                use_reasoner=self.use_reasoner,
                fixed_skill_id=self.fixed_skill_id
            )

            try:
                while True:
                    # Get user input with prompt_toolkit (supports multi-line)
                    try:
                        user_input = await self.prompt_session.prompt_async(
                            HTML(f'<ansibrightcyan><b>你:</b></ansibrightcyan> '),
                            multiline=True,  # Enable multi-line mode
                            key_bindings=self.key_bindings
                        )
                        user_input = user_input.strip()
                    except (EOFError, KeyboardInterrupt):
                        print("\n\n👋 再见！\n")
                        break

                    if not user_input:
                        continue

                    # Handle commands
                    if user_input.startswith("/"):
                        should_continue = await self.process_command(user_input)
                        if not should_continue:
                            break
                        continue

                    # Process message with agent
                    print()  # New line before response

                    # Simplified state tracking
                    assistant_started = False

                    def stream_callback(msg_type: str, content: str):
                        nonlocal assistant_started

                        if msg_type == 'thinking':
                            if not assistant_started:
                                print(format_thinking_prefix(), end=" ", flush=True)
                                assistant_started = True
                            print(dim(content), end="", flush=True)

                        elif msg_type == 'content':
                            if not assistant_started:
                                print(format_assistant_prefix(), end=" ", flush=True)
                                assistant_started = True
                            print(content, end="", flush=True)

                        elif msg_type == 'tool_call':
                            print(format_tool_call(content), end="", flush=True)

                        elif msg_type == 'tool_result':
                            # 判断是成功还是失败
                            if '✓' in content:
                                print(f" {format_tool_success(content)}", end="", flush=True)
                            elif '✗' in content:
                                print(f" {format_tool_error(content)}", end="", flush=True)
                            else:
                                print(f" {content}", end="", flush=True)

                    try:
                        response = await self.agent.process_message(
                            user_input,
                            session_id=UUID(self.session_id) if self.session_id else None,
                            stream_callback=stream_callback
                        )

                        # Update session info
                        if not self.session_id:
                            self.session_id = response["session_id"]

                        self.message_count += 1

                        # Print response only if not streamed
                        if not assistant_started and response["success"]:
                            print(f"{format_assistant_prefix()} {response['text']}")
                        elif not response["success"]:
                            error_msg = f"❌ 错误: {response.get('error', '未知错误')}"
                            print(f"\n{Colors.RED}{error_msg}{Colors.RESET}")

                        # Add extra newline after response for clean separation
                        print("\n")

                    except Exception as e:
                        print(f"\n❌ 处理消息时出错: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        print("\n", end="", flush=True)

                    # Commit after each successful interaction
                    await db.commit()

            except Exception as e:
                print(f"\n❌ 发生错误: {str(e)}")
                await db.rollback()
            finally:
                break


def main():
    """Main entry point."""
    import argparse

    # Initialize all skill tools
    initialize_all_tools()

    parser = argparse.ArgumentParser(description='GauzAssist - 你的智能助手')
    parser.add_argument(
        '--reasoner',
        action='store_true',
        help='使用 Reasoner 模式（显示思考过程）'
    )
    parser.add_argument(
        '--skill',
        type=str,
        help='固定加载指定的 skill ID，跳过 LLM 自动选择'
    )
    args = parser.parse_args()

    chat = ChatInterface(use_reasoner=args.reasoner, fixed_skill_id=args.skill)
    try:
        asyncio.run(chat.chat_loop())
    except KeyboardInterrupt:
        print("\n\n👋 再见！\n")


if __name__ == "__main__":
    main()
