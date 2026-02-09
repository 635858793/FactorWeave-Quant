from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
matplotlib中文字体配置工具
统一解决系统中matplotlib中文字体显示为方格的问题
"""

import os
import platform
from typing import List, Optional

try:
    import matplotlib as mpl
    mpl.use('Agg')
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

class MatplotlibFontConfig:
    """matplotlib字体配置管理器"""

    # 不同系统的中文字体映射
    SYSTEM_FONTS = {
        'Windows': [
            'SimHei',           # 黑体
            'Microsoft YaHei',  # 微软雅黑
            'SimSun',           # 宋体
            'KaiTi'             # 楷体
        ],
        'Darwin': [  # macOS
            'PingFang SC',      # 苹方
            'Heiti SC',         # 黑体-简
            'STSong',           # 华文宋体
            'Arial Unicode MS'   # Arial Unicode MS
        ],
        'Linux': [
            'DejaVu Sans',      # DejaVu Sans
            'WenQuanYi Micro Hei',  # 文泉驿微米黑
            'Noto Sans CJK SC',  # 思源黑体
            'SimHei'            # 黑体（如果安装了）
        ]
    }

    # 通用后备字体
    FALLBACK_FONTS = ['DejaVu Sans', 'Arial', 'sans-serif']

    @classmethod
    def get_system_fonts(cls) -> List[str]:
        """获取当前系统推荐的中文字体列表"""
        system = platform.system()
        fonts = cls.SYSTEM_FONTS.get(system, cls.SYSTEM_FONTS['Linux'])
        return fonts + cls.FALLBACK_FONTS

    @classmethod
    def configure_chinese_font(cls, font_size: int = 10, force_config: bool = False) -> bool:
        """
        配置matplotlib中文字体

        Args:
            font_size: 字体大小，默认10
            force_config: 是否强制重新配置，默认False

        Returns:
            bool: 配置是否成功
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.info("matplotlib不可用，跳过字体配置")
            return False

        # 检查是否已经配置过
        if not force_config and cls._is_chinese_font_configured():
            logger.info("SUCCESS: matplotlib中文字体已配置")
            return True

        try:
            # 获取系统推荐字体
            fonts = cls.get_system_fonts()

            # 配置字体
            mpl.rcParams["font.sans-serif"] = fonts
            mpl.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题
            mpl.rcParams["font.size"] = font_size

            # 验证配置
            if cls._test_chinese_display():
                logger.info(f"SUCCESS: matplotlib中文字体配置成功，使用字体: {fonts[0]}")
                return True
            else:
                logger.info("matplotlib中文字体配置可能有问题")
                return False

        except Exception as e:
            logger.info(f"ERROR: matplotlib字体配置失败: {e}")
            return False

    @classmethod
    def _is_chinese_font_configured(cls) -> bool:
        """检查是否已经配置了中文字体"""
        if not MATPLOTLIB_AVAILABLE:
            return False

        try:
            current_fonts = mpl.rcParams.get("font.sans-serif", [])
            system_fonts = cls.get_system_fonts()

            # 检查是否包含系统字体
            for font in system_fonts[:3]:  # 检查前3个系统字体
                if font in current_fonts:
                    return True
            return False
        except:
            return False

    @classmethod
    def _test_chinese_display(cls) -> bool:
        """测试中文字符显示"""
        if not MATPLOTLIB_AVAILABLE:
            return False

        try:
            # 创建一个简单的测试图表
            fig, ax = plt.subplots(figsize=(1, 1))
            ax.text(0.5, 0.5, '测试中文', ha='center', va='center')
            plt.close(fig)  # 立即关闭图表
            return True
        except Exception as e:
            logger.info(f"中文字体测试失败: {e}")
            return False

    @classmethod
    def get_available_fonts(cls) -> List[str]:
        """获取系统可用的字体列表"""
        if not MATPLOTLIB_AVAILABLE:
            return []

        try:
            from matplotlib.font_manager import fontManager
            fonts = [f.name for f in fontManager.ttflist]
            # 过滤出可能的中文字体
            chinese_fonts = []
            for font in fonts:
                if any(keyword in font for keyword in ['Hei', 'Song', 'Kai', 'YaHei', 'PingFang', 'Noto', 'WenQuanYi']):
                    chinese_fonts.append(font)
            return chinese_fonts
        except Exception as e:
            logger.info(f"获取字体列表失败: {e}")
            return []

    @classmethod
    def reset_font_config(cls):
        """重置matplotlib字体配置为默认值"""
        if not MATPLOTLIB_AVAILABLE:
            return

        try:
            mpl.rcdefaults()
            logger.info("SUCCESS: matplotlib字体配置已重置为默认值")
        except Exception as e:
            logger.info(f"ERROR: 重置字体配置失败: {e}")

def configure_matplotlib_chinese_font(font_size: int = 10, force_config: bool = False) -> bool:
    """
    便捷函数：配置matplotlib中文字体

    Args:
        font_size: 字体大小
        force_config: 是否强制重新配置

    Returns:
        bool: 配置是否成功
    """
    return MatplotlibFontConfig.configure_chinese_font(font_size, force_config)

# 自动配置（当模块被导入时）
if __name__ != "__main__":
    try:
        configure_matplotlib_chinese_font()
    except Exception:
        pass  # 静默忽略初始化错误，避免阻塞模块导入

if __name__ == "__main__":
    # 测试脚本
    logger.info("=== matplotlib字体配置测试 ===")

    logger.info("\n1. 系统推荐字体:")
    fonts = MatplotlibFontConfig.get_system_fonts()
    for i, font in enumerate(fonts[:5]):  # 显示前5个
        logger.info(f"   {i+1}. {font}")

    logger.info("\n2. 配置中文字体:")
    success = MatplotlibFontConfig.configure_chinese_font(force_config=True)
    logger.info(f"   配置结果: {'成功' if success else '失败'}")

    logger.info("\n3. 系统可用中文字体:")
    available_fonts = MatplotlibFontConfig.get_available_fonts()
    if available_fonts:
        for i, font in enumerate(available_fonts[:10]):  # 显示前10个
            logger.info(f"   {i+1}. {font}")
    else:
        logger.info(" 未找到中文字体")

    logger.info("\n=== 测试完成 ===")
