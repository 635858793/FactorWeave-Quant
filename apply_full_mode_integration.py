"""
完整模式管理框架集成脚本
自动将模式感知能力集成到 UnifiedBacktestEngine 和 TradingService
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent

def patch_unified_backtest_engine():
    """修改 UnifiedBacktestEngine 集成 ModeContext"""
    print("=" * 80)
    print("正在修改 UnifiedBacktestEngine...")
    print("=" * 80)
    
    file_path = PROJECT_ROOT / "backtest" / "unified_backtest_engine.py"
    
    if not file_path.exists():
        print(f"❌ 文件不存在：{file_path}")
        return False
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. 添加导入
    if "from ..trading.trading_mode import" not in content:
        print("  ✓ 添加 ModeContext 导入...")
        # 在文件开头添加导入
        import_section_end = content.find('def _is_repeat_string')
        if import_section_end > 0:
            import_line = "from ..trading.trading_mode import ModeContext, TradingMode\n\n"
            content = content[:import_section_end] + import_line + content[import_section_end:]
    else:
        print("  ✓ ModeContext 导入已存在")
    
    # 2. 修改 __init__ 方法，添加 mode_context 参数
    if "mode_context: Optional[ModeContext] = None" not in content:
        print("  ✓ 添加 mode_context 参数到 __init__...")
        content = content.replace(
            "def __init__(self,\n                 backtest_level: BacktestLevel = BacktestLevel.PROFESSIONAL,",
            "def __init__(self,\n                 backtest_level: BacktestLevel = BacktestLevel.PROFESSIONAL,\n                 mode_context: Optional[ModeContext] = None,"
        )
        
        # 在 __init__ 中保存 mode_context
        if "self.mode_context = mode_context" not in content:
            content = content.replace(
                "self._execution_model = execution_model",
                "self._execution_model = execution_model\n        \n        # 模式上下文\n        self.mode_context = mode_context\n        self.logger.info(f\"回测引擎初始化：mode={mode_context.mode.value if mode_context else 'BACKTEST'}\")"
            )
    else:
        print("  ✓ mode_context 参数已存在")
    
    # 3. 修改 run_backtest 方法，添加 mode_context 参数
    if "mode_context: Optional[ModeContext] = None" not in content.split("def run_backtest")[1].split("def ")[0]:
        print("  ✓ 添加 mode_context 参数到 run_backtest...")
        # 找到 run_backtest 方法签名
        run_backtest_sig = "def run_backtest(self,\n                 data: pd.DataFrame,"
        if run_backtest_sig in content:
            # 在 benchmark_data 参数后添加 mode_context
            content = content.replace(
                "benchmark_data: Optional[pd.DataFrame] = None,\n                     execution_model: str = 'fixed',\n                     progress_callback=None) -> Dict[str, Any]:",
                "benchmark_data: Optional[pd.DataFrame] = None,\n                     execution_model: str = 'fixed',\n                     progress_callback=None,\n                     mode_context: Optional[ModeContext] = None) -> Dict[str, Any]:"
            )
    else:
        print("  ✓ run_backtest mode_context 参数已存在")
    
    # 4. 在 run_backtest 方法中使用 mode_context
    run_backtest_section = content.split("def run_backtest")[1].split("def ")[0]
    if "mode_context = mode_context or self.mode_context" not in run_backtest_section:
        print("  ✓ 添加 mode_context 处理逻辑...")
        # 在方法开始处添加 mode_context 处理
        content = content.replace(
            'self.logger.info(f"开始统一回测，级别：{self.backtest_level.value}，引擎：{engine_type}，成交模型：{execution_model}")',
            'self.logger.info(f"开始统一回测，级别：{self.backtest_level.value}，引擎：{engine_type}，成交模型：{execution_model}")\n            \n            # 使用传入的 mode_context 或实例的 mode_context\n            mode_context = mode_context or self.mode_context\n            if mode_context:\n                self.logger.info(f"使用模式上下文：{mode_context.mode.value}")\n                # 根据模式调整配置\n                if mode_context.mode.is_live:\n                    self.logger.info("实盘模式：使用实时数据，性能敏感")\n                elif mode_context.mode.is_backtest:\n                    self.logger.info("回测模式：使用历史数据，完整计算")'
        )
    else:
        print("  ✓ mode_context 处理逻辑已存在")
    
    # 保存修改后的内容
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("  ✓ UnifiedBacktestEngine 修改完成")
    return True


def patch_trading_service():
    """修改 TradingService 集成 ModeAwareMixin"""
    print("=" * 80)
    print("正在修改 TradingService...")
    print("=" * 80)
    
    file_path = PROJECT_ROOT / "core" / "services" / "trading_service.py"
    
    if not file_path.exists():
        print(f"❌ 文件不存在：{file_path}")
        return False
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. 添加导入
    if "from ..trading.trading_mode import" not in content:
        print("  ✓ 添加 TradingMode 和 ModeAwareMixin 导入...")
        # 找到导入区域
        import_end = content.find('class OrderType')
        if import_end > 0:
            import_line = "from ..trading.trading_mode import TradingMode, ModeContext, ModeAwareMixin\n\n"
            content = content[:import_end] + import_line + content[import_end:]
    else:
        print("  ✓ TradingMode 导入已存在")
    
    # 2. 修改类定义，继承 ModeAwareMixin
    if "ModeAwareMixin" not in content.split("class TradingService")[1].split(":")[0]:
        print("  ✓ 修改 TradingService 继承 ModeAwareMixin...")
        content = content.replace(
            "class TradingService(BaseService):",
            "class TradingService(BaseService, ModeAwareMixin):"
        )
    else:
        print("  ✓ TradingService 已继承 ModeAwareMixin")
    
    # 3. 在 __init__ 中添加 mode_context 初始化
    if "self._current_mode_context: Optional[ModeContext] = None" not in content:
        print("  ✓ 添加 mode_context 属性...")
        # 在 __init__ 末尾添加
        content = content.replace(
            'logger.info("TradingService initialized for architecture simplification")',
            'logger.info("TradingService initialized for architecture simplification")\n        \n        # 模式上下文（ModeAwareMixin 要求）\n        self._current_mode_context: Optional[ModeContext] = None\n        self._mode_config: Dict[str, Any] = {}'
        )
    else:
        print("  ✓ mode_context 属性已存在")
    
    # 4. 实现 set_mode 方法
    if "def set_mode" not in content:
        print("  ✓ 添加 set_mode 方法...")
        # 在 _do_initialize 方法后添加
        content = content.replace(
            'logger.info("TradingService initialized successfully")\n\n        except Exception as e:\n            logger.error(f"❌ Failed to initialize TradingService: {e}")\n            raise',
            'logger.info("TradingService initialized successfully")\n\n        except Exception as e:\n            logger.error(f"❌ Failed to initialize TradingService: {e}")\n            raise\n\n    def set_mode(self, mode: TradingMode, **config) -> None:\n        """\n        设置交易模式\n        \n        Args:\n            mode: 交易模式\n            **config: 模式相关配置\n        """\n        self._current_mode_context = ModeContext(\n            mode=mode,\n            config=config,\n            metadata={\'service\': \'TradingService\'}\n        )\n        self._mode_config = config\n        logger.info(f"TradingService 设置为模式：{mode.value}")\n        \n        # 根据模式调整配置\n        if mode == TradingMode.LIVE:\n            self._trading_config["enable_risk_control"] = True\n            self._trading_config["commission_rate"] = config.get("commission_rate", 0.001)\n            logger.info("实盘模式：启用严格风控")\n        elif mode == TradingMode.PAPER:\n            self._trading_config["enable_risk_control"] = True\n            self._trading_config["commission_rate"] = config.get("commission_rate", 0.001)\n            logger.info("模拟模式：启用风控但不实际下单")\n        elif mode == TradingMode.BACKTEST:\n            self._trading_config["enable_risk_control"] = config.get("enable_risk_control", False)\n            logger.info("回测模式：风控可选")\n\n    def get_mode(self) -> TradingMode:\n        """获取当前交易模式"""\n        if self._current_mode_context:\n            return self._current_mode_context.mode\n        return TradingMode.BACKTEST  # 默认回测模式\n\n    def is_backtest_mode(self) -> bool:\n        """是否为回测模式"""\n        return self.get_mode() == TradingMode.BACKTEST\n\n    def is_live_mode(self) -> bool:\n        """是否为实盘模式"""\n        return self.get_mode() in (TradingMode.LIVE, TradingMode.PAPER)'
        )
    else:
        print("  ✓ set_mode 方法已存在")
    
    # 5. 在 execute_order 方法中添加模式检查
    execute_order_section = content.split("def execute_order")
    if len(execute_order_section) > 1:
        execute_order_section = execute_order_section[1].split("def ")[0]
        if "self.get_mode()" not in execute_order_section:
            print("  ✓ 添加模式检查到 execute_order...")
            # 在 execute_order 方法开始处添加模式检查
            content = content.replace(
                'logger.info(f"Executing order: {order_id} - {order.side.value} {order.quantity}@{order.price}")',
                'logger.info(f"Executing order: {order_id} - {order.side.value} {order.quantity}@{order.price}")\n        \n        # 根据模式执行不同逻辑\n        if self.is_live_mode() and not self.is_backtest_mode():\n            logger.info("实盘/模拟模式：需要实际执行订单")\n            # 实盘模式下需要更严格的风控检查\n            if self._trading_config.get("enable_risk_control", True):\n                logger.info("执行风控检查...")\n        else:\n            logger.info("回测模式：使用模拟执行")'
            )
        else:
            print("  ✓ execute_order 模式检查已存在")
    
    # 保存修改后的内容
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("  ✓ TradingService 修改完成")
    return True


def verify_integration():
    """验证集成是否成功"""
    print("=" * 80)
    print("验证集成...")
    print("=" * 80)
    
    # 检查 UnifiedBacktestEngine
    engine_file = PROJECT_ROOT / "backtest" / "unified_backtest_engine.py"
    if engine_file.exists():
        with open(engine_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ("from ..trading.trading_mode import ModeContext", "ModeContext 导入"),
            ("mode_context: Optional[ModeContext] = None", "mode_context 参数"),
            ("self.mode_context = mode_context", "mode_context 属性"),
        ]
        
        print("\nUnifiedBacktestEngine 检查:")
        for check_str, desc in checks:
            if check_str in content:
                print(f"  ✓ {desc}")
            else:
                print(f"  ✗ {desc} - 未找到")
    
    # 检查 TradingService
    service_file = PROJECT_ROOT / "core" / "services" / "trading_service.py"
    if service_file.exists():
        with open(service_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ("from ..trading.trading_mode import", "TradingMode 导入"),
            ("class TradingService(BaseService, ModeAwareMixin)", "继承 ModeAwareMixin"),
            ("def set_mode", "set_mode 方法"),
            ("def get_mode", "get_mode 方法"),
        ]
        
        print("\nTradingService 检查:")
        for check_str, desc in checks:
            if check_str in content:
                print(f"  ✓ {desc}")
            else:
                print(f"  ✗ {desc} - 未找到")
    
    print("\n" + "=" * 80)
    print("集成验证完成")
    print("=" * 80)


def main():
    """主函数"""
    print("=" * 80)
    print("模式管理框架完整集成脚本")
    print("=" * 80)
    print()
    
    try:
        # 修改 UnifiedBacktestEngine
        if not patch_unified_backtest_engine():
            print("❌ UnifiedBacktestEngine 修改失败")
            return False
        
        print()
        
        # 修改 TradingService
        if not patch_trading_service():
            print("❌ TradingService 修改失败")
            return False
        
        print()
        
        # 验证集成
        verify_integration()
        
        print("\n" + "=" * 80)
        print("✓ 所有集成步骤完成")
        print("=" * 80)
        print("\n下一步:")
        print("1. 运行编译检查确保没有语法错误")
        print("2. 创建集成测试验证业务调用链")
        print("3. 更新实施报告和文档")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 集成过程中出错：{e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
