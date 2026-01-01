import sys

print("步骤1: 导入基础模块...")
from PyQt5.QtWidgets import QDialog, QVBoxLayout
print("✓ PyQt5.QtWidgets 导入成功")

from PyQt5.QtCore import Qt, pyqtSignal
print("✓ PyQt5.QtCore 导入成功")

from PyQt5.QtGui import QDrag
print("✓ PyQt5.QtGui 导入成功")

print("\n步骤2: 导入日志模块...")
from loguru import logger
print("✓ loguru 导入成功")

print("\n步骤3: 导入策略服务...")
try:
    from core.services.strategy_service import StrategyService, StrategyConfig
    print("✓ StrategyService 导入成功")
except Exception as e:
    print(f"✗ StrategyService 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n步骤4: 导入策略扩展...")
try:
    from core.strategy_extensions import StrategyContext
    print("✓ StrategyContext 导入成功")
except Exception as e:
    print(f"✗ StrategyContext 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n步骤5: 导入主题模块...")
try:
    from utils.theme import get_theme_manager
    print("✓ get_theme_manager 导入成功")
except Exception as e:
    print(f"✗ get_theme_manager 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n步骤6: 导入事件总线...")
try:
    from core.events.event_bus import get_event_bus
    print("✓ get_event_bus 导入成功")
except Exception as e:
    print(f"✗ get_event_bus 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n步骤7: 导入资源管理器...")
try:
    from utils.resource_manager import ResourceManager
    print("✓ ResourceManager 导入成功")
except Exception as e:
    print(f"✗ ResourceManager 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n步骤8: 导入异步任务管理器...")
try:
    from utils.async_task_manager import AsyncTaskManager
    print("✓ AsyncTaskManager 导入成功")
except Exception as e:
    print(f"✗ AsyncTaskManager 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n步骤9: 导入完整对话框模块...")
try:
    from gui.dialogs.enhanced_strategy_manager_dialog import EnhancedStrategyManagerDialog
    print("✓ EnhancedStrategyManagerDialog 导入成功")
except Exception as e:
    print(f"✗ EnhancedStrategyManagerDialog 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n所有导入步骤完成！")
sys.exit(0)
