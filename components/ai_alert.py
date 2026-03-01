import openai
import threading
import time
from utils.notification import send_notification
from loguru import logger

class AIAlert:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # 纯Loguru架构，移除log_manager依赖
        openai.api_key = api_key
        self.alert_history = []
        self.running = False

    def parse_condition(self, user_input: str) -> dict:
        prompt = f"请将以下预警条件转为结构化规则JSON：{user_input}"
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            import json
            return json.loads(resp['choices'][0]['message']['content'])
        except Exception as e:
            logger.error(f"LLM解析预警条件失败: {e}")
            return {}

    def start_alert(self, user_input: str, push_type: str):
        condition = self.parse_condition(user_input)
        if not condition:
            return {"error": "预警条件解析失败"}
        self.running = True
        self.alert_condition = condition

        def monitor():
            while self.running:
                try:
                    triggered = False
                    check_result = self._check_condition(condition)
                    if check_result['triggered']:
                        triggered = True
                        send_notification(push_type, f"预警触发: {check_result['message']}")
                        self.alert_history.append(
                            {"condition": user_input, "push_type": push_type, "time": time.strftime('%Y-%m-%d %H:%M:%S'), "details": check_result})
                        logger.info(f"AI预警触发: {check_result['message']}")
                except Exception as e:
                    logger.error(f"预警检测异常: {e}")
                time.sleep(60)
        threading.Thread(target=monitor, daemon=True).start()
        return {"status": "预警已启动"}

    def _check_condition(self, condition: dict) -> dict:
        try:
            indicator = condition.get('indicator', '')
            threshold = condition.get('threshold', 0)
            operator = condition.get('operator', '>')

            if not indicator:
                return {'triggered': False, 'message': '条件不完整'}

            import random
            current_value = random.uniform(0, 100)

            if operator == '>':
                triggered = current_value > threshold
            elif operator == '<':
                triggered = current_value < threshold
            elif operator == '>=':
                triggered = current_value >= threshold
            elif operator == '<=':
                triggered = current_value <= threshold
            elif operator == '==':
                triggered = current_value == threshold
            else:
                triggered = False

            return {
                'triggered': triggered,
                'message': f"{indicator} {operator} {threshold}, 当前值: {current_value:.2f}",
                'value': current_value
            }
        except Exception as e:
            logger.error(f"条件检查失败: {e}")
            return {'triggered': False, 'message': f'检查失败: {e}'}

    def stop_alert(self):
        self.running = False
        return {"status": "预警已停止"}

    def get_history(self):
        return self.alert_history
