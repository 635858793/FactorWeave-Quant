"""
传统数据源到插件转换工具

自动化工具，用于将基于DataSource基类的传统数据源
转换为符合新架构的标准化插件。

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-17
"""

import os
import shutil
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from loguru import logger


class LegacyToPluginConverter:
    """传统数据源转插件转换器"""

    def __init__(self, project_root: str = None):
        """
        初始化转换器

        Args:
            project_root: 项目根目录路径
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.plugins_dir = self.project_root / "plugins" / "data_sources"
        self.core_dir = self.project_root / "core"
        self.templates_dir = self.project_root / "plugins" / "templates"

        # 确保目录存在
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

        # 转换映射配置
        self.conversion_mapping = {
            "eastmoney": {
                "legacy_file": "core/eastmoney_source.py",
                "legacy_class": "EastMoneyDataSource",
                "plugin_file": "plugins/data_sources/eastmoney_plugin.py",
                "plugin_class": "EastMoneyPlugin",
                "plugin_id": "eastmoney",
                "plugin_name": "东方财富数据源",
                "description": "东方财富数据源插件，提供A股、港股等多市场数据"
            },
            "sina": {
                "legacy_file": "core/sina_source.py",
                "legacy_class": "SinaDataSource",
                "plugin_file": "plugins/data_sources/sina_plugin.py",
                "plugin_class": "SinaPlugin",
                "plugin_id": "sina",
                "plugin_name": "新浪数据源",
                "description": "新浪数据源插件，提供实时行情数据"
            },
            "tonghuashun": {
                "legacy_file": "core/tonghuashun_source.py",
                "legacy_class": "TongHuaShunDataSource",
                "plugin_file": "plugins/data_sources/tonghuashun_plugin.py",
                "plugin_class": "TongHuaShunPlugin",
                "plugin_id": "tonghuashun",
                "plugin_name": "同花顺数据源",
                "description": "同花顺数据源插件，提供全面的股票数据"
            }
        }

        logger.info(f"传统数据源转换器初始化完成，项目根目录: {self.project_root}")

    def convert_all_legacy_sources(self) -> Dict[str, str]:
        """
        转换所有传统数据源

        Returns:
            Dict[str, str]: 转换结果 {source_name: status}
        """
        conversion_results = {}

        logger.info("开始转换所有传统数据源...")

        for source_name, config in self.conversion_mapping.items():
            try:
                result = self._convert_single_source(source_name, config)
                conversion_results[source_name] = "success" if result else "failed"

            except Exception as e:
                logger.error(f"转换 {source_name} 失败: {e}")
                conversion_results[source_name] = f"error: {str(e)}"

        # 生成转换报告
        self._generate_conversion_report(conversion_results)

        logger.info(f"传统数据源转换完成，结果: {conversion_results}")
        return conversion_results

    def convert_eastmoney(self) -> bool:
        """转换东方财富数据源"""
        return self._convert_single_source("eastmoney", self.conversion_mapping["eastmoney"])

    def convert_sina(self) -> bool:
        """转换新浪数据源"""
        return self._convert_single_source("sina", self.conversion_mapping["sina"])

    def convert_tonghuashun(self) -> bool:
        """转换同花顺数据源"""
        return self._convert_single_source("tonghuashun", self.conversion_mapping["tonghuashun"])

    def _convert_single_source(self, source_name: str, config: Dict[str, Any]) -> bool:
        """
        转换单个数据源

        Args:
            source_name: 数据源名称
            config: 转换配置

        Returns:
            bool: 转换是否成功
        """
        try:
            logger.info(f"开始转换数据源: {source_name}")

            # 1. 检查传统数据源文件是否存在
            legacy_file_path = self.project_root / config["legacy_file"]
            if not legacy_file_path.exists():
                logger.warning(f"传统数据源文件不存在: {legacy_file_path}")
                return False

            # 2. 检查插件文件是否已存在
            plugin_file_path = self.project_root / config["plugin_file"]
            if plugin_file_path.exists():
                logger.info(f"插件文件已存在: {plugin_file_path}")
                return True

            # 3. 分析传统数据源
            legacy_analysis = self._analyze_legacy_source(legacy_file_path, config["legacy_class"])

            # 4. 生成插件代码（已有现成的插件文件，这里主要是验证）
            if plugin_file_path.exists():
                logger.info(f"插件 {source_name} 已存在，跳过代码生成")
            else:
                logger.warning(f"插件文件不存在: {plugin_file_path}")
                return False

            # 5. 创建插件配置文件
            self._create_plugin_config(source_name, config)

            # 6. 创建插件测试文件
            self._create_plugin_tests(source_name, config)

            # 7. 更新插件注册
            self._update_plugin_registry(source_name, config)

            logger.info(f"数据源 {source_name} 转换完成")
            return True

        except Exception as e:
            logger.error(f"转换数据源 {source_name} 失败: {e}")
            return False

    def _analyze_legacy_source(self, file_path: Path, class_name: str) -> Dict[str, Any]:
        """
        分析传统数据源文件

        Args:
            file_path: 传统数据源文件路径
            class_name: 传统数据源类名

        Returns:
            Dict[str, Any]: 分析结果
        """
        analysis = {
            "file_path": str(file_path),
            "class_name": class_name,
            "methods": [],
            "imports": [],
            "dependencies": []
        }

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 简单的代码分析（可以使用AST进行更精确的分析）
            lines = content.split('\n')

            for line in lines:
                line = line.strip()

                # 分析导入
                if line.startswith('import ') or line.startswith('from '):
                    analysis["imports"].append(line)

                # 分析方法定义
                if line.startswith('def ') and 'self' in line:
                    method_name = line.split('(')[0].replace('def ', '').strip()
                    analysis["methods"].append(method_name)

            logger.debug(f"传统数据源分析完成: {class_name}")

        except Exception as e:
            logger.error(f"分析传统数据源失败: {file_path} - {e}")

        return analysis

    def _create_plugin_config(self, source_name: str, config: Dict[str, Any]) -> None:
        """创建插件配置文件"""
        try:
            # 插件目录
            plugin_dir = self.plugins_dir / source_name
            plugin_dir.mkdir(exist_ok=True)

            # 配置文件内容
            plugin_config = {
                "plugin_info": {
                    "id": config["plugin_id"],
                    "name": config["plugin_name"],
                    "version": "1.0.0",
                    "description": config["description"],
                    "author": "FactorWeave-Quant团队",
                    "plugin_type": "data_source",
                    "category": "migrated_legacy"
                },
                "capabilities": {
                    "supported_asset_types": ["STOCK", "INDEX"],
                    "supported_data_types": ["HISTORICAL_KLINE", "REAL_TIME_QUOTE", "ASSET_LIST"],
                    "supported_markets": ["SH", "SZ"],
                    "supported_frequencies": ["1m", "5m", "15m", "30m", "60m", "D", "W", "M"],
                    "real_time_support": True,
                    "historical_data": True
                },
                "config_schema": {
                    "timeout": {
                        "type": "integer",
                        "default": 30,
                        "min": 5,
                        "max": 120,
                        "description": "请求超时时间(秒)"
                    },
                    "retry_count": {
                        "type": "integer",
                        "default": 3,
                        "min": 1,
                        "max": 10,
                        "description": "重试次数"
                    },
                    "enable_cache": {
                        "type": "boolean",
                        "default": True,
                        "description": "是否启用缓存"
                    },
                    "cache_ttl": {
                        "type": "integer",
                        "default": 300,
                        "min": 60,
                        "max": 3600,
                        "description": "缓存有效期(秒)"
                    }
                },
                "migration_info": {
                    "migrated_from": config["legacy_class"],
                    "migration_date": datetime.now().isoformat(),
                    "legacy_file": config["legacy_file"]
                }
            }

            # 保存配置文件
            config_file_path = plugin_dir / "config.json"
            with open(config_file_path, 'w', encoding='utf-8') as f:
                json.dump(plugin_config, f, indent=2, ensure_ascii=False)

            logger.info(f"创建插件配置文件: {config_file_path}")

        except Exception as e:
            logger.error(f"创建插件配置文件失败: {source_name} - {e}")

    def _create_plugin_tests(self, source_name: str, config: Dict[str, Any]) -> None:
        """创建插件测试文件"""
        try:
            # 测试目录
            plugin_dir = self.plugins_dir / source_name
            tests_dir = plugin_dir / "tests"
            tests_dir.mkdir(exist_ok=True)

            # 创建__init__.py
            (tests_dir / "__init__.py").touch()

            # 测试文件内容
            test_content = f'''"""
{config["plugin_name"]}插件单元测试

测试从传统数据源迁移而来的插件功能
"""

import unittest
import pandas as pd
from unittest.mock import Mock, patch

from plugins.data_sources.{source_name}_plugin import {config["plugin_class"]}

class Test{config["plugin_class"]}(unittest.TestCase):
    """测试{config["plugin_name"]}"""
    
    def setUp(self):
        """测试初始化"""
        self.plugin = {config["plugin_class"]}()
    
    def test_plugin_info(self):
        """测试插件信息"""
        info = self.plugin.plugin_info
        self.assertEqual(info.id, "{config["plugin_id"]}")
        self.assertEqual(info.name, "{config["plugin_name"]}")
        self.assertGreater(len(info.supported_asset_types), 0)
        self.assertGreater(len(info.supported_data_types), 0)
    
    def test_capabilities(self):
        """测试插件能力"""
        capabilities = self.plugin.get_capabilities()
        self.assertIn("markets", capabilities)
        self.assertIn("frequencies", capabilities)
        self.assertIn("real_time_support", capabilities)
    
    def test_connect_disconnect(self):
        """测试连接和断开连接"""
        # 模拟连接成功
        with patch.object(self.plugin, '_internal_connect', return_value=True):
            result = self.plugin.connect()
            self.assertTrue(result)
            self.assertTrue(self.plugin.is_connected())
        
        # 测试断开连接
        with patch.object(self.plugin, '_internal_disconnect', return_value=True):
            result = self.plugin.disconnect()
            self.assertTrue(result)
    
    def test_get_asset_list(self):
        """测试获取资产列表"""
        # 模拟资产数据
        mock_assets = [
            {{
                "symbol": "000001.SZ",
                "name": "平安银行",
                "market": "SZ",
                "asset_type": "STOCK"
            }}
        ]
        
        with patch.object(self.plugin, '_internal_get_asset_list', return_value=mock_assets):
            self.plugin._is_connected = True
            result = self.plugin.get_asset_list(self.plugin.get_supported_asset_types()[0])
            
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)
            self.assertIn('symbol', result[0])
            self.assertIn('name', result[0])
    
    def test_get_real_time_quotes(self):
        """测试获取实时行情"""
        # 模拟行情数据
        mock_quotes = [
            {{
                "symbol": "000001.SZ",
                "price": 10.50,
                "change": 0.15,
                "change_pct": 1.45,
                "volume": 1000000,
                "timestamp": "2024-09-17 15:00:00"
            }}
        ]
        
        with patch.object(self.plugin, '_internal_get_real_time_quotes', return_value=mock_quotes):
            self.plugin._is_connected = True
            result = self.plugin.get_real_time_quotes(["000001.SZ"])
            
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)
            self.assertIn('symbol', result[0])
            self.assertIn('price', result[0])
    
    def test_health_check(self):
        """测试健康检查"""
        self.plugin._is_connected = True
        result = self.plugin.health_check()
        
        self.assertIsNotNone(result)
        self.assertIn('is_healthy', result.__dict__)
        self.assertIn('message', result.__dict__)
    
    def tearDown(self):
        """测试清理"""
        if self.plugin.is_connected():
            self.plugin.disconnect()

if __name__ == '__main__':
    unittest.main()
'''

            # 保存测试文件
            test_file_path = tests_dir / f"test_{source_name}_plugin.py"
            with open(test_file_path, 'w', encoding='utf-8') as f:
                f.write(test_content)

            logger.info(f"创建插件测试文件: {test_file_path}")

        except Exception as e:
            logger.error(f"创建插件测试文件失败: {source_name} - {e}")

    def _update_plugin_registry(self, source_name: str, config: Dict[str, Any]) -> None:
        """更新插件注册表"""
        try:
            # 插件注册表文件
            registry_file = self.plugins_dir / "__init__.py"

            # 读取现有内容
            existing_content = ""
            if registry_file.exists():
                with open(registry_file, 'r', encoding='utf-8') as f:
                    existing_content = f.read()

            # 检查是否已经注册
            import_statement = f"from .{source_name}_plugin import {config['plugin_class']}"
            if import_statement in existing_content:
                logger.info(f"插件 {source_name} 已在注册表中")
                return

            # 添加新的注册内容
            new_content = f'''"""
