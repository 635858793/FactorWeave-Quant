import pandas as pd
from loguru import logger

logger = logger.bind(module=__name__)


class SignalGenerator:
    """策略信号生成器，桥接 backtest 与 core/strategy 系统"""

    def __init__(self):
        self._registry = None
        self._engine = None

    def _ensure_initialized(self):
        if self._registry is None:
            from core.strategy.strategy_registry import get_strategy_registry
            self._registry = get_strategy_registry()
        if self._engine is None:
            from core.strategy.strategy_engine import get_strategy_engine
            self._engine = get_strategy_engine()

    def generate_signals(self, kdata: pd.DataFrame, strategy: str,
                         strategy_params: dict = None) -> pd.DataFrame:
        self._ensure_initialized()
        kdata = kdata.copy()
        kdata['signal'] = 0

        try:
            signals, exec_info = self._engine.execute_strategy(
                strategy, kdata, use_cache=True, save_to_db=False
            )
            if exec_info.get('success') and signals:
                for s in signals:
                    if s.timestamp in kdata.index:
                        sig_val = s.signal_type.value.lower() if hasattr(s.signal_type, 'value') else str(s.signal_type).lower()
                        if sig_val in ('buy', 'strong_buy'):
                            signal_val = 1
                        elif sig_val in ('sell', 'strong_sell'):
                            signal_val = -1
                        else:
                            signal_val = 0
                        kdata.loc[s.timestamp, 'signal'] = signal_val
        except Exception as e:
            logger.warning(f"信号生成失败 [{strategy}]: {e}")

        return kdata