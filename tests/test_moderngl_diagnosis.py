"""
ModernGL 环境诊断脚本
检查 Windows 11 conda 环境下 ModernGL 不可用的原因
"""
import sys
import platform

print("=" * 70)
print("ModernGL 环境诊断工具 - Windows 11")
print("=" * 70)
print(f"\n系统信息:")
print(f"  操作系统：{platform.system()} {platform.release()}")
print(f"  Python 版本：{sys.version}")
print(f"  Python 路径：{sys.executable}")

# 1. 检查 ModernGL 安装状态
print("\n" + "=" * 70)
print("1. ModernGL 安装状态检查")
print("=" * 70)

try:
    import moderngl
    print(f"  ✓ ModernGL 已安装")
    print(f"    版本：{moderngl.__version__}")
    
    # 检查 ModernGL 上下文创建
    print("\n  尝试创建 standalone 上下文...")
    try:
        ctx = moderngl.create_context(standalone=True)
        print(f"  ✓ Standalone 上下文创建成功")
        print(f"    OpenGL 版本：{ctx.version_code}")
        try:
            print(f"    OpenGL 渲染器：{ctx.info.get('Renderer', '未知')}")
            print(f"    OpenGL 厂商：{ctx.info.get('Vendor', '未知')}")
        except:
            print(f"    无法获取详细 GPU 信息（可能是无头模式）")
        ctx.release()
    except Exception as e:
        print(f"  ✗ Standalone 上下文创建失败")
        print(f"    错误：{e}")
        import traceback
        traceback.print_exc()
        
except ImportError as e:
    print(f"  ✗ ModernGL 未安装")
    print(f"    错误：{e}")
    print(f"\n  建议安装命令:")
    print(f"    pip install moderngl")
    print(f"    或 conda install -c conda-forge moderngl")

# 2. 检查 OpenGL 支持
print("\n" + "=" * 70)
print("2. OpenGL 支持检查")
print("=" * 70)

try:
    import OpenGL
    import OpenGL.GL as gl
    print(f"  ✓ PyOpenGL 已安装")
    print(f"    版本：{getattr(OpenGL, '__version__', 'unknown')}")
except ImportError:
    print(f"  ✗ PyOpenGL 未安装")
    print(f"    ModernGL 需要 OpenGL 驱动支持")

# 3. 检查显卡信息（使用 ctypes 调用 Windows API）
print("\n" + "=" * 70)
print("3. 显卡信息检查")
print("=" * 70)

try:
    import ctypes
    from ctypes import wintypes
    
    # 简单的 DXGI 调用来获取显卡信息
    print(f"  尝试获取显卡信息...")
    
    # 使用 wmic 命令获取显卡信息（Windows 特有）
    import subprocess
    result = subprocess.run(
        ['wmic', 'path', 'win32_VideoController', 'get', 'Name,DriverVersion,VideoProcessor'],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        print(f"  显卡信息:")
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                print(f"    {line}")
    else:
        print(f"  无法获取显卡信息")
        
except Exception as e:
    print(f"  显卡信息检查失败：{e}")

# 4. 检查 conda 环境
print("\n" + "=" * 70)
print("4. Conda 环境检查")
print("=" * 70)

import os
conda_prefix = os.environ.get('CONDA_PREFIX', '未知')
conda_name = os.environ.get('CONDA_DEFAULT_ENV', '未知')

print(f"  Conda 环境：{conda_name}")
print(f"  Conda 路径：{conda_prefix}")

# 检查 conda 安装的 moderngl
try:
    import importlib.metadata
    try:
        moderngl_dist = importlib.metadata.distribution('moderngl')
        print(f"  ModernGL 安装位置：{moderngl_dist.locate_file('moderngl')}")
    except:
        pass
except:
    pass

# 5. 列出相关包版本
print("\n" + "=" * 70)
print("5. 相关 Python 包版本")
print("=" * 70)

packages = ['moderngl', 'numpy', 'matplotlib', 'PIL', 'PyOpenGL']

for pkg_name in packages:
    try:
        if pkg_name == 'PyOpenGL':
            import OpenGL
            version = getattr(OpenGL, '__version__', 'unknown')
        elif pkg_name == 'PIL':
            from PIL import Image
            version = Image.__version__ if hasattr(Image, '__version__') else 'unknown'
        else:
            import importlib.metadata
            version = importlib.metadata.version(pkg_name)
        print(f"  ✓ {pkg_name}: {version}")
    except Exception as e:
        print(f"  ✗ {pkg_name}: 未安装或版本未知 ({e})")

# 6. 检查 DirectX 和 GPU 支持（Windows 特有）
print("\n" + "=" * 70)
print("6. DirectX 和 GPU 支持检查")
print("=" * 70)

try:
    # 使用 dxdiag 命令（Windows 特有）
    import subprocess
    result = subprocess.run(
        ['dxdiag', '/t', 'NUL'],
        capture_output=True,
        text=True,
        timeout=10,
        shell=True
    )
    print(f"  DirectX 诊断工具可用")
    print(f"  建议运行 dxdiag 查看详细显卡信息")
except:
    print(f"  无法运行 DirectX 诊断")

# 7. 总结和建议
print("\n" + "=" * 70)
print("7. 诊断总结和建议")
print("=" * 70)

issues = []

try:
    import moderngl
    print("✓ ModernGL 已正确安装")
except:
    issues.append("ModernGL 未安装")
    print("✗ ModernGL 未安装")

try:
    ctx = moderngl.create_context(standalone=True)
    ctx.release()
    print("✓ ModernGL 上下文可以正常创建")
except Exception as e:
    issues.append(f"ModernGL 上下文创建失败：{e}")
    print(f"✗ ModernGL 上下文创建失败")

if issues:
    print(f"\n⚠️ 发现 {len(issues)} 个问题:")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
    
    print("\n💡 解决建议:")
    if "ModernGL 未安装" in str(issues):
        print("  1. 安装 ModernGL:")
        print("     pip install moderngl")
        print("     或 conda install -c conda-forge moderngl")
    
    if "上下文创建失败" in str(issues):
        print("  2. 更新显卡驱动:")
        print("     - NVIDIA: https://www.nvidia.com/Download/index.aspx")
        print("     - AMD: https://www.amd.com/en/support")
        print("     - Intel: https://downloadcenter.intel.com/")
        print("  3. 确保 OpenGL 3.3+ 支持")
        print("  4. 检查是否在无头模式运行")
else:
    print("✓ 所有检查通过，ModernGL 应该可以正常工作")
    print("\n如果仍然遇到问题，可能是:")
    print("  - Qt 线程问题（避免在非 GUI 线程创建上下文）")
    print("  - 多 GPU 切换问题（确保使用独立显卡）")
    print("  - 防火墙/杀毒软件阻止")

print("\n" + "=" * 70)