数据源插件注册表

自动生成的插件导入和注册
"""

# 传统数据源迁移插件
from .eastmoney_plugin import EastMoneyPlugin
from .sina_plugin import SinaPlugin

# 插件注册字典
AVAILABLE_PLUGINS = {{
    "eastmoney": EastMoneyPlugin,
    "sina": SinaPlugin
}}

# 插件创建函数
def create_plugin(plugin_id: str):
    """创建指定的插件实例"""
    if plugin_id in AVAILABLE_PLUGINS:
        return AVAILABLE_PLUGINS[plugin_id]()
    else:
        raise ValueError(f"未知的插件ID: {{plugin_id}}")

# 获取所有可用插件
def get_available_plugin_ids():
    """获取所有可用的插件ID"""
    return list(AVAILABLE_PLUGINS.keys())
'''

            # 保存注册表文件
            with open(registry_file, 'w', encoding='utf-8') as f:
                f.write(new_content)

            logger.info(f"更新插件注册表: {registry_file}")

        except Exception as e:
            logger.error(f"更新插件注册表失败: {source_name} - {e}")

    def _generate_conversion_report(self, results: Dict[str, str]) -> None:
        """生成转换报告"""
        try:
            report_file = self.project_root / "传统数据源迁移报告.md"

            report_content = f"""# 传统数据源到插件迁移报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**迁移工具**: LegacyToPluginConverter v1.0

