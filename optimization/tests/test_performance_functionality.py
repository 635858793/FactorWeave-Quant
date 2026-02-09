"""
性能监控器功能测试 - 验证手动启动/停止和协调器延迟初始化
"""
import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

def test_manual_start_stop():
    """测试手动启动/停止功能"""
    print("=" * 60)
    print("测试：验证手动启动/停止功能")
    print("=" * 60)
    
    from core.performance import get_performance_monitor
    
    # 1. 获取监控器实例（不应自动启动）
    print("\n1. 获取性能监控器实例...")
    monitor = get_performance_monitor()
    if not monitor.is_running:
        print("   ✓ 监控器未自动启动")
    else:
        print("   ✗ 监控器已自动启动")
        return False
    
    # 2. 手动启动监控器
    print("\n2. 手动启动监控器...")
    monitor.start()
    if monitor.is_running:
        print("   ✓ 监控器启动成功")
    else:
        print("   ✗ 监控器启动失败")
        return False
    
    # 3. 等待一段时间
    print("\n3. 等待监控器运行...")
    time.sleep(2)
    print("   ✓ 监控器运行中")
    
    # 4. 手动停止监控器
    print("\n4. 手动停止监控器...")
    monitor.stop()
    if not monitor.is_running:
        print("   ✓ 监控器停止成功")
    else:
        print("   ✗ 监控器停止失败")
        return False
    
    # 5. 再次启动监控器
    print("\n5. 再次启动监控器...")
    monitor.start()
    if monitor.is_running:
        print("   ✓ 监控器重新启动成功")
    else:
        print("   ✗ 监控器重新启动失败")
        return False
    
    # 6. 清理
    print("\n6. 清理资源...")
    monitor.stop()
    print("   ✓ 清理完成")
    
    return True

def test_coordinator_lazy_init():
    """测试性能协调器的延迟初始化"""
    print("\n" + "=" * 60)
    print("测试：验证性能协调器延迟初始化")
    print("=" * 60)
    
    from core.performance.unified_performance_coordinator import (
        UnifiedPerformanceCoordinator, get_performance_coordinator
    )
    
    # 1. 创建协调器实例（不应自动启动监控器）
    print("\n1. 创建协调器实例...")
    coordinator = UnifiedPerformanceCoordinator()
    from core.performance import get_performance_monitor
    monitor = get_performance_monitor()
    
    if not monitor.is_running:
        print("   ✓ 协调器创建未自动启动监控器")
    else:
        print("   ✗ 协调器创建时自动启动了监控器")
        return False
    
    # 2. 启动协调器（应该延迟初始化并启动监控器）
    print("\n2. 启动协调器...")
    coordinator.start()
    if monitor.is_running:
        print("   ✓ 协调器启动成功启动了监控器")
    else:
        print("   ✗ 协调器启动未能启动监控器")
        return False
    
    # 3. 等待协调器运行
    print("\n3. 等待协调器运行...")
    time.sleep(2)
    print("   ✓ 协调器运行中")
    
    # 4. 停止协调器
    print("\n4. 停止协调器...")
    coordinator.stop()
    if not monitor.is_running:
        print("   ✓ 协调器停止成功，监控器也停止")
    else:
        print("   ✗ 协调器停止后监控器仍在运行")
        return False
    
    # 5. 测试全局协调器函数
    print("\n5. 测试全局协调器函数...")
    coordinator2 = get_performance_coordinator()
    if coordinator is coordinator2:
        print("   ✓ 全局协调器返回相同实例")
    else:
        print("   ✗ 全局协调器返回不同实例")
        return False
    
    # 6. 清理
    print("\n6. 清理资源...")
    coordinator.stop()
    print("   ✓ 清理完成")
    
    return True

def test_multiple_instances():
    """测试多实例行为"""
    print("\n" + "=" * 60)
    print("测试：验证多实例行为")
    print("=" * 60)
    
    from core.performance import get_performance_monitor
    
    # 1. 获取多个实例
    print("\n1. 获取多个监控器实例...")
    monitor1 = get_performance_monitor()
    monitor2 = get_performance_monitor()
    monitor3 = get_performance_monitor()
    
    if monitor1 is monitor2 is monitor3:
        print("   ✓ 所有实例相同（单例模式）")
    else:
        print("   ✗ 实例不相同")
        return False
    
    # 2. 通过一个实例启动
    print("\n2. 通过monitor1启动...")
    monitor1.start()
    
    if monitor1.is_running and monitor2.is_running and monitor3.is_running:
        print("   ✓ 所有实例都显示为运行状态")
    else:
        print("   ✗ 实例状态不一致")
        return False
    
    # 3. 通过另一个实例停止
    print("\n3. 通过monitor2停止...")
    monitor2.stop()
    
    if not monitor1.is_running and not monitor2.is_running and not monitor3.is_running:
        print("   ✓ 所有实例都显示为停止状态")
    else:
        print("   ✗ 实例状态不一致")
        return False
    
    return True

def main():
    """主函数"""
    print("🚀 性能监控器功能全面测试")
    print("=" * 60)
    
    results = []
    
    # 测试1：手动启动/停止
    print("\n【测试1：手动启动/停止功能】")
    try:
        result1 = test_manual_start_stop()
        results.append(("手动启动/停止", result1))
    except Exception as e:
        print(f"   ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("手动启动/停止", False))
    
    # 测试2：协调器延迟初始化
    print("\n【测试2：协调器延迟初始化】")
    try:
        result2 = test_coordinator_lazy_init()
        results.append(("协调器延迟初始化", result2))
    except Exception as e:
        print(f"   ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("协调器延迟初始化", False))
    
    # 测试3：多实例行为
    print("\n【测试3：多实例行为】")
    try:
        result3 = test_multiple_instances()
        results.append(("多实例行为", result3))
    except Exception as e:
        print(f"   ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("多实例行为", False))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("📋 测试结果汇总")
    print("=" * 60)
    
    for test_name, result in results:
        status = "通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    # 总体评估
    passed_count = sum(1 for _, result in results if result)
    total_count = len(results)
    
    print(f"\n✨ 总体评估:")
    print(f"   通过测试: {passed_count}/{total_count}")
    print(f"   通过率: {passed_count/total_count*100:.0f}%")
    
    if passed_count == total_count:
        print("   🎉 所有测试通过！性能监控器功能正常！")
        return True
    else:
        print("   ⚠️  部分测试失败，需要检查")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 测试套件失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
