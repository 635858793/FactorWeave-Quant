"""
安全pickle加载工具模块

提供受限制的反序列化功能，通过 find_class 白名单机制防止任意代码执行。
"""

import io
import pickle
from typing import Any, Set

SAFE_MODULES: Set[str] = {
    'builtins',
    'numpy',
    'numpy.core.multiarray',
    'numpy.core.numeric',
    'numpy._globals',
    'pandas',
    'pandas.core.frame',
    'pandas.core.series',
    'pandas.core.indexes',
    'pandas._libs',
    'datetime',
    'collections',
    'decimal',
    'numbers',
    'dateutil',
    'pytz',
    'scipy',
}


class SafeUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str) -> Any:
        if module not in SAFE_MODULES:
            if not module.startswith(('numpy.', 'pandas.', 'scipy.')):
                raise pickle.UnpicklingError(
                    f"禁止反序列化: module={module}, name={name}"
                )
        return super().find_class(module, name)


def safe_load(file, **kwargs) -> Any:
    """安全的pickle.load，使用受限类白名单"""
    unpickler = SafeUnpickler(file, **kwargs)
    return unpickler.load()


def safe_loads(data: bytes, **kwargs) -> Any:
    """安全的pickle.loads，使用受限类白名单"""
    return safe_load(io.BytesIO(data), **kwargs)