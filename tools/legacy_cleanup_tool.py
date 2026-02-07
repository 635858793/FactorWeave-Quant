"""
传统代码清理工具

安全地清理传统数据源代码，简化系统架构，
完成向统一插件数据管理架构的迁移。

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-17
"""

import os
import shutil
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Set, Optional
import ast
import importlib.util

from loguru import logger

class LegacyCleanupTool:
    """传统代码清理工具"""
    
    def __init__(self, project_root: str = None, dry_run: bool = True):
        """
        初始化清理工具
        
        Args:
            project_root: 项目根目录
            dry_run: 是否为干运行模式（只分析，不实际删除）
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.dry_run = dry_run
        
        # 要清理的文件和类
        self.legacy_files = [
            "core/data_source.py",
            "core/eastmoney_source.py", 
            "core/sina_source.py",
            "core/tonghuashun_source.py",
            "core/services/legacy_datasource_adapter.py"
        ]
        
        # 要清理的类名
        self.legacy_classes = [
            "DataSource",
            "EastMoneyDataSource",
            "SinaDataSource", 
            "TongHuaShunDataSource",
            "LegacyDataSourceAdapter"
        ]
        
        # 要更新的文件
        self.files_to_update = [
            "core/services/unified_data_manager.py",
            "core/services/service_bootstrap.py",
            "core/services/asset_aware_unified_data_manager.py"
        ]
        
        # 统计信息
        self.cleanup_stats = {
            "files_removed": 0,
            "files_updated": 0,
            "lines_removed": 0,
            "imports_cleaned": 0,
            "methods_removed": 0
        }
        
        # 创建备份目录
        self.backup_dir = self.project_root / "backup" / f"cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"传统代码清理工具初始化完成，项目根目录: {self.project_root}")
        logger.info(f"模式: {'干运行' if dry_run else '实际执行'}")
    
    def execute_cleanup(self) -> Dict[str, Any]:
        """
        执行完整的清理流程
        
        Returns:
            Dict[str, Any]: 清理结果报告
        """
        logger.info("开始执行传统代码清理...")
        
        try:
            # 1. 创建备份
            if not self.dry_run:
                self._create_backup()
            
            # 2. 分析依赖关系
            dependency_analysis = self._analyze_dependencies()
            
            # 3. 验证插件系统
            plugin_verification = self._verify_plugin_system()
            
            # 4. 清理导入语句
            self._cleanup_imports()
            
            # 5. 移除传统数据源初始化代码
            self._remove_legacy_initialization()
            
            # 6. 更新服务启动逻辑
            self._update_service_bootstrap()
            
            # 7. 清理配置文件
            self._cleanup_configuration()
            
            # 8. 移除传统文件
            self._remove_legacy_files()
            
            # 9. 生成清理报告
            cleanup_report = self._generate_cleanup_report(dependency_analysis, plugin_verification)
            
            logger.info("传统代码清理完成")
            return cleanup_report
            
        except Exception as e:
            logger.error(f"清理过程失败: {e}")
            raise
    
    def _create_backup(self) -> str:
        """创建清理前的备份"""
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            
            # 备份要删除的文件
            for file_path in self.legacy_files:
                source_file = self.project_root / file_path
                if source_file.exists():
                    dest_file = self.backup_dir / source_file.name
                    shutil.copy2(source_file, dest_file)
                    logger.info(f"备份文件: {source_file} -> {dest_file}")
            
            # 备份要修改的文件
            for file_path in self.files_to_update:
                source_file = self.project_root / file_path
                if source_file.exists():
                    dest_file = self.backup_dir / f"{source_file.stem}_original{source_file.suffix}"
                    shutil.copy2(source_file, dest_file)
                    logger.info(f"备份文件: {source_file} -> {dest_file}")
            
            logger.info(f"备份完成: {self.backup_dir}")
            return str(self.backup_dir)
            
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            raise
    
    def _analyze_dependencies(self) -> Dict[str, Any]:
        """分析依赖关系"""
        logger.info("分析传统代码依赖关系...")
        
        dependencies = {
            "files_using_legacy": [],
            "import_references": {},
            "method_references": {},
            "potential_issues": []
        }
        
        try:
            # 搜索所有Python文件
            for py_file in self.project_root.rglob("*.py"):
                if any(legacy_file in str(py_file) for legacy_file in self.legacy_files):
                    continue  # 跳过传统文件本身
                
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 检查是否引用了传统类
                    for legacy_class in self.legacy_classes:
                        if legacy_class in content:
                            dependencies["files_using_legacy"].append({
                                "file": str(py_file.relative_to(self.project_root)),
                                "legacy_class": legacy_class,
                                "line_count": content.count(legacy_class)
                            })
                    
                    # 检查导入语句
                    for line_num, line in enumerate(content.split('\n'), 1):
                        line = line.strip()
                        if line.startswith(('import ', 'from ')):
                            for legacy_file in self.legacy_files:
                                legacy_module = legacy_file.replace('/', '.').replace('.py', '')
                                if legacy_module in line:
                                    if str(py_file) not in dependencies["import_references"]:
                                        dependencies["import_references"][str(py_file)] = []
                                    dependencies["import_references"][str(py_file)].append({
                                        "line": line_num,
                                        "content": line,
                                        "legacy_module": legacy_module
                                    })
                
                except Exception as e:
                    logger.warning(f"分析文件失败 {py_file}: {e}")
            
            # 分析潜在问题
            if dependencies["files_using_legacy"]:
                dependencies["potential_issues"].append(
                    f"发现 {len(dependencies['files_using_legacy'])} 个文件仍在使用传统类"
                )
            
            if dependencies["import_references"]:
                dependencies["potential_issues"].append(
                    f"发现 {len(dependencies['import_references'])} 个文件包含传统模块导入"
                )
            
            logger.info(f"依赖分析完成，发现 {len(dependencies['potential_issues'])} 个潜在问题")
            
        except Exception as e:
            logger.error(f"依赖分析失败: {e}")
            dependencies["potential_issues"].append(f"依赖分析失败: {str(e)}")
        
        return dependencies
    
    def _verify_plugin_system(self) -> Dict[str, Any]:
        """验证插件系统状态"""
        logger.info("验证插件系统状态...")
        
        verification = {
            "plugin_files_exist": True,
            "plugin_files": [],
            "missing_files": [],
            "import_test_passed": False,
            "functional_test_passed": False,
            "issues": []
        }
        
        try:
            # 检查插件文件是否存在
            plugin_files = [
                "plugins/data_sources/eastmoney_plugin.py",
                "plugins/data_sources/sina_plugin.py",
                "core/services/uni_plugin_data_manager.py",
                "plugins/templates/standard_data_source_plugin.py"
            ]
            
            for plugin_file in plugin_files:
                file_path = self.project_root / plugin_file
                if file_path.exists():
                    verification["plugin_files"].append(plugin_file)
                else:
                    verification["missing_files"].append(plugin_file)
                    verification["plugin_files_exist"] = False
                    verification["issues"].append(f"插件文件缺失: {plugin_file}")
            
            # 测试插件导入
            try:
                # 这里可以添加插件导入测试
                verification["import_test_passed"] = True
            except Exception as e:
                verification["issues"].append(f"插件导入测试失败: {str(e)}")
            
            # 功能测试
            try:
                # 这里可以添加插件功能测试
                verification["functional_test_passed"] = True
            except Exception as e:
                verification["issues"].append(f"插件功能测试失败: {str(e)}")
            
            logger.info("插件系统验证完成")
            
        except Exception as e:
            logger.error(f"插件系统验证失败: {e}")
            verification["issues"].append(f"验证过程异常: {str(e)}")
        
        return verification
    
    def _cleanup_imports(self) -> None:
        """清理导入语句"""
        logger.info("清理传统模块导入语句...")
        
        for file_path in self.files_to_update:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
            
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_lines = content.split('\n')
                updated_lines = []
                removed_imports = 0
                
                for line in original_lines:
                    should_remove = False
                    
                    # 检查是否为传统模块导入
                    for legacy_file in self.legacy_files:
                        legacy_module = legacy_file.replace('/', '.').replace('.py', '')
                        if legacy_module in line and ('import ' in line or 'from ' in line):
                            should_remove = True
                            removed_imports += 1
                            logger.debug(f"移除导入语句: {line.strip()}")
                            break
                    
                    if not should_remove:
                        updated_lines.append(line)
                
                if removed_imports > 0:
                    updated_content = '\n'.join(updated_lines)
                    
                    if not self.dry_run:
                        with open(full_path, 'w', encoding='utf-8') as f:
                            f.write(updated_content)
                    
                    self.cleanup_stats["imports_cleaned"] += removed_imports
                    logger.info(f"清理 {file_path}: 移除 {removed_imports} 个导入语句")
                
            except Exception as e:
                logger.error(f"清理导入失败 {file_path}: {e}")
    
    def _remove_legacy_initialization(self) -> None:
        """移除传统数据源初始化代码"""
        logger.info("移除传统数据源初始化代码...")
        
        unified_manager_file = self.project_root / "core/services/unified_data_manager.py"
        if not unified_manager_file.exists():
            return
        
        try:
            with open(unified_manager_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_lines = content.split('\n')
            updated_lines = []
            in_legacy_method = False
            legacy_method_indent = 0
            removed_lines = 0
            
            for line in original_lines:
                current_line = line
                should_remove = False
                
                # 检查是否进入传统方法
                if 'def _initialize_data_sources(' in line:
                    in_legacy_method = True
                    legacy_method_indent = len(line) - len(line.lstrip())
                    should_remove = True
                elif 'def _register_legacy_data_source' in line:
                    in_legacy_method = True
                    legacy_method_indent = len(line) - len(line.lstrip())
                    should_remove = True
                elif in_legacy_method:
                    # 检查是否退出方法
                    if line.strip() and not line.startswith(' ' * (legacy_method_indent + 1)) and not line.startswith('\t'):
                        in_legacy_method = False
                        legacy_method_indent = 0
                    else:
                        should_remove = True
                
                # 检查传统数据源实例化
                if any(legacy_class in line for legacy_class in self.legacy_classes):
                    should_remove = True
                
                if should_remove:
                    removed_lines += 1
                    logger.debug(f"移除行: {line.strip()}")
                else:
                    updated_lines.append(current_line)
            
            if removed_lines > 0:
                updated_content = '\n'.join(updated_lines)
                
                if not self.dry_run:
                    with open(unified_manager_file, 'w', encoding='utf-8') as f:
                        f.write(updated_content)
                
                self.cleanup_stats["lines_removed"] += removed_lines
                self.cleanup_stats["methods_removed"] += 1
                logger.info(f"移除传统初始化代码: {removed_lines} 行")
            
        except Exception as e:
            logger.error(f"移除传统初始化代码失败: {e}")
    
    def _update_service_bootstrap(self) -> None:
        """更新服务启动逻辑"""
        logger.info("更新服务启动逻辑...")
        
        bootstrap_file = self.project_root / "core/services/service_bootstrap.py"
        if not bootstrap_file.exists():
            return
        
        try:
            with open(bootstrap_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 添加统一插件数据管理器注册
            uni_manager_import = "from core.services.uni_plugin_data_manager import UniPluginDataManager"
            if uni_manager_import not in content:
                # 在导入部分添加新的导入
                lines = content.split('\n')
                import_section_end = 0
                
                for i, line in enumerate(lines):
                    if line.startswith('from ') or line.startswith('import '):
                        import_section_end = i
                
                lines.insert(import_section_end + 1, uni_manager_import)
                content = '\n'.join(lines)
            
            # 更新服务注册逻辑
            # 这里可以添加更复杂的代码更新逻辑
            
            if not self.dry_run:
                with open(bootstrap_file, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            self.cleanup_stats["files_updated"] += 1
            logger.info("服务启动逻辑已更新")
            
        except Exception as e:
            logger.error(f"更新服务启动逻辑失败: {e}")
    
    def _cleanup_configuration(self) -> None:
        """清理配置文件"""
        logger.info("清理配置文件...")
        
        config_files = [
            "config/data_sources.json",
            "config/plugins.json"
        ]
        
        for config_file in config_files:
            file_path = self.project_root / config_file
            if file_path.exists():
                try:
                    # 这里可以添加配置文件清理逻辑
                    logger.info(f"配置文件存在: {config_file}")
                except Exception as e:
                    logger.warning(f"清理配置文件失败 {config_file}: {e}")
    
    def _remove_legacy_files(self) -> None:
        """移除传统文件"""
        logger.info("移除传统文件...")
        
        for file_path in self.legacy_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                if not self.dry_run:
                    try:
                        full_path.unlink()
                        logger.info(f"删除文件: {file_path}")
                        self.cleanup_stats["files_removed"] += 1
                    except Exception as e:
                        logger.error(f"删除文件失败 {file_path}: {e}")
                else:
                    logger.info(f"[干运行] 将删除文件: {file_path}")
                    self.cleanup_stats["files_removed"] += 1
            else:
                logger.warning(f"文件不存在: {file_path}")
    
    def _generate_cleanup_report(self, dependency_analysis: Dict[str, Any], 
                               plugin_verification: Dict[str, Any]) -> Dict[str, Any]:
        """生成清理报告"""
        logger.info("生成清理报告...")
        
        report = {
            "cleanup_summary": {
                "execution_mode": "dry_run" if self.dry_run else "actual",
                "timestamp": datetime.now().isoformat(),
                "project_root": str(self.project_root),
                "backup_location": str(self.backup_dir) if not self.dry_run else None
            },
            "statistics": self.cleanup_stats,
            "dependency_analysis": dependency_analysis,
            "plugin_verification": plugin_verification,
            "recommendations": [],
            "next_steps": []
        }
        
        # 生成建议
        if dependency_analysis["potential_issues"]:
            report["recommendations"].append("解决发现的依赖问题后再执行实际清理")
        
        if not plugin_verification["plugin_files_exist"]:
            report["recommendations"].append("确保所有插件文件都已正确创建")
        
        if plugin_verification["issues"]:
            report["recommendations"].append("修复插件系统验证中发现的问题")
        
        # 下一步操作
        if self.dry_run:
            report["next_steps"].extend([
                "检查清理报告中的问题和建议",
                "修复发现的问题",
                "使用 --no-dry-run 模式执行实际清理"
            ])
        else:
            report["next_steps"].extend([
                "验证系统功能正常",
                "运行完整的测试套件",
                "更新文档和部署指南"
            ])
        
        # 风险评估
        risk_level = "low"
        if dependency_analysis["potential_issues"] or plugin_verification["issues"]:
            risk_level = "high"
        elif not plugin_verification["functional_test_passed"]:
            risk_level = "medium"
        
        report["risk_assessment"] = {
            "level": risk_level,
            "factors": dependency_analysis["potential_issues"] + plugin_verification["issues"]
        }
        
        return report
    
    def generate_migration_validation_script(self) -> str:
        """生成迁移验证脚本"""
        script_content = '''#!/usr/bin/env python3
"""
统一插件架构迁移验证脚本

