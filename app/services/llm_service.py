"""LLM 构建

这里刻意**没有**全局单例，也没有环境变量兜底：
模型配置属于家庭，只有拿到某个家庭的配置才能建出对应的 LLM。
一旦留了 `get_llm()` 这种"读环境变量"的入口，就很容易有人顺手用回服务端的 key，
等于把"谁都能白嫖站长额度"这个洞又开回来。
"""

from hello_agents import HelloAgentsLLM


def build_llm(config: dict) -> HelloAgentsLLM:
    """按家庭配置创建 LLM 实例。

    provider 固定传 "custom"：HelloAgentsLLM 在 provider 为 None/auto 时会先嗅探
    OPENAI_API_KEY / DEEPSEEK_API_KEY 等环境变量，可能让用户配置的 key 被环境变量
    顶掉（或者反过来，服务端的 key 悄悄生效）。custom 分支只认显式传入的参数。
    """
    return HelloAgentsLLM(
        model=config["model"],
        api_key=config["api_key"],
        base_url=config["base_url"],
        provider="custom",
        temperature=float(config.get("temperature", 0.7)),
        timeout=int(config.get("timeout", 120)),
    )
