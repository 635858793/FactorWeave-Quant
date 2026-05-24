#!/usr/bin/env python3
"""
系统维护工具使用示例

这个示例展示了如何使用系统维护工具进行：
1. 编程方式的系统维护
2. GUI界面的系统维护
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from core.services.system_optimizer import (
    SystemOptimizerService,
    OptimizationLevel,
    OptimizationConfig
)


async def example_programmatic_maintenance():
    """编程方式的系统维护示例"""
    logger.info("=== 编程方式的系统维护 ===")

    # 创建系统优化器服务
    service = SystemOptimizerService()

    try:
        # 初始化服务
        await service.initialize_async()
        logger.info("服务初始化成功")

        # 分析系统状态
        logger.info("\n1. 分析系统状态...")
        analysis = await service.analyze_system()
        logger.info(f"   - 总文件数: {analysis.get('total_files', 0)}")
        logger.info(f"   - Python文件数: {analysis.get('python_files', 0)}")
        logger.info(f"   - 大文件数: {len(analysis.get('large_files', []))}")
        logger.info(f"   - 缓存文件数: {len(analysis.get('cache_files', []))}")
        logger.info(f"   - 临时文件数: {len(analysis.get('temp_files', []))}")

        # 获取维护建议
        logger.info("\n2. 获取维护建议...")
        suggestions = await service.get_optimization_suggestions()
        for i, suggestion in enumerate(suggestions[:5], 1):
            logger.info(f"   {i}. {suggestion}")

        # 执行轻度维护
        logger.info("\n3. 执行轻度维护...")
        result = await service.optimize_system(OptimizationLevel.LIGHT)

        logger.info(f"   - 维护级别: {result.level.value}")
        logger.info(f"   - 清理文件: {result.files_cleaned} 个")
        logger.info(f"   - 优化文件: {result.files_optimized} 个")
        logger.info(f"   - 释放空间: {result.bytes_freed / 1024 / 1024:.2f} MB")
        logger.info(f"   - 耗时: {result.duration.total_seconds():.2f} 秒")
        logger.info(f"   - 成功率: {result.success_rate:.2%}")

    except Exception as e:
        logger.info(f" 维护过程中发生错误: {e}")

    finally:
        # 清理服务
        await service.dispose_async()
        logger.info("\n 服务清理完成")


def example_gui_maintenance():
    """GUI界面的系统维护示例"""
    logger.info("\n=== GUI界面的系统维护 ===")

    try:
        logger.info("GUI界面使用说明：")
        logger.info("1. 选择维护级别（轻度/中度/深度/自定义）")
        logger.info("2. 配置维护选项（如果选择自定义）")
        logger.info("3. 点击'开始维护'按钮")
        logger.info("4. 查看维护进度和结果")
        logger.info("5. 查看维护历史记录")
        logger.info("\n要使用GUI界面，请运行以下代码：")
        logger.info("```python")
        logger.info("from PyQt5.QtWidgets import QApplication")
        logger.info("from gui.dialogs.system_optimizer_dialog import show_system_optimizer_dialog")
        logger.info("app = QApplication([])")
        logger.info("show_system_optimizer_dialog()")
        logger.info("app.exec_()")
        logger.info("```")
        logger.info("GUI界面示例说明完成")

    except Exception as e:
        logger.info(f" GUI示例失败: {e}")


def example_custom_maintenance():
    """自定义维护配置示例"""
    logger.info("\n=== 自定义维护配置 ===")

    # 创建自定义配置
    custom_config = OptimizationConfig(
        level=OptimizationLevel.CUSTOM,
        clean_cache=True,           # 清理缓存文件
        clean_temp_files=True,      # 清理临时文件
        clean_logs=False,           # 不清理日志文件
        optimize_imports=True,      # 优化导入语句
        optimize_memory=True,       # 内存优化
        backup_before_optimize=True,  # 维护前备份
        log_retention_days=30,      # 日志保留30天
        max_file_size_mb=100       # 大文件阈值100MB
    )

    logger.info("自定义配置:")
    logger.info(f"  - 维护级别: {custom_config.level.value}")
    logger.info(f"  - 清理缓存: {custom_config.clean_cache}")
    logger.info(f"  - 清理临时文件: {custom_config.clean_temp_files}")
    logger.info(f"  - 清理日志: {custom_config.clean_logs}")
    logger.info(f"  - 优化导入: {custom_config.optimize_imports}")
    logger.info(f"  - 内存优化: {custom_config.optimize_memory}")
    logger.info(f"  - 维护前备份: {custom_config.backup_before_optimize}")
    logger.info(f"  - 日志保留天数: {custom_config.log_retention_days}")
    logger.info(f"  - 大文件阈值: {custom_config.max_file_size_mb} MB")

    logger.info("\n使用自定义配置进行维护...")
    logger.info("（实际维护过程请使用 example_programmatic_maintenance 函数）")


async def main():
    """主函数"""
    logger.info("系统维护工具使用示例")
    logger.info("=" * 50)

    # 1. 编程方式的系统维护
    await example_programmatic_maintenance()

    # 2. 自定义维护配置
    example_custom_maintenance()

    # 3. GUI界面的系统维护（仅演示，不实际运行）
    example_gui_maintenance()

    logger.info("\n" + "=" * 50)
    logger.info("示例完成！")
    logger.info("\n使用建议：")
    logger.info("1. 日常维护建议使用轻度或中度维护")
    logger.info("2. 定期（如每月）进行一次深度维护")
    logger.info("3. 重要操作前建议开启维护前备份")
    logger.info("4. 可以通过GUI界面进行交互式维护")
    logger.info("5. 可以通过编程方式集成到自动化脚本中")

if __name__ == "__main__":
    asyncio.run(main())
