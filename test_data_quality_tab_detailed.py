#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据质量监控标签页导入 - 详细调试
"""

import sys
import os
import traceback

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from loguru import logger

try:
    logger.info("开始测试数据质量监控标签页导入...")
    
    # 测试1：导入pandas
    logger.info("步骤1: 导入pandas...")
    try:
        import pandas as pd
        logger.info("✓ pandas导入成功")
    except Exception as e:
        logger.error(f"✗ pandas导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试2：导入numpy
    logger.info("步骤2: 导入numpy...")
    try:
        import numpy as np
        logger.info("✓ numpy导入成功")
    except Exception as e:
        logger.error(f"✗ numpy导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试3：导入matplotlib
    logger.info("步骤3: 导入matplotlib...")
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
        logger.info("✓ matplotlib导入成功")
    except Exception as e:
        logger.error(f"✗ matplotlib导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试4：导入PyQt5
    logger.info("步骤4: 导入PyQt5...")
    try:
        from PyQt5.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
            QTabWidget, QFrame, QPushButton, QComboBox, QDateEdit, QTextEdit,
            QGroupBox, QGridLayout, QProgressBar, QSplitter,
            QCheckBox, QSpinBox, QSlider,
            QFileDialog, QMessageBox, QDialogButtonBox, QDialog, QHeaderView
        )
        from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QDate
        from PyQt5.QtGui import QFont, QColor
        logger.info("✓ PyQt5导入成功")
    except Exception as e:
        logger.error(f"✗ PyQt5导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试5：导入核心模块
    logger.info("步骤5: 导入核心模块...")
    try:
        from core.services.enhanced_data_quality_monitor import EnhancedDataQualityMonitor
        from core.services.quality_report_generator import QualityReportGenerator
        from core.plugin_types import DataType
        logger.info("✓ 核心模块导入成功")
    except Exception as e:
        logger.error(f"✗ 核心模块导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试6：导入真实数据提供者
    logger.info("步骤6: 导入真实数据提供者...")
    try:
        from gui.widgets.enhanced_ui.data_quality_monitor_tab_real_data import get_real_data_provider
        logger.info("✓ 真实数据提供者导入成功")
    except Exception as e:
        logger.error(f"✗ 真实数据提供者导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试7：导入ModernMetricCard
    logger.info("步骤7: 导入ModernMetricCard...")
    try:
        from gui.widgets.performance.components.metric_card import ModernMetricCard
        logger.info("✓ ModernMetricCard导入成功")
    except Exception as e:
        logger.error(f"✗ ModernMetricCard导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试8：导入DataQualityMonitorTab
    logger.info("步骤8: 导入DataQualityMonitorTab...")
    try:
        from gui.widgets.enhanced_ui.data_quality_monitor_tab import DataQualityMonitorTab
        logger.info("✓ DataQualityMonitorTab导入成功")
    except Exception as e:
        logger.error(f"✗ DataQualityMonitorTab导入失败: {e}")
        traceback.print_exc()
        raise
    
    logger.info("测试成功完成")
    
except Exception as e:
    logger.error(f"测试失败: {e}")
    traceback.print_exc()
finally:
    logger.info("测试结束")