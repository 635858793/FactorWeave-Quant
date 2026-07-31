"""R218 GUI L513 调用契约验证 (R+1 round 子智能体验证)"""
from core.plugin_manager import PluginManager
import tempfile
from pathlib import Path

# 模拟 GUI L513 调用模式 (enhanced_plugin_market_dialog.py:513-516)
print("=" * 60)
print("GUI L513 调用契约验证")
print("=" * 60)

# Test 1: 异常路径 (插件不存在)
print("\n[Test 1] 异常路径 - 插件不存在 (生产环境 AttributeError 必触发场景)")
with tempfile.TemporaryDirectory() as tmp:
    plugin_dir = Path(tmp)
    pm = PluginManager(plugin_dir=plugin_dir, main_window=None)
    try:
        result = pm._resolve_plugin_path("nonexistent_plugin")
        print(f"  L513 返回: {result}")
    except AttributeError as e:
        print(f"  [P0 失败] L513 仍抛 AttributeError: {e}")
    except FileNotFoundError as e:
        print(f"  [R218 修复成功] L513 抛 FileNotFoundError")
        print(f"  GUI 端 L526-528 try/except 会捕获并显示给用户")
        print(f"  错误信息: {str(e)[:150]}")

# Test 2: 正常路径 (主目录命中)
print("\n[Test 2] 正常路径 - 主目录命中")
with tempfile.TemporaryDirectory() as tmp:
    plugin_dir = Path(tmp)
    target = plugin_dir / "my_plugin"
    target.mkdir()
    (target / "plugin.json").write_text("{}")
    pm = PluginManager(plugin_dir=plugin_dir, main_window=None)
    result = pm._resolve_plugin_path("my_plugin")
    print(f"  返回类型: {type(result).__name__}")
    print(f"  返回路径: {result}")
    print(f"  路径存在: {result.exists()}")
    print(f"  路径是目录: {result.is_dir()}")
    print(f"  GUI L516 可直接传入: load_plugin('my_plugin', {result})")

# Test 3: 父目录 fallback
print("\n[Test 3] 父目录 fallback (路径 2)")
with tempfile.TemporaryDirectory() as tmp:
    subdir_plugins = Path(tmp) / "subdir_plugins"
    subdir_plugins.mkdir()
    fallback_dir = Path(tmp) / "fallback_plugin"
    fallback_dir.mkdir()
    (fallback_dir / "plugin.json").write_text("{}")
    pm = PluginManager(plugin_dir=subdir_plugins, main_window=None)
    result = pm._resolve_plugin_path("fallback_plugin")
    print(f"  返回路径: {result}")
    print(f"  路径 2 (父目录) 命中: {result.parent == Path(tmp)}")

# Test 4: 模拟 GUI install_plugin 完整降级路径
print("\n[Test 4] 模拟 GUI install_plugin 完整降级路径")
with tempfile.TemporaryDirectory() as tmp:
    plugin_dir = Path(tmp)
    target = plugin_dir / "test_install_plugin"
    target.mkdir()
    (target / "plugin.json").write_text("{}")
    pm = PluginManager(plugin_dir=plugin_dir, main_window=None)

    # 模拟 L513
    plugin_path = pm._resolve_plugin_path("test_install_plugin")
    print(f"  L513 解析成功: {plugin_path}")

    # 模拟 L514: if plugin_path is None: raise RuntimeError
    if plugin_path is None:
        print("  L514 触发 RuntimeError (不应发生)")
    else:
        print(f"  L514 检查通过 (plugin_path 非 None)")

    # 模拟 L516: self.plugin_manager.load_plugin(plugin_name, plugin_path)
    print(f"  L516 调用 load_plugin('test_install_plugin', {plugin_path})")
    print(f"  load_plugin 签名 plugin_path: Path 兼容: {isinstance(plugin_path, Path)}")

print("\n" + "=" * 60)
print("GUI L513 调用契约验证完成")
print("=" * 60)
