"""
统一贝叶斯优化模块

整合项目中5处独立的GP+EI实现，提供统一的贝叶斯优化接口。

## 5处独立实现对比

| # | 文件 | GP代理模型 | 采集函数 | 参数空间 | 候选点数 | 状态 |
|---|------|-----------|---------|---------|---------|------|
| 1 | strategy_service.py | 手动RBF+Cholesky(scipy) | EI | Dict[range] | 500 | 待迁移 |
| 2 | strategy_optimizer.py | sklearn GPR+Matern(2.5) | EI(scipy) | Grid索引 | 1000 | **首选迁移** |
| 3 | parameter_manager.py | sklearn GPR+Matern(2.5) | UCB(k=2.576) | ParameterRange | 5000 | 待迁移 |
| 4 | algorithm_optimizer.py | 无(启发式) | 无 | 自定义 | N/A | 不迁移 |
| 5 | auto_ml_optimizer.py | skopt.gp_minimize | gp_hedge | skopt dims | 内部 | 不迁移 |

## 设计决策

- **GP后端**: sklearn.GaussianProcessRegressor + Matern(nu=2.5)（实现2&3已验证）
- **采集函数**: EI/UCB/PI 可选
- **参数类型**: 连续/离散/序数 (ParameterSpec封装)
- **降级策略**: sklearn不可用→随机搜索 + 最近邻启发式
- **GP重置**: 连续失败5次后自动重置（实现2的机制）
- **y_std动态更新**: 每次迭代重新计算（第12轮修复）

## 使用示例

```python
from core.optimization import BayesianOptimizer, ParameterSpec, OptParameterType, AcquisitionFunction

params = [
    ParameterSpec("learning_rate", OptParameterType.CONTINUOUS, bounds=(1e-4, 1e-1)),
    ParameterSpec("max_depth", OptParameterType.DISCRETE, bounds=(3, 15)),
    ParameterSpec("activation", OptParameterType.ORDINAL, values=["relu", "tanh", "sigmoid"]),
]

optimizer = BayesianOptimizer(
    params,
    acquisition=AcquisitionFunction.EI,
    random_state=42,
)

def objective_fn(**kwargs) -> float:
    # kwargs = {"learning_rate": 0.001, "max_depth": 8, "activation": "relu"}
    model = train_model(**kwargs)
    return model.score

result = optimizer.optimize(objective_fn, n_calls=50)
print(result.best_params, result.best_score)
```
"""

import numpy as np
import time
import warnings
from enum import Enum
from typing import Dict, List, Any, Tuple, Optional, Callable, Union, Iterable
from dataclasses import dataclass, field
from loguru import logger as _logger

try:
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import Matern, WhiteKernel, ConstantKernel
    _SKLEARN_GP_AVAILABLE = True
except ImportError:
    _SKLEARN_GP_AVAILABLE = False

try:
    from scipy.stats import norm as _scipy_norm
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False

try:
    from scipy.linalg import cho_solve, cho_factor
    _SCIPY_LINALG_AVAILABLE = True
except ImportError:
    _SCIPY_LINALG_AVAILABLE = False


# ======================================================================
# 枚举定义
# ======================================================================

class OptParameterType(Enum):
    """参数类型（优化参数维度分类，区别于indicator_extensions.ParameterType）"""
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"
    ORDINAL = "ordinal"


class AcquisitionFunction(Enum):
    """采集函数类型"""
    EI = "ei"
    UCB = "ucb"
    PI = "pi"


class GPMode(Enum):
    """GP代理模型模式"""
    SKLEARN = "sklearn"
    SKOPT = "skopt"
    PURE_SCIPY = "pure_scipy"
    HEURISTIC = "heuristic"


# ======================================================================
# 数据类
# ======================================================================

@dataclass
class TrialRecord:
    """单次试验记录"""
    iteration: int
    params: Dict[str, Any]
    score: float
    is_best: bool = False


@dataclass
class OptimizationResult:
    """贝叶斯优化结果"""
    best_params: Dict[str, Any]
    best_score: float
    trials: List[TrialRecord] = field(default_factory=list)
    method: str = "bayesian_gp"
    total_iterations: int = 0
    elapsed_time: float = 0.0
    gp_available: bool = True
    gp_reset_count: int = 0


# ======================================================================
# ParameterSpec
# ======================================================================

@dataclass
class ParameterSpec:
    """参数规格定义，封装归一化/反归一化逻辑"""
    name: str
    type: OptParameterType
    bounds: Optional[Tuple[float, float]] = None
    values: Optional[List[Any]] = None

    def __post_init__(self):
        if self.type == OptParameterType.CONTINUOUS:
            if self.bounds is None or len(self.bounds) != 2:
                raise ValueError(f"CONTINUOUS参数 '{self.name}' 必须提供 bounds=(min, max)")
        elif self.type == OptParameterType.DISCRETE:
            if self.bounds is None or len(self.bounds) != 2:
                raise ValueError(f"DISCRETE参数 '{self.name}' 必须提供 bounds=(min, max)")
            self._int_range = range(int(self.bounds[0]), int(self.bounds[1]) + 1)
            self._int_values = list(self._int_range)
        elif self.type == OptParameterType.ORDINAL:
            if self.values is None or len(self.values) == 0:
                raise ValueError(f"ORDINAL参数 '{self.name}' 必须提供 values=列表")
        self._low = self.bounds[0] if self.bounds else 0.0
        self._high = self.bounds[1] if self.bounds else (len(self.values) - 1 if self.values else 1.0)

    def normalize(self, value: Any) -> float:
        """将参数值归一化到 [0, 1]"""
        if self.type == OptParameterType.ORDINAL:
            if value not in self.values:
                raise ValueError(f"ORDINAL参数 '{self.name}' 的值 '{value}' 不在 {self.values} 中")
            return self.values.index(value) / (len(self.values) - 1) if len(self.values) > 1 else 0.5
        if self._high == self._low:
            return 0.5
        return (float(value) - self._low) / (self._high - self._low)

    def denormalize(self, norm: float) -> Any:
        """将归一化值 [0, 1] 还原为实际参数值"""
        if self.type == OptParameterType.ORDINAL:
            idx = int(round(norm * (len(self.values) - 1)))
            idx = max(0, min(idx, len(self.values) - 1))
            return self.values[idx]
        if self.type == OptParameterType.DISCRETE:
            val = self._low + norm * (self._high - self._low)
            discrete_val = int(round(val))
            discrete_val = max(self._low, min(discrete_val, self._high))
            return discrete_val
        return self._low + norm * (self._high - self._low)

    def midpoint_normalize(self, value: Any) -> float:
        """离散参数的中点归一化（消除离散化偏差）"""
        if self.type in (OptParameterType.DISCRETE, OptParameterType.ORDINAL):
            actual_norm = self.normalize(value)
            if self.type == OptParameterType.DISCRETE:
                lo = self.normalize(int(round(self._low + (actual_norm - 0.5 / (self._high - self._low + 1)) * (self._high - self._low))))
                hi = self.normalize(int(round(self._low + (actual_norm + 0.5 / (self._high - self._low + 1)) * (self._high - self._low))))
                return (lo + hi) / 2.0
            return actual_norm
        return self.normalize(value)

    @property
    def dimension(self) -> int:
        return 1


# ======================================================================
# BayesianOptimizer
# ======================================================================

class BayesianOptimizer:
    """统一贝叶斯优化器

    支持：
    - sklearn GPR（首选）→ scipy 手动GP（备选）→ 随机搜索（最终降级）
    - 3种采集函数：EI / UCB / PI
    - 连续/离散/序数混合参数空间
    - GP连续失败自动重置
    - y_std 每次迭代动态更新
    """

    _GP_RESET_INTERVAL: int = 5

    def __init__(
        self,
        parameter_specs: List[ParameterSpec],
        acquisition: AcquisitionFunction = AcquisitionFunction.EI,
        xi: float = 0.01,
        kappa_ucb: float = 2.576,
        random_state: Optional[int] = None,
        verbose: bool = True,
    ):
        self.parameter_specs = parameter_specs
        self.n_params = len(parameter_specs)
        self.acquisition = acquisition
        self.xi = xi
        self.kappa_ucb = kappa_ucb
        self.random_state = random_state
        self.verbose = verbose

        self._gp_rng = np.random.RandomState(random_state)
        self._gp_available = False
        self._gp_mode = GPMode.HEURISTIC
        self._gp_fail_count = 0
        self._gp_reset_count = 0
        self._GPR = None
        self._kernel = None

        self._detect_gp_backend()

    def _detect_gp_backend(self):
        """检测可用的GP后端"""
        if _SKLEARN_GP_AVAILABLE:
            self._GPR = GaussianProcessRegressor
            self._gp_available = True
            self._gp_mode = GPMode.SKLEARN
            n_features = self.n_params
            self._kernel = (
                ConstantKernel(1.0, constant_value_bounds=(1e-3, 1e3))
                * Matern(length_scale=np.ones(n_features), length_scale_bounds=(1e-3, 1e3), nu=2.5)
                + WhiteKernel(noise_level=0.01, noise_level_bounds=(1e-5, 1.0))
            )
            if self.verbose:
                _logger.info(f"贝叶斯优化: 使用 sklearn.GaussianProcessRegressor (Matern nu=2.5, {n_features}维参数)")
        elif _SCIPY_LINALG_AVAILABLE and _SCIPY_AVAILABLE:
            self._gp_available = True
            self._gp_mode = GPMode.PURE_SCIPY
            if self.verbose:
                _logger.info("贝叶斯优化: 使用手动GP (scipy RBF+Cholesky)")
        else:
            self._gp_available = False
            self._gp_mode = GPMode.HEURISTIC
            _logger.warning("贝叶斯优化: 无可用的GP后端，使用随机搜索+最近邻启发式")

    # ---- 参数空间辅助方法 ----

    def _normalize_params(self, params: Dict[str, Any]) -> np.ndarray:
        """将参数字典归一化为 [0,1] 向量"""
        vec = np.zeros(self.n_params)
        for i, spec in enumerate(self.parameter_specs):
            value = params.get(spec.name, spec._low)
            vec[i] = spec.normalize(value)
        return vec

    def _denormalize_params(self, norm_vec: np.ndarray) -> Dict[str, Any]:
        """将归一化向量还原为参数字典"""
        params = {}
        for i, spec in enumerate(self.parameter_specs):
            params[spec.name] = spec.denormalize(norm_vec[i])
        return params

    def _midpoint_normalize(self, params: Dict[str, Any]) -> np.ndarray:
        """离散参数的中点归一化（消除离散化偏差）"""
        vec = np.zeros(self.n_params)
        for i, spec in enumerate(self.parameter_specs):
            value = params.get(spec.name, spec._low)
            vec[i] = spec.midpoint_normalize(value)
        return vec

    def _random_sample(self) -> np.ndarray:
        """生成随机归一化参数向量"""
        return self._gp_rng.uniform(0, 1, self.n_params)

    def _generate_candidates(self, n: int) -> np.ndarray:
        """生成候选参数矩阵"""
        return self._gp_rng.uniform(0, 1, size=(n, self.n_params))

    # ---- GP预测 ----

    def _gp_predict(self, X_train: np.ndarray, y_train: np.ndarray,
                    X_test: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """GP预测 (mean, std)"""
        if self._gp_mode == GPMode.SKLEARN and self._GPR is not None:
            try:
                gp = self._GPR(
                    kernel=self._kernel,
                    n_restarts_optimizer=5,
                    random_state=self.random_state,
                    normalize_y=True,
                )
                gp.fit(X_train, y_train)
                mu, sigma = gp.predict(X_test, return_std=True)
                return mu, sigma
            except Exception as e:
                _logger.warning(f"sklearn GP拟合失败: {e}")
                raise

        if self._gp_mode == GPMode.PURE_SCIPY:
            # 手动RBF + Cholesky实现
            n_train = len(X_train)
            n_test = len(X_test)

            sq_dist = (
                np.sum(X_train ** 2, 1).reshape(-1, 1)
                + np.sum(X_train ** 2, 1)
                - 2 * np.dot(X_train, X_train.T)
            )
            K = np.exp(-0.5 * sq_dist) + 1e-5 * np.eye(n_train)

            try:
                L = cho_factor(K)
                K_s = np.exp(-0.5 * (
                    np.sum(X_train ** 2, 1).reshape(-1, 1)
                    + np.sum(X_test ** 2, 1)
                    - 2 * np.dot(X_train, X_test.T)
                ))
                alpha = cho_solve(L, y_train)
                mu = K_s.T @ alpha
                v = cho_solve(L, K_s)
                K_ss = np.exp(-0.5 * (
                    np.sum(X_test ** 2, 1).reshape(-1, 1)
                    + np.sum(X_test ** 2, 1)
                    - 2 * np.dot(X_test, X_test.T)
                ))
                cov = K_ss - K_s.T @ v
                sigma = np.sqrt(np.maximum(np.diag(cov), 1e-10))
            except np.linalg.LinAlgError:
                mu = np.zeros(n_test)
                sigma = np.ones(n_test)

            return mu, sigma

        raise RuntimeError("无可用的GP后端")

    # ---- 采集函数 ----

    def _acquisition_values(self, mu: np.ndarray, sigma: np.ndarray,
                            y_best: float) -> np.ndarray:
        """计算采集函数值"""
        if self.acquisition == AcquisitionFunction.EI:
            return self._ei(mu, sigma, y_best, self.xi)
        elif self.acquisition == AcquisitionFunction.UCB:
            return self._ucb(mu, sigma, self.kappa_ucb)
        elif self.acquisition == AcquisitionFunction.PI:
            return self._pi(mu, sigma, y_best, self.xi)
        return self._ei(mu, sigma, y_best, self.xi)

    @staticmethod
    def _ei(mu: np.ndarray, sigma: np.ndarray, y_best: float, xi: float = 0.01) -> np.ndarray:
        """Expected Improvement"""
        if not _SCIPY_AVAILABLE:
            imp = mu - y_best - xi
            ei = np.maximum(imp, 0)
            return np.where(sigma > 1e-10, ei, 0.0)

        with np.errstate(divide='ignore'):
            imp = mu - y_best - xi
            Z = np.where(sigma > 1e-10, imp / sigma, 0.0)
            ei = imp * _scipy_norm.cdf(Z) + sigma * _scipy_norm.pdf(Z)
            ei = np.where(sigma > 1e-10, ei, 0.0)
        return np.maximum(ei, 0.0)

    @staticmethod
    def _ucb(mu: np.ndarray, sigma: np.ndarray, kappa: float = 2.576) -> np.ndarray:
        """Upper Confidence Bound"""
        return mu + kappa * sigma

    @staticmethod
    def _pi(mu: np.ndarray, sigma: np.ndarray, y_best: float, xi: float = 0.01) -> np.ndarray:
        """Probability of Improvement"""
        if not _SCIPY_AVAILABLE:
            return np.where(mu > y_best + xi, 1.0, 0.0)
        with np.errstate(divide='ignore'):
            Z = np.where(sigma > 1e-10, (mu - y_best - xi) / sigma, -np.inf)
            return _scipy_norm.cdf(Z)

    # ---- 最近邻启发式(降级) ----

    @staticmethod
    def _nearest_neighbor_heuristic(X_train: np.ndarray, y_train: np.ndarray,
                                    X_candidates: np.ndarray,
                                    maximize: bool = True,
                                    xi: float = 0.01) -> np.ndarray:
        """最近邻启发式：候选点到最近已评估点的距离"""
        ei_values = np.zeros(len(X_candidates))
        for j, candidate in enumerate(X_candidates):
            distances = np.sqrt(np.sum((X_train - candidate) ** 2, axis=1))
            nearest_y = y_train[int(np.argmin(distances))]
            y_best = y_train.max() if maximize else y_train.min()
            if maximize:
                ei_values[j] = max(0.0, nearest_y - y_best + xi)
            else:
                ei_values[j] = max(0.0, y_best - nearest_y + xi)
        return ei_values

    # ---- 优化主循环 ----

    def optimize(
        self,
        objective_function: Callable[..., float],
        n_calls: int = 50,
        n_initial_points: Optional[int] = None,
        n_candidates_per_iter: int = 500,
        maximize: bool = True,
        early_stopping_rounds: Optional[int] = None,
    ) -> OptimizationResult:
        """执行贝叶斯优化

        Args:
            objective_function: 目标函数，接收 **kwargs (参数名=值)，返回 float score
            n_calls: 总评估次数（含初始采样）
            n_initial_points: 初始随机采样数，默认 max(5, n_params*2, n_calls//5)
            n_candidates_per_iter: 每轮候选点数
            maximize: True=最大化目标，False=最小化
            early_stopping_rounds: 连续无改进则早停，None=不早停

        Returns:
            OptimizationResult 包含 best_params, best_score, trials 等
        """
        start_time = time.time()

        if n_initial_points is None:
            n_initial_points = max(5, self.n_params * 2, min(n_calls // 5, n_calls - 1))

        X_observed: List[np.ndarray] = []
        y_observed: List[float] = []
        trials: List[TrialRecord] = []

        best_score = float('-inf') if maximize else float('inf')
        best_params: Dict[str, Any] = {}
        no_improvement_count = 0

        # ---- 阶段1: 初始随机采样 ----
        for iteration in range(n_initial_points):
            x_norm = self._random_sample()
            params = self._denormalize_params(x_norm)
            score = float(objective_function(**params))

            X_observed.append(x_norm)
            y_observed.append(score)
            is_best = self._update_best(score, params, maximize, best_score)
            if is_best:
                best_score = score
                best_params = params.copy()
                no_improvement_count = 0
            else:
                no_improvement_count += 1

            trials.append(TrialRecord(
                iteration=iteration + 1, params=params.copy(),
                score=score, is_best=is_best
            ))

            if self.verbose:
                _logger.debug(f"[Bayesian] 初始采样 {iteration + 1}/{n_initial_points}, score={score:.4f}")

        X_train = np.array(X_observed)
        y_train = np.array(y_observed)

        # ---- 阶段2: GP+采集函数迭代 ----
        for iteration in range(n_initial_points, n_calls):
            if early_stopping_rounds and no_improvement_count >= early_stopping_rounds:
                if self.verbose:
                    _logger.info(f"[Bayesian] 早停: 连续 {no_improvement_count} 次无改进")
                break

            # 2a. 生成候选点
            X_candidates = self._generate_candidates(n_candidates_per_iter)

            # 2b. 尝试GP预测 + 采集函数
            best_candidate_idx = None

            if self._gp_available and len(X_train) >= 3:
                try:
                    mu, sigma = self._gp_predict(X_train, y_train, X_candidates)
                    acq_values = self._acquisition_values(mu, sigma, y_train.max() if maximize else y_train.min())
                    best_candidate_idx = int(np.argmax(acq_values))
                    self._gp_fail_count = 0
                except Exception as e:
                    self._gp_fail_count += 1
                    _logger.warning(
                        f"[Bayesian] GP拟合失败: {e} "
                        f"(连续失败 {self._gp_fail_count}/{self._GP_RESET_INTERVAL})"
                    )
                    if self._gp_fail_count >= self._GP_RESET_INTERVAL:
                        _logger.info(
                            f"[Bayesian] 已连续失败 {self._gp_fail_count} 次，重置GP代理模型"
                        )
                        self._gp_available = True
                        self._gp_fail_count = 0
                        self._gp_reset_count += 1
                    else:
                        self._gp_available = False

            # 2c. GP不可用时使用最近邻启发式
            if not self._gp_available or best_candidate_idx is None:
                ei_values = self._nearest_neighbor_heuristic(
                    X_train, y_train, X_candidates, maximize, self.xi
                )
                best_candidate_idx = int(np.argmax(ei_values))

            # 2d. 评估候选点
            candidate_norm = X_candidates[best_candidate_idx]
            params = self._denormalize_params(candidate_norm)
            score = float(objective_function(**params))

            # 离散参数中点归一化（消除离散化偏差）
            evaluated_norm = self._midpoint_normalize(params)

            X_train = np.vstack([X_train, evaluated_norm])
            y_train = np.append(y_train, score)

            is_best = self._update_best(score, params, maximize, best_score)
            if is_best:
                best_score = score
                best_params = params.copy()
                no_improvement_count = 0
            else:
                no_improvement_count += 1

            trials.append(TrialRecord(
                iteration=iteration + 1, params=params.copy(),
                score=score, is_best=is_best
            ))

            if self.verbose and (iteration % 5 == 0 or is_best):
                model_label = self._gp_mode.value if self._gp_available else "heuristic"
                _logger.info(
                    f"[Bayesian] 迭代 {iteration + 1}/{n_calls}, "
                    f"score={score:.4f}, best={best_score:.4f}, "
                    f"model={model_label}"
                )

        elapsed_time = time.time() - start_time
        if self.verbose:
            _logger.info(
                f"[Bayesian] 优化完成: {len(trials)}次评估, "
                f"best_score={best_score:.4f}, "
                f"耗时={elapsed_time:.1f}s, "
                f"gp_reset={self._gp_reset_count}次"
            )

        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            trials=trials,
            method=f"bayesian_{self._gp_mode.value}",
            total_iterations=len(trials),
            elapsed_time=elapsed_time,
            gp_available=self._gp_available,
            gp_reset_count=self._gp_reset_count,
        )

    # ---- 辅助 ----

    def _update_best(self, score: float, params: Dict[str, Any],
                     maximize: bool, current_best: float) -> bool:
        """检查是否更新最优解"""
        if maximize:
            return score > current_best
        return score < current_best


# ======================================================================
# 工具函数
# ======================================================================

def normalize_params_to_array(params: Dict[str, Any],
                              specs: List[ParameterSpec]) -> np.ndarray:
    """将参数字典转为归一化向量"""
    vec = np.zeros(len(specs))
    for i, spec in enumerate(specs):
        vec[i] = spec.normalize(params.get(spec.name, 0))
    return vec


def denormalize_array_to_params(norm_vec: np.ndarray,
                                specs: List[ParameterSpec]) -> Dict[str, Any]:
    """将归一化向量转为参数字典"""
    return {specs[i].name: specs[i].denormalize(norm_vec[i])
            for i in range(len(specs))}


def midpoint_normalize_params(params: Dict[str, Any],
                              specs: List[ParameterSpec]) -> np.ndarray:
    """离散参数的中点归一化（消除离散化偏差）"""
    vec = np.zeros(len(specs))
    for i, spec in enumerate(specs):
        vec[i] = spec.midpoint_normalize(params.get(spec.name, 0))
    return vec