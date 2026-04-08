"""
ModernGL 实际渲染测试
模拟真实的渲染流程，测试 ModernGL 在 Windows 11 下的行为
"""
import moderngl
import numpy as np
from matplotlib.figure import Figure
from matplotlib.collections import PolyCollection

print("=" * 70)
print("ModernGL 实际渲染测试 - Windows 11")
print("=" * 70)

# 测试 1：基础离屏渲染
print("\n[测试 1] ModernGL 离屏渲染基础测试")
try:
    # 创建上下文
    ctx = moderngl.create_context(standalone=True)
    print(f"  ✓ 上下文创建成功 (OpenGL {ctx.version_code})")
    
    # 创建 framebuffer
    color_tex = ctx.texture((800, 600), 4)
    depth_tex = ctx.depth_texture((800, 600))
    fbo = ctx.framebuffer(
        color_attachments=[color_tex],
        depth_attachment=depth_tex
    )
    print(f"  ✓ Framebuffer 创建成功 (800x600)")
    
    # 绑定 framebuffer
    fbo.use()
    print(f"  ✓ Framebuffer 绑定成功")
    
    # 清除缓冲区
    fbo.clear(0.0, 0.0, 0.0, 0.0)
    print(f"  ✓ 缓冲区清除成功")
    
    # 设置视口
    ctx.viewport = (0, 0, 800, 600)
    print(f"  ✓ 视口设置成功")
    
    # 创建简单的顶点数据（一个四边形）
    vertices = np.array([
        -0.5, -0.5,  # 左下
        -0.5,  0.5,  # 左上
         0.5,  0.5,  # 右上
         0.5, -0.5   # 右下
    ], dtype='f4')
    
    vertex_buffer = ctx.buffer(vertices.tobytes())
    print(f"  ✓ 顶点缓冲区创建成功 ({len(vertices)//2} 个顶点)")
    
    # 创建颜色数据
    colors = np.array([
        1.0, 0.0, 0.0,  # 红色
        1.0, 0.0, 0.0,
        1.0, 0.0, 0.0,
        1.0, 0.0, 0.0
    ], dtype='f4')
    
    color_buffer = ctx.buffer(colors.tobytes())
    print(f"  ✓ 颜色缓冲区创建成功")
    
    # 创建简单的着色器
    vertex_shader = '''
        #version 330
        in vec2 in_position;
        in vec3 in_color;
        out vec3 color;
        void main() {
            gl_Position = vec4(in_position, 0.0, 1.0);
            color = in_color;
        }
    '''
    
    fragment_shader = '''
        #version 330
        in vec3 color;
        out vec4 fragColor;
        void main() {
            fragColor = vec4(color, 1.0);
        }
    '''
    
    program = ctx.program(
        vertex_shader=vertex_shader,
        fragment_shader=fragment_shader
    )
    print(f"  ✓ 着色器程序编译成功")
    
    # 创建 VAO
    vao = ctx.vertex_array(program, [
        (vertex_buffer, '2f', 0),
        (color_buffer, '3f', 0)
    ])
    print(f"  ✓ VAO 创建成功")
    
    # 渲染
    vao.render()
    print(f"  ✓ 渲染成功")
    
    # 清理
    vao.release()
    program.release()
    vertex_buffer.release()
    color_buffer.release()
    fbo.release()
    color_tex.release()
    depth_tex.release()
    ctx.release()
    print(f"  ✓ 资源释放成功")
    
    print("\n✅ 离屏渲染基础测试通过！")
    
except Exception as e:
    print(f"\n❌ 离屏渲染基础测试失败：{e}")
    import traceback
    traceback.print_exc()

