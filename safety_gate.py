"""
安全门槛 — 首次运行需确认风险
"""
import os
import sys
from pathlib import Path

ACK_FILE = Path(__file__).parent / ".acknowledged"


def check_acknowledgment():
    """
    检查用户是否已确认风险。
    首次运行强制显示警告，必须输入特定文字才能继续。
    确认后创建 .acknowledged 文件，后续不再提示。
    """
    if ACK_FILE.exists():
        return True

    print("""
╔══════════════════════════════════════════════════════════════╗
║                    ⚠️  重要风险警告                          ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  本工具通过浏览器自动化在社交平台发布内容。                    ║
║                                                              ║
║  风险包括但不限于：                                           ║
║  • 所有平台用户协议均禁止自动化操作                           ║
║  • 可能导致账号被永久封禁（已有真实案例）                      ║
║  • 批量发布可能触犯相关法律法规                               ║
║                                                              ║
║  本工具仅供技术研究和学习，研究浏览器自动化与反检测技术。      ║
║  请勿用于违反平台服务条款的行为。                              ║
║                                                              ║
║  继续使用即表示你已充分了解上述风险，                          ║
║  并自行承担一切可能的后果。                                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

    try:
        answer = input("输入 'I understand the risks' 确认继续: ").strip()
        if answer == "I understand the risks":
            ACK_FILE.touch()
            print("✅ 已确认。\n")
            return True
        else:
            print("❌ 未确认，退出。")
            sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print("\n❌ 已取消。")
        sys.exit(1)


def ensure_acknowledged():
    """非交互模式：直接创建确认文件（用于服务端自动部署）"""
    ACK_FILE.touch()
    return True
