"""FastAPI主应用"""

import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings, validate_config, print_config
from app.api.routes import trip, poi, map as map_routes

# 获取配置
settings = get_settings()

# 创建FastAPI应用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="基于HelloAgents框架的智能旅行规划助手API",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
# allow_origins 为显式白名单(见 .env 的 CORS_ORIGINS)；
# allow_origin_regex 兜底放行本机任意端口，避免前端换端口(80/5173/3000...)后再次跨域失败
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?|https?://[\w.-]+\.vicp\.fun(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(trip.router, prefix="/api")
app.include_router(poi.router, prefix="/api")
app.include_router(map_routes.router, prefix="/api")


def _warm_up_agents() -> None:
    """后台预热 Agent 与高德 MCP。

    第一次生成行程时，初始化要连一次 MCP（首次还会现下 amap-mcp-server，
    几十秒到一两分钟），这段时间全算在第一个用户的等待里。
    放到后台线程提前做掉，用户点“生成”时就已经是热态。
    """
    try:
        from app.agents.trip_planner_agent import get_trip_planner_agent

        get_trip_planner_agent()
        print("✅ 预热完成：多智能体与高德 MCP 已就绪")
    except Exception as exc:
        # 预热失败不影响服务启动，第一次真实请求会再试一次
        print(f"⚠️  预热失败（不影响启动，首个请求会重试）: {type(exc).__name__}: {exc}")


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    print("\n" + "="*60)
    print(f"🚀 {settings.app_name} v{settings.app_version}")
    print("="*60)
    
    # 打印配置信息
    print_config()
    
    # 验证配置
    try:
        validate_config()
        print("\n✅ 配置验证通过")
    except ValueError as e:
        print(f"\n❌ 配置验证失败:\n{e}")
        print("\n请检查.env文件并确保所有必要的配置项都已设置")
        raise
    
    print("\n" + "="*60)
    print("📚 API文档: http://localhost:8000/docs")
    print("📖 ReDoc文档: http://localhost:8000/redoc")
    print("="*60 + "\n")

    # 后台预热，不阻塞启动
    threading.Thread(target=_warm_up_agents, name="warmup", daemon=True).start()


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    print("\n" + "="*60)
    print("👋 应用正在关闭...")
    print("="*60 + "\n")


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )

