from loguru import logger
"""
警告抑制器

用于抑制不必要的警告信息，提升用户体验。
"""

import warnings
import os

logger = logger

def suppress_warnings():
    """抑制各种不必要的警告"""
    try:
        # 抑制pandas警告
        warnings.filterwarnings('ignore', category=FutureWarning)
        warnings.filterwarnings('ignore', category=UserWarning)
        warnings.filterwarnings('ignore', category=DeprecationWarning)

        # 抑制matplotlib警告
        warnings.filterwarnings('ignore', message='.*GUI is implemented.*')
        warnings.filterwarnings('ignore', message='.*Agg backend.*')

        # 抑制numpy警告
        warnings.filterwarnings('ignore', message='.*overflow encountered.*')
        warnings.filterwarnings(
            'ignore', message='.*invalid value encountered.*')

        # 抑制Qt警告
        os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.*=false'

        # 抑制libpng sRGB警告
        os.environ['LIBPNG_WARN'] = '0'
        os.environ['PNG_SKIP_sRGB_CHECK_PROFILE'] = '1'

        # 抑制hikyuu相关警告
        warnings.filterwarnings('ignore', message='.*hikyuu.*')

        logger.info("Warning suppression configured")

    except Exception as e:
        logger.error(f"Failed to configure warning suppression: {e}")
