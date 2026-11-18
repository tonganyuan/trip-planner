"""配置管理模块"""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 加载环境变量
# 首先尝试加载当前目录的.env
load_dotenv()

# 然后尝试加载HelloAgents的.env(如果存在)
helloagents_env = Path(__file__).parent.parent.parent.parent / "HelloAgents" / ".env"
if helloagents_env.exists():
    load_dotenv(helloagents_env, override=False)  # 不覆盖已有的环境变量


class Settings(BaseSettings):
    """应用配置"""

    # 应用基本配置
    app_name: str = "myAgents智能旅行助手"
    app_version: str = "1.0.0"
    debug: bool = False

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS配置 - 使用字符串,在代码中分割
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000,http://localhost,http://127.0.0.1,https://364665hcrp34.vicp.fun"

    # 高德地图API配置
    amap_api_key: str = "083a77e9ca19b44c3ee9987083abaad4"

    # Unsplash API配置
    unsplash_access_key: str = "wgoH1HiYulJI6DkHnfYx-bUChBvUo_UlUPMstaDpZUY"
    unsplash_secret_key: str = "xejUD2ogD8K1sOYu_AG0YY9d-TVGfFQ-HDOEGn0Z0Lk"
    unsplash_base_url: str = "https://api.unsplash.com"

    # LLM配置
    # 注意：服务端不再持有"给所有人用"的模型 Key。
    # 每个家庭在「模型设置」里填自己的 base_url / model / api_key，
    # 生成行程时只用该家庭的配置（见 services/llm_config_service.py）。
    # 下面的值仅作为部署时的历史兼容字段保留，逻辑上已无人读取。
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""

    # 日志配置
    log_level: str = "INFO"

    # ============ 用户认证 ============
    # SQLite 数据库位置，相对路径按项目根目录解析
    db_path: str = "data/app.db"
    # JWT 签名密钥。留空时自动生成并落盘到 data/.auth_secret，
    # 保证重启后已签发的 token 依然有效；线上建议用环境变量显式配置
    auth_secret: str = ""
    # token 有效期(分钟)，默认 7 天
    auth_token_expire_minutes: int = 60 * 24 * 7
    # 是否开放注册。关掉之后就只剩已有账号能登录(适合单人使用)
    allow_register: bool = False

    class Config:
        env_file = "../.env"
        case_sensitive = False
        extra = "ignore"  # 忽略额外的环境变量

    def get_cors_origins_list(self) -> List[str]:
        """获取CORS origins列表"""
        return [origin.strip() for origin in self.cors_origins.split(',')]


# 创建全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings


# 验证必要的配置
def validate_config():
    """验证配置是否完整"""
    errors = []
    warnings = []

    if not settings.amap_api_key:
        errors.append("AMAP_API_KEY未配置")

    # 模型改由各家庭自行配置，服务端不再需要 LLM_API_KEY，
    # 这里只做提示：有值也不代表会用它（不会）。
    if os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"):
        warnings.append(
            "检测到服务端配置了 LLM_API_KEY，但它已不再被使用："
            "模型按家庭配置，请在站点「模型设置」里为每个家庭填写自己的 Key"
        )

    if errors:
        error_msg = "配置错误:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)

    if warnings:
        print("\n⚠️  配置警告:")
        for w in warnings:
            print(f"  - {w}")

    return True


# 打印配置信息(用于调试)
def print_config():
    """打印当前配置(隐藏敏感信息)"""
    print(f"应用名称: {settings.app_name}")
    print(f"版本: {settings.app_version}")
    print(f"服务器: {settings.host}:{settings.port}")
    print(f"高德地图API Key: {'已配置' if settings.amap_api_key else '未配置'}")

    # 检查LLM配置
    llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    llm_base_url = os.getenv("LLM_BASE_URL") or settings.openai_base_url
    llm_model = os.getenv("LLM_MODEL_ID") or settings.openai_model

    print("LLM: 由各家庭在「模型设置」中自行配置（服务端不持有可用 Key）")
    if llm_api_key:
        print("     ⚠️ 检测到服务端 LLM_API_KEY，但已不参与生成请求，建议从 .env 中移除")
        print(f"     （历史残留：{llm_base_url or '-'} / {llm_model or '-'}）")
    print(f"日志级别: {settings.log_level}")
    print(f"数据库: {settings.db_path}")
    print(f"开放注册: {'是' if settings.allow_register else '否(仅已有账号可登录)'}")
    print(f"JWT 密钥: {'环境变量' if settings.auth_secret else '未配置，将使用 data/.auth_secret'}")

