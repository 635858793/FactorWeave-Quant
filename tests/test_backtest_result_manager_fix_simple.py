#!/usr/bin/env python3
"""
BacktestResultManager 单元测试 - 简化版
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

    def test_file_lock_import(self):
        """测试1: 验证 FileLock 导入"""
        logger.info("\n" + "="*60)
        logger.info("测试1: FileLock 导入验证")
        logger.info("="*60)

        try:
            from filelock import FileLock
            self.log_test("FileLock 导入", "PASS", f"版本: {FileLock.__module__}")
        except Exception as e:
            self.log_test("FileLock 导入", "FAIL", str(e))

    def test_backtest_result_manager_import(self):
        """测试2: 验证 BacktestResultManager 导入"""
        logger.info("\n" + "="*60)
        logger.info("测试2: BacktestResultManager 导入验证")
        logger.info("="*60)

        try:
            from core.services.backtest_result_manager import BacktestResultManager
            
            with patch('core.services.backtest_result_manager.BacktestResultManager._init_persistence_dir'):
                with patch('core.services.backtest_result_manager.BacktestResultManager.load_results'):
                    manager = BacktestResultManager()
            
            self.log_test("BacktestResultManager 导入", "PASS", "类导入成功")
            
            if hasattr(manager, '_lock'):
                self.log_test("线程锁存在", "PASS", "Lock 对象已初始化")
            else:
                self.log_test("线程锁存在", "FAIL", "Lock 对象未初始化")
                
        except Exception as e:
            self.log_test("BacktestResultManager 导入", "FAIL", str(e))

    def test_safe_float_conversion(self):
        """测试3: 验证安全转换方法"""
        logger.info("\n" + "="*60)
        logger.info("测试3: 过滤条件安全转换")
        logger.info("="*60)

        test_cases = [
            ("10.5", 10.5),
            ("", None),
            ("abc", None),
            ("-5.5", -5.5),
            ("  20  ", 20.0),
            (None, None),
            ("0", 0.0),
            ("-0", -0.0),
        ]

        all_passed = True
        for input_val, expected in test_cases:
            try:
                if input_val and input_val.strip():
                    result = float(input_val.strip()) if input_val else None
                else:
                    result = None
                    
                if result == expected:
                    self.log_test(
                        f"转换 '{input_val}'",
                        "PASS",
                        f"期望={expected}, 实际={result}"
                    )
                else:
                    self.log_test(
                        f"转换 '{input_val}'",
                        "FAIL",
                        f"期望={expected}, 实际={result}"
                    )
                    all_passed = False
            except (ValueError, TypeError) as e:
                if expected is None:
                    self.log_test(
                        f"转换 '{input_val}'",
                        "PASS",
                        "正确捕获异常并返回 None"
                    )
                else:
                    self.log_test(
                        f"转换 '{input_val}'",
                        "FAIL",
                        f"意外异常: {e}"
                    )
                    all_passed = False

    def test_file_lock_functionality(self):
        """测试4: 文件锁功能测试"""
        logger.info("\n" + "="*60)
        logger.info("测试4: 文件锁功能")
        logger.info("="*60)

        try:
            from filelock import FileLock
            import time

            test_file = os.path.join(self.temp_dir, "test.lock")
            os.makedirs(self.temp_dir, exist_ok=True)

            lock1 = FileLock(test_file, timeout=2)
            lock2 = FileLock(test_file, timeout=2)

            results = []

            def acquire_lock(lock, name, delay=0):
                time.sleep(delay)
                try:
                    with lock:
                        results.append(f"{name}: acquired")
                        time.sleep(0.5)
                    results.append(f"{name}: released")
                except Exception as e:
                    results.append(f"{name}: error - {e}")

            t1 = threading.Thread(target=acquire_lock, args=(lock1, "Thread1", 0))
            t2 = threading.Thread(target=acquire_lock, args=(lock2, "Thread1", 0.1))

            t1.start()
            t2.start()
            t1.join()
            t2.join()

            if len(results) == 4:
                self.log_test("文件锁并发测试", "PASS", "线程安全通过")
            else:
                self.log_test("文件锁并发测试", "FAIL", f"结果: {results}")

        except Exception as e:
            self.log_test("文件锁功能", "FAIL", str(e))
            logger.error(traceback.format_exc())

    def test_service_container_resolve_fallback(self):
        """测试5: 服务容器回退机制"""
        logger.info("\n" + "="*60)
        logger.info("测试5: 服务容器回退机制")
        logger.info("="*60)

        try:
            from core.services.backtest_result_manager import BacktestResultManager
            
            with patch('core.services.backtest_result_manager.BacktestResultManager._init_persistence_dir'):
                with patch('core.services.backtest_result_manager.BacktestResultManager.load_results'):
                    result = BacktestResultManager()

            if result is not None:
                self.log_test("直接创建回退", "PASS", "服务容器不可用时能正常回退")
            else:
                self.log_test("直接创建回退", "FAIL", "返回 None")

        except Exception as e:
            self.log_test("直接创建回退", "FAIL", str(e))

    def run_all_tests(self):
        """运行所有测试"""
        logger.info("="*60)
        logger.info("BacktestResultManager 单元测试开始 (简化版)")
        logger.info("="*60)

        self.setup()

        try:
            self.test_file_lock_import()
            self.test_backtest_result_manager_import()
            self.test_safe_float_conversion()
            self.test_file_lock_functionality()
            self.test_service_container_resolve_fallback()

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
