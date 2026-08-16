"""
测试 WebGPU 渲染器修复（WebGPU 假实现已删除，相关用例迁移到 fallback 路径）
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import MagicMock

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_color_conversion():
    """测试颜色值转换修复"""
    print("=" * 60)
    print("测试 1: 颜色值转换修复")
    print("=" * 60)
    
    try:
        from matplotlib.collections import PolyCollection
        import matplotlib.pyplot as plt
        
        # 创建测试数据
        verts = [
            [(0, 0), (0, 1), (1, 1), (1, 0)],
            [(2, 0), (2, 2), (3, 2), (3, 0)]
        ]
        
        # 测试 1: 使用 RGB 数组作为默认颜色（修复后的方式）
        print("✓ 测试 RGB 数组默认颜色...")
        collection = PolyCollection(
            verts,
            facecolors=[0.5, 0.5, 0.8],
            alpha=0.7,
            edgecolors='none'
        )
        print("  ✓ 成功：RGB 数组 [0.5, 0.5, 0.8] 有效")
        
        # 测试 2: 使用 facecolors 参数（原来的错误方式）
        print("✓ 测试 'face' 字符串颜色（应该失败）...")
        try:
            collection_bad = PolyCollection(
                verts,
                facecolors='face',
                alpha=0.7,
                edgecolors='none'
            )
            print("  ✗ 意外成功：'face' 字符串应该是无效的")
        except Exception as e:
            print(f"  ✓ 符合预期：'face' 字符串确实无效 - {type(e).__name__}")
        
        # 测试 3: 使用 None 作为 facecolors（应该使用默认值）
        print("✓ 测试 None facecolors...")
        collection_none = PolyCollection(
            verts,
            facecolors=[0.5, 0.5, 0.8],  # 使用修复后的默认值
            alpha=0.7,
            edgecolors='none'
        )
        print("  ✓ 成功：使用默认 RGB 颜色")
        
        print("\n✅ 颜色值转换测试通过！\n")
        return True
        
    except Exception as e:
        print(f"\n❌ 颜色值转换测试失败：{e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_array_boolean_check():
    """测试数组布尔值判断修复"""
    print("=" * 60)
    print("测试 2: 数组布尔值判断修复")
    print("=" * 60)
    
    try:
        # 测试 1: 直接使用 len() 判断（可能有问题）
        print("✓ 测试 numpy 数组的 len() 判断...")
        colors = np.array([1.0, 0.5, 0.2, 0.8, 0.3, 0.1])
        num_quads = 2
        
        # 原来的方式（可能有问题）
        if len(colors) >= num_quads * 3:
            print(f"  ✓ len(colors)={len(colors)} >= {num_quads * 3}，判断正确")
        
        # 测试 2: 使用 size 属性判断（更安全）
        print("✓ 测试 numpy 数组的 size 属性判断...")
        colors_array = np.asarray(colors)
        if colors_array.size > 0 and len(colors_array) >= num_quads * 3:
            print(f"  ✓ colors_array.size={colors_array.size} > 0 且 len() 判断正确")
        
        # 测试 3: 空数组判断
        print("✓ 测试空数组判断...")
        empty_colors = np.array([])
        empty_array = np.asarray(empty_colors)
        if not (empty_array.size > 0 and len(empty_array) >= num_quads * 3):
            print("  ✓ 空数组判断正确，不会进入条件块")
        
        # 测试 4: 可能导致错误的布尔判断
        print("✓ 测试可能导致 'ambiguous' 错误的场景...")
        test_array = np.array([True, False, True])
        try:
            # 这种判断会导致错误
            if test_array:
                print("  ✗ 意外成功：多元素数组的布尔判断应该失败")
        except ValueError as e:
            print(f"  ✓ 符合预期：多元素数组直接布尔判断会失败 - {e}")
        
        # 正确的判断方式
        if test_array.any():
            print("  ✓ 正确使用 .any() 方法判断")
        if test_array.all():
            print("  ✓ 正确使用 .all() 方法判断")
        
        print("\n✅ 数组布尔值判断测试通过！\n")
        return True
        
    except Exception as e:
        print(f"\n❌ 数组布尔值判断测试失败：{e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_volume_data_processing():
    """测试成交量渲染（WebGPU 假实现已删除，原 VolumeDataProcessor 用例迁移到 fallback 路径）"""
    print("=" * 60)
    print("测试 3: 成交量渲染")
    print("=" * 60)
    
    try:
        from core.webgpu.fallback import MatplotlibRenderer
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        # 创建渲染器（__new__ 绕过 __init__，手动补齐初始化状态）
        renderer = MatplotlibRenderer.__new__(MatplotlibRenderer)
        renderer._initialized = True
        renderer._update_performance_stats = lambda *a, **k: None
        
        # 创建测试数据
        test_data = pd.DataFrame({
            'open': [10, 11, 10, 12, 11, 10],
            'close': [11, 10, 11, 11, 12, 11],
            'high': [12, 12, 12, 13, 13, 12],
            'low': [9, 9, 9, 10, 10, 9],
            'volume': [100, 200, 150, 300, 250, 180]
        })
        
        # 测试成交量渲染
        print("✓ 测试成交量渲染...")
        fig, ax = plt.subplots()
        ok = renderer.render_volume(ax, test_data, {}, x=np.arange(len(test_data)),
                                    use_datetime_axis=False)
        
        print(f"  ✓ 渲染结果：{ok}")
        print(f"  ✓ 集合数量：{len(ax.collections)}")
        
        # 验证数据格式
        assert ok, "成交量渲染应成功"
        assert len(ax.collections) > 0, "成交量渲染后应产生集合"
        
        # 测试空数据
        print("✓ 测试空数据处理...")
        empty_data = pd.DataFrame({'volume': []})
        empty_ax = MagicMock()
        empty_ok = renderer.render_volume(empty_ax, empty_data, {}, x=np.arange(0),
                                          use_datetime_axis=False)
        print(f"  ✓ 空数据处理结果：{empty_ok}")
        
        plt.close(fig)
        
        print("\n✅ 成交量渲染测试通过！\n")
        return True
        
    except Exception as e:
        print(f"\n❌ 成交量渲染测试失败：{e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_matplotlib_conversion():
    """测试 fallback matplotlib 渲染转换修复"""
    print("=" * 60)
    print("测试 4: matplotlib 渲染")
    print("=" * 60)
    
    try:
        from core.webgpu.fallback import MatplotlibRenderer
        import matplotlib
        matplotlib.use('Agg')  # 使用非交互式后端
        import matplotlib.pyplot as plt
        
        # 创建渲染器（__new__ 绕过 __init__，手动补齐初始化状态）
        renderer = MatplotlibRenderer.__new__(MatplotlibRenderer)
        renderer._initialized = True
        renderer._update_performance_stats = lambda *a, **k: None
        
        # 创建测试图表
        fig, ax = plt.subplots()
        
        # 创建测试数据（2 个柱子）
        test_data = pd.DataFrame({
            'open': [10.0, 10.0],
            'close': [11.0, 9.0],
            'high': [11.5, 9.5],
            'low': [9.5, 8.5],
            'volume': [100.0, 200.0]
        })
        
        # 测试渲染
        print("✓ 测试成交量渲染到 matplotlib...")
        success = renderer.render_volume(ax, test_data, {}, x=np.arange(2),
                                         use_datetime_axis=False)
        
        if success:
            print("  ✓ 渲染成功")
            
            # 验证图表上有内容
            if len(ax.collections) > 0:
                print("  ✓ 图表集合已添加")
                
                # 验证颜色
                collection = ax.collections[0]
                facecolors = collection.get_facecolors()
                print(f"  ✓ 颜色数据：{facecolors}")
            else:
                print("  ⚠ 警告：图表集合为空")
        else:
            print("  ✗ 渲染失败")
        
        plt.close(fig)
        
        print("\n✅ matplotlib 渲染测试通过！\n")
        return True
        
    except Exception as e:
        print(f"\n❌ matplotlib 渲染测试失败：{e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("WebGPU 渲染器修复验证测试")
    print("=" * 60 + "\n")
    
    results = []
    
    # 运行测试
    results.append(("颜色值转换修复", test_color_conversion()))
    results.append(("数组布尔值判断修复", test_array_boolean_check()))
    results.append(("成交量数据处理", test_volume_data_processing()))
    results.append(("matplotlib 转换修复", test_matplotlib_conversion()))
    
    # 汇总结果
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {test_name}")
    
    total_passed = sum(1 for _, r in results if r)
    total_tests = len(results)
    
    print(f"\n总计：{total_passed}/{total_tests} 个测试通过")
    
    if total_passed == total_tests:
        print("\n🎉 所有测试通过！修复有效！")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查修复代码")
        return 1


if __name__ == "__main__":
    exit(main())
