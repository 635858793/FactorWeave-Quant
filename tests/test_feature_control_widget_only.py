"""
单独测试FeatureControlWidget
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

def test_feature_control_widget():
    """测试FeatureControlWidget"""
    logger.info("=" * 60)
    logger.info("测试FeatureControlWidget - 功能开关管理")
    logger.info("=" * 60)
    
    try:
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.feature_control_widget import FeatureControlWidget
        from core.services.feature_control_service import FeatureControlService
        
        # 创建应用实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建UI组件
        widget = FeatureControlWidget()
        logger.info("✓ FeatureControlWidget创建成功")
        
        # 测试服务初始化
        if widget.feature_service:
            logger.info("✓ FeatureControlService初始化成功")
        else:
            logger.warning("⚠ FeatureControlService未初始化")
        
        # 测试UI组件
        logger.info("✓ UI组件包含以下标签页:")
        for i in range(widget.tab_widget.count()):
            logger.info(f"  - {widget.tab_widget.tabText(i)}")
        
        # 测试配置表格
        if hasattr(widget, 'config_table'):
            row_count = widget.config_table.rowCount()
            logger.info(f"✓ 配置表格行数: {row_count}")
        
        # 测试状态表格
        if hasattr(widget, 'status_table'):
            row_count = widget.status_table.rowCount()
            logger.info(f"✓ 状态表格行数: {row_count}")
        
        # 测试工具栏按钮
        logger.info("✓ 工具栏按钮:")
        for action in widget.toolbar.actions():
            if not action.isSeparator():
                logger.info(f"  - {action.text()}")
        
        # 测试信号连接
        logger.info("✓ 信号连接:")
        logger.info(f"  - feature_toggled: {widget.feature_toggled}")
        logger.info(f"  - feature_status_changed: {widget.feature_status_changed}")
        
        logger.info("✓ FeatureControlWidget测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ FeatureControlWidget测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = test_feature_control_widget()
    sys.exit(0 if result else 1)
