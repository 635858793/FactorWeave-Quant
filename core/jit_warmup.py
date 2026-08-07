"""
通用 JIT 预热管理器
自动扫描指定模块中所有 @njit/@jit 装饰的函数，用哑数据触发 Numba 编译。
新增 @njit 函数无需手动维护 — 引擎初始化时自动覆盖。
"""
import inspect
import time
import warnings
from typing import List, Optional, Dict, Any
from loguru import logger


class JITWarmupManager:
    """
    自动发现并预热模块中所有 Numba JIT 函数。

    使用方式:
        warmup = JITWarmupManager()
        warmup.warmup_modules([
            "backtest.backtest_optimizer",
            "backtest.jit_optimizer",
            "core.indicators.jit_indicators",
        ])
    """

    # 为不同参数名生成哑数据
    _DUMMY_MAP = {
        "prices": lambda: _make_array(100.0),
        "signals": lambda: _make_array(0.0),
        "returns": lambda: _make_array(0.001),
        "returns_matrix": lambda: _make_array(0.001, shape=(10, 3)),
        "price": lambda: 100.0,
        "initial_capital": lambda: 10000.0,
        "position_size": lambda: 1.0,
        "commission_pct": lambda: 0.0003,
        "slippage_pct": lambda: 0.0001,
        "stop_loss_pct": lambda: 0.05,
        "take_profit_pct": lambda: 0.12,
        "max_holding_periods": lambda: 20,
        "window": lambda: 5,
        "risk_free_rate": lambda: 0.02,
    }

    def __init__(self):
        self._warmed: Dict[str, float] = {}
        # R237 HVD-237-B-006: dispose 幂等标志 (R78 铁律 #6)
        self._disposed = False

    def warmup_modules(self, module_names: List[str]) -> None:
        """
        预热指定模块中所有 Numba JIT 函数。

        Args:
            module_names: 模块名列表 (如 "backtest.backtest_optimizer")
        """
        total = 0.0
        count = 0
        for mod_name in module_names:
            t0 = time.perf_counter()
            n = self._warmup_one_module(mod_name)
            elapsed = time.perf_counter() - t0
            total += elapsed
            count += n
            if n > 0:
                logger.info(f"JIT预热: {mod_name} — {n}个函数, {elapsed:.2f}s")
        logger.info(f"JIT预热完成: {count}个函数, 总耗时={total:.2f}s")

    def _warmup_one_module(self, module_name: str) -> int:
        """预热单个模块中所有 Numba JIT 函数（含模块级函数和类的静态方法）"""
        import importlib
        try:
            mod = importlib.import_module(module_name)
        except ImportError:
            return 0

        warmed = 0

        # 收集所有候选函数: 模块级 + 类静态方法
        candidates = []
        for name, obj in inspect.getmembers(mod, inspect.isfunction):
            candidates.append((name, obj))
        for _cls_name, cls in inspect.getmembers(mod, inspect.isclass):
            try:
                for m_name, method in inspect.getmembers(cls, inspect.isfunction):
                    if hasattr(method, '__self__') and method.__self__ is cls:
                        candidates.append((f"{_cls_name}.{m_name}", method))
            except Exception:
                pass

        for name, obj in candidates:
            if not self._is_jit_function(obj) and not self._is_jit_function(getattr(obj, '__func__', None)):
                continue

            qualname = f"{module_name}:{name}"
            if qualname in self._warmed:
                continue

            actual = obj
            if hasattr(obj, '__func__'):
                actual = obj.__func__

            try:
                dummy = self._build_dummy_args(actual)
                if dummy is not None:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        actual(**dummy)
                    self._warmed[qualname] = 0.0
                    warmed += 1
            except Exception:
                logger.debug(f"JIT预热跳过: {qualname} (签名不匹配)")

        return warmed

    @staticmethod
    def _is_jit_function(func) -> bool:
        """检查函数是否有 Numba JIT 装饰"""
        if not hasattr(func, "_type") and not hasattr(func, "signatures"):
            return False
        # Numba JIT 编译后函数有 _type 属性, 或在编译前有 py_func
        if hasattr(func, "py_func"):
            func = func.py_func
        return hasattr(func, "_type") or hasattr(func, "signatures") or hasattr(func, "_dispatcher")

    def _build_dummy_args(self, func) -> Optional[Dict[str, Any]]:
        """根据函数签名构造哑参数"""
        try:
            sig = inspect.signature(func)
        except (ValueError, TypeError):
            return None

        kwargs = {}
        for param_name, param in sig.parameters.items():
            if param_name in self._DUMMY_MAP:
                kwargs[param_name] = self._DUMMY_MAP[param_name]()
            elif param.annotation in (float, "float", "float64"):
                kwargs[param_name] = 1.0
            elif param.annotation in (int, "int", "int64"):
                kwargs[param_name] = 5
            elif param.default is not inspect.Parameter.empty:
                continue  # 有默认值的参数可以跳过
            else:
                return None  # 无法推断类型
        return kwargs

    # ========================================================================
    # R237 HVD-237-B-006: 4 链 dispose 治理 (R78 铁律)
    # 业务影响: 1-2 业务方 (main.py 通过 get_jit_warmup_manager 调用, 启动期单例)
    # 业务资源: _warmed (Dict[str, float]) - 预热函数记录
    # ========================================================================
    def dispose(self) -> None:
        """R237 HVD-237-B-006: 4 链 dispose 入口 (R78 铁律 #6 幂等短路)"""
        if getattr(self, '_disposed', False):
            return
        try:
            self.shutdown()
            self.close()
            self.cleanup()
        except Exception as e:
            logger.warning(
                f"JITWarmupManager.dispose 异常: {e}",
                exc_info=True,
            )
        finally:
            self._disposed = True

    def shutdown(self) -> None:
        """R237 HVD-237-B-006: shutdown - 业务数据清空 (_warmed dict)"""
        try:
            if hasattr(self, '_warmed') and isinstance(self._warmed, dict):
                self._warmed.clear()
        except Exception as e:
            logger.warning(
                f"JITWarmupManager.shutdown 异常: {e}",
                exc_info=True,
            )

    def close(self) -> None:
        """R237 HVD-237-B-006: close - 资源引用释放 (无外部子组件, 主要清理 _DUMMY_MAP 不需要)"""
        try:
            # JITWarmupManager 无外部子组件, close 主要做完整性确认
            pass
        except Exception as e:
            logger.warning(
                f"JITWarmupManager.close 异常: {e}",
                exc_info=True,
            )

    def cleanup(self) -> None:
        """R237 HVD-237-B-006: cleanup - 单例重置 (R235 子智能体 B: 启动期单例清理)"""
        try:
            # 启动期单例引用置 None, 允许 GC 回收
            if hasattr(self, '_warmed'):
                self._warmed = None
        except Exception as e:
            logger.warning(
                f"JITWarmupManager.cleanup 异常: {e}",
                exc_info=True,
            )


def _make_array(fill: float, length: int = 5, shape=None):
    import numpy as np
    if shape:
        return np.full(shape, fill, dtype=np.float64)
    return np.full(length, fill, dtype=np.float64)


# 全局预定义: 关键模块列表
DEFAULT_WARMUP_MODULES = [
    "backtest.backtest_optimizer",
    "backtest.jit_optimizer",
    "backtest.ultra_performance_optimizer",
    "core.indicators.jit_indicators",
]

_jit_warmup_manager: Optional[JITWarmupManager] = None


def get_jit_warmup_manager() -> JITWarmupManager:
    """获取全局 JIT 预热管理器 (延迟创建, 避免导入时阻塞)"""
    global _jit_warmup_manager
    if _jit_warmup_manager is None:
        _jit_warmup_manager = JITWarmupManager()
    return _jit_warmup_manager


def warmup_all_jit_functions(extra_modules: Optional[List[str]] = None) -> None:
    """
    一键预热所有核心模块的 JIT 函数。
    在引擎初始化完成后调用。

    Args:
        extra_modules: 额外需要预热的模块
    """
    modules = list(DEFAULT_WARMUP_MODULES)
    if extra_modules:
        modules.extend(extra_modules)
    get_jit_warmup_manager().warmup_modules(modules)