from loguru import logger
"""
统一数据处理库导入管理模块

该模块提供了项目中所有数据处理、可视化、机器学习等库的统一导入接口，
包括错误处理、版本兼容性和可选依赖管理。

使用方式:
    from utils.imports import pd, np, plt, sns, go, px
    # 或者
    from utils.imports import get_pandas, get_numpy, get_matplotlib
"""

import sys
import warnings
from typing import Optional, Any, Dict, List
import importlib
from functools import lru_cache

# 使用系统统一组件
# Loguru导入已移除

# 导入状态缓存
_import_cache: Dict[str, Any] = {}
_import_errors: Dict[str, str] = {}

class ImportManager:
    """导入管理器，负责统一管理所有第三方库的导入"""

    def __init__(self):
        self._cache = {}
        self._errors = {}
        self._warnings_shown = set()
        self.logger = logger.bind(module=__name__)

    def _safe_import(self, module_name: str, package: Optional[str] = None,
                     alias: Optional[str] = None, required: bool = True) -> Optional[Any]:
        """
        安全导入模块，带错误处理和缓存

        Args:
            module_name: 模块名称
            package: 包名称（用于相对导入）
            alias: 别名
            required: 是否为必需模块

        Returns:
            导入的模块对象，失败时返回None
        """
        cache_key = f"{module_name}:{package}:{alias}"

        # 检查缓存
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 检查是否已知导入失败
        if cache_key in self._errors:
            if required and cache_key not in self._warnings_shown:
                self.logger.warning(
                    f"Required module '{module_name}' is not available: {self._errors[cache_key]}")
                self._warnings_shown.add(cache_key)
            return None

        try:
            if package:
                module = importlib.import_module(module_name, package)
            else:
                module = importlib.import_module(module_name)

            self._cache[cache_key] = module
            self.logger.debug(f"Successfully imported module: {module_name}")
            return module

        except ImportError as e:
            error_msg = str(e)
            self._errors[cache_key] = error_msg

            if required and cache_key not in self._warnings_shown:
                self.logger.warning(
                    f"Required module '{module_name}' is not available: {error_msg}")
                self._warnings_shown.add(cache_key)

            return None
        except Exception as e:
            error_msg = f"Unexpected error importing {module_name}: {str(e)}"
            self._errors[cache_key] = error_msg

            if required and cache_key not in self._warnings_shown:
                self.logger.error(error_msg)
                self._warnings_shown.add(cache_key)

            return None

    def get_module_info(self) -> Dict[str, Dict[str, Any]]:
        """获取所有模块的导入状态信息"""
        info = {
            'available': {},
            'errors': {},
            'cache_size': len(self._cache)
        }

        for key, module in self._cache.items():
            module_name = key.split(':')[0]
            info['available'][module_name] = {
                'version': getattr(module, '__version__', 'unknown'),
                'file': getattr(module, '__file__', 'unknown')
            }

        info['errors'] = self._errors.copy()
        return info

# 全局导入管理器实例
_import_manager = ImportManager()

# =============================================================================
# 基础数据处理库
# =============================================================================

@lru_cache(maxsize=1)
def get_pandas():
    """获取pandas库"""
    return _import_manager._safe_import('pandas', required=True)

@lru_cache(maxsize=1)
def get_numpy():
    """获取numpy库"""
    return _import_manager._safe_import('numpy', required=True)

# 创建标准别名
pd = get_pandas()
np = get_numpy()

# =============================================================================
# 可视化库
# =============================================================================

@lru_cache(maxsize=1)
def get_matplotlib():
    """获取matplotlib库"""
    return _import_manager._safe_import('matplotlib', required=True)

@lru_cache(maxsize=1)
def get_matplotlib_pyplot():
    """获取matplotlib.pyplot"""
    return _import_manager._safe_import('matplotlib.pyplot', required=True)

@lru_cache(maxsize=1)
def get_matplotlib_dates():
    """获取matplotlib.dates"""
    return _import_manager._safe_import('matplotlib.dates', required=False)

@lru_cache(maxsize=1)
def get_matplotlib_backends():
    """获取matplotlib后端"""
    try:
        backend = _import_manager._safe_import(
            'matplotlib.backends.backend_qt5agg', required=False)
        if backend:
            return {
                'FigureCanvas': getattr(backend, 'FigureCanvasQTAgg', None),
                'NavigationToolbar': getattr(backend, 'NavigationToolbar2QT', None)
            }
    except Exception as e:
        logger.debug(f"无法导入matplotlib Qt后端: {e}")
    return None

@lru_cache(maxsize=1)
def get_matplotlib_figure():
    """获取matplotlib.figure"""
    return _import_manager._safe_import('matplotlib.figure', required=False)

@lru_cache(maxsize=1)
def get_seaborn():
    """获取seaborn库"""
    return _import_manager._safe_import('seaborn', required=False)

@lru_cache(maxsize=1)
def get_plotly():
    """获取plotly相关模块"""
    plotly_modules = {}

    # 主要plotly模块
    plotly_modules['graph_objects'] = _import_manager._safe_import(
        'plotly.graph_objects', required=False)
    plotly_modules['express'] = _import_manager._safe_import(
        'plotly.express', required=False)
    plotly_modules['subplots'] = _import_manager._safe_import(
        'plotly.subplots', required=False)
    plotly_modules['figure_factory'] = _import_manager._safe_import(
        'plotly.figure_factory', required=False)
    plotly_modules['io'] = _import_manager._safe_import(
        'plotly.io', required=False)

    return plotly_modules

# 创建标准别名
plt = get_matplotlib_pyplot()
mdates = get_matplotlib_dates()
sns = get_seaborn()

# Plotly别名
_plotly_modules = get_plotly()
go = _plotly_modules.get('graph_objects') if _plotly_modules else None
px = _plotly_modules.get('express') if _plotly_modules else None

# Matplotlib后端
_mpl_backends = get_matplotlib_backends()
FigureCanvas = _mpl_backends.get('FigureCanvas') if _mpl_backends else None
NavigationToolbar = _mpl_backends.get(
    'NavigationToolbar') if _mpl_backends else None

# Matplotlib Figure
_mpl_figure = get_matplotlib_figure()
Figure = getattr(_mpl_figure, 'Figure', None) if _mpl_figure else None

# =============================================================================
# 科学计算库
# =============================================================================

@lru_cache(maxsize=1)
def get_scipy():
    """获取scipy相关模块"""
    scipy_modules = {}

    # 主要scipy模块
    scipy_modules['stats'] = _import_manager._safe_import(
        'scipy.stats', required=False)
    scipy_modules['optimize'] = _import_manager._safe_import(
        'scipy.optimize', required=False)

    return scipy_modules

# Scipy别名
_scipy_modules = get_scipy()
scipy_stats = _scipy_modules.get('stats') if _scipy_modules else None
scipy_optimize = _scipy_modules.get('optimize') if _scipy_modules else None

# =============================================================================
# 机器学习库
# =============================================================================

@lru_cache(maxsize=1)
def get_sklearn():
    """获取sklearn相关模块"""
    sklearn_modules = {}

    # 主要sklearn模块
    sklearn_modules['metrics'] = _import_manager._safe_import(
        'sklearn.metrics', required=False)
    sklearn_modules['model_selection'] = _import_manager._safe_import(
        'sklearn.model_selection', required=False)
    sklearn_modules['preprocessing'] = _import_manager._safe_import(
        'sklearn.preprocessing', required=False)
    sklearn_modules['feature_selection'] = _import_manager._safe_import(
        'sklearn.feature_selection', required=False)
    sklearn_modules['decomposition'] = _import_manager._safe_import(
        'sklearn.decomposition', required=False)

    # 机器学习算法
    sklearn_modules['ensemble'] = _import_manager._safe_import(
        'sklearn.ensemble', required=False)
    sklearn_modules['linear_model'] = _import_manager._safe_import(
        'sklearn.linear_model', required=False)
    sklearn_modules['svm'] = _import_manager._safe_import(
        'sklearn.svm', required=False)

    return sklearn_modules

# Sklearn别名
_sklearn_modules = get_sklearn()
sklearn_metrics = _sklearn_modules.get('metrics') if _sklearn_modules else None
sklearn_model_selection = _sklearn_modules.get(
    'model_selection') if _sklearn_modules else None
sklearn_preprocessing = _sklearn_modules.get(
    'preprocessing') if _sklearn_modules else None

# =============================================================================
# 技术分析库
# =============================================================================

@lru_cache(maxsize=1)
def get_talib():
    """获取talib库"""
    return _import_manager._safe_import('talib', required=False)

talib = get_talib()

# =============================================================================
# 便捷函数
# =============================================================================

def check_required_libraries() -> Dict[str, bool]:
    """检查必需库的可用性

    Returns:
        库名到可用性的映射
    """
    required_libs = {
        'pandas': get_pandas(),
        'numpy': get_numpy(),
        'matplotlib': get_matplotlib(),
        'matplotlib.pyplot': get_matplotlib_pyplot()
    }

    return {name: lib is not None for name, lib in required_libs.items()}

def get_import_summary() -> str:
    """获取导入状态摘要

    Returns:
        导入状态的字符串摘要
    """
    info = _import_manager.get_module_info()

    summary = f"导入状态摘要:\n"
    summary += f"- 成功导入: {len(info['available'])} 个模块\n"
    summary += f"- 导入失败: {len(info['errors'])} 个模块\n"
    summary += f"- 缓存大小: {info['cache_size']}\n"

    if info['available']:
        summary += "\n成功导入的模块:\n"
        for name, details in info['available'].items():
            summary += f"  - {name}: {details['version']}\n"

    if info['errors']:
        summary += "\n导入失败的模块:\n"
        for key, error in info['errors'].items():
            module_name = key.split(':')[0]
            summary += f"  - {module_name}: {error}\n"

    return summary

def ensure_required_libraries():
    """确保必需库可用，如果不可用则抛出异常"""
    required_status = check_required_libraries()
    missing_libs = [name for name,
                    available in required_status.items() if not available]

    if missing_libs:
        raise ImportError(
            f"Missing required libraries: {', '.join(missing_libs)}")

def safe_import(module_name: str, required: bool = True) -> Optional[Any]:
    """安全导入模块的便捷函数

    Args:
        module_name: 模块名称
        required: 是否为必需模块

    Returns:
        导入的模块对象，失败时返回None
    """
    return _import_manager._safe_import(module_name, required=required)

# 导出所有公共接口
__all__ = [
    # 基础库
    'pd', 'np', 'plt', 'sns', 'go', 'px',

    # 获取函数
    'get_pandas', 'get_numpy', 'get_matplotlib', 'get_matplotlib_pyplot',
    'get_seaborn', 'get_plotly', 'get_scipy', 'get_sklearn', 'get_talib',

    # 便捷函数
    'check_required_libraries', 'get_import_summary', 'ensure_required_libraries',
    'safe_import',

    # 模块别名
    'scipy_stats', 'scipy_optimize', 'sklearn_metrics', 'sklearn_model_selection',
    'sklearn_preprocessing', 'talib'
]
