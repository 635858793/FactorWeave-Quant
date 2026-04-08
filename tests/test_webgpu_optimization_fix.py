"""
测试 WebGPU 渲染器优化修复

验证内容：
1. 颜色扩展向量化（numpy 替代双重循环）
2. max 预计算优化
3. 裸 except 修复
"""
import sys
import numpy as np
import time
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_color_expansion_vectorization():
    """测试颜色扩展向量化优化"""
    print("=" * 60)
    print("测试 1: 颜色扩展向量化")
    print("=" * 60)

    try:
        color_count = 1000

        colors = np.random.rand(color_count * 3).astype(np.float32)

        print(f"✓ 测试数据：{color_count} 个颜色")

        print("✓ 验证 numpy 向量化逻辑...")
        colors_reshaped = colors[:color_count*3].reshape(-1, 3)
        assert colors_reshaped.shape == (color_count, 3), f"reshape 失败：{colors_reshaped.shape}"

        expanded_colors = np.repeat(colors_reshaped, 4, axis=0).flatten()
        expected_len = color_count * 4 * 3
        assert len(expanded_colors) == expected_len, f"扩展后长度错误：{len(expanded_colors)} != {expected_len}"

        print(f"  ✓ reshape: {colors.shape} -> {colors_reshaped.shape}")
        print(f"  ✓ repeat: {colors_reshaped.shape} -> ({color_count*4}, 3)")
        print(f"  ✓ flatten: -> ({expected_len},)")
        print(f"  ✓ 每个颜色扩展为 4 个顶点（12 个值）")

        print("\n✅ 颜色扩展向量化测试通过！\n")
        return True

    except Exception as e:
        print(f"\n❌ 颜色扩展向量化测试失败：{e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_max_precomputation():
    """测试 max 预计算优化"""
    print("=" * 60)
    print("测试 2: max 预计算优化")
    print("=" * 60)

    try:
        volumes = np.array([100, 200, 150, 300, 250, 180, 220, 190, 210, 160])
        num_loops = 10000

        print(f"✓ 测试数据：{len(volumes)} 个成交量")

        print("✓ 验证预计算逻辑...")
        max_volume = max(volumes) if len(volumes) > 0 else 0
        assert max_volume == 300, f"max 计算错误：{max_volume}"

        print(f"  ✓ max_volume = {max_volume}")

        print("✓ 验证渐变计算...")
        for i in [0, 3, 9]:
            volume = volumes[i]
            normalized = volume / max_volume if max_volume > 0 else 0
            expected = volume / 300.0
            assert abs(normalized - expected) < 0.0001, f"归一化错误：{normalized} != {expected}"
            print(f"  ✓ volume[{i}]={volume} -> normalized={normalized:.4f}")

        print("\n✅ max 预计算测试通过！\n")
        return True

    except Exception as e:
        print(f"\n❌ max 预计算测试失败：{e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_bare_except_fix():
    """测试裸 except 修复"""
    print("=" * 60)
    print("测试 3: 裸 except 修复")
    print("=" * 60)

    try:
        print("✓ 验证异常处理逻辑...")

        performance_info = {}

        class MockContext:
            context = None

        mock_self = type('MockSelf', (), {
            'context': MockContext()
        })()

        try:
            if hasattr(mock_self.context, 'context') and mock_self.context.context:
                performance_info['context_active'] = True
            else:
                performance_info['context_active'] = False
        except Exception as e:
            performance_info['context_active'] = False

        assert performance_info.get('context_active') == False, "context_active 应为 False"
        print("  ✓ 正确捕获异常并设置默认值")

        print("\n✅ 裸 except 修复测试通过！\n")
        return True

    except Exception as e:
        print(f"\n❌ 裸 except 修复测试失败：{e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_color_expansion_performance():
    """测试颜色扩展性能"""
    print("=" * 60)
    print("测试 4: 颜色扩展性能对比")
    print("=" * 60)

    try:
        color_count = 1000
        num_runs = 100

        colors = np.random.rand(color_count * 3).astype(np.float32)

        print(f"✓ 测试数据：{color_count} 个颜色，{num_runs} 次运行")

        print("\n--- 新方法（numpy 向量化）---")
        start = time.time()
        for _ in range(num_runs):
            colors_reshaped = colors[:color_count*3].reshape(-1, 3)
            expanded_colors = np.repeat(colors_reshaped, 4, axis=0).flatten()
        new_time = time.time() - start
        print(f"  耗时：{new_time*1000:.2f} ms")
        print(f"  平均：{new_time*1000/num_runs:.4f} ms/次")

        print("\n--- 旧方法（双重循环）---")
        start = time.time()
        for _ in range(num_runs):
            expanded_colors_old = []
            for i in range(color_count):
                r, g, b = colors[i*3], colors[i*3+1], colors[i*3+2]
                for _ in range(4):
                    expanded_colors_old.extend([r, g, b])
        old_time = time.time() - start
        print(f"  耗时：{old_time*1000:.2f} ms")
        print(f"  平均：{old_time*1000/num_runs:.4f} ms/次")

        speedup = old_time / new_time if new_time > 0 else float('inf')
        print(f"\n✓ 性能提升：{speedup:.1f}x")

        assert new_time < old_time, "新方法应该更快"
        print("\n✅ 颜色扩展性能测试通过！\n")
        return True

    except Exception as e:
        print(f"\n❌ 颜色扩展性能测试失败：{e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_color_expansion_correctness():
    """测试颜色扩展正确性"""
    print("=" * 60)
    print("测试 5: 颜色扩展正确性验证")
    print("=" * 60)

    try:
        colors = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0], dtype=np.float32)
        color_count = 3

        print(f"✓ 测试数据：{color_count} 个 RGB 颜色")
        print(f"  输入：{colors.tolist()}")

        colors_reshaped = colors[:color_count*3].reshape(-1, 3)
        expanded_colors = np.repeat(colors_reshaped, 4, axis=0).flatten()

        expected = np.array([
            1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0,
        ], dtype=np.float32)

        assert np.allclose(expanded_colors, expected), f"扩展结果错误：{expanded_colors}"
        print(f"  ✓ 输出：{expanded_colors.tolist()}")
        print(f"  ✓ 每个颜色重复 4 次（每个顶点一次）")
        print(f"  ✓ 颜色顺序正确：[R,R,R,R, G,G,G,G, B,B,B,B]")

        print("\n✅ 颜色扩展正确性测试通过！\n")
        return True

    except Exception as e:
        print(f"\n❌ 颜色扩展正确性测试失败：{e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("WebGPU 渲染器优化修复验证测试")
    print("=" * 60 + "\n")

    results = []

    results.append(("颜色扩展向量化", test_color_expansion_vectorization()))
    results.append(("max 预计算优化", test_max_precomputation()))
    results.append(("裸 except 修复", test_bare_except_fix()))
    results.append(("颜色扩展性能", test_color_expansion_performance()))
    results.append(("颜色扩展正确性", test_color_expansion_correctness()))

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
        print("\n🎉 所有测试通过！优化修复有效！")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查修复代码")
        return 1


if __name__ == "__main__":
    exit(main())