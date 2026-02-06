"""
性能监控器修复验证 - 全面测试
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

def test_import_chain():
    """测试完整的导入链"""
    print("=" * 60)
    print("测试：验证性能监控器不会在导入时自动启动")
    print("=" * 60)
    
    # 1. 测试基础服务导入
    print("\n1. 测试导入 core.services.base_service...")
    from core.services.base_service import BaseService
    print("   ✓ 导入成功")
    
    # 2. 测试策略服务导入
    print("\n2. 测试导入 core.services.strategy_service...")
    from core.services.strategy_service import StrategyService
    print("   ✓ 导入成功")
    
    # 3. 测试AI预测服务导入
    print("\n3. 测试导入 core.services.ai_prediction_service...")
    from core.services.ai_prediction_service import AIPredictionService
    print("   ✓ 导入成功")
    
    # 4. 测试TensorFlow GPU管理器导入
    print("\n4. 测试导入 core.services.tensorflow_gpu_manager...")
    from core.services.tensorflow_gpu_manager import TensorFlowGPUManager
    print("   ✓ 导入成功")
    
    # 5. 测试性能协调器导入
    print("\n5. 测试导入 core.performance.unified_performance_coordinator...")
    from core.performance.unified_performance_coordinator import UnifiedPerformanceCoordinator
    print("   ✓ 导入成功")
    
    # 6. 测试高级优化模块导入
    print("\n6. 测试导入 core.advanced_optimization.real_time_monitoring...")
    from core.advanced_optimization.real_time_monitoring import DeepOptimizationMonitor
    print("   ✓ 导入成功")
    
    # 7. 检查性能监控器状态
    print("\n7. 检查性能监控器状态...")
    from core.performance import get_performance_monitor
    monitor = get_performance_monitor()
    
    if monitor.is_running:
        print("   ✗ 性能监控器仍在自动启动！")
        print(f"   当前状态: running={monitor.is_running}")
        return False
    else:
        print("   ✓ 性能监控器未自动启动")
        print(f"   当前状态: running={monitor.is_running}")
    
    # 8. 测试手动启动
    print("\n8. 测试手动启动性能监控器...")
    monitor.start()
    if monitor.is_running:
        print("   ✓ 手动启动成功")
    else:
        print("   ✗ 手动启动失败")
        return False
    
    # 9. 测试停止
    print("\n9. 测试停止性能监控器...")
    monitor.stop()
    if not monitor.is_running:
        print("   ✓ 停止成功")
    else:
        print("   ✗ 停止失败")
        return False
    
    # 10. 测试性能协调器
    print("\n10. 测试性能协调器...")
    coordinator = UnifiedPerformanceCoordinator()
    if not monitor.is_running:
        print("   ✓ 协调器创建未自动启动监控器")
    else:
        print("   ✗ 协调器创建时自动启动了监控器")
        return False
    
    # 11. 测试协调器启动
    print("\n11. 测试协调器启动...")
    coordinator.start()
    if monitor.is_running:
        print("   ✓ 协调器启动成功启动了监控器")
    else:
        print("   ✗ 协调器启动未能启动监控器")
        return False
    
    # 12. 清理
    print("\n12. 清理资源...")
    coordinator.stop()
    monitor.stop()
    print("   ✓ 清理完成")
    
    print("\n" + "=" * 60)
    print("所有测试通过！✓")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_import_chain()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