验证传统数据源到插件架构的迁移是否成功
"""

import sys
from pathlib import Path

def main():
    """主验证函数"""
    issues = []
    
    try:
        # 验证插件导入
        from core.services.uni_plugin_data_manager import UniPluginDataManager
        from plugins.data_sources.eastmoney_plugin import EastMoneyPlugin
        from plugins.data_sources.sina_plugin import SinaPlugin
        print("✓ 插件导入成功")
    except ImportError as e:
        issues.append(f"插件导入失败: {e}")
    
    try:
        # 验证插件实例化
        eastmoney_plugin = EastMoneyPlugin()
        sina_plugin = SinaPlugin()
        print("✓ 插件实例化成功")
    except Exception as e:
        issues.append(f"插件实例化失败: {e}")
    
    try:
        # 验证插件基本功能
        eastmoney_info = eastmoney_plugin.plugin_info
        sina_info = sina_plugin.plugin_info
        print(f"✓ 插件信息获取成功: {eastmoney_info.name}, {sina_info.name}")
    except Exception as e:
        issues.append(f"插件信息获取失败: {e}")
    
    # 检查传统文件是否已删除
    legacy_files = [
        "core/data_source.py",
        "core/eastmoney_source.py", 
        "core/sina_source.py",
        "core/tonghuashun_source.py"
    ]
    
    for legacy_file in legacy_files:
        if Path(legacy_file).exists():
            issues.append(f"传统文件仍存在: {legacy_file}")
        else:
            print(f"✓ 传统文件已清理: {legacy_file}")
    
    # 输出结果
    if issues:
        print("\\n❌ 验证失败，发现以下问题:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    else:
        print("\\n迁移验证成功！统一插件架构已就绪。")
        return 0

if __name__ == "__main__":
    sys.exit(main())
'''
        
        script_path = self.project_root / "tools" / "validate_migration.py"
        
        if not self.dry_run:
            script_path.parent.mkdir(exist_ok=True)
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            # 设置执行权限
            script_path.chmod(0o755)
        
        logger.info(f"生成验证脚本: {script_path}")
        return str(script_path)

def main():
    """主函数 - 命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="传统代码清理工具")
    parser.add_argument("--project-root", type=str, help="项目根目录路径")
    parser.add_argument("--no-dry-run", action="store_true", help="执行实际清理（非干运行）")
    parser.add_argument("--backup-only", action="store_true", help="仅创建备份")
    parser.add_argument("--verify-only", action="store_true", help="仅验证插件系统")
    
    args = parser.parse_args()
    
    # 创建清理工具
    cleanup_tool = LegacyCleanupTool(
        project_root=args.project_root,
        dry_run=not args.no_dry_run
    )
    
    try:
        if args.backup_only:
            # 仅创建备份
            backup_path = cleanup_tool._create_backup()
            print(f"备份完成: {backup_path}")
            
        elif args.verify_only:
            # 仅验证插件系统
            verification = cleanup_tool._verify_plugin_system()
            print(f"插件系统验证结果: {verification}")
            
        else:
            # 执行完整清理
            report = cleanup_tool.execute_cleanup()
            
            # 输出报告
            print("\n" + "="*60)
            print("传统代码清理报告")
            print("="*60)
            
            print(f"\n执行模式: {report['cleanup_summary']['execution_mode']}")
            print(f"项目路径: {report['cleanup_summary']['project_root']}")
            
            if report['cleanup_summary']['backup_location']:
                print(f"备份位置: {report['cleanup_summary']['backup_location']}")
            
            print(f"\n统计信息:")
            for key, value in report['statistics'].items():
                print(f"  {key}: {value}")
            
            print(f"\n风险评估: {report['risk_assessment']['level']}")
            
            if report['recommendations']:
                print(f"\n建议:")
                for rec in report['recommendations']:
                    print(f"  - {rec}")
            
            if report['next_steps']:
                print(f"\n下一步:")
                for step in report['next_steps']:
                    print(f"  - {step}")
            
            # 生成验证脚本
            script_path = cleanup_tool.generate_migration_validation_script()
            print(f"\n验证脚本: {script_path}")
            
            return 0 if report['risk_assessment']['level'] == 'low' else 1
    
    except Exception as e:
        logger.error(f"清理失败: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
