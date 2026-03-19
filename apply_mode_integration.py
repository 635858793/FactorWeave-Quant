#!/usr/bin/env python3
"""
自动应用模式管理集成补丁
修改核心服务文件以集成 TradingMode 框架
"""

import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

def patch_strategy_service():
    """修改 StrategyService 集成 TradingMode"""
    print("=" * 80)
    print("正在修改 StrategyService...")
    print("=" * 80)
    
    file_path = PROJECT_ROOT / "core" / "services" / "strategy_service.py"
    
    if not file_path.exists():
        print(f"❌ 文件不存在：{file_path}")
        return False
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. 添加导入
    if "from ..trading.trading_mode import" not in content:
        print("  ✓ 添加 TradingMode 导入...")
        import_line = "from ..trading.trading_mode import TradingMode, ModeContext"
        # 在其他导入后添加
        content = content.replace(
            "from .base_service import BaseService",
            "from .base_service import BaseService\nfrom ..trading.trading_mode import TradingMode, ModeContext"
        )
    else:
        print("  ✓ TradingMode 导入已存在")
    
    # 2. 修改 run_backtest 方法签名
    if "mode: TradingMode = TradingMode.BACKTEST" not in content:
        print("  ✓ 修改 run_backtest 方法签名...")
        old_signature = """async def run_backtest(self,
                           strategy_id: str,
                           market_data: StandardMarketData,
                           context: StrategyContext) -> str:"""
        
        new_signature = """async def run_backtest(self,
                           strategy_id: str,
                           market_data: StandardMarketData,
                           context: StrategyContext,
                           mode: TradingMode = TradingMode.BACKTEST) -> str:"""
        
        content = content.replace(old_signature, new_signature)
    else:
        print("  ✓ run_backtest 方法签名已更新")
    
    # 3. 添加 ModeContext 创建代码
    if "mode_context = ModeContext.create_backtest" not in content:
        print("  ✓ 添加 ModeContext 创建代码...")
        # 在创建回测任务后添加
        mode_context_code = """
            self._backtest_tasks[task_id] = backtest_task

            # 创建模式上下文并传递给策略
            mode_context = ModeContext.create_backtest(
                start_date=context.start_date.isoformat() if hasattr(context.start_date, 'isoformat') else str(context.start_date),
                end_date=context.end_date.isoformat() if hasattr(context.end_date, 'isoformat') else str(context.end_date),
                mode=mode.value,
                use_full_data=mode == TradingMode.BACKTEST,
                performance_critical=mode == TradingMode.LIVE,
            )
            
            logger.info(f"创建模式上下文：{mode.value}, 策略：{strategy_id}, 时间范围：{context.start_date} 至 {context.end_date}")
"""
        
        content = content.replace(
            "self._backtest_tasks[task_id] = backtest_task\n\n            # 启动回测任务",
            mode_context_code + "\n            # 启动回测任务"
        )
    else:
        print("  ✓ ModeContext 创建代码已存在")
    
    # 4. 修改 _execute_backtest 调用
    if "self._execute_backtest(task_id, mode_context)" not in content:
        print("  ✓ 修改 _execute_backtest 调用...")
        content = content.replace(
            "self._execute_backtest(task_id),",
            "self._execute_backtest(task_id, mode_context),"
        )
    else:
        print("  ✓ _execute_backtest 调用已更新")
    
    # 5. 修改 _execute_backtest 方法签名
    if "mode_context: ModeContext = None" not in content:
        print("  ✓ 修改 _execute_backtest 方法签名...")
        content = content.replace(
            "async def _execute_backtest(self, task_id: str) -> None:",
            "async def _execute_backtest(self, task_id: str, mode_context: ModeContext = None) -> None:"
        )
    else:
        print("  ✓ _execute_backtest 方法签名已更新")
    
    # 6. 添加策略模式设置代码
    if "plugin.mode_context = mode_context" not in content:
        print("  ✓ 添加策略模式设置代码...")
        # 在创建策略插件后添加
        mode_setter_code = """# 设置策略的模式上下文
            if mode_context and hasattr(plugin, 'mode_context'):
                plugin.mode_context = mode_context
                logger.info(f"已为策略 {strategy_id} 设置模式上下文：{mode_context.mode.value}")
            
            # 更新插件使用时间"""
        
        content = content.replace(
            "# 更新插件使用时间",
            mode_setter_code
        )
    else:
        print("  ✓ 策略模式设置代码已存在")
    
    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ StrategyService 修改完成")
    return True


def patch_backtest_widget():
    """修改 BacktestWidget UI 添加模式选择"""
    print("\n" + "=" * 80)
    print("正在修改 BacktestWidget UI...")
    print("=" * 80)
    
    file_path = PROJECT_ROOT / "gui" / "widgets" / "backtest_widget.py"
    
    if not file_path.exists():
        print(f"⚠️  文件不存在：{file_path}，跳过")
        return False
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. 添加导入
    if "from core.trading.trading_mode import" not in content:
        print("  ✓ 添加 TradingMode 导入...")
        content = content.replace(
            "from loguru import logger",
            "from loguru import logger\nfrom core.trading.trading_mode import TradingMode"
        )
    else:
        print("  ✓ TradingMode 导入已存在")
    
    # 2. 添加模式选择控件初始化（在__init__方法中）
    if "self.mode_selector" not in content:
        print("  ✓ 添加模式选择控件...")
        # 在__init__方法中添加，假设在某个初始化代码后
        init_code = """
        # 模式选择器
        self.mode_label = QLabel("交易模式:")
        self.mode_selector = QComboBox()
        self.mode_selector.addItems(['回测模式', '实盘模式', '混合模式'])
        self.mode_selector.setToolTip("选择回测/实盘/混合模式")
        self.mode_selector.currentTextChanged.connect(self.on_mode_changed)
        self.current_mode = TradingMode.BACKTEST  # 默认回测模式
"""
        # 尝试在__init__方法中添加
        if "def __init__(self," in content:
            content = content.replace(
                "def __init__(self,",
                "def __init__(self,\n" + init_code
            )
            print("  ✓ 模式选择器已添加到__init__方法")
        else:
            print("  ⚠️  未找到__init__方法，需要手动添加")
    else:
        print("  ✓ 模式选择控件已存在")
    
    # 3. 添加模式切换处理方法
    if "def on_mode_changed" not in content:
        print("  ✓ 添加模式切换处理方法...")
        handler_code = """
    def on_mode_changed(self, mode_text: str):
        \"\"\"处理模式切换\"\"\"
        mode_map = {
            '回测模式': TradingMode.BACKTEST,
            '实盘模式': TradingMode.LIVE,
            '混合模式': TradingMode.HYBRID
        }
        self.current_mode = mode_map.get(mode_text, TradingMode.BACKTEST)
        logger.info(f"切换交易模式：{mode_text} -> {self.current_mode.value}")

"""
        # 在类中添加方法
        if "class BacktestWidget" in content:
            # 在类的最后一个方法后添加
            content = content.rstrip() + "\n" + handler_code
    
    # 4. 修改回测启动方法传递 mode
    if "mode=self.current_mode" not in content:
        print("  ✓ 修改回测启动方法...")
        # 查找 run_backtest 调用并添加 mode 参数
        if "await self.strategy_service.run_backtest(" in content:
            # 这是一个简化处理，实际可能需要更精确的替换
            print("  ⚠️  需要手动在 run_backtest 调用中添加 mode=self.current_mode")
    else:
        print("  ✓ 回测启动方法已更新")
    
    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ BacktestWidget UI 修改完成")
    return True


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("模式管理集成补丁自动应用工具")
    print("=" * 80)
    
    success_count = 0
    total_count = 2
    
    # 应用补丁
    if patch_strategy_service():
        success_count += 1
    
    if patch_backtest_widget():
        success_count += 1
    
    # 输出结果
    print("\n" + "=" * 80)
    print(f"补丁应用完成：{success_count}/{total_count} 成功")
    print("=" * 80)
    
    if success_count == total_count:
        print("\n✅ 所有补丁已成功应用！")
        print("\n下一步:")
        print("1. 运行编译检查：python -m py_compile core/services/strategy_service.py")
        print("2. 测试功能：启动系统并选择不同模式运行回测")
        print("3. 检查日志：确认模式上下文正确传递")
    else:
        print("\n⚠️  部分补丁应用失败，请检查输出信息")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
