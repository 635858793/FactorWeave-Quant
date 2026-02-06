"""
验证性能监控器修复 - 测试导入时不再自动启动
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

def test_import_no_auto_start():
    """测试导入时不再自动启动性能监控器"""
    print("=" * 60)
    print("测试：验证导入时不再自动启动性能监控器")
    print("=" * 60)
    
    # 1. 导入基础服务（之前会触发性能监控器）
    print("\n1. 导入 core.services.base_service...")
    from core.services.base_service import BaseService
    print("   ✓ 导入成功")
    
    # 2. 检查性能监控器是否已启动
    print("\n2. 检查性能监控器状态...")
    from core.performance import get_performance_monitor
    monitor = get_performance_monitor()
    
    if monitor.is_running:
        print("   ✗ 性能监控器仍在自动启动！")
        print(f"   当前状态: running={monitor.is_running}")
        return False
    else:
        print("   ✓ 性能监控器未自动启动")
        print(f"   当前状态: running={monitor.is_running}")
    
    # 3. 手动启动性能监控器
    print("\n3. 手动启动性能监控器...")
    monitor.start()
    if monitor.is_running:
        print("   ✓ 手动启动成功")
    else:
        print("   ✗ 手动启动失败")
        return False
    
    # 4. 停止性能监控器
    print("\n4. 停止性能监控器...")
    monitor.stop()
    if not monitor.is_running:
        print("   ✓ 停止成功")
    else:
        print("   ✗ 停止失败")
        return False
    
    # 5. 测试其他导入
    print("\n5. 测试其他导入...")
    from core.services.strategy_service import StrategyEngine
    print("   ✓ 导入 StrategyEngine 成功")
    
    from core.services.ai_prediction_service import AIPredictionService
    print("   ✓ 导入 AIPredictionService 成功")
    
    # 6. 再次检查状态
    print("\n6. 再次检查性能监控器状态...")
    monitor = get_performance_monitor()
    if not monitor.is_running:
        print("   ✓ 性能监控器保持未启动状态")
    else:
        print("   ✗ 性能监控器被意外启动")
        return False
    
    print("\n" + "=" * 60)
    print("所有测试通过！✓")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_import_no_auto_start()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
