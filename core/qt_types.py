from loguru import logger
"""
Qt类型注册模块

负责注册自定义Qt类型，解决信号槽中的类型注册问题。
"""

import os
from PyQt5.QtCore import QMetaType, QObject, pyqtSignal, pyqtProperty, QVariant, QMetaObject, Qt, Q_ARG, QMessageLogContext, QtMsgType
from PyQt5.QtGui import QTextCursor, QFont, QColor, QPen, QBrush, QTextCharFormat
from PyQt5.QtWidgets import QWidget
from typing import Dict, Any, List, Optional, Type

_qRegisterMetaType: Optional[callable] = None

def _qt_message_handler(msg_type: QtMsgType, context: QMessageLogContext, message: str):
    """Qt 消息处理程序，用于过滤特定的警告消息"""
    if "QVector<int>" in message or "known incorrect sRGB profile" in message:
        return
    original_message = str(message)
    logger.debug(f"Qt Message: {original_message}")

def _get_qRegisterMetaType():
    """尝试获取 qRegisterMetaType 函数，处理不同 PyQt5 版本差异"""
    global _qRegisterMetaType
    if _qRegisterMetaType is not None:
        return _qRegisterMetaType
    
    try:
        from PyQt5.QtCore import qRegisterMetaType
        _qRegisterMetaType = qRegisterMetaType
        return _qRegisterMetaType
    except ImportError:
        try:
            import sip
            if hasattr(sip, 'qRegisterMetaType'):
                _qRegisterMetaType = sip.qRegisterMetaType
                return _qRegisterMetaType
        except ImportError:
            pass
        
        _qRegisterMetaType = None
        return None


def init_qt_types():
    """
    集中注册所有需要跨线程使用的自定义信号和复杂数据类型。
    这个函数应该在应用程序启动时尽早调用。
    """
    logger.info("Initializing Qt type registration...")

    try:
        from PyQt5.QtCore import qInstallMessageHandler
        qInstallMessageHandler(_qt_message_handler)
        logger.debug("Qt message handler installed to filter warnings")
    except ImportError:
        logger.debug("qInstallMessageHandler not available")
    except Exception as e:
        logger.debug(f"Failed to install Qt message handler: {e}")

    qRegisterMetaType = _get_qRegisterMetaType()
    
    if qRegisterMetaType is None:
        logger.warning("qRegisterMetaType not available, skipping type registration")
    else:
        types_to_register = {
            "QTextCursor": QTextCursor,
            "QTextCharFormat": QTextCharFormat,
            "QFont": QFont,
            "QColor": QColor,
            "QPen": QPen,
            "QBrush": QBrush
        }

        for name, type_class in types_to_register.items():
            try:
                type_id = qRegisterMetaType(name)
                logger.debug(f"Successfully registered {name}, type ID: {type_id}")
            except Exception as e:
                logger.error(f"Failed to register {name}: {e}")

        try:
            type_id = qRegisterMetaType("QVector<int>")
            logger.debug(f"Successfully registered QVector<int>, type ID: {type_id}")
        except Exception as e:
            logger.debug(f"QVector<int> registration skipped: {e}")

    try:
        from .events import UIDataReadyEvent, StockSelectedEvent, IndicatorChangedEvent
        if qRegisterMetaType:
            try:
                qRegisterMetaType(UIDataReadyEvent)
                qRegisterMetaType(StockSelectedEvent)
                qRegisterMetaType(IndicatorChangedEvent)
                logger.debug("Successfully registered custom event types.")
            except Exception as e:
                logger.error(f"Failed to register custom event types: {e}")
        else:
            logger.debug("qRegisterMetaType not available, skipping custom event type registration")
    except ImportError as e:
        logger.debug(f"Custom event types import failed: {e}")

    logger.info("Qt type registration completed.")

# 确保类型注册在模块导入时就执行
init_qt_types()
