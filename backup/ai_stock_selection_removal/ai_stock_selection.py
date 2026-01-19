import openai
from features.feature_selection import auto_feature_select
from core.stock_screener import screen_by_all
from loguru import logger

class AIStockSelector:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # 纯Loguru架构，移除log_manager依赖
        openai.api_key = api_key

    def parse_factors(self, user_input: str) -> dict:
        """用LLM解析自然语言或参数化因子，返回因子组合和权重建议"""
        prompt = f"请将以下选股需求转为结构化因子组合和权重建议，输出JSON：{user_input}"
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            content = resp['choices'][0]['message']['content']
            import json
            return json.loads(content)
        except Exception as e:
            logger.error(f"LLM解析因子失败: {e}")
            return {}

    def ai_select(self, user_input: str) -> dict:
        """AI智能选股主入口"""
        try:
            factors = self.parse_factors(user_input)
            if not factors:
                return {"error": "因子解析失败"}
            features = auto_feature_select(factors)
            result = screen_by_all(features)
            return {"factors": factors, "features": features, "result": result}
        except Exception as e:
            logger.error(f"AI选股失败: {e}")