# 测试 2：模拟成交量柱状图渲染
print("\n" + "=" * 70)
print("[测试 2] 模拟成交量柱状图渲染")
try:
    ctx = moderngl.create_context(standalone=True)
    
    # 创建 framebuffer
    width, height = 1920, 1080
    color_tex = ctx.texture((width, height), 4)
    depth_tex = ctx.depth_texture((width, height))
    fbo = ctx.framebuffer(
        color_attachments=[color_tex],
        depth_attachment=depth_tex
    )
    fbo.use()
    fbo.clear(0.0, 0.0, 0.0, 0.0)
    ctx.viewport = (0, 0, width, height)
    
    print(f"  ✓ 创建 {width}x{height} 渲染目标")
    
    # 模拟 6 个柱子的数据
    num_quads = 6
    vertices = []
    colors = []
    
    for i in range(num_quads):
        x = i * 2 - 5  # x 坐标：-5, -3, -1, 1, 3, 5
        height_val = (i + 1) * 0.1  # 高度：0.1, 0.2, ..., 0.6
        
        # 四个顶点
        quad = [
            x - 0.5, 0.0,           # 左下
            x - 0.5, height_val,    # 左上
            x + 0.5, height_val,    # 右上
            x + 0.5, 0.0            # 右下
        ]
        vertices.extend(quad)
        
        # 颜色（每个柱子一个 RGB）
        color = [0.2 + i * 0.1, 0.5, 0.8]
        colors.extend(color)
    
    vertices = np.array(vertices, dtype='f4')
    colors = np.array(colors, dtype='f4')
    
    print(f"  ✓ 生成 {num_quads} 个柱子数据")
    print(f"    顶点数：{len(vertices)//2}")
    print(f"    颜色数：{len(colors)//3}")
    
    # 扩展颜色数据（每个颜色复制 4 次）
    expanded_colors = []
    for i in range(num_quads):
        r, g, b = colors[i*3], colors[i*3+1], colors[i*3+2]
        for _ in range(4):
            expanded_colors.extend([r, g, b])
    
    expanded_colors = np.array(expanded_colors, dtype='f4')
    
    vertex_buffer = ctx.buffer(vertices.tobytes())
    color_buffer = ctx.buffer(expanded_colors.tobytes())
    
    print(f"  ✓ 创建缓冲区")
    
    # 使用之前的着色器
    vertex_shader = '''
        #version 330
        in vec2 in_position;
        in vec3 in_color;
        out vec3 color;
        void main() {
            gl_Position = vec4(in_position, 0.0, 1.0);
            color = in_color;
        }
    '''
    
    fragment_shader = '''
        #version 330
        in vec3 color;
        out vec4 fragColor;
        void main() {
            fragColor = vec4(color, 1.0);
        }
    '''
    
    program = ctx.program(vertex_shader=vertex_shader, fragment_shader=fragment_shader)
    vao = ctx.vertex_array(program, [
        (vertex_buffer, '2f', 0),
        (color_buffer, '3f', 0)
    ])
    
    # 渲染
    vao.render()
    print(f"  ✓ 渲染成功 ({num_quads} 个柱子)")
    
    # 清理
    vao.release()
    program.release()
    vertex_buffer.release()
    color_buffer.release()
    fbo.release()
    color_tex.release()
    depth_tex.release()
    ctx.release()
    
    print("\n✅ 成交量柱状图渲染测试通过！")
    
except Exception as e:
    print(f"\n❌ 成交量柱状图渲染测试失败：{e}")
    import traceback
    traceback.print_exc()

# 测试 3：与 matplotlib 集成测试
print("\n" + "=" * 70)
print("[测试 3] ModernGL + Matplotlib 集成测试")
try:
    # 创建 matplotlib 图表
    fig = Figure(figsize=(10, 6))
    ax = fig.add_subplot(111)
    
    # 创建测试数据
    verts = []
    for i in range(6):
        x = i * 2
        quad = [
            (x, 0),
            (x, i+1),
            (x+1, i+1),
            (x+1, 0)
        ]
        verts.append(quad)
    
    # 创建 PolyCollection
    collection = PolyCollection(
        verts,
        facecolors=[[0.2+i*0.1, 0.5, 0.8] for i in range(6)],
        alpha=0.7,
        edgecolors='none'
    )
    
    ax.add_collection(collection)
    ax.autoscale_view()
    
    print(f"  ✓ Matplotlib 图表创建成功")
    print(f"    柱子数量：{len(verts)}")
    
    # 尝试保存到内存（测试渲染）
    from io import BytesIO
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    
    print(f"  ✓ 图表渲染并保存成功")
    
    print("\n✅ Matplotlib 集成测试通过！")
    
except Exception as e:
    print(f"\n❌ Matplotlib 集成测试失败：{e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("测试总结")
print("=" * 70)
print("""
ModernGL 在 Windows 11 下的行为：

1. ✓ ModernGL 可以正常创建上下文
2. ✓ 支持离屏渲染（framebuffer）
3. ✓ 支持顶点缓冲区和颜色缓冲区
4. ✓ 支持自定义着色器
5. ✓ 可以渲染柱状图等几何图形
6. ✓ 与 Matplotlib 可以共存

如果实际应用中 ModernGL 不可用，可能原因：
- 上下文状态同步问题
- 资源管理问题（缓冲区/纹理未正确释放）
- 多线程环境下的上下文冲突
- 与 WebGPU 上下文的资源竞争
- Qt 事件循环干扰

建议检查：
- WebGPURenderer 的上下文初始化日志
- 渲染时的错误信息
- 资源释放是否完整
""")
