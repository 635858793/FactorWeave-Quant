"""
资产数据 Fallback 加载器

统一处理各资产类型的降级数据加载，提供多层数据源 fallback 机制：
1. 服务组件（如 StockService）
2. DuckDB 数据库
3. 外部 API（针对特定资产类型）

支持资产类型：
- 股票（STOCK_A, STOCK_B, STOCK_H, STOCK_US, STOCK_HK）
- 指数（INDEX）
- 基金（FUND）
- 债券（BOND）
- 加密货币（CRYPTO）
- 期货（FUTURES）
- 外汇（FOREX）
- 期权（OPTION）
- 涡轮（WARRANT）
- 大宗商品（COMMODITY）
- 行业板块（INDUSTRY_SECTOR）
- 概念板块（CONCEPT_SECTOR）
- 风格板块（STYLE_SECTOR）
- 主题板块（THEME_SECTOR）
"""

import pandas as pd
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger

try:
    from ..plugin_types import AssetType
except ImportError:
    from core.plugin_types import AssetType


class AssetFallbackLoader:
    """资产数据 Fallback 加载器 - 统一处理各资产类型的降级数据加载"""

    def __init__(self,
                 duckdb_manager=None,
                 stock_service=None,
                 index_service=None,
                 fund_service=None,
                 bond_service=None,
                 crypto_api_config: Dict[str, Any] = None):
        """
        初始化 Fallback 加载器

        Args:
            duckdb_manager: DuckDB 连接管理器
            stock_service: 股票服务（用于获取股票列表）
            index_service: 指数服务
            fund_service: 基金服务
            bond_service: 债券服务
            crypto_api_config: 加密货币 API 配置
        """
        self.duckdb_manager = duckdb_manager
        self.stock_service = stock_service
        self.index_service = index_service
        self.fund_service = fund_service
        self.bond_service = bond_service
        self.crypto_api_config = crypto_api_config or {
            'provider': 'binance',
            'enabled': False,
            'api_key': None,
            'api_secret': None
        }

        # API 端点配置
        self._api_endpoints = {
            'binance': {
                'spot': 'https://api.binance.com/api/v3/ticker/allTickers',
                'futures': 'https://fapi.binance.com/fapi/v1/ticker/allPrices'
            },
            'coingecko': {
                'coins': 'https://api.coingecko.com/api/v3/coins/markets',
                'search': 'https://api.coingecko.com/api/v3/search'
            }
        }

        # 缓存 HTTP session
        self._http_session = None

    def get_asset_list(self,
                       asset_type: AssetType,
                       market: str = None,
                       **filters) -> pd.DataFrame:
        """
        获取资产列表的统一入口

        Args:
            asset_type: 资产类型
            market: 市场代码
            **filters: 其他过滤条件

        Returns:
            DataFrame: 资产列表数据
        """
        method_name = f"_get_{asset_type.value.lower()}_asset_list"
        method = getattr(self, method_name, self._get_default_asset_list)
        return method(asset_type, market, **filters)

    def _get_default_asset_list(self,
                                 asset_type: AssetType,
                                 market: str = None,
                                 **filters) -> pd.DataFrame:
        """默认资产列表获取方法"""
        logger.warning(f"未找到 {asset_type.value} 资产类型的获取方法，返回空 DataFrame")
        return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def _get_stock_a_asset_list(self,
                                 asset_type: AssetType,
                                 market: str = None,
                                 **filters) -> pd.DataFrame:
        """获取 A 股资产列表"""
        return self._get_stock_asset_list(asset_type, market, ['SH', 'SZ', 'CSI', 'A'])

    def _get_stock_b_asset_list(self,
                                 asset_type: AssetType,
                                 market: str = None,
                                 **filters) -> pd.DataFrame:
        """获取 B 股资产列表"""
        return self._get_stock_asset_list(asset_type, market, ['B'])

    def _get_stock_h_asset_list(self,
                                 asset_type: AssetType,
                                 market: str = None,
                                 **filters) -> pd.DataFrame:
        """获取 H 股资产列表"""
        return self._get_stock_asset_list(asset_type, market, ['HK', 'HKEX', 'H股'])

    def _get_stock_us_asset_list(self,
                                  asset_type: AssetType,
                                  market: str = None,
                                  **filters) -> pd.DataFrame:
        """获取美股资产列表"""
        return self._get_stock_asset_list(asset_type, market, ['US', 'NASDAQ', 'NYSE', 'AMEX', '美股'])

    def _get_stock_hk_asset_list(self,
                                  asset_type: AssetType,
                                  market: str = None,
                                  **filters) -> pd.DataFrame:
        """获取港股资产列表"""
        return self._get_stock_asset_list(asset_type, market, ['HK', 'HKEX', '港股'])

    def _get_stock_asset_list(self,
                               asset_type: AssetType,
                               market: str = None,
                               valid_markets: List[str] = None) -> pd.DataFrame:
        """获取股票资产列表 - 通用实现"""
        try:
            # 1. 优先使用 StockService
            if self.stock_service is not None:
                if hasattr(self.stock_service, 'get_stock_list'):
                    # R244-P0-2 修复: StockService 初始化期间(_do_initialize → _load_stock_list
                    # → DataAccess → StockRepository → data_manager.get_stock_list)会自我调用
                    # 回同一尚未初始化完成的实例并抛 "Service StockService is not initialized"。
                    # 未初始化完成时跳过服务路径，走 DuckDB/空后备，初始化完成后自动恢复。
                    if not getattr(self.stock_service, '_initialized', False):
                        logger.debug("StockService 尚未初始化完成，跳过服务路径，尝试从 DuckDB 获取")
                    else:
                        stock_list = self.stock_service.get_stock_list()
                        if stock_list is not None and not stock_list.empty:
                            df = stock_list.copy()

                            # 重命名列
                            if 'symbol' in df.columns and 'code' not in df.columns:
                                df['code'] = df['symbol']

                            # 添加 asset_type 列
                            df['asset_type'] = asset_type.value

                            # 过滤市场
                            if valid_markets and 'market' in df.columns:
                                df['market'] = df['market'].astype(str).str.upper().str.strip()
                                df = df[df['market'].isin(valid_markets)]

                            logger.debug(f"从 StockService 获取 {asset_type.value} 资产列表: {len(df)} 条")
                            return df

            # 2. 尝试从 DuckDB 获取
            if self.duckdb_manager is not None:
                try:
                    db_path = self.duckdb_manager.get_database_path(asset_type) if hasattr(self.duckdb_manager, 'get_database_path') else None
                    if db_path:
                        query = "SELECT * FROM asset_metadata WHERE asset_type = ?"
                        params = [asset_type.value]
                        if market:
                            query += " AND market = ?"
                            params.append(market.upper())

                        result = self._query_duckdb(db_path, query, params)
                        if result is not None and not result.empty:
                            logger.debug(f"从 DuckDB 获取 {asset_type.value} 资产列表: {len(result)} 条")
                            return result
                except Exception as e:
                    logger.warning(f"⚠️ 从 DuckDB 获取 {asset_type.value} 资产列表失败: {e}")

            # 3. 返回空 DataFrame
            logger.warning(f"⚠️ 无法获取 {asset_type.value} 资产列表，所有数据源均不可用")
            return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

        except Exception as e:
            logger.error(f"❌ 获取 {asset_type.value} 资产列表失败: {e}")
            return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def _get_index_asset_list(self,
                               asset_type: AssetType,
                               market: str = None,
                               **filters) -> pd.DataFrame:
        """获取指数资产列表"""
        try:
            # 1. 尝试使用 IndexService
            if self.index_service is not None:
                if hasattr(self.index_service, 'get_index_list'):
                    index_list = self.index_service.get_index_list()
                    if index_list is not None and not index_list.empty:
                        df = index_list.copy()
                        df['asset_type'] = asset_type.value
                        logger.debug(f"从 IndexService 获取指数资产列表: {len(df)} 条")
                        return df

            # 2. 尝试从 DuckDB 获取
            if self.duckdb_manager is not None:
                try:
                    db_path = self.duckdb_manager.get_database_path(asset_type) if hasattr(self.duckdb_manager, 'get_database_path') else None
                    if db_path:
                        query = "SELECT * FROM asset_metadata WHERE asset_type = ?"
                        result = self._query_duckdb(db_path, query, ['index'])
                        if result is not None and not result.empty:
                            logger.debug(f"从 DuckDB 获取指数资产列表: {len(result)} 条")
                            return result
                except Exception as e:
                    logger.warning(f"⚠️ 从 DuckDB 获取指数资产列表失败: {e}")

            # 3. 返回内置的常用指数列表
            return self._get_common_indexes()

        except Exception as e:
            logger.error(f"❌ 获取指数资产列表失败: {e}")
            return self._get_common_indexes()

    def _get_common_indexes(self) -> pd.DataFrame:
        """获取常用指数列表（内置备用数据）"""
        common_indexes = [
            {'code': '000001', 'name': '上证指数', 'market': 'SH', 'industry': '大盘指数', 'sector': 'index'},
            {'code': '399001', 'name': '深证成指', 'market': 'SZ', 'industry': '大盘指数', 'sector': 'index'},
            {'code': '399006', 'name': '创业板指', 'market': 'SZ', 'industry': '大盘指数', 'sector': 'index'},
            {'code': '000300', 'name': '沪深300', 'market': 'SH', 'industry': '大盘指数', 'sector': 'index'},
            {'code': '000016', 'name': '上证50', 'market': 'SH', 'industry': '大盘指数', 'sector': 'index'},
            {'code': '000010', 'name': '上证180', 'market': 'SH', 'industry': '大盘指数', 'sector': 'index'},
            {'code': '399005', 'name': '中小板指', 'market': 'SZ', 'industry': '大盘指数', 'sector': 'index'},
            {'code': '000852', 'name': '中证1000', 'market': 'SH', 'industry': '大盘指数', 'sector': 'index'},
            {'code': '399106', 'name': '深证综指', 'market': 'SZ', 'industry': '大盘指数', 'sector': 'index'},
            {'code': '000905', 'name': '中证500', 'market': 'SH', 'industry': '大盘指数', 'sector': 'index'},
        ]
        df = pd.DataFrame(common_indexes)
        df['asset_type'] = 'index'
        df['list_date'] = None
        df['status'] = 'active'
        logger.info(f"📦 返回内置常用指数列表: {len(df)} 条")
        return df

    def _get_fund_asset_list(self,
                              asset_type: AssetType,
                              market: str = None,
                              **filters) -> pd.DataFrame:
        """获取基金资产列表"""
        try:
            # 1. 尝试使用 FundService
            if self.fund_service is not None:
                if hasattr(self.fund_service, 'get_fund_list'):
                    fund_list = self.fund_service.get_fund_list()
                    if fund_list is not None and not fund_list.empty:
                        df = fund_list.copy()
                        df['asset_type'] = asset_type.value
                        logger.debug(f"从 FundService 获取基金资产列表: {len(df)} 条")
                        return df

            # 2. 尝试从 DuckDB 获取
            if self.duckdb_manager is not None:
                try:
                    db_path = self.duckdb_manager.get_database_path(asset_type) if hasattr(self.duckdb_manager, 'get_database_path') else None
                    if db_path:
                        query = "SELECT * FROM asset_metadata WHERE asset_type = ?"
                        result = self._query_duckdb(db_path, query, ['fund'])
                        if result is not None and not result.empty:
                            logger.debug(f"从 DuckDB 获取基金资产列表: {len(result)} 条")
                            return result
                except Exception as e:
                    logger.warning(f"⚠️ 从 DuckDB 获取基金资产列表失败: {e}")

            # 3. 返回内置的常用基金列表
            return self._get_common_funds()

        except Exception as e:
            logger.error(f"❌ 获取基金资产列表失败: {e}")
            return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def _get_bond_asset_list(self,
                              asset_type: AssetType,
                              market: str = None,
                              **filters) -> pd.DataFrame:
        """获取债券资产列表"""
        try:
            # 1. 尝试使用 BondService
            if self.bond_service is not None:
                if hasattr(self.bond_service, 'get_bond_list'):
                    bond_list = self.bond_service.get_bond_list()
                    if bond_list is not None and not bond_list.empty:
                        df = bond_list.copy()
                        df['asset_type'] = asset_type.value
                        logger.debug(f"从 BondService 获取债券资产列表: {len(df)} 条")
                        return df

            # 2. 尝试从 DuckDB 获取
            if self.duckdb_manager is not None:
                try:
                    db_path = self.duckdb_manager.get_database_path(asset_type) if hasattr(self.duckdb_manager, 'get_database_path') else None
                    if db_path:
                        query = "SELECT * FROM asset_metadata WHERE asset_type = ?"
                        result = self._query_duckdb(db_path, query, ['bond'])
                        if result is not None and not result.empty:
                            logger.debug(f"从 DuckDB 获取债券资产列表: {len(result)} 条")
                            return result
                except Exception as e:
                    logger.warning(f"⚠️ 从 DuckDB 获取债券资产列表失败: {e}")

            # 3. 返回内置的常用债券列表
            return self._get_common_bonds()

        except Exception as e:
            logger.error(f"❌ 获取债券资产列表失败: {e}")
            return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def _get_crypto_asset_list(self,
                                asset_type: AssetType,
                                market: str = None,
                                **filters) -> pd.DataFrame:
        """获取加密货币资产列表"""
        try:
            # 1. 如果启用 API，尝试从外部 API 获取
            if self.crypto_api_config.get('enabled', False):
                crypto_list = self._fetch_crypto_from_api()
                if crypto_list is not None and not crypto_list.empty:
                    crypto_list['asset_type'] = asset_type.value
                    logger.debug(f"从 API 获取加密货币资产列表: {len(crypto_list)} 条")
                    return crypto_list

            # 2. 尝试从 DuckDB 获取
            if self.duckdb_manager is not None:
                try:
                    db_path = self.duckdb_manager.get_database_path(asset_type) if hasattr(self.duckdb_manager, 'get_database_path') else None
                    if db_path:
                        query = "SELECT * FROM asset_metadata WHERE asset_type = ?"
                        result = self._query_duckdb(db_path, query, ['crypto'])
                        if result is not None and not result.empty:
                            logger.debug(f"从 DuckDB 获取加密货币资产列表: {len(result)} 条")
                            return result
                except Exception as e:
                    logger.warning(f"⚠️ 从 DuckDB 获取加密货币资产列表失败: {e}")

            # 3. 返回内置的常用加密货币列表
            return self._get_common_cryptocurrencies()

        except Exception as e:
            logger.error(f"❌ 获取加密货币资产列表失败: {e}")
            return self._get_common_cryptocurrencies()

    def _get_common_cryptocurrencies(self) -> pd.DataFrame:
        """获取常用加密货币列表（内置备用数据）"""
        common_cryptos = [
            {'code': 'BTC', 'name': 'Bitcoin', 'market': 'Global', 'industry': '加密货币', 'sector': 'crypto'},
            {'code': 'ETH', 'name': 'Ethereum', 'market': 'Global', 'industry': '加密货币', 'sector': 'crypto'},
            {'code': 'BNB', 'name': 'Binance Coin', 'market': 'Global', 'industry': '加密货币', 'sector': 'crypto'},
            {'code': 'XRP', 'name': 'Ripple', 'market': 'Global', 'industry': '加密货币', 'sector': 'crypto'},
            {'code': 'ADA', 'name': 'Cardano', 'market': 'Global', 'industry': '加密货币', 'sector': 'crypto'},
            {'code': 'SOL', 'name': 'Solana', 'market': 'Global', 'industry': '加密货币', 'sector': 'crypto'},
            {'code': 'DOGE', 'name': 'Dogecoin', 'market': 'Global', 'industry': '加密货币', 'sector': 'crypto'},
            {'code': 'DOT', 'name': 'Polkadot', 'market': 'Global', 'industry': '加密货币', 'sector': 'crypto'},
            {'code': 'MATIC', 'name': 'Polygon', 'market': 'Global', 'industry': '加密货币', 'sector': 'crypto'},
            {'code': 'LTC', 'name': 'Litecoin', 'market': 'Global', 'industry': '加密货币', 'sector': 'crypto'},
        ]
        df = pd.DataFrame(common_cryptos)
        df['asset_type'] = 'crypto'
        df['list_date'] = None
        df['status'] = 'active'
        logger.info(f"📦 返回内置常用加密货币列表: {len(df)} 条")
        return df

    def _get_futures_asset_list(self,
                                 asset_type: AssetType,
                                 market: str = None,
                                 **filters) -> pd.DataFrame:
        """获取期货资产列表"""
        try:
            # 1. 尝试从 DuckDB 获取
            if self.duckdb_manager is not None:
                try:
                    db_path = self.duckdb_manager.get_database_path(asset_type) if hasattr(self.duckdb_manager, 'get_database_path') else None
                    if db_path:
                        query = "SELECT * FROM asset_metadata WHERE asset_type = ?"
                        result = self._query_duckdb(db_path, query, ['futures'])
                        if result is not None and not result.empty:
                            logger.debug(f"从 DuckDB 获取期货资产列表: {len(result)} 条")
                            return result
                except Exception as e:
                    logger.warning(f"⚠️ 从 DuckDB 获取期货资产列表失败: {e}")

            # 2. 返回内置的常用期货列表
            return self._get_common_futures()

        except Exception as e:
            logger.error(f"❌ 获取期货资产列表失败: {e}")
            return self._get_common_futures()

    def _get_common_futures(self) -> pd.DataFrame:
        """获取常用期货列表（内置备用数据）"""
        common_futures = [
            {'code': 'IF', 'name': '沪深300指数期货', 'market': 'SHFE', 'industry': '金融期货', 'sector': 'futures'},
            {'code': 'IC', 'name': '中证500指数期货', 'market': 'SHFE', 'industry': '金融期货', 'sector': 'futures'},
            {'code': 'IH', 'name': '上证50指数期货', 'market': 'SHFE', 'industry': '金融期货', 'sector': 'futures'},
            {'code': 'TF', 'name': '5年期国债期货', 'market': 'SHFE', 'industry': '国债期货', 'sector': 'futures'},
            {'code': 'T', 'name': '10年期国债期货', 'market': 'SHFE', 'industry': '国债期货', 'sector': 'futures'},
            {'code': 'TS', 'name': '2年期国债期货', 'market': 'SHFE', 'industry': '国债期货', 'sector': 'futures'},
            {'code': 'CU', 'name': '铜期货', 'market': 'SHFE', 'industry': '金属期货', 'sector': 'futures'},
            {'code': 'AL', 'name': '铝期货', 'market': 'SHFE', 'industry': '金属期货', 'sector': 'futures'},
            {'code': 'ZN', 'name': '锌期货', 'market': 'SHFE', 'industry': '金属期货', 'sector': 'futures'},
            {'code': 'RU', 'name': '橡胶期货', 'market': 'SHFE', 'industry': '化工期货', 'sector': 'futures'},
            {'code': 'AU', 'name': '黄金期货', 'market': 'SHFE', 'industry': '贵金属期货', 'sector': 'futures'},
            {'code': 'AG', 'name': '白银期货', 'market': 'SHFE', 'industry': '贵金属期货', 'sector': 'futures'},
        ]
        df = pd.DataFrame(common_futures)
        df['asset_type'] = 'futures'
        df['list_date'] = None
        df['status'] = 'active'
        logger.info(f"📦 返回内置常用期货列表: {len(df)} 条")
        return df

    def _get_forex_asset_list(self,
                               asset_type: AssetType,
                               market: str = None,
                               **filters) -> pd.DataFrame:
        """获取外汇资产列表"""
        try:
            # 1. 尝试从 DuckDB 获取
            if self.duckdb_manager is not None:
                try:
                    db_path = self.duckdb_manager.get_database_path(asset_type) if hasattr(self.duckdb_manager, 'get_database_path') else None
                    if db_path:
                        query = "SELECT * FROM asset_metadata WHERE asset_type = ?"
                        result = self._query_duckdb(db_path, query, ['forex'])
                        if result is not None and not result.empty:
                            logger.debug(f"从 DuckDB 获取外汇资产列表: {len(result)} 条")
                            return result
                except Exception as e:
                    logger.warning(f"⚠️ 从 DuckDB 获取外汇资产列表失败: {e}")

            # 2. 返回内置的常用外汇列表
            return self._get_common_forex()

        except Exception as e:
            logger.error(f"❌ 获取外汇资产列表失败: {e}")
            return self._get_common_forex()

    def _get_common_forex(self) -> pd.DataFrame:
        """获取常用外汇列表（内置备用数据）"""
        common_forex = [
            {'code': 'USD/CNY', 'name': '美元/人民币', 'market': 'FX', 'industry': '外汇', 'sector': 'forex'},
            {'code': 'EUR/CNY', 'name': '欧元/人民币', 'market': 'FX', 'industry': '外汇', 'sector': 'forex'},
            {'code': 'JPY/CNY', 'name': '日元/人民币', 'market': 'FX', 'industry': '外汇', 'sector': 'forex'},
            {'code': 'GBP/CNY', 'name': '英镑/人民币', 'market': 'FX', 'industry': '外汇', 'sector': 'forex'},
            {'code': 'AUD/CNY', 'name': '澳元/人民币', 'market': 'FX', 'industry': '外汇', 'sector': 'forex'},
            {'code': 'CAD/CNY', 'name': '加元/人民币', 'market': 'FX', 'industry': '外汇', 'sector': 'forex'},
            {'code': 'CHF/CNY', 'name': '瑞郎/人民币', 'market': 'FX', 'industry': '外汇', 'sector': 'forex'},
            {'code': 'HKD/CNY', 'name': '港币/人民币', 'market': 'FX', 'industry': '外汇', 'sector': 'forex'},
            {'code': 'EUR/USD', 'name': '欧元/美元', 'market': 'FX', 'industry': '外汇', 'sector': 'forex'},
            {'code': 'GBP/USD', 'name': '英镑/美元', 'market': 'FX', 'industry': '外汇', 'sector': 'forex'},
            {'code': 'USD/JPY', 'name': '美元/日元', 'market': 'FX', 'industry': '外汇', 'sector': 'forex'},
            {'code': 'USD/CHF', 'name': '美元/瑞郎', 'market': 'FX', 'industry': '外汇', 'sector': 'forex'},
        ]
        df = pd.DataFrame(common_forex)
        df['asset_type'] = 'forex'
        df['list_date'] = None
        df['status'] = 'active'
        logger.info(f"📦 返回内置常用外汇列表: {len(df)} 条")
        return df

    def _get_option_asset_list(self,
                                asset_type: AssetType,
                                market: str = None,
                                **filters) -> pd.DataFrame:
        """获取期权资产列表"""
        try:
            if self.duckdb_manager is not None:
                try:
                    db_path = self.duckdb_manager.get_database_path(asset_type) if hasattr(self.duckdb_manager, 'get_database_path') else None
                    if db_path:
                        query = "SELECT * FROM asset_metadata WHERE asset_type = ?"
                        result = self._query_duckdb(db_path, query, ['option'])
                        if result is not None and not result.empty:
                            logger.debug(f"从 DuckDB 获取期权资产列表: {len(result)} 条")
                            return result
                except Exception as e:
                    logger.warning(f"⚠️ 从 DuckDB 获取期权资产列表失败: {e}")

            # 3. 返回内置的常用期权列表
            return self._get_common_options()

        except Exception as e:
            logger.error(f"❌ 获取期权资产列表失败: {e}")
            return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def _get_warrant_asset_list(self,
                                 asset_type: AssetType,
                                 market: str = None,
                                 **filters) -> pd.DataFrame:
        """获取涡轮资产列表"""
        try:
            if self.duckdb_manager is not None:
                try:
                    db_path = self.duckdb_manager.get_database_path(asset_type) if hasattr(self.duckdb_manager, 'get_database_path') else None
                    if db_path:
                        query = "SELECT * FROM asset_metadata WHERE asset_type = ?"
                        result = self._query_duckdb(db_path, query, ['warrant'])
                        if result is not None and not result.empty:
                            logger.debug(f"从 DuckDB 获取涡轮资产列表: {len(result)} 条")
                            return result
                except Exception as e:
                    logger.warning(f"⚠️ 从 DuckDB 获取涡轮资产列表失败: {e}")

            # 3. 返回内置的常用涡轮列表
            return self._get_common_warrants()

        except Exception as e:
            logger.error(f"❌ 获取涡轮资产列表失败: {e}")
            return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def _get_commodity_asset_list(self,
                                   asset_type: AssetType,
                                   market: str = None,
                                   **filters) -> pd.DataFrame:
        """获取大宗商品资产列表"""
        try:
            if self.duckdb_manager is not None:
                try:
                    db_path = self.duckdb_manager.get_database_path(asset_type) if hasattr(self.duckdb_manager, 'get_database_path') else None
                    if db_path:
                        query = "SELECT * FROM asset_metadata WHERE asset_type = ?"
                        result = self._query_duckdb(db_path, query, ['commodity'])
                        if result is not None and not result.empty:
                            logger.debug(f"从 DuckDB 获取大宗商品资产列表: {len(result)} 条")
                            return result
                except Exception as e:
                    logger.warning(f"⚠️ 从 DuckDB 获取大宗商品资产列表失败: {e}")

            # 返回内置的大宗商品列表
            return self._get_common_commodities()

        except Exception as e:
            logger.error(f"❌ 获取大宗商品资产列表失败: {e}")
            return self._get_common_commodities()

    def _get_common_commodities(self) -> pd.DataFrame:
        """获取常用大宗商品列表（内置备用数据）"""
        common_commodities = [
            {'code': 'CU', 'name': '铜', 'market': 'LME', 'industry': '金属', 'sector': 'commodity'},
            {'code': 'AL', 'name': '铝', 'market': 'LME', 'industry': '金属', 'sector': 'commodity'},
            {'code': 'ZN', 'name': '锌', 'market': 'LME', 'industry': '金属', 'sector': 'commodity'},
            {'code': 'PB', 'name': '铅', 'market': 'LME', 'industry': '金属', 'sector': 'commodity'},
            {'code': 'NI', 'name': '镍', 'market': 'LME', 'industry': '金属', 'sector': 'commodity'},
            {'code': 'AU', 'name': '黄金', 'market': 'COMEX', 'industry': '贵金属', 'sector': 'commodity'},
            {'code': 'AG', 'name': '白银', 'market': 'COMEX', 'industry': '贵金属', 'sector': 'commodity'},
            {'code': 'CL', 'name': '原油', 'market': 'NYMEX', 'industry': '能源', 'sector': 'commodity'},
            {'code': 'NG', 'name': '天然气', 'market': 'NYMEX', 'industry': '能源', 'sector': 'commodity'},
            {'code': 'RB', 'name': '螺纹钢', 'market': 'SHFE', 'industry': '黑色金属', 'sector': 'commodity'},
            {'code': 'HC', 'name': '热轧卷板', 'market': 'SHFE', 'industry': '黑色金属', 'sector': 'commodity'},
            {'code': 'SR', 'name': '白糖', 'market': 'CZCE', 'industry': '农产品', 'sector': 'commodity'},
            {'code': 'CF', 'name': '棉花', 'market': 'CZCE', 'industry': '农产品', 'sector': 'commodity'},
            {'code': 'RM', 'name': '菜粕', 'market': 'CZCE', 'industry': '农产品', 'sector': 'commodity'},
            {'code': 'MA', 'name': '甲醇', 'market': 'CZCE', 'industry': '化工', 'sector': 'commodity'},
        ]
        df = pd.DataFrame(common_commodities)
        df['asset_type'] = 'commodity'
        df['list_date'] = None
        df['status'] = 'active'
        logger.info(f"📦 返回内置常用大宗商品列表: {len(df)} 条")
        return df

    def _get_industry_sector_asset_list(self,
                                         asset_type: AssetType,
                                         market: str = None,
                                         **filters) -> pd.DataFrame:
        """获取行业板块资产列表"""
        return self._get_sector_asset_list(asset_type, 'industry')

    def _get_concept_sector_asset_list(self,
                                        asset_type: AssetType,
                                        market: str = None,
                                        **filters) -> pd.DataFrame:
        """获取概念板块资产列表"""
        return self._get_sector_asset_list(asset_type, 'concept')

    def _get_style_sector_asset_list(self,
                                      asset_type: AssetType,
                                      market: str = None,
                                      **filters) -> pd.DataFrame:
        """获取风格板块资产列表"""
        return self._get_sector_asset_list(asset_type, 'style')

    def _get_theme_sector_asset_list(self,
                                      asset_type: AssetType,
                                      market: str = None,
                                      **filters) -> pd.DataFrame:
        """获取主题板块资产列表"""
        return self._get_sector_asset_list(asset_type, 'theme')

    def _get_sector_asset_list(self,
                                asset_type: AssetType,
                                sector_type: str = 'industry') -> pd.DataFrame:
        """获取板块资产列表 - 通用实现"""
        try:
            return self._get_common_sectors(sector_type)

        except Exception as e:
            logger.error(f"❌ 获取 {sector_type} 板块资产列表失败: {e}")
            return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def _get_macro_asset_list(self,
                               asset_type: AssetType,
                               market: str = None,
                               **filters) -> pd.DataFrame:
        """获取宏观经济数据资产列表"""
        try:
            if self.duckdb_manager is not None:
                try:
                    db_path = self.duckdb_manager.get_database_path(asset_type) if hasattr(self.duckdb_manager, 'get_database_path') else None
                    if db_path:
                        query = "SELECT * FROM asset_metadata WHERE asset_type = ?"
                        result = self._query_duckdb(db_path, query, ['macro'])
                        if result is not None and not result.empty:
                            logger.debug(f"从 DuckDB 获取宏观经济资产列表: {len(result)} 条")
                            return result
                except Exception as e:
                    logger.warning(f"⚠️ 从 DuckDB 获取宏观经济资产列表失败: {e}")

            return self._get_common_macros()

        except Exception as e:
            logger.error(f"❌ 获取宏观经济资产列表失败: {e}")
            return self._get_common_macros()

    def _get_common_macros(self) -> pd.DataFrame:
        """获取常用宏观经济指标列表（内置备用数据）"""
        common_macros = [
            {'code': 'GDP', 'name': '国内生产总值', 'market': 'CN', 'industry': '宏观经济', 'sector': 'macro'},
            {'code': 'CPI', 'name': '居民消费价格指数', 'market': 'CN', 'industry': '宏观经济', 'sector': 'macro'},
            {'code': 'PPI', 'name': '工业生产者出厂价格指数', 'market': 'CN', 'industry': '宏观经济', 'sector': 'macro'},
            {'code': 'PMI', 'name': '采购经理人指数', 'market': 'CN', 'industry': '宏观经济', 'sector': 'macro'},
            {'code': 'M2', 'name': '货币供应量M2', 'market': 'CN', 'industry': '宏观经济', 'sector': 'macro'},
            {'code': 'LPR', 'name': '贷款市场报价利率', 'market': 'CN', 'industry': '宏观经济', 'sector': 'macro'},
            {'code': 'USD_CNY', 'name': '美元兑人民币汇率', 'market': 'CN', 'industry': '宏观经济', 'sector': 'macro'},
            {'code': 'SHIBOR_1M', 'name': '上海银行间同业拆借利率(1月)', 'market': 'CN', 'industry': '宏观经济', 'sector': 'macro'},
            {'code': '10Y_CN', 'name': '中国10年期国债收益率', 'market': 'CN', 'industry': '宏观经济', 'sector': 'macro'},
            {'code': '10Y_US', 'name': '美国10年期国债收益率', 'market': 'US', 'industry': '宏观经济', 'sector': 'macro'},
            {'code': 'FED_RATE', 'name': '美联储联邦基金利率', 'market': 'US', 'industry': '宏观经济', 'sector': 'macro'},
            {'code': 'VIX', 'name': '恐慌指数', 'market': 'US', 'industry': '宏观经济', 'sector': 'macro'},
        ]
        df = pd.DataFrame(common_macros)
        df['asset_type'] = 'macro'
        df['list_date'] = None
        df['status'] = 'active'
        logger.info(f"📦 返回内置常用宏观经济指标列表: {len(df)} 条")
        return df

    def _get_common_funds(self) -> pd.DataFrame:
        """获取常用基金列表（内置备用数据）"""
        common_funds = [
            {'code': '510300', 'name': '沪深300指数ETF', 'market': 'SH', 'industry': '指数基金', 'sector': 'fund'},
            {'code': '159915', 'name': '创业板ETF', 'market': 'SZ', 'industry': '指数基金', 'sector': 'fund'},
            {'code': '512880', 'name': '中证500ETF', 'market': 'SH', 'industry': '指数基金', 'sector': 'fund'},
            {'code': '513050', 'name': '中概互联网ETF', 'market': 'SH', 'industry': '指数基金', 'sector': 'fund'},
            {'code': '161039', 'name': '富国中证新能源汽车指数(LOF)', 'market': 'SZ', 'industry': '指数基金', 'sector': 'fund'},
            {'code': '001552', 'name': '天弘中证银行指数C', 'market': 'SH', 'industry': '指数基金', 'sector': 'fund'},
            {'code': '005827', 'name': '易方达蓝筹精选混合', 'market': 'SH', 'industry': '混合基金', 'sector': 'fund'},
            {'code': '161725', 'name': '易方达消费行业股票', 'market': 'SZ', 'industry': '股票基金', 'sector': 'fund'},
            {'code': '000311', 'name': '景顺长城沪深300指数增强', 'market': 'SH', 'industry': '指数基金', 'sector': 'fund'},
            {'code': '470009', 'name': '汇添富中证主要消费ETF联接', 'market': 'SH', 'industry': '指数基金', 'sector': 'fund'},
        ]
        df = pd.DataFrame(common_funds)
        df['asset_type'] = 'fund'
        df['list_date'] = None
        df['status'] = 'active'
        logger.info(f"📦 返回内置常用基金列表: {len(df)} 条")
        return df

    def _get_common_bonds(self) -> pd.DataFrame:
        """获取常用债券列表（内置备用数据）"""
        common_bonds = [
            {'code': '204001', 'name': 'GC204', 'market': 'SH', 'industry': '国债逆回购', 'sector': 'bond'},
            {'code': '204002', 'name': 'GC204', 'market': 'SH', 'industry': '国债逆回购', 'sector': 'bond'},
            {'code': '511660', 'name': '国债ETF', 'market': 'SH', 'industry': '债券ETF', 'sector': 'bond'},
            {'code': '511010', 'name': '上证国债ETF', 'market': 'SH', 'industry': '债券ETF', 'sector': 'bond'},
            {'code': '000001', 'name': '上证国债指数', 'market': 'SH', 'industry': '债券指数', 'sector': 'bond'},
        ]
        df = pd.DataFrame(common_bonds)
        df['asset_type'] = 'bond'
        df['list_date'] = None
        df['status'] = 'active'
        logger.info(f"📦 返回内置常用债券列表: {len(df)} 条")
        return df

    def _get_common_options(self) -> pd.DataFrame:
        """获取常用期权列表（内置备用数据）"""
        common_options = [
            {'code': '510050C2306', 'name': '50ETF购2306', 'market': 'SH', 'industry': 'ETF期权', 'sector': 'option'},
            {'code': '510050P2306', 'name': '50ETF沽2306', 'market': 'SH', 'industry': 'ETF期权', 'sector': 'option'},
            {'code': '510300C2306', 'name': '300ETF购2306', 'market': 'SH', 'industry': 'ETF期权', 'sector': 'option'},
            {'code': '510300P2306', 'name': '300ETF沽2306', 'market': 'SH', 'industry': 'ETF期权', 'sector': 'option'},
            {'code': '159919C2306', 'name': '创业板ETF购2306', 'market': 'SZ', 'industry': 'ETF期权', 'sector': 'option'},
            {'code': '159919P2306', 'name': '创业板ETF沽2306', 'market': 'SZ', 'industry': 'ETF期权', 'sector': 'option'},
        ]
        df = pd.DataFrame(common_options)
        df['asset_type'] = 'option'
        df['list_date'] = None
        df['status'] = 'active'
        logger.info(f"📦 返回内置常用期权列表: {len(df)} 条")
        return df

    def _get_common_warrants(self) -> pd.DataFrame:
        """获取常用涡轮列表（内置备用数据）"""
        common_warrants = [
            {'code': '580020', 'name': '华宝油气购A', 'market': 'SH', 'industry': '认购涡轮', 'sector': 'warrant'},
            {'code': '580022', 'name': '华宝油气购B', 'market': 'SH', 'industry': '认购涡轮', 'sector': 'warrant'},
            {'code': '538000', 'name': '300ETF购A', 'market': 'SH', 'industry': '认购涡轮', 'sector': 'warrant'},
            {'code': '538001', 'name': '300ETF购B', 'market': 'SH', 'industry': '认购涡轮', 'sector': 'warrant'},
            {'code': '130023', 'name': '50ETF购A', 'market': 'SH', 'industry': '认购涡轮', 'sector': 'warrant'},
            {'code': '130024', 'name': '50ETF购B', 'market': 'SH', 'industry': '认购涡轮', 'sector': 'warrant'},
        ]
        df = pd.DataFrame(common_warrants)
        df['asset_type'] = 'warrant'
        df['list_date'] = None
        df['status'] = 'active'
        logger.info(f"📦 返回内置常用涡轮列表: {len(df)} 条")
        return df

    def _get_common_sectors(self, sector_type: str = 'industry') -> pd.DataFrame:
        """获取常用板块列表（内置备用数据）"""
        industry_sectors = [
            {'code': 'I01', 'name': '农林牧渔', 'market': 'A', 'industry': '农林牧渔', 'sector': 'industry'},
            {'code': 'I02', 'name': '采掘', 'market': 'A', 'industry': '采掘', 'sector': 'industry'},
            {'code': 'I03', 'name': '化工', 'market': 'A', 'industry': '化工', 'sector': 'industry'},
            {'code': 'I04', 'name': '钢铁', 'market': 'A', 'industry': '钢铁', 'sector': 'industry'},
            {'code': 'I05', 'name': '有色金属', 'market': 'A', 'industry': '有色金属', 'sector': 'industry'},
            {'code': 'I06', 'name': '电子', 'market': 'A', 'industry': '电子', 'sector': 'industry'},
            {'code': 'I07', 'name': '汽车', 'market': 'A', 'industry': '汽车', 'sector': 'industry'},
            {'code': 'I08', 'name': '家用电器', 'market': 'A', 'industry': '家用电器', 'sector': 'industry'},
            {'code': 'I09', 'name': '食品饮料', 'market': 'A', 'industry': '食品饮料', 'sector': 'industry'},
            {'code': 'I10', 'name': '纺织服装', 'market': 'A', 'industry': '纺织服装', 'sector': 'industry'},
            {'code': 'I11', 'name': '轻工制造', 'market': 'A', 'industry': '轻工制造', 'sector': 'industry'},
            {'code': 'I12', 'name': '医药生物', 'market': 'A', 'industry': '医药生物', 'sector': 'industry'},
            {'code': 'I13', 'name': '公用事业', 'market': 'A', 'industry': '公用事业', 'sector': 'industry'},
            {'code': 'I14', 'name': '交通运输', 'market': 'A', 'industry': '交通运输', 'sector': 'industry'},
            {'code': 'I15', 'name': '房地产', 'market': 'A', 'industry': '房地产', 'sector': 'industry'},
            {'code': 'I16', 'name': '商业贸易', 'market': 'A', 'industry': '商业贸易', 'sector': 'industry'},
            {'code': 'I17', 'name': '休闲服务', 'market': 'A', 'industry': '休闲服务', 'sector': 'industry'},
            {'code': 'I18', 'name': '计算机', 'market': 'A', 'industry': '计算机', 'sector': 'industry'},
            {'code': 'I19', 'name': '传媒', 'market': 'A', 'industry': '传媒', 'sector': 'industry'},
            {'code': 'I20', 'name': '非银金融', 'market': 'A', 'industry': '非银金融', 'sector': 'industry'},
            {'code': 'I21', 'name': '银行', 'market': 'A', 'industry': '银行', 'sector': 'industry'},
            {'code': 'I22', 'name': '综合', 'market': 'A', 'industry': '综合', 'sector': 'industry'},
            {'code': 'I23', 'name': '国防军工', 'market': 'A', 'industry': '国防军工', 'sector': 'industry'},
            {'code': 'I24', 'name': '机械设备', 'market': 'A', 'industry': '机械设备', 'sector': 'industry'},
        ]

        concept_sectors = [
            {'code': 'C01', 'name': '新能源', 'market': 'A', 'industry': '概念', 'sector': 'concept'},
            {'code': 'C02', 'name': '5G概念', 'market': 'A', 'industry': '概念', 'sector': 'concept'},
            {'code': 'C03', 'name': '人工智能', 'market': 'A', 'industry': '概念', 'sector': 'concept'},
            {'code': 'C04', 'name': '半导体', 'market': 'A', 'industry': '概念', 'sector': 'concept'},
            {'code': 'C05', 'name': '新能源汽车', 'market': 'A', 'industry': '概念', 'sector': 'concept'},
            {'code': 'C06', 'name': '光伏', 'market': 'A', 'industry': '概念', 'sector': 'concept'},
            {'code': 'C07', 'name': '集成电路', 'market': 'A', 'industry': '概念', 'sector': 'concept'},
            {'code': 'C08', 'name': '大数据', 'market': 'A', 'industry': '概念', 'sector': 'concept'},
            {'code': 'C09', 'name': '云计算', 'market': 'A', 'industry': '概念', 'sector': 'concept'},
            {'code': 'C10', 'name': '物联网', 'market': 'A', 'industry': '概念', 'sector': 'concept'},
        ]

        if sector_type == 'industry':
            sectors = industry_sectors
        elif sector_type == 'concept':
            sectors = concept_sectors
        else:
            sectors = industry_sectors

        df = pd.DataFrame(sectors)
        df['asset_type'] = f'{sector_type}_sector'
        df['list_date'] = None
        df['status'] = 'active'
        logger.info(f"📦 返回内置{sector_type}板块列表: {len(df)} 条")
        return df

    def _fetch_crypto_from_api(self) -> Optional[pd.DataFrame]:
        """从外部 API 获取加密货币数据"""
        provider = self.crypto_api_config.get('provider', 'binance')

        if provider == 'binance':
            return self._fetch_from_binance()
        elif provider == 'coingecko':
            return self._fetch_from_coingecko()
        else:
            logger.warning(f"⚠️ 不支持的加密货币 API 提供商: {provider}")
            return None

    def _fetch_from_binance(self) -> Optional[pd.DataFrame]:
        """从 Binance API 获取加密货币数据"""
        try:
            import aiohttp
            from utils.async_utils import run_async_blocking

            async def fetch():
                async with aiohttp.ClientSession() as session:
                    async with session.get(self._api_endpoints['binance']['spot'], timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            data = await response.json()
                            cryptos = []
                            for item in data[:50]:
                                if item['symbol'].endswith('USDT'):
                                    symbol = item['symbol'].replace('USDT', '')
                                    cryptos.append({
                                        'code': symbol,
                                        'name': symbol,
                                        'market': 'Global',
                                        'industry': '加密货币',
                                        'sector': 'crypto'
                                    })
                            return pd.DataFrame(cryptos)
                        return None

            return run_async_blocking(fetch())

        except Exception as e:
            logger.warning(f"⚠️ 从 Binance API 获取数据失败: {e}")
            return None

    def _fetch_from_coingecko(self) -> Optional[pd.DataFrame]:
        """从 CoinGecko API 获取加密货币数据"""
        try:
            import aiohttp
            from utils.async_utils import run_async_blocking

            async def fetch():
                async with aiohttp.ClientSession() as session:
                    params = {
                        'vs_currency': 'usd',
                        'order': 'market_cap_desc',
                        'per_page': 50,
                        'page': 1
                    }
                    async with session.get(self._api_endpoints['coingecko']['coins'], params=params,
                                          timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            data = await response.json()
                            cryptos = []
                            for item in data:
                                cryptos.append({
                                    'code': item['symbol'].upper(),
                                    'name': item['name'],
                                    'market': 'Global',
                                    'industry': '加密货币',
                                    'sector': 'crypto'
                                })
                            return pd.DataFrame(cryptos)
                        return None

            return run_async_blocking(fetch())

        except Exception as e:
            logger.warning(f"⚠️ 从 CoinGecko API 获取数据失败: {e}")
            return None

    def _query_duckdb(self, db_path: str, query: str, params=None) -> Optional[pd.DataFrame]:
        """查询 DuckDB 数据库"""
        try:
            if self.duckdb_manager is not None:
                with self.duckdb_manager.get_connection(db_path) as conn:
                    if params:
                        result = conn.execute(query, params).fetchdf()
                    else:
                        result = conn.execute(query).fetchdf()
                    return result
            else:
                import duckdb
                conn = duckdb.connect(db_path)
                try:
                    if params:
                        result = conn.execute(query, params).fetchdf()
                    else:
                        result = conn.execute(query).fetchdf()
                    return result
                finally:
                    conn.close()
        except Exception as e:
            logger.warning(f"⚠️ DuckDB 查询失败: {e}")
            return None

    async def fetch_async(self,
                          asset_type: AssetType,
                          market: str = None,
                          **filters) -> pd.DataFrame:
        """
        异步获取资产列表

        Args:
            asset_type: 资产类型
            market: 市场代码
            **filters: 其他过滤条件

        Returns:
            DataFrame: 资产列表数据
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.get_asset_list,
            asset_type,
            market,
            filters
        )

    def reload_from_api(self,
                        asset_type: AssetType,
                        market: str = None) -> bool:
        """
        从 API 重新加载资产数据

        Args:
            asset_type: 资产类型
            market: 市场代码

        Returns:
            bool: 是否成功
        """
        try:
            if asset_type == AssetType.CRYPTO:
                if self.crypto_api_config.get('enabled', False):
                    crypto_data = self._fetch_crypto_from_api()
                    if crypto_data is not None and not crypto_data.empty:
                        logger.info(f"成功从 API 获取 {asset_type.value} 资产数据: {len(crypto_data)} 条")
                        return True

            logger.warning(f"⚠️ 无法从 API 重新加载 {asset_type.value} 资产数据")
            return False

        except Exception as e:
            logger.error(f"❌ 从 API 重新加载 {asset_type.value} 资产数据失败: {e}")
            return False

    def clear_cache(self):
        """清理缓存"""
        if self._http_session:
            try:
                from utils.async_utils import run_async_safe
                run_async_safe(self._http_session.close())
            except Exception as e:
                logger.debug(f"关闭HTTP会话失败: {e}")
        self._http_session = None
        logger.info("Fallback 加载器缓存已清理")
