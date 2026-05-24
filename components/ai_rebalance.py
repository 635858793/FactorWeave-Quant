from openai import OpenAI
from loguru import logger

class AIRebalancer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key)

    def rebalance(self, positions: list, strategy: str = "", risk_params: dict = None, user_input: str = "") -> dict:
        """
        positions: [{"code": 股票代码, "name": 名称, "amount": 持仓数量, "cost": 持仓成本}]
        strategy: 策略描述
        risk_params: 风控参数（如最大回撤、单股权重上限等）
        user_input: 可选，自然语言补充说明
        """
        try:
            prompt = f"""
你是一名专业量化投顾，请根据以下持仓、策略和风险参数，给出调仓建议、风险分析和预警：
持仓：{positions}
策略：{strategy}
风险参数：{risk_params}
补充说明：{user_input}
请结构化输出：1. 调仓建议（增减仓、换股、调权重等）；2. 风险分析（如集中度、回撤、流动性等）；3. 预警提示（如单股过重、行业过于集中等）。
"""
            resp = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            return {"result": resp.choices[0].message.content}
        except Exception as e:
            logger.error(f"AI调仓/风控失败: {e}")
            return {"error": str(e)}

    def ask(self, user_input: str) -> dict:
        """支持自然语言调仓/风控问答"""
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": user_input}],
                temperature=0.2
            )
            return {"result": resp.choices[0].message.content}
        except Exception as e:
            logger.error(f"AI调仓/风控问答失败: {e}")
            return {"error": str(e)}
