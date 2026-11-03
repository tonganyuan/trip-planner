"""高德地图 MCP 工具的统一创建入口。

这里集中处理 Windows 上最容易踩的两个坑：

1. **uvx 不在 PATH 里**
   `uvx` 由 `uv` 附带，安装在本项目的 `.venv/Scripts/uvx.exe`。
   只有"激活虚拟环境"后它才在 PATH 上；用 IDE 直接以 `.venv` 的解释器运行、
   或者用系统 Python 运行时，`MCPTool` 里 `subprocess` 找不到 `uvx`，
   于是 `FileNotFoundError: [WinError 2]`。

2. **依赖版本冲突导致服务进程刚启动就退出**
   `amap-mcp-server 0.1.11` 把依赖钉成 `mcp==1.8.1`，
   而 `mcp 1.8.1` 只声明了 `pydantic<3.0.0`。`uvx` 于是装上最新的
   pydantic 2.14，但 `mcp 1.8.1` 会 import 早已在 pydantic 2.12 中被删除的
   `pydantic._internal._typing_extra.eval_type_backport`，瞬间崩溃：

       ImportError: cannot import name 'eval_type_backport'

   用 `uvx --with "pydantic<2.12"` 把 pydantic 约束回兼容版本即可。

另外，`MCPTool.__init__` 内部会 `except Exception: pass` 把上面两类错误全部吞掉，
只留下空的 `_available_tools`，表现为"看起来初始化成功，但一个工具都没有"，
这次一并改成失败即抛出可读的错误。
"""

import asyncio
import concurrent.futures
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

from hello_agents.tools import MCPTool

# amap-mcp-server 0.1.11 钉死了 mcp==1.8.1，必须把 pydantic 限制在 2.11.x
PINNED_DEPENDENCIES = ("pydantic<2.12",)

AMAP_MCP_PACKAGE = "amap-mcp-server"


class AmapMcpError(RuntimeError):
    """高德 MCP 服务不可用。"""


def find_uvx() -> str:
    """定位 uvx 可执行文件：优先 PATH，其次当前解释器所在的虚拟环境。"""
    found = shutil.which("uvx")
    if found:
        return found

    exe_name = "uvx.exe" if os.name == "nt" else "uvx"
    python_dir = Path(sys.executable).resolve().parent
    candidates = [
        python_dir / exe_name,
        python_dir.parent / "Scripts" / exe_name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    raise AmapMcpError(
        "找不到 uvx 命令（uvx 随 uv 一起安装）。任选一种方式：\n"
        "  1. 先激活虚拟环境再启动：.venv\\Scripts\\activate 然后 python run.py\n"
        "  2. 把 uv 装进当前环境：.venv\\Scripts\\python.exe -m pip install uv\n"
        "  3. 安装 uv 后重启终端，确认 `uvx --version` 有输出"
    )


def build_server_command() -> List[str]:
    """构造 MCP 服务器的启动命令。"""
    command = [find_uvx()]
    for dep in PINNED_DEPENDENCIES:
        command.extend(["--with", dep])
    command.append(AMAP_MCP_PACKAGE)
    return command


async def _list_tools(env: Dict[str, str]) -> List[Dict[str, Any]]:
    from hello_agents.protocols.mcp.client import MCPClient

    async with MCPClient(build_server_command(), env=env) as client:
        return await client.list_tools()


def _probe(env: Dict[str, str], timeout: float = 180.0) -> List[Dict[str, Any]]:
    """真正连一次服务器，用来在失败时拿到被 MCPTool 吞掉的原始异常。

    MCPTool 可能是在事件循环里被调用的，所以放到独立线程里 `asyncio.run`，
    避免 "asyncio.run() cannot be called from a running event loop"。
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, _list_tools(env)).result(timeout=timeout)


def create_amap_mcp_tool(api_key: str, description: str = "高德地图服务") -> MCPTool:
    """创建已确认可用的高德 MCP 工具（失败时抛出 AmapMcpError）。"""
    if not api_key:
        raise AmapMcpError("高德地图 API Key 未配置，请在 .env 中设置 AMAP_API_KEY")

    env = {"AMAP_MAPS_API_KEY": api_key}
    tool = MCPTool(
        name="amap",
        description=description,
        server_command=build_server_command(),
        env=env,
        auto_expand=True,
    )

    expanded = tool.get_expanded_tools()
    if expanded:
        print(f"✅ 高德 MCP 服务已连接，发现 {len(expanded)} 个工具")
        return tool

    # 走到这里说明 MCPTool 把连接失败吞掉了，重连一次把真实原因暴露出来
    try:
        tools = _probe(env)
    except Exception as exc:
        raise AmapMcpError(
            "高德 MCP 服务连接失败：" f"{type(exc).__name__}: {exc}\n"
            f"启动命令：{' '.join(build_server_command())}"
        ) from exc

    raise AmapMcpError(
        f"高德 MCP 服务已连上但没有返回任何工具（返回 {len(tools)} 个），"
        "请检查 amap-mcp-server 版本"
    )
