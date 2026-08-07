from loguru import logger
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from itertools import product
import random
import math

from core.strategy_extensions import TradingPerformanceMetrics


class OptimizationMethod(Enum):
    """参数优化方法"""
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    BAYESIAN = "bayesian"


class OptimizationObjective(Enum):
    """优化目标"""
    MAXIMIZE_SHARPE = "sharpe_ratio"
    MAXIMIZE_RETURN = "total_return"
    MINIMIZE_DRAWDOWN = "max_drawdown"
    MAXIMIZE_WIN_RATE = "win_rate"


@dataclass
class OptimizationResult:
    """单次优化结果"""
    parameters: Dict[str, Any]
    metrics: TradingPerformanceMetrics
    score: float
    rank: int


@dataclass
class OptimizationConfig:
    """优化配置"""
    method: OptimizationMethod = OptimizationMethod.GRID_SEARCH
    objective: OptimizationObjective = OptimizationObjective.MAXIMIZE_SHARPE
    max_iterations: int = 100
    n_jobs: int = 1
    cv_folds: int = 1
    early_stopping_rounds: int = 10
    random_seed: int = 42
    verbose: bool = True


@dataclass
class OptimizationRun:
    """优化运行状态"""
    run_id: str
    config: OptimizationConfig
    start_time: datetime
    status: str = "pending"
    progress: float = 0.0
    current_iteration: int = 0
    total_iterations: int = 0
    best_result: Optional[OptimizationResult] = None
    results: List[OptimizationResult] = field(default_factory=list)
    error_message: Optional[str] = None


@dataclass
class WalkForwardWindow:
    """Walk-Forward Analysis 单个窗口结果"""
    window_index: int
    train_start: Any
    train_end: Any
    test_start: Any
    test_end: Any
    best_params: Dict[str, Any]
    train_metrics: Any
    test_metrics: Dict[str, Any]
    train_score: float = 0.0
    test_score: float = 0.0
