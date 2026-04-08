"""
ModernGL 线程安全性测试
测试在不同线程中创建 ModernGL 上下文的行为
"""
import threading
import moderngl
import time

print("=" * 70)
print("ModernGL 线程安全性测试")
print("=" * 70)

# 测试 1：主线程创建上下文
print("\n[测试 1] 主线程创建 ModernGL 上下文")
try:
    ctx_main = moderngl.create_context(standalone=True)
    print(f"  ✓ 主线程上下文创建成功")
    print(f"    OpenGL 版本：{ctx_main.version_code}")
    ctx_main.release()
    print(f"  ✓ 上下文已释放")
except Exception as e:
    print(f"  ✗ 主线程上下文创建失败：{e}")

# 测试 2：子线程创建上下文
print("\n[测试 2] 子线程创建 ModernGL 上下文")

def create_context_in_thread(result_dict, thread_name):
    """在线程中创建上下文"""
    try:
        print(f"  [{thread_name}] 开始创建上下文...")
        ctx = moderngl.create_context(standalone=True)
        print(f"  [{thread_name}] ✓ 上下文创建成功")
        print(f"  [{thread_name}]   OpenGL 版本：{ctx.version_code}")
        
        # 尝试创建 framebuffer（模拟实际使用场景）
        color_tex = ctx.texture((800, 600), 4)
        depth_tex = ctx.depth_texture((800, 600))
        fbo = ctx.framebuffer(
            color_attachments=[color_tex],
            depth_attachment=depth_tex
        )
        print(f"  [{thread_name}] ✓ Framebuffer 创建成功")
        
        # 清理
        fbo.release()
        color_tex.release()
        depth_tex.release()
        ctx.release()
        print(f"  [{thread_name}] ✓ 上下文已释放")
        
        result_dict[thread_name] = "success"
    except Exception as e:
        print(f"  [{thread_name}] ✗ 创建失败：{e}")
        import traceback
        traceback.print_exc()
        result_dict[thread_name] = f"failed: {e}"

# 测试 2a：单个子线程
print("\n  场景 A: 单个子线程")
result = {}
thread = threading.Thread(target=create_context_in_thread, args=(result, "Thread-1"))
thread.start()
thread.join()
print(f"  结果：{result.get('Thread-1', 'unknown')}")

# 测试 2b：多个子线程（测试并发）
print("\n  场景 B: 多个子线程并发")
results = {}
threads = []
for i in range(3):
    t = threading.Thread(target=create_context_in_thread, args=(results, f"Thread-{i+1}"))
    threads.append(t)

# 同时启动
for t in threads:
    t.start()
    time.sleep(0.1)  # 稍微错开避免输出混乱

# 等待完成
for t in threads:
    t.join()

print(f"\n  结果汇总:")
for thread_name, result in results.items():
    status = "✓" if result == "success" else "✗"
    print(f"    {status} {thread_name}: {result}")

# 测试 3：重复创建上下文
print("\n[测试 3] 同一线程重复创建上下文")
try:
    print("  第一次创建...")
    ctx1 = moderngl.create_context(standalone=True)
    print(f"  ✓ 第一次创建成功")
    
    print("  第二次创建（不释放第一个）...")
    ctx2 = moderngl.create_context(standalone=True)
    print(f"  ✓ 第二次创建成功")
    
    ctx1.release()
    ctx2.release()
    print(f"  ✓ 所有上下文已释放")
except Exception as e:
    print(f"  ✗ 重复创建失败：{e}")

# 测试 4：释放后重新创建
print("\n[测试 4] 释放后重新创建上下文")
try:
    print("  第一次创建...")
    ctx1 = moderngl.create_context(standalone=True)
    print(f"  ✓ 第一次创建成功")
    ctx1.release()
    print(f"  ✓ 第一次已释放")
    
    print("  重新创建...")
    ctx2 = moderngl.create_context(standalone=True)
    print(f"  ✓ 重新创建成功")
    ctx2.release()
    print(f"  ✓ 第二次已释放")
except Exception as e:
    print(f"  ✗ 重新创建失败：{e}")

print("\n" + "=" * 70)
print("测试总结")
print("=" * 70)
print("""
ModernGL 线程安全性说明：

1. ModernGL 上下文不是线程安全的
   - 每个线程需要自己的上下文
   - 不能跨线程共享上下文对象

2. 常见问题：
   - 在 Qt 非 GUI 线程创建上下文可能导致警告
   - 多个线程同时创建上下文可能失败
   - 上下文释放后不能再次使用

3. 建议：
   - 在主线程或专用渲染线程创建上下文
   - 避免在 worker 线程中频繁创建/销毁上下文
   - 使用上下文池或单例模式管理上下文

4. 如果遇到问题：
   - 检查是否在正确的线程创建上下文
   - 确保上下文没有被重复使用
   - 考虑使用 CPU 回退方案
""")
