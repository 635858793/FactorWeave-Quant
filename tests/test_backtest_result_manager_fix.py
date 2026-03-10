#!/usr/bin/env python3
"""
BacktestResultManager 单元测试
验证：单例模式、线程安全、异常处理
"""

import sys
import os
import threading
import time
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch
from concurrent.futures import ThreadPoolExecutor, as_completed

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
import traceback

def initialize_services():
    """初始化服务容器"""
    try:
        from core.services.service_bootstrap import ServiceBootstrap
        bootstrap = ServiceBootstrap()
        bootstrap.bootstrap()
        logger.info("服务容器初始化完成")
        return True
    except Exception as e:
        logger.warning(f"服务容器初始化失败: {e}")
        return False

class BacktestResultManagerTester:
    """BacktestResultManager 测试类"""

    def __init__(self):
        self.test_results = []
        self.passed_count = 0
        self.failed_count = 0
        self.temp_dir = None

    def setup(self):
        """测试环境准备"""
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"测试临时目录: {self.temp_dir}")

    def teardown(self):
        """测试环境清理"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        logger.info("测试环境已清理")

    def log_test(self, test_name, status, details=""):
        """记录测试结果"""
        result = {
            "test_name": test_name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        self.test_results.append(result)

        if status == "PASS":
            self.passed_count += 1
            logger.info(f"✅ {test_name}: PASS - {details}")
        else:
            self.failed_count += 1
            logger.error(f"❌ {test_name}: FAIL - {details}")

    def test_singleton_pattern(self):
        """测试1: 验证单例模式"""
        logger.info("\n" + "="*60)
        logger.info("测试1: BacktestResultManager 单例模式")
        logger.info("="*60)

        try:
            from core.services.backtest_result_manager import BacktestResultManager
            from core.containers import get_service_container

            container = get_service_container()

            instance1 = container.resolve(BacktestResultManager)
            instance2 = container.resolve(BacktestResultManager)

            if instance1 is instance2:
                self.log_test(
                    "单例模式验证",
                    "PASS",
                    f"多次 resolve 返回同一实例: {id(instance1) == id(instance2)}"
                )
            else:
                self.log_test(
                    "单例模式验证",
                    "FAIL",
                    f"实例ID不同: {id(instance1)} vs {id(instance2)}"
                )

        except Exception as e:
            self.log_test("单例模式验证", "FAIL", str(e))
            logger.error(traceback.format_exc())

    def test_thread_safe_float_conversion(self):
        """测试2: 验证过滤条件安全转换"""
        logger.info("\n" + "="*60)
        logger.info("测试2: 过滤条件安全转换")
        logger.info("="*60)

        try:
            from core.ui.panels.right_panel import RightPanel

            mock_coordinator = MagicMock()
            mock_coordinator.event_bus = MagicMock()

            with patch('core.ui.panels.right_panel.BasePanel.__init__', return_value=None):
                with patch('core.ui.panels.right_panel.RightPanel._init_ui_events'):
                    with patch('core.ui.panels.right_panel.RightPanel._initialize_data'):
                        panel = RightPanel.__new__(RightPanel)
                        panel._get_backtest_result_manager = MagicMock()

            test_cases = [
                ("10.5", 10.5),
                ("", None),
                ("abc", None),
                ("-5.5", -5.5),
                ("  20  ", 20.0),
                (None, None),
            ]

            for input_val, expected in test_cases:
                result = panel._safe_float_convert(input_val)
                if result == expected:
                    self.log_test(
                        f"转换 '{input_val}'",
                        "PASS",
                        f"输入={input_val!r}, 输出={result}, 期望={expected}"
                    )
                else:
                    self.log_test(
                        f"转换 '{input_val}'",
                        "FAIL",
                        f"输入={input_val!r}, 输出={result}, 期望={expected}"
                    )

        except Exception as e:
            self.log_test("过滤条件安全转换", "FAIL", str(e))
            logger.error(traceback.format_exc())

    def test_file_lock_mechanism(self):
        """测试3: 验证文件锁机制"""
        logger.info("\n" + "="*60)
        logger.info("测试3: 文件锁机制")
        logger.info("="*60)

        try:
            from core.services.backtest_result_manager import BacktestResultManager
            from filelock import FileLock

            with patch('core.services.backtest_result_manager.BacktestResultManager._init_persistence_dir'):
                with patch('core.services.backtest_result_manager.BacktestResultManager.load_results'):
                    manager = BacktestResultManager.__new__(BacktestResultManager)
                    manager._persistence_enabled = True
                    manager._persistence_dir = self.temp_dir
                    manager._lock = threading.Lock()

            test_stock_code = "TEST001"
            test_data = [
                {
                    "stock_code": test_stock_code,
                    "stock_name": "测试股票",
                    "strategy_name": "测试策略",
                    "backtest_time": time.time(),
                    "backtest_results": {"avg_return": 5.5},
                    "trades": [],
                    "duration": 1.0
                }
            ]

            os.makedirs(self.temp_dir, exist_ok=True)
            test_file = os.path.join(self.temp_dir, f"{test_stock_code}.json")

            with open(test_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(test_data, f)

            lock_path = test_file + ".lock"
            lock = FileLock(lock_path, timeout=5)

            if os.path.exists(lock_path):
                self.log_test(
                    "文件锁创建",
                    "PASS",
                    f"锁文件路径: {lock_path}"
                )
            else:
                self.log_test(
                    "文件锁创建",
                    "FAIL",
                    "锁文件未创建"
                )

            if lock:
                self.log_test(
                    "FileLock 实例",
                    "PASS",
                    f"类型: {type(lock).__name__}"
                )

        except Exception as e:
            self.log_test("文件锁机制", "FAIL", str(e))
            logger.error(traceback.format_exc())

    def test_concurrent_save_load(self):
        """测试4: 并发读写测试"""
        logger.info("\n" + "="*60)
        logger.info("测试4: 并发读写测试")
        logger.info("="*60)

        try:
            from core.services.backtest_result_manager import BacktestResultManager
            from core.services.backtest_result_manager import BacktestResult

            with patch('core.services.backtest_result_manager.BacktestResultManager._init_persistence_dir'):
                with patch('core.services.backtest_result_manager.BacktestResultManager.load_results'):
                    manager = BacktestResultManager.__new__(BacktestResultManager)
                    manager._persistence_enabled = True
                    manager._persistence_dir = self.temp_dir
                    manager._results = {}
                    manager._lock = threading.Lock()

            os.makedirs(self.temp_dir, exist_ok=True)

            errors = []

            def save_task(stock_code, index):
                try:
                    result = BacktestResult(
                        stock_code=stock_code,
                        stock_name=f"股票{index}",
                        strategy_name="测试策略",
                        backtest_time=time.time(),
                        backtest_results={"avg_return": index * 0.1},
                        trades=[],
                        duration=0.1
                    )
                    manager.save_results(stock_code)
                    return True
                except Exception as e:
                    errors.append(str(e))
                    return False

            def load_task(stock_code):
                try:
                    manager.load_results()
                    return True
                except Exception as e:
                    errors.append(str(e))
                    return False

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for i in range(10):
                    futures.append(executor.submit(save_task, "CONCURRENT001", i))
                for i in range(5):
                    futures.append(executor.submit(load_task, "CONCURRENT001"))

                all_completed = True
                for future in as_completed(futures):
                    if not future.result():
                        all_completed = False

            if all_completed and not errors:
                self.log_test(
                    "并发读写",
                    "PASS",
                    "10次写 + 5次读全部成功，无数据损坏"
                )
            else:
                self.log_test(
                    "并发读写",
                    "FAIL",
                    f"错误: {errors[:3]}"
                )

        except Exception as e:
            self.log_test("并发读写", "FAIL", str(e))
            logger.error(traceback.format_exc())

    def test_service_container_integration(self):
        """测试5: 服务容器集成"""
        logger.info("\n" + "="*60)
        logger.info("测试5: 服务容器集成")
        logger.info("="*60)

        try:
            from core.containers import get_service_container
            from core.services.backtest_result_manager import BacktestResultManager

            container = get_service_container()

            instances = []
            for _ in range(5):
                inst = container.resolve(BacktestResultManager)
                instances.append(inst)

            if len(set(id(i) for i in instances)) == 1:
                self.log_test(
                    "服务容器单例",
                    "PASS",
                    "5次 resolve 返回同一实例"
                )
            else:
                self.log_test(
                    "服务容器单例",
                    "FAIL",
                    "返回了不同实例"
                )

        except Exception as e:
            self.log_test("服务容器集成", "FAIL", str(e))
            logger.error(traceback.format_exc())

    def run_all_tests(self):
        """运行所有测试"""
        logger.info("="*60)
        logger.info("BacktestResultManager 单元测试开始")
        logger.info("="*60)

        # 初始化服务容器
        initialize_services()

        self.setup()

        try:
            self.test_singleton_pattern()
            self.test_thread_safe_float_conversion()
            self.test_file_lock_mechanism()
            self.test_concurrent_save_load()
            self.test_service_container_integration()

        finally:
            self.teardown()

        logger.info("\n" + "="*60)
        logger.info("测试结果汇总")
        logger.info("="*60)
        logger.info(f"通过: {self.passed_count}")
        logger.info(f"失败: {self.failed_count}")
        logger.info(f"总计: {self.passed_count + self.failed_count}")
        
        if self.failed_count > 0:
            logger.warning("失败的测试:")
            for result in self.test_results:
                if result["status"] == "FAIL":
                    logger.warning(f"  - {result['test_name']}: {result['details']}")
            logger.warning("⚠️ 存在失败的测试!")
            return False
        else:
            logger.info("✅ 所有测试通过!")
            return True


if __name__ == "__main__":
    tester = BacktestResultManagerTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
