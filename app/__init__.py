"""应用包入口。

Windows 控制台/IDE 输出被重定向时，stdout 往往是 GBK(cp936)。
hello_agents 内部会 print emoji（例如 "📝 使用 Stdio 传输"），GBK 编码不了 emoji
就会抛 UnicodeEncodeError；而 MCPTool 把异常全部吞掉，表现成"工具连不上"。
这里让无法编码的字符降级显示，而不是直接抛异常。
"""

import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except (AttributeError, ValueError):  # 非标准流，忽略
        pass
