# -*- coding: utf-8 -*-
"""R238-NEW-P0-CWE-22 plugin_market 路径逃逸拦截 TDD 测试

验证: install_plugin 对 metadata.name 做净化 (basename + 拒绝分隔符 + realpath 校验)

强约束: CWE-22 zip-slip + R235 §14.1 凭据不入库
TDD: tests/test_r238_c_plugin_market_cwe22_path_traversal.py
"""

import os
import shutil
import sys
import tempfile
import unittest
import zipfile


class TestPluginMarketCWE22(unittest.TestCase):
    """R238-NEW-P0-CWE-22: plugin_market.install_plugin 路径逃逸拦截"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="r238_cwe22_")
        self.plugins_dir = os.path.join(self.tmpdir, "plugins")
        os.makedirs(self.plugins_dir, exist_ok=True)
        # 引入被测模块
        try:
            from plugins.plugin_market import PluginInstaller
            self.PluginInstaller = PluginInstaller
        except ImportError as e:  # pragma: no cover
            self.PluginInstaller = None
            self.import_error = str(e)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_zip(self, metadata_name, extra_content=None):
        """构造含恶意 metadata.name 的 zip (完整元数据字段, R231 §13.3 测试 bug 鉴别)"""
        zip_path = os.path.join(self.tmpdir, "evil_plugin.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            metadata = {
                'name': metadata_name,
                'version': '1.0.0',
                'description': 'test',
                'author': 'test',
                'email': 'test@example.com',
                'website': '',
                'license': 'MIT',
                'plugin_type': 'strategy',
                'category': 'test',
                'dependencies': [],
                'min_framework_version': '1.0.0',
                'max_framework_version': '99.0.0',
                'tags': [],
            }
            import json
            zf.writestr('plugin.json', json.dumps(metadata))
            if extra_content:
                for name, content in extra_content.items():
                    zf.writestr(name, content)
        return zip_path

    def test_T01_traversal_name_sanitized(self):
        """T01: metadata.name='../../evil' 被 basename 净化, 不逃逸 plugins_dir"""
        if self.PluginInstaller is None:
            self.skipTest(f"plugin_market 导入失败: {getattr(self, 'import_error', '')}")
        installer = self.PluginInstaller(self.plugins_dir)
        sanitized = installer._sanitize_plugin_name("../../evil")
        self.assertEqual("evil", sanitized, "basename 应剥离路径段")
        plugin_dir = os.path.realpath(os.path.join(self.plugins_dir, sanitized))
        self.assertTrue(plugin_dir.startswith(os.path.realpath(self.plugins_dir) + os.sep),
                        "净化后路径必须仍在 plugins_dir 内 (CWE-22)")

    def test_T02_abs_path_sanitized(self):
        """T02: metadata.name='/etc/evil' 被 basename 净化"""
        if self.PluginInstaller is None:
            self.skipTest(f"plugin_market 导入失败: {getattr(self, 'import_error', '')}")
        installer = self.PluginInstaller(self.plugins_dir)
        sanitized = installer._sanitize_plugin_name("/etc/evil")
        self.assertEqual("evil", sanitized, "绝对路径应被 basename 剥离")

    def test_T03_dotdot_only_rejected(self):
        """T03: metadata.name='..' 必须被拦截 (异常)"""
        if self.PluginInstaller is None:
            self.skipTest(f"plugin_market 导入失败: {getattr(self, 'import_error', '')}")
        installer = self.PluginInstaller(self.plugins_dir)
        with self.assertRaises(Exception) as ctx:
            installer._sanitize_plugin_name("..")
        self.assertIn("非法插件名称", str(ctx.exception), "'..' 应被拦截")

    def test_T04_dot_only_rejected(self):
        """T04: metadata.name='.' 必须被拦截"""
        if self.PluginInstaller is None:
            self.skipTest(f"plugin_market 导入失败: {getattr(self, 'import_error', '')}")
        installer = self.PluginInstaller(self.plugins_dir)
        with self.assertRaises(Exception) as ctx:
            installer._sanitize_plugin_name(".")
        self.assertIn("非法插件名称", str(ctx.exception), "'.' 应被拦截")

    def test_T05_empty_rejected(self):
        """T05: metadata.name='' 必须被拦截"""
        if self.PluginInstaller is None:
            self.skipTest(f"plugin_market 导入失败: {getattr(self, 'import_error', '')}")
        installer = self.PluginInstaller(self.plugins_dir)
        with self.assertRaises(Exception) as ctx:
            installer._sanitize_plugin_name("")
        self.assertIn("非法插件名称", str(ctx.exception), "空名应被拦截")

    def test_T06_normal_name_allowed(self):
        """T06: 正常插件名 'normal_plugin' 原样返回"""
        if self.PluginInstaller is None:
            self.skipTest(f"plugin_market 导入失败: {getattr(self, 'import_error', '')}")
        installer = self.PluginInstaller(self.plugins_dir)
        self.assertEqual("normal_plugin", installer._sanitize_plugin_name("normal_plugin"))

    def test_T07_windows_style_name_rejected(self):
        """T07: Windows 反斜杠路径名 '..\\evil' 被 basename 净化"""
        if self.PluginInstaller is None:
            self.skipTest(f"plugin_market 导入失败: {getattr(self, 'import_error', '')}")
        installer = self.PluginInstaller(self.plugins_dir)
        sanitized = installer._sanitize_plugin_name("..\\evil")
        self.assertEqual("evil", sanitized, "Windows 反斜杠路径应被 basename 剥离")

    def test_T08_install_plugin_rejects_dotdot_zip(self):
        """T08: 端到端 — zip metadata.name='..' 时 install_plugin 抛"非法插件名称"异常"""
        if self.PluginInstaller is None:
            self.skipTest(f"plugin_market 导入失败: {getattr(self, 'import_error', '')}")
        installer = self.PluginInstaller(self.plugins_dir)
        zip_path = self._make_zip("..")
        with self.assertRaises(Exception) as ctx:
            with unittest.mock.patch.object(installer, '_verify_plugin_file', return_value=True):
                installer.install_plugin(zip_path)
        self.assertIn("非法插件名称", str(ctx.exception), "端到端安装应拦截 '..' 名称")


if __name__ == '__main__':
    unittest.main()
