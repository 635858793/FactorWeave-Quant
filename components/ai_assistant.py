import openai
from loguru import logger

class AIAssistant:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # 纯Loguru架构，移除log_manager依赖
        self._client = openai.OpenAI(api_key=api_key)
        self.history = []

    def chat(self, user_input: str) -> dict:
        self.history.append({"role": "user", "content": user_input})
        try:
            intent = self._recognize_intent(user_input)
            logger.info(f"AI助手识别意图: {intent}")

            if intent['action'] == 'query':
                resp = self._client.chat.completions.create(
                    model="gpt-4o",
                    messages=self.history,
                    temperature=0.2
                )
                reply = resp.choices[0].message.content
            elif intent['action'] == 'backtest':
                reply = self._execute_backtest_intent(user_input)
            elif intent['action'] == 'screening':
                reply = self._execute_screening_intent(user_input)
            elif intent['action'] == 'alert':
                reply = self._execute_alert_intent(user_input)
            else:
                resp = self._client.chat.completions.create(
                    model="gpt-4o",
                    messages=self.history,
                    temperature=0.2
                )
                reply = resp.choices[0].message.content

            self.history.append({"role": "assistant", "content": reply})
            return {"reply": reply, "intent": intent}
        except Exception as e:
            logger.error(f"AI助手对话失败: {e}")
            return {"error": str(e)}

    def _recognize_intent(self, user_input: str) -> dict:
        user_lower = user_input.lower()
        if any(kw in user_lower for kw in ['回测', 'backtest', '测试策略']):
            return {'action': 'backtest', 'type': 'strategy_backtest'}
        elif any(kw in user_lower for kw in ['选股', '筛选', 'screener', '筛选股票']):
            return {'action': 'screening', 'type': 'stock_screening'}
        elif any(kw in user_lower for kw in ['预警', 'alert', '监控', '提醒']):
            return {'action': 'alert', 'type': 'price_alert'}
        elif any(kw in user_lower for kw in ['什么', '谁', 'how', 'what', 'why', '解释']):
            return {'action': 'query', 'type': 'information'}
        else:
            return {'action': 'query', 'type': 'general'}

    def _execute_backtest_intent(self, user_input: str) -> str:
        return "我理解了，您想要进行回测分析。请打开回测页面进行操作，当前支持专业回测引擎。"

    def _execute_screening_intent(self, user_input: str) -> str:
        return "我理解了，您想要选股。请打开选股器页面，支持技术指标、基本面和资金流向筛选。"

    def _execute_alert_intent(self, user_input: str) -> str:
        return "我理解了，您想要设置预警。请打开预警管理页面，设置价格或指标预警条件。"
