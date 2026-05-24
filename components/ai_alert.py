import openai
import threading
import time
import pandas as pd
try:
    from utils.notification import send_notification
except ImportError:
    send_notification = None
from loguru import logger

class AIAlert:
    def __init__(self, api_key: str, data_manager=None):
        self.api_key = api_key
        self._client = openai.OpenAI(api_key=api_key)
        self.alert_history = []
        self.running = False
        self.data_manager = data_manager

    def parse_condition(self, user_input: str) -> dict:
        prompt = f"请将以下预警条件转为结构化规则JSON：{user_input}"
        try:
            resp = self._client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            import json
            return json.loads(resp.choices[0].message.content)
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
                        if send_notification:
                            send_notification(push_type, f"预警触发: {check_result['message']}")
                        else:
                            logger.warning(f"通知服务不可用，预警: {check_result['message']}")
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
            stock_code = condition.get('stock_code', '')

            if not indicator:
                return {'triggered': False, 'message': '条件不完整'}

            current_value = self._fetch_indicator_value(indicator, stock_code)

            if operator == '>':
                triggered = current_value > threshold
            elif operator == '<':
                triggered = current_value < threshold
            elif operator == '>=':
                triggered = current_value >= threshold
            elif operator == '<=':
                triggered = current_value <= threshold
            elif operator == '==':
                triggered = abs(current_value - threshold) < 1e-6
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

    def _fetch_indicator_value(self, indicator: str, stock_code: str = '') -> float:
        """
        从真实数据源获取当前指标值，失败时降级到模拟数据

        Args:
            indicator: 指标名称
            stock_code: 股票代码

        Returns:
            float: 当前指标值
        """
        try:
            if stock_code and self.data_manager:
                return self._fetch_from_data_manager(indicator, stock_code)
        except Exception as e:
            logger.debug(f"从数据管理器获取指标失败，降级到模拟: {e}")

        try:
            value = self._fetch_ai_predicted_value(indicator)
            if value is not None:
                return value
        except Exception as e:
            logger.debug(f"AI预测指标值获取失败，降级到模拟: {e}")

        logger.warning(f"无法获取 {indicator} 的真实指标值，返回0.0作为降级值")
        return 0.0

    def _fetch_from_data_manager(self, indicator: str, stock_code: str) -> float:
        """从统一数据管理器获取真实指标值"""
        indicator_lower = indicator.lower()

        try:
            kdata = self.data_manager.get_kdata(stock_code, period='D', count=60)
            if kdata is None or kdata.empty:
                raise ValueError("无法获取K线数据")

            close_prices = kdata['close'].astype(float)

            if indicator_lower == 'price' or indicator_lower == 'close':
                return float(close_prices.iloc[-1])

            if indicator_lower == 'volume':
                return float(kdata['volume'].astype(float).iloc[-1])

            if indicator_lower in ('ma5', 'ma10', 'ma20', 'ma30', 'ma60'):
                window = int(indicator_lower[2:])
                return float(close_prices.rolling(window=window).mean().iloc[-1])

            if indicator_lower in ('rsi', 'rsi14', 'rsi_14'):
                delta = close_prices.diff()
                gain = delta.where(delta > 0, 0)
                loss = (-delta.where(delta < 0, 0))
                avg_gain = gain.rolling(window=14).mean()
                avg_loss = loss.rolling(window=14).mean()
                rs = avg_gain / avg_loss.replace(0, 1e-10)
                return float(100 - (100 / (1 + rs.iloc[-1])))

            if indicator_lower == 'macd':
                exp12 = close_prices.ewm(span=12, adjust=False).mean()
                exp26 = close_prices.ewm(span=26, adjust=False).mean()
                return float((exp12 - exp26).iloc[-1])

            if indicator_lower == 'atr':
                high = kdata['high'].astype(float)
                low = kdata['low'].astype(float)
                close = kdata['close'].astype(float)
                tr = pd.concat([
                    high - low,
                    abs(high - close.shift()),
                    abs(low - close.shift())
                ], axis=1).max(axis=1)
                return float(tr.rolling(window=14).mean().iloc[-1])

            if indicator_lower == 'volatility':
                returns = close_prices.pct_change()
                return float(returns.rolling(window=20).std().iloc[-1] * 100)

            if indicator_lower in ('change', 'change_pct', '涨跌幅'):
                return float(close_prices.pct_change().iloc[-1] * 100)

            if indicator_lower in ('turnover', '换手率'):
                if 'turnover' in kdata.columns:
                    return float(kdata['turnover'].iloc[-1])
                if 'turn' in kdata.columns:
                    return float(kdata['turn'].iloc[-1])

            raise ValueError(f"不支持的指标: {indicator}")

        except Exception as e:
            logger.debug(f"真实数据获取失败({indicator}): {e}")
            raise

    def _fetch_ai_predicted_value(self, indicator: str) -> float:
        """尝试通过AI预测当前指标值"""
        try:
            prompt = (
                f"根据当前A股市场状况，估算 {indicator} 指标的当前数值，"
                f"请仅返回一个合理的浮点数，不要有任何其他文字。"
            )
            resp = self._client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=10
            )
            text = resp.choices[0].message.content.strip()
            return float(text)
        except Exception as e:
            logger.debug(f"AI预测指标值失败({indicator}): {e}")
            return None

    def stop_alert(self):
        self.running = False
        return {"status": "预警已停止"}

    def get_history(self):
        return self.alert_history