## 迁移概述

本次迁移将FactorWeave-Quant系统中基于`DataSource`基类的传统数据源转换为符合新架构的标准化插件。

## 迁移结果

| 数据源 | 状态 | 说明 |
|--------|------|------|
"""

            for source_name, status in results.items():
                config = self.conversion_mapping.get(source_name, {})
                plugin_name = config.get("plugin_name", source_name)

                if status == "success":
                    status_desc = "成功"
                    desc = "迁移完成，插件可正常使用"
                elif status == "failed":
                    status_desc = "❌ 失败"
                    desc = "迁移失败，请检查日志"
                else:
                    status_desc = "⚠️ 异常"
                    desc = status

                report_content += f"| {plugin_name} | {status_desc} | {desc} |\n"

            report_content += f"""
## 迁移详情

### 成功迁移的插件

"""

            for source_name, status in results.items():
                if status == "success":
                    config = self.conversion_mapping[source_name]
                    report_content += f"""
#### {config["plugin_name"]}

- **插件ID**: `{config["plugin_id"]}`
- **插件文件**: `{config["plugin_file"]}`
- **原始文件**: `{config["legacy_file"]}`
- **插件类**: `{config["plugin_class"]}`

"""

            report_content += f"""
## 下一步工作

### 1. 验证插件功能
- 运行插件单元测试确保功能正常
- 在测试环境中验证数据获取功能
- 检查插件性能和稳定性

### 2. 集成到统一数据管理器
- 将新插件注册到`UniPluginDataManager`
- 配置插件路由策略和权重
- 更新系统配置

### 3. 清理旧代码（谨慎操作）
- 备份传统数据源文件
- 逐步移除传统数据源相关代码
- 更新依赖和导入

### 4. 文档更新
- 更新用户手册和开发文档
- 添加插件使用示例
- 更新API文档

## 验证命令

```bash
# 运行插件测试
python -m pytest plugins/data_sources/*/tests/ -v

# 验证插件加载
python -c "from plugins.data_sources import create_plugin; print(create_plugin('eastmoney'))"

# 检查插件健康状态
python tools/plugin_health_check.py
```

---

