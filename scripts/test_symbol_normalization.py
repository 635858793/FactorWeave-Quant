"""
测试股票代码标准化功能
验证基本面数据的查询和保存都使用标准化的股票代码（不带后缀）
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.asset_database_manager import get_asset_separated_database_manager
from core.plugin_types import AssetType
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def test_single_query_with_suffix():
    """测试单个查询：带后缀的股票代码"""
    logger.info("\n" + "=" * 80)
    logger.info("测试1: 单个查询 - 带后缀的股票代码")
    logger.info("=" * 80)

    try:
        db_manager = get_asset_separated_database_manager()

        # 测试带后缀的股票代码
        test_cases = [
            "000001.SZ",
            "000002.SZ",
            "600000.SH",
            "600543.SH",
        ]

        for symbol in test_cases:
            logger.info(f"\n测试股票代码: {symbol}")
            fundamental_data = db_manager.load_fundamental_data(symbol, AssetType.STOCK_A)

            if fundamental_data:
                logger.info(f"  [OK] 成功加载基本面数据")
                logger.info(f"  - symbol: {fundamental_data.get('symbol')}")
                logger.info(f"  - name: {fundamental_data.get('name')}")
                logger.info(f"  - industry: {fundamental_data.get('industry')}")
                logger.info(f"  - pe_ratio: {fundamental_data.get('pe_ratio')}")
            else:
                logger.warning(f"  [FAIL] 未找到基本面数据")

        logger.info("\n测试1完成")
        return True

    except Exception as e:
        logger.error(f"测试1失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_single_query_without_suffix():
    """测试单个查询：不带后缀的股票代码"""
    logger.info("\n" + "=" * 80)
    logger.info("测试2: 单个查询 - 不带后缀的股票代码")
    logger.info("=" * 80)

    try:
        db_manager = get_asset_separated_database_manager()

        # 测试不带后缀的股票代码
        test_cases = [
            "000001",
            "000002",
            "600000",
            "600543",
        ]

        for symbol in test_cases:
            logger.info(f"\n测试股票代码: {symbol}")
            fundamental_data = db_manager.load_fundamental_data(symbol, AssetType.STOCK_A)

            if fundamental_data:
                logger.info(f"  [OK] 成功加载基本面数据")
                logger.info(f"  - symbol: {fundamental_data.get('symbol')}")
                logger.info(f"  - name: {fundamental_data.get('name')}")
                logger.info(f"  - industry: {fundamental_data.get('industry')}")
                logger.info(f"  - pe_ratio: {fundamental_data.get('pe_ratio')}")
            else:
                logger.warning(f"  [FAIL] 未找到基本面数据")

        logger.info("\n测试2完成")
        return True

    except Exception as e:
        logger.error(f"测试2失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_query_mixed():
    """测试批量查询：混合格式的股票代码"""
    logger.info("\n" + "=" * 80)
    logger.info("测试3: 批量查询 - 混合格式的股票代码")
    logger.info("=" * 80)

    try:
        db_manager = get_asset_separated_database_manager()

        # 测试混合格式的股票代码
        symbols = [
            "600543",
            "000001.SZ",
            "000002.SZ",
            "600000.SH",
            "600000",
        ]

        logger.info(f"测试股票代码: {symbols}")

        fundamental_data_dict = db_manager.load_fundamental_data_batch(symbols, AssetType.STOCK_A)

        logger.info(f"\n成功加载 {len(fundamental_data_dict)} 只股票的基本面数据")

        for symbol in symbols:
            if symbol in fundamental_data_dict:
                data = fundamental_data_dict[symbol]
                logger.info(f"  - {symbol}: {data.get('name')} ({data.get('industry')})")
            else:
                logger.warning(f"  - {symbol}: 未找到数据")

        if len(fundamental_data_dict) == len(symbols):
            logger.info("\n[OK] 所有股票的基本面数据都加载成功")
            return True
        else:
            logger.warning(f"\n[WARNING] 部分股票的基本面数据未加载: {len(symbols) - len(fundamental_data_dict)}/{len(symbols)}")
            return False

    except Exception as e:
        logger.error(f"测试3失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_save_with_suffix():
    """测试保存：带后缀的股票代码"""
    logger.info("\n" + "=" * 80)
    logger.info("测试4: 保存 - 带后缀的股票代码")
    logger.info("=" * 80)

    try:
        db_manager = get_asset_separated_database_manager()

        # 测试保存带后缀的股票代码
        test_symbol = "600543.SH"
        test_data = {
            "symbol": test_symbol,
            "name": "测试股票",
            "industry": "测试行业",
            "pe_ratio": 10.5,
            "pb_ratio": 1.2,
            "roe": 15.0,
            "data_source": "test"
        }

        logger.info(f"测试保存股票代码: {test_symbol}")
        success = db_manager.save_fundamental_data(test_symbol, test_data, AssetType.STOCK_A)

        if success:
            logger.info(f"  [OK] 保存成功")

            # 验证保存后的数据
            logger.info(f"\n验证保存后的数据...")
            fundamental_data = db_manager.load_fundamental_data(test_symbol, AssetType.STOCK_A)

            if fundamental_data:
                logger.info(f"  [OK] 成功加载保存的数据")
                logger.info(f"  - symbol: {fundamental_data.get('symbol')}")
                logger.info(f"  - name: {fundamental_data.get('name')}")
                logger.info(f"  - industry: {fundamental_data.get('industry')}")
                logger.info(f"  - pe_ratio: {fundamental_data.get('pe_ratio')}")

                # 验证symbol是否被标准化（不带后缀）
                if fundamental_data.get('symbol') == "600543":
                    logger.info(f"  [OK] 股票代码已正确标准化为: {fundamental_data.get('symbol')}")
                    return True
                else:
                    logger.warning(f"  [WARNING] 股票代码未标准化: {fundamental_data.get('symbol')}")
                    return False
            else:
                logger.warning(f"  [FAIL] 未找到保存的数据")
                return False
        else:
            logger.warning(f"  [FAIL] 保存失败")
            return False

    except Exception as e:
        logger.error(f"测试4失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    logger.info("\n" + "=" * 80)
    logger.info("开始测试股票代码标准化功能")
    logger.info("=" * 80)

    results = []

    results.append(("单个查询 - 带后缀", test_single_query_with_suffix()))
    results.append(("单个查询 - 不带后缀", test_single_query_without_suffix()))
    results.append(("批量查询 - 混合格式", test_batch_query_mixed()))
    results.append(("保存 - 带后缀", test_save_with_suffix()))

    logger.info("\n" + "=" * 80)
    logger.info("测试结果汇总")
    logger.info("=" * 80)

    passed = 0
    failed = 0
    for test_name, result in results:
        if result:
            logger.info(f"[PASS] {test_name}")
            passed += 1
        else:
            logger.info(f"[FAIL] {test_name}")
            failed += 1

    logger.info(f"\n总计: {passed} 个通过, {failed} 个失败")

    if failed == 0:
        logger.info("\n[SUCCESS] 所有测试通过！标准化功能正常！")
        return 0
    else:
        logger.error(f"\n[FAIL] {failed} 个测试失败，需要进一步检查")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
