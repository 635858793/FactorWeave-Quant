"""
详细诊断监控组件问题
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def diagnose_monitor_widget():
    """详细诊断监控组件问题"""
    from loguru import logger
    """详细诊断监控组件问题"""
    try:
        logger.info("=" * 80)
        logger.info("详细诊断监控组件问题")
        logger.info("=" * 80)

        # 1. 检查 PyQt5 导入
        logger.info("\n1. 检查 PyQt5 导入...")
        try:
            from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
            from PyQt5.QtCore import QTimer, pyqtSignal
            from PyQt5.QtGui import QColor
            logger.info("   ✅ PyQt5 导入成功")
        except ImportError as e:
            logger.error(f"   ❌ PyQt5 导入失败: {e}")
            return False

        # 2. 检查 loguru 导入
        logger.info("\n2. 检查 loguru 导入...")
        logger.info("   ✅ loguru 导入成功")

        # 3. 检查文件是否存在
        logger.info("\n3. 检查文件是否存在...")
        import os
        file_path = "gui/widgets/adaptive_pool_monitor_widget.py"
        if os.path.exists(file_path):
            logger.info(f"   ✅ 文件存在: {file_path}")
        else:
            logger.error(f"   ❌ 文件不存在: {file_path}")
            return False

        # 4. 尝试导入模块
        logger.info("\n4. 尝试导入模块...")
        try:
            from gui.widgets.adaptive_pool_monitor_widget import AdaptivePoolMonitorWidget
            logger.info("   ✅ 模块导入成功")
        except ImportError as e:
            logger.error(f"   ❌ 模块导入失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        except Exception as e:
            logger.error(f"   ❌ 模块导入异常: {e}")
            import traceback
            traceback.print_exc()
            return False

        # 5. 尝试创建实例（不显示UI）
        logger.info("\n5. 尝试创建实例...")
        try:
            # 设置环境变量，避免显示UI
            os.environ['QT_QPA_PLATFORM'] = 'offscreen'
            
            widget = AdaptivePoolMonitorWidget()
            logger.info("   ✅ 实例创建成功")
            logger.info(f"   类型: {type(widget)}")
            logger.info(f"   父类: {widget.__class__.__bases__}")
        except Exception as e:
            logger.error(f"   ❌ 实例创建失败: {e}")
            import traceback
            traceback.print_exc()
            return False

        # 6. 检查类的属性和方法
        logger.info("\n6. 检查类的属性和方法...")
        from gui.widgets.adaptive_pool_monitor_widget import AdaptivePoolMonitorWidget
        logger.info(f"   类名: {AdaptivePoolMonitorWidget.__name__}")
        logger.info(f"   文档: {AdaptivePoolMonitorWidget.__doc__}")
        logger.info(f"   信号: {getattr(AdaptivePoolMonitorWidget, 'status_updated', None)}")
        logger.info(f"   方法数量: {len([m for m in dir(AdaptivePoolMonitorWidget) if not m.startswith('_')])}")

        # 7. 检查 UI 组件导入
        logger.info("\n7. 检查 UI 组件导入...")
        try:
            from gui.dialogs.connection_pool_manager_dialog import ConnectionPoolManagerDialog
            logger.info("   ✅ ConnectionPoolManagerDialog 导入成功")
        except ImportError as e:
            logger.error(f"   ❌ ConnectionPoolManagerDialog 导入失败: {e}")
            return False

        logger.info("\n" + "=" * 80)
        logger.info("诊断完成")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 诊断失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    diagnose_monitor_widget()
