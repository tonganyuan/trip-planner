import json
import time
from typing import Any, Dict, List, Optional, Tuple

from hello_agents.tools import MCPTool
from ..config import get_settings
from ..models.schedmas import POIInfo, WeatherInfo, Location
from .amap_mcp import create_amap_mcp_tool

# 天气结果缓存：高德 MCP 一次调用 5~8 秒，首页每次进来都等一遍太难受。
# 单进程 + 单 worker，字典读写足够，不需要额外锁。
_WEATHER_TTL_SECONDS = 600


def _extract_json(payload: Any) -> Optional[dict]:
    """MCP 工具返回的是 "工具 'x' 执行结果:\\n{...}" 这类字符串，截出 JSON 段再解析"""
    if isinstance(payload, dict):
        return payload
    if not isinstance(payload, str):
        return None
    start = payload.find("{")
    end = payload.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(payload[start:end + 1])
    except json.JSONDecodeError:
        return None


class AmapService:

    def __init__(self):
        self.mcp_tool = get_amap_mcp_tool()
        self._weather_cache: Dict[str, Tuple[float, List[WeatherInfo]]] = {}

    def search_poi(self, keywords: str, city: str, citylimit: bool = True) -> List[POIInfo]:
        """
        搜索POI

        Args:
            keywords: 搜索关键词
            city: 城市
            citylimit: 是否限制在城市范围内

        Returns:
            POI信息列表
        """
        try:
            # 调用MCP工具
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_text_search",
                "arguments": {
                    "keywords": keywords,
                    "city": city,
                    "citylimit": str(citylimit).lower()
                }
            })

            # 解析结果
            # 注意: MCP工具返回的是字符串,需要解析
            # 这里简化处理,实际应该解析JSON
            print(f"POI搜索结果: {result[:200]}...")  # 打印前200字符

            # TODO: 解析实际的POI数据
            return []

        except Exception as e:
            print(f"❌ POI搜索失败: {str(e)}")
            return []

    def get_weather(self, city: str) -> List[WeatherInfo]:
        """
        查询天气

        Args:
            city: 城市名称

        Returns:
            天气信息列表(未来若干天)
        """
        cached = self._weather_cache.get(city)
        if cached and time.time() - cached[0] < _WEATHER_TTL_SECONDS:
            return cached[1]

        try:
            # 调用MCP工具
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_weather",
                "arguments": {
                    "city": city
                }
            })
        except Exception as e:
            print(f"❌ 天气查询失败: {str(e)}")
            return []

        data = _extract_json(result)
        if not data:
            print(f"⚠️ 天气数据解析失败: {str(result)[:200]}")
            return []

        # 高德返回字段是 dayweather/daytemp 这种紧凑命名，翻译成前端用的下划线命名
        items: List[WeatherInfo] = []
        for forecast in data.get("forecasts") or []:
            if not isinstance(forecast, dict):
                continue
            items.append(WeatherInfo(
                date=str(forecast.get("date", "")),
                day_weather=str(forecast.get("dayweather", "")),
                night_weather=str(forecast.get("nightweather", "")),
                day_temp=forecast.get("daytemp", 0),
                night_temp=forecast.get("nighttemp", 0),
                wind_direction=str(forecast.get("daywind", "")),
                wind_power=str(forecast.get("daypower", "")),
            ))

        if items:
            self._weather_cache[city] = (time.time(), items)
            print(f"✅ 天气查询完成: {data.get('city', city)}，{len(items)} 天")
        return items

    def plan_route(
            self,
            origin_address: str,
            destination_address: str,
            origin_city: Optional[str] = None,
            destination_city: Optional[str] = None,
            route_type: str = "walking"
    ) -> Dict[str, Any]:
        """
        规划路线

        Args:
            origin_address: 起点地址
            destination_address: 终点地址
            origin_city: 起点城市
            destination_city: 终点城市
            route_type: 路线类型 (walking/driving/transit)

        Returns:
            路线信息
        """
        try:
            # 根据路线类型选择工具
            tool_map = {
                "walking": "maps_direction_walking_by_address",
                "driving": "maps_direction_driving_by_address",
                "transit": "maps_direction_transit_integrated_by_address"
            }

            tool_name = tool_map.get(route_type, "maps_direction_walking_by_address")

            # 构建参数
            arguments = {
                "origin_address": origin_address,
                "destination_address": destination_address
            }

            # 公共交通需要城市参数
            if route_type == "transit":
                if origin_city:
                    arguments["origin_city"] = origin_city
                if destination_city:
                    arguments["destination_city"] = destination_city
            else:
                # 其他路线类型也可以提供城市参数提高准确性
                if origin_city:
                    arguments["origin_city"] = origin_city
                if destination_city:
                    arguments["destination_city"] = destination_city

            # 调用MCP工具
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": tool_name,
                "arguments": arguments
            })

            print(f"路线规划结果: {result[:200]}...")

            # TODO: 解析实际的路线数据
            return {}

        except Exception as e:
            print(f"❌ 路线规划失败: {str(e)}")
            return {}

    def geocode(self, address: str, city: Optional[str] = None) -> Optional[Location]:
        """
        地理编码(地址转坐标)

        Args:
            address: 地址
            city: 城市

        Returns:
            经纬度坐标
        """
        try:
            arguments = {"address": address}
            if city:
                arguments["city"] = city

            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_geo",
                "arguments": arguments
            })

            print(f"地理编码结果: {result[:200]}...")

            # TODO: 解析实际的坐标数据
            return None

        except Exception as e:
            print(f"❌ 地理编码失败: {str(e)}")
            return None

    def get_poi_detail(self, poi_id: str) -> Dict[str, Any]:
        """
        获取POI详情

        Args:
            poi_id: POI ID

        Returns:
            POI详情信息
        """
        try:
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_search_detail",
                "arguments": {
                    "id": poi_id
                }
            })

            print(f"POI详情结果: {result[:200]}...")

            # 解析结果并提取图片
            import json
            import re

            # 尝试从结果中提取JSON
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data

            return {"raw": result}

        except Exception as e:
            print(f"❌ 获取POI详情失败: {str(e)}")
            return {}


# 创建全局服务实例
_amap_service = None


def get_amap_service() -> AmapService:
    """获取高德地图服务实例(单例模式)"""
    global _amap_service

    if _amap_service is None:
        _amap_service = AmapService()

    return _amap_service


# 全局MCP工具实例
_amap_mcp_tool = None

def get_amap_mcp_tool() -> MCPTool:

    global _amap_mcp_tool
    if _amap_mcp_tool is not None:
        return _amap_mcp_tool

    settings = get_settings()
    if not settings.amap_api_key:
        raise ValueError("高德地图API Key未配置,请在.env文件中设置AMAP_API_KEY")

    # 创建MCP工具
    _amap_mcp_tool = create_amap_mcp_tool(
        settings.amap_api_key,
        description="高德地图服务,支持POI搜索、路线规划、天气查询等功能",
    )

    print(f"✅ 高德地图MCP工具初始化成功")
    print(f"   工具数量: {len(_amap_mcp_tool._available_tools)}")

    # 打印可用工具列表
    if _amap_mcp_tool._available_tools:
        print("   可用工具:")
        for tool in _amap_mcp_tool._available_tools[:5]:  # 只打印前5个
            print(f"     - {tool.get('name', 'unknown')}")
        if len(_amap_mcp_tool._available_tools) > 5:
            print(f"     ... 还有 {len(_amap_mcp_tool._available_tools) - 5} 个工具")


    return _amap_mcp_tool

