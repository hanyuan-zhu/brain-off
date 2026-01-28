"""
CLI颜色和样式工具 - 使用ANSI转义码
"""


class Colors:
    """ANSI颜色代码"""
    # 基础颜色
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # 亮色
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

    # 背景色
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'

    # 样式
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'

    # 重置
    RESET = '\033[0m'


class Symbols:
    """Unicode符号和图案"""
    # 状态符号
    CHECK = '✓'
    CROSS = '✗'
    ARROW_RIGHT = '→'
    ARROW_LEFT = '←'
    ARROW_UP = '↑'
    ARROW_DOWN = '↓'

    # 进度符号
    SPINNER = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    DOTS = ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷']

    # 边框符号
    BOX_LIGHT_HORIZONTAL = '─'
    BOX_LIGHT_VERTICAL = '│'
    BOX_LIGHT_DOWN_RIGHT = '┌'
    BOX_LIGHT_DOWN_LEFT = '┐'
    BOX_LIGHT_UP_RIGHT = '└'
    BOX_LIGHT_UP_LEFT = '┘'
    BOX_LIGHT_VERTICAL_RIGHT = '├'
    BOX_LIGHT_VERTICAL_LEFT = '┤'

    # 其他符号
    BULLET = '•'
    STAR = '★'
    HEART = '♥'
    DIAMOND = '◆'
    CIRCLE = '●'
    SQUARE = '■'


def colorize(text: str, color: str, bold: bool = False) -> str:
    """
    给文本添加颜色

    Args:
        text: 要着色的文本
        color: 颜色代码（来自Colors类）
        bold: 是否加粗

    Returns:
        带颜色的文本
    """
    style = Colors.BOLD if bold else ''
    return f"{style}{color}{text}{Colors.RESET}"


def success(text: str) -> str:
    """成功消息（绿色）"""
    return colorize(f"{Symbols.CHECK} {text}", Colors.GREEN)


def error(text: str) -> str:
    """错误消息（红色）"""
    return colorize(f"{Symbols.CROSS} {text}", Colors.RED)


def warning(text: str) -> str:
    """警告消息（黄色）"""
    return colorize(f"⚠ {text}", Colors.YELLOW)


def info(text: str) -> str:
    """信息消息（蓝色）"""
    return colorize(f"ℹ {text}", Colors.BLUE)


def dim(text: str) -> str:
    """暗淡文本（用于次要信息）"""
    return f"{Colors.DIM}{text}{Colors.RESET}"


def bold(text: str) -> str:
    """加粗文本"""
    return f"{Colors.BOLD}{text}{Colors.RESET}"


def draw_box(text: str, width: int = 60, color: str = Colors.CYAN) -> str:
    """
    绘制文本框

    Args:
        text: 框内文本
        width: 框宽度
        color: 边框颜色

    Returns:
        带边框的文本
    """
    s = Symbols
    top = f"{s.BOX_LIGHT_DOWN_RIGHT}{s.BOX_LIGHT_HORIZONTAL * (width - 2)}{s.BOX_LIGHT_DOWN_LEFT}"
    bottom = f"{s.BOX_LIGHT_UP_RIGHT}{s.BOX_LIGHT_HORIZONTAL * (width - 2)}{s.BOX_LIGHT_UP_LEFT}"
    middle = f"{s.BOX_LIGHT_VERTICAL} {text.ljust(width - 4)} {s.BOX_LIGHT_VERTICAL}"

    return colorize(f"{top}\n{middle}\n{bottom}", color)


def draw_separator(width: int = 60, char: str = '─', color: str = Colors.BRIGHT_BLACK) -> str:
    """绘制分隔线"""
    return colorize(char * width, color)


# 预定义的主题颜色
class Theme:
    """主题颜色配置"""
    # 用户输入
    USER_PREFIX = Colors.BRIGHT_CYAN
    USER_TEXT = Colors.WHITE

    # 助手输出
    ASSISTANT_PREFIX = Colors.BRIGHT_GREEN
    ASSISTANT_TEXT = Colors.WHITE

    # 思考过程
    THINKING_PREFIX = Colors.BRIGHT_MAGENTA
    THINKING_TEXT = Colors.DIM

    # 工具调用
    TOOL_CALL = Colors.BRIGHT_YELLOW
    TOOL_SUCCESS = Colors.GREEN
    TOOL_ERROR = Colors.RED

    # 系统消息
    SYSTEM = Colors.BRIGHT_BLACK
    ERROR = Colors.RED
    WARNING = Colors.YELLOW
    INFO = Colors.BLUE


def format_user_input(text: str) -> str:
    """格式化用户输入"""
    prefix = colorize("你:", Theme.USER_PREFIX, bold=True)
    return f"{prefix} {text}"


def format_assistant_prefix() -> str:
    """格式化助手前缀"""
    return colorize("🤖 助手:", Theme.ASSISTANT_PREFIX, bold=True)


def format_thinking_prefix() -> str:
    """格式化思考前缀"""
    return colorize("💭 思考中:", Theme.THINKING_PREFIX, bold=True)


def format_tool_call(text: str) -> str:
    """格式化工具调用"""
    return colorize(text, Theme.TOOL_CALL)


def format_tool_success(text: str) -> str:
    """格式化工具成功"""
    return colorize(text, Theme.TOOL_SUCCESS)


def format_tool_error(text: str) -> str:
    """格式化工具错误"""
    return colorize(text, Theme.TOOL_ERROR)