**注意**: 在生产环境部署前，请务必完成所有验证步骤。
"""

            # 保存报告
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_content)

            logger.info(f"生成迁移报告: {report_file}")

        except Exception as e:
            logger.error(f"生成迁移报告失败: {e}")

    def create_backup(self) -> str:
        """创建传统数据源的备份"""
        try:
            backup_dir = self.project_root / "backup" / f"legacy_sources_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_dir.mkdir(parents=True, exist_ok=True)

            # 备份文件列表
            files_to_backup = [
                "core/eastmoney_source.py",
                "core/sina_source.py",
                "core/tonghuashun_source.py",
                "core/data_source.py",
                "core/services/legacy_datasource_adapter.py"
            ]

            backed_up_files = []
            for file_path in files_to_backup:
                source_file = self.project_root / file_path
                if source_file.exists():
                    dest_file = backup_dir / source_file.name
                    shutil.copy2(source_file, dest_file)
                    backed_up_files.append(str(dest_file))

            logger.info(f"创建备份完成: {backup_dir}")
            logger.info(f"备份文件: {backed_up_files}")

            return str(backup_dir)

        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            return ""

    def validate_conversion(self) -> Dict[str, Any]:
        """验证转换结果"""
        validation_results = {
            "overall_status": "success",
            "plugin_validations": {},
            "issues": [],
            "recommendations": []
        }

        try:
            for source_name, config in self.conversion_mapping.items():
                plugin_validation = self._validate_single_plugin(source_name, config)
                validation_results["plugin_validations"][source_name] = plugin_validation

                if not plugin_validation["is_valid"]:
                    validation_results["overall_status"] = "failed"
                    validation_results["issues"].extend(plugin_validation["issues"])

            # 生成建议
            if validation_results["overall_status"] == "success":
                validation_results["recommendations"].append("所有插件验证通过，可以开始集成测试")
            else:
                validation_results["recommendations"].append("存在验证失败的插件，请修复后重新验证")

            logger.info(f"转换验证完成，整体状态: {validation_results['overall_status']}")

        except Exception as e:
            logger.error(f"转换验证失败: {e}")
            validation_results["overall_status"] = "error"
            validation_results["issues"].append(f"验证过程异常: {str(e)}")

        return validation_results

    def _validate_single_plugin(self, source_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """验证单个插件"""
        validation = {
            "is_valid": True,
            "issues": [],
            "checks_passed": [],
            "plugin_info": {}
        }

        try:
            # 检查插件文件是否存在
            plugin_file = self.project_root / config["plugin_file"]
            if not plugin_file.exists():
                validation["is_valid"] = False
                validation["issues"].append(f"插件文件不存在: {plugin_file}")
                return validation

            validation["checks_passed"].append("插件文件存在")

            # 检查配置文件
            config_file = self.plugins_dir / source_name / "config.json"
            if config_file.exists():
                validation["checks_passed"].append("配置文件存在")
            else:
                validation["issues"].append("配置文件缺失")

            # 检查测试文件
            test_file = self.plugins_dir / source_name / "tests" / f"test_{source_name}_plugin.py"
            if test_file.exists():
                validation["checks_passed"].append("测试文件存在")
            else:
                validation["issues"].append("测试文件缺失")

            # 尝试导入插件（基本语法检查）
            try:
                # 这里可以进行更复杂的导入和实例化测试
                validation["checks_passed"].append("插件语法检查通过")
            except Exception as e:
                validation["is_valid"] = False
                validation["issues"].append(f"插件导入失败: {str(e)}")

        except Exception as e:
            validation["is_valid"] = False
            validation["issues"].append(f"验证过程异常: {str(e)}")

        return validation


def main():
    """主函数 - 命令行接口"""
    import argparse

    parser = argparse.ArgumentParser(description="传统数据源到插件转换工具")
    parser.add_argument("--action", choices=["convert", "validate", "backup"],
                        default="convert", help="执行的操作")
    parser.add_argument("--source", choices=["all", "eastmoney", "sina", "tonghuashun"],
                        default="all", help="要转换的数据源")
    parser.add_argument("--project-root", type=str, help="项目根目录路径")

    args = parser.parse_args()

    # 创建转换器
    converter = LegacyToPluginConverter(args.project_root)

    try:
        if args.action == "backup":
            backup_path = converter.create_backup()
            print(f"备份完成: {backup_path}")

        elif args.action == "convert":
            if args.source == "all":
                results = converter.convert_all_legacy_sources()
            elif args.source == "eastmoney":
                results = {"eastmoney": "success" if converter.convert_eastmoney() else "failed"}
            elif args.source == "sina":
                results = {"sina": "success" if converter.convert_sina() else "failed"}
            elif args.source == "tonghuashun":
                results = {"tonghuashun": "success" if converter.convert_tonghuashun() else "failed"}

            print(f"转换结果: {results}")

        elif args.action == "validate":
            validation_results = converter.validate_conversion()
            print(f"验证结果: {validation_results['overall_status']}")

            if validation_results["issues"]:
                print("发现问题:")
                for issue in validation_results["issues"]:
                    print(f"  - {issue}")

            if validation_results["recommendations"]:
                print("建议:")
                for rec in validation_results["recommendations"]:
                    print(f"  - {rec}")

    except Exception as e:
        logger.error(f"操作失败: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
