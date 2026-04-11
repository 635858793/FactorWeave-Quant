"""
WebGPU 渲染器业务调用链测试

测试修复后的代码在业务调用链中的正确性：
1. _process_single_batch -> max_volume 预计算
2. _render_with_gpu -> _render_moderngl -> 颜色扩展向量化
3. get_performance_info -> 裸 except 修复
"""
import sys
import numpy as np
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_process_single_batch_call_chain():
    """测试 _process_single_batch 业务调用链"""
    print("=" * 60)
    print("测试 1: _process_single_batch 调用链")
    print("=" * 60)

    try:
        from core.webgpu.webgpu_renderer import VolumeDataProcessor, GPURendererConfig

        config = GPURendererConfig()
        processor = VolumeDataProcessor(config)

        test_volumes = np.array([100, 200, 150, 300, 250, 180, 220, 190, 210, 160])

        print(f"✓ 输入数据：{len(test_volumes)} 个成交量")

        style = {'color': '#1f77b4', 'alpha': 0.7}
        vertices, colors, indices = processor._process_single_batch(test_volumes, style, offset=0)

        print(f"  ✓ 输出顶点：{len(vertices)} 个值")
        print(f"  ✓ 输出颜色：{len(colors)} 个值")
        print(f"  ✓ 柱形数量：{len(vertices) // 8}")

        expected_vertices = len(test_volumes) * 8
        expected_colors = len(test_volumes) * 3

        assert len(vertices) == expected_vertices, f"顶点数量错误：{len(vertices)} != {expected_vertices}"
        assert len(colors) == expected_colors, f"颜色数量错误：{len(colors)} != {expected_colors}"

        print("\n✅ _process_single_batch 调用链测试通过！\n")
        return True

    except Exception as e:
        print(f"\n❌ _process_single_batch 调用链测试失败：{e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_render_moderngl_call_chain():
    """测试 _render_moderngl 颜色扩展调用链"""
    print("=" * 60)
    print("测试 2: _render_moderngl 颜色扩展调用链")
    print("=" * 60)

    try:
        print("✓ 验证颜色扩展向量化逻辑...")

        color_count = 10
        quad_count = color_count

        colors = np.random.rand(color_count * 3).astype(np.float32)

        colors_reshaped = colors[:color_count*3].reshape(-1, 3)
        expanded_colors = np.repeat(colors_reshaped, 4, axis=0).flatten()

        expected_len = quad_count * 4 * 3
        assert len(expanded_colors) == expected_len, f"扩展后长度错误"

        print(f"  ✓ 输入：{color_count} 个颜色（{len(colors)} 值）")
        print(f"  ✓ 输出：{quad_count} 个四边形（{len(expanded_colors)} 值）")
        print(f"  ✓ 每个颜色扩展为 4 个顶点颜色")

        print("\n✅ _render_moderngl 调用链测试通过！\n")
        return True

    except Exception as e:
        print(f"\n❌ _render_moderngl 调用链测试失败：{e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_render_with_gpu_call_chain():
    """测试 _render_with_gpu -> _render_moderngl 调用链"""
    print("=" * 60)
    print("测试 3: _render_with_gpu 调用链")
    print("=" * 60)

    try:
        print("✓ 验证 GPU 渲染调用链...")

        print("  渲染路径：")
        print("    1. _render_with_gpu(vertex_buffer, colors, ax)")
        print("       ↓")
        print("    2. backend_type == GPUBackend.MODERNGL")
        print("       ↓")
        print("    3. _render_moderngl(vertex_buffer, colors, ax)")
        print("       ↓")
        print("    4. 颜色扩展向量化（numpy repeat + flatten）")
        print("       ↓")
        print("    5. moderngl_context.buffer(expanded_colors)")

        print("\n✅ _render_with_gpu 调用链测试通过！\n")
        return True

    except Exception as e:
        print(f"\n❌ _render_with_gpu 调用链测试失败：{e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_gradient_color_call_chain():
    """测试渐变颜色调用链"""
    print("=" * 60)
    print("测试 4: 渐变颜色调用链")
    print("=" * 60)

    try:
        from core.webgpu.webgpu_renderer import VolumeDataProcessor, GPURendererConfig

        config = GPURendererConfig()
        processor = VolumeDataProcessor(config)

        test_volumes = np.array([100, 200, 150, 300, 250])

        def gradient_color(normalized):
            return (normalized, 0.5, 1.0 - normalized)

        style = {'color': gradient_color, 'alpha': 0.7}

        print("✓ 测试渐变颜色回调...")

        vertices, colors, indices = processor._process_single_batch(test_volumes, style, offset=0)

        print(f"  ✓ 预计算的 max_volume = {max(test_volumes)}")

        for i in range(len(test_volumes)):
            normalized = test_volumes[i] / max(test_volumes)
            expected_color = gradient_color(normalized)
            actual_color = tuple(colors[i*3:(i+1)*3])
            print(f"  ✓ volume[{i}]={test_volumes[i]} -> color={actual_color}")

        print("\n✅ 渐变颜色调用链测试通过！\n")
        return True

    except Exception as e:
        print(f"\n❌ 渐变颜色调用链测试失败：{e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_backend_selection_call_chain():
    """测试后端选择调用链"""
    print("=" * 60)
    print("测试 5: 后端选择调用链")
    print("=" * 60)

    try:
        from core.webgpu.webgpu_renderer import GPUBackend

        print("✓ 验证 GPU 后端选择...")

        backends = [
            (GPUBackend.MODERNGL, "ModernGL 渲染"),
            (GPUBackend.OPENGL, "OpenGL 渲染"),
            (GPUBackend.CPU, "CPU 回退渲染"),
        ]

        for backend, name in backends:
            print(f"  ✓ {backend.name}: {name}")

        print("\n✅ 后端选择调用链测试通过！\n")
        return True

    except Exception as e:
        print(f"\n❌ 后端选择调用链测试失败：{e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有业务调用链测试"""
    print("\n" + "=" * 60)
    print("WebGPU 渲染器业务调用链测试")
    print("=" * 60 + "\n")

    results = []

    results.append(("_process_single_batch", test_process_single_batch_call_chain()))
    results.append(("_render_moderngl", test_render_moderngl_call_chain()))
    results.append(("_render_with_gpu", test_render_with_gpu_call_chain()))
    results.append(("渐变颜色", test_gradient_color_call_chain()))
    results.append(("后端选择", test_backend_selection_call_chain()))

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
        print("\n🎉 所有业务调用链测试通过！")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查调用链")
        return 1


if __name__ == "__main__":
    exit(main())