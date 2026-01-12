#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账户仓储

负责账户、持仓、资金数据的持久化
"""

import json
from loguru import logger
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4

from core.trading.account_models import (
    Account, Position, FundInfo, 
    AccountQuery, PositionQuery, AccountStatus, PositionSide
)
from core.containers import ServiceContainer
from core.events import EventBus
from core.utils.crypto_utils import get_crypto_utils


class AccountRepository:
    """账户仓储"""

    def __init__(self, service_container: ServiceContainer, event_bus: EventBus):
        self.service_container = service_container
        self.event_bus = event_bus
        self.crypto_utils = get_crypto_utils()
        self._init_database_tables()
        logger.info("账户仓储初始化完成")

    def _get_database_service(self):
        """获取数据库服务"""
        from core.services.database_service import DatabaseService
        return self.service_container.resolve(DatabaseService)

    def _init_database_tables(self):
        """初始化数据库表"""
        try:
            db_service = self._get_database_service()
            
            # 检查连接池是否存在，如果不存在则创建
            if "tradeaccount_sqlite" not in db_service._connection_pools:
                from core.services.database_service import DatabaseConfig, DatabaseType
                config = DatabaseConfig(
                    db_type=DatabaseType.SQLITE,
                    db_path="data/tradeaccount.sqlite",
                    pool_size=10,
                    max_pool_size=30
                )
                db_service.create_connection_pool("tradeaccount_sqlite", config)
                logger.info("✓ Created tradeaccount_sqlite connection pool")
            
            # 创建账户表
            create_accounts_table = """
            CREATE TABLE IF NOT EXISTS accounts (
                account_id VARCHAR(64) PRIMARY KEY,
                account_name VARCHAR(128) NOT NULL,
                account_type VARCHAR(32) NOT NULL,
                status VARCHAR(32) NOT NULL,
                balance DECIMAL(20, 4) NOT NULL DEFAULT 0,
                available_balance DECIMAL(20, 4) NOT NULL DEFAULT 0,
                frozen_balance DECIMAL(20, 4) NOT NULL DEFAULT 0,
                market_value DECIMAL(20, 4) NOT NULL DEFAULT 0,
                total_assets DECIMAL(20, 4) NOT NULL DEFAULT 0,
                profit_loss DECIMAL(20, 4) NOT NULL DEFAULT 0,
                profit_loss_ratio DECIMAL(10, 6) NOT NULL DEFAULT 0,
                create_time TIMESTAMP NOT NULL,
                update_time TIMESTAMP NOT NULL,
                user_id VARCHAR(64) NOT NULL DEFAULT 'system',
                trading_day VARCHAR(16) DEFAULT '',
                risk_level VARCHAR(32) DEFAULT 'normal',
                margin_ratio DECIMAL(10, 6) DEFAULT 0,
                maintenance_margin DECIMAL(20, 4) DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                
                -- 机构信息
                institution_name VARCHAR(128) DEFAULT '',
                institution_type VARCHAR(32) DEFAULT 'broker',
                
                -- 交易接口类型
                trading_interface_type VARCHAR(32) DEFAULT 'mock',
                
                -- CTP交易接口配置
                ctp_broker_id VARCHAR(32) DEFAULT '',
                ctp_investor_id VARCHAR(32) DEFAULT '',
                ctp_password VARCHAR(128) DEFAULT '',
                ctp_trade_front VARCHAR(256) DEFAULT '',
                ctp_quote_front VARCHAR(256) DEFAULT '',
                ctp_app_id VARCHAR(64) DEFAULT '',
                ctp_auth_code VARCHAR(128) DEFAULT '',
                ctp_product_info VARCHAR(128) DEFAULT '',
                
                -- XTP交易接口配置
                xtp_account_id VARCHAR(32) DEFAULT '',
                xtp_password VARCHAR(128) DEFAULT '',
                xtp_server_address VARCHAR(256) DEFAULT '',
                xtp_client_id INT DEFAULT 0,
                xtp_software_key VARCHAR(128) DEFAULT '',
                xtp_md_ip VARCHAR(64) DEFAULT '',
                xtp_md_port INT DEFAULT 0,
                xtp_protocol VARCHAR(16) DEFAULT 'tcp',
                xtp_buffer_size INT DEFAULT 0,
                xtp_td_ip VARCHAR(64) DEFAULT '',
                xtp_td_port INT DEFAULT 0,
                
                -- 币安（Binance）配置
                binance_api_key VARCHAR(128) DEFAULT '',
                binance_secret_key VARCHAR(128) DEFAULT '',
                binance_rest_url VARCHAR(256) DEFAULT 'https://api.binance.com',
                binance_ws_url VARCHAR(256) DEFAULT 'wss://stream.binance.com:9443',
                
                -- 币安合约配置
                binance_futures_api_key VARCHAR(128) DEFAULT '',
                binance_futures_secret_key VARCHAR(128) DEFAULT '',
                binance_futures_rest_url VARCHAR(256) DEFAULT 'https://fapi.binance.com',
                binance_futures_ws_url VARCHAR(256) DEFAULT 'wss://fstream.binance.com',
                
                -- OKX配置
                okx_api_key VARCHAR(128) DEFAULT '',
                okx_secret_key VARCHAR(128) DEFAULT '',
                okx_passphrase VARCHAR(128) DEFAULT '',
                okx_rest_url VARCHAR(256) DEFAULT 'https://www.okx.com',
                okx_ws_url VARCHAR(256) DEFAULT 'wss://ws.okx.com:8443',
                
                -- OKX合约配置
                okx_futures_api_key VARCHAR(128) DEFAULT '',
                okx_futures_secret_key VARCHAR(128) DEFAULT '',
                okx_futures_passphrase VARCHAR(128) DEFAULT '',
                okx_futures_rest_url VARCHAR(256) DEFAULT 'https://www.okx.com',
                okx_futures_ws_url VARCHAR(256) DEFAULT 'wss://ws.okx.com:8443',
                
                -- 火币（Huobi/HTX）配置
                huobi_api_key VARCHAR(128) DEFAULT '',
                huobi_secret_key VARCHAR(128) DEFAULT '',
                huobi_rest_url VARCHAR(256) DEFAULT 'https://api.huobi.pro',
                huobi_ws_url VARCHAR(256) DEFAULT 'wss://api.huobi.pro/ws',
                
                -- 火币合约配置
                huobi_futures_api_key VARCHAR(128) DEFAULT '',
                huobi_futures_secret_key VARCHAR(128) DEFAULT '',
                huobi_futures_rest_url VARCHAR(256) DEFAULT 'https://api.hbdm.com',
                huobi_futures_ws_url VARCHAR(256) DEFAULT 'wss://api.hbdm.com/ws',
                
                -- Bitget配置
                bitget_api_key VARCHAR(128) DEFAULT '',
                bitget_secret_key VARCHAR(128) DEFAULT '',
                bitget_passphrase VARCHAR(128) DEFAULT '',
                bitget_rest_url VARCHAR(256) DEFAULT 'https://api.bitget.com',
                bitget_ws_url VARCHAR(256) DEFAULT 'wss://ws.bitget.com',
                
                -- Bybit配置
                bybit_api_key VARCHAR(128) DEFAULT '',
                bybit_secret_key VARCHAR(128) DEFAULT '',
                bybit_rest_url VARCHAR(256) DEFAULT 'https://api.bybit.com',
                bybit_ws_url VARCHAR(256) DEFAULT 'wss://stream.bybit.com',
                
                -- 交易接口（已废弃，使用 trading_interface_type 替代）
                trading_interface VARCHAR(32) DEFAULT ''
            )
            """

            # 创建持仓表
            create_positions_table = """
            CREATE TABLE IF NOT EXISTS positions (
                position_id VARCHAR(64) PRIMARY KEY,
                account_id VARCHAR(64) NOT NULL,
                asset_type VARCHAR(32) NOT NULL,
                stock_code VARCHAR(32) NOT NULL,
                stock_name VARCHAR(128) DEFAULT '',
                side VARCHAR(16) NOT NULL,
                quantity INT NOT NULL,
                available_quantity INT NOT NULL,
                open_price DECIMAL(20, 4) NOT NULL,
                current_price DECIMAL(20, 4) NOT NULL,
                market_value DECIMAL(20, 4) NOT NULL,
                cost_price DECIMAL(20, 4) NOT NULL,
                cost_value DECIMAL(20, 4) NOT NULL,
                profit_loss DECIMAL(20, 4) NOT NULL,
                profit_loss_ratio DECIMAL(10, 6) NOT NULL,
                open_time TIMESTAMP NOT NULL,
                update_time TIMESTAMP NOT NULL,
                commission DECIMAL(20, 4) DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
            )
            """

            # 创建资金信息表
            create_fund_infos_table = """
            CREATE TABLE IF NOT EXISTS fund_infos (
                account_id VARCHAR(64) PRIMARY KEY,
                total_balance DECIMAL(20, 4) NOT NULL,
                available_balance DECIMAL(20, 4) NOT NULL,
                frozen_balance DECIMAL(20, 4) NOT NULL,
                market_value DECIMAL(20, 4) NOT NULL,
                total_assets DECIMAL(20, 4) NOT NULL,
                profit_loss DECIMAL(20, 4) NOT NULL,
                profit_loss_ratio DECIMAL(10, 6) NOT NULL,
                margin_used DECIMAL(20, 4) NOT NULL,
                margin_available DECIMAL(20, 4) NOT NULL,
                maintenance_margin DECIMAL(20, 4) NOT NULL,
                update_time TIMESTAMP NOT NULL,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
            )
            """

            # 创建索引
            create_indexes = [
                "CREATE INDEX IF NOT EXISTS idx_accounts_account_type ON accounts(account_type)",
                "CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status)",
                "CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_accounts_update_time ON accounts(update_time)",
                "CREATE INDEX IF NOT EXISTS idx_positions_account_id ON positions(account_id)",
                "CREATE INDEX IF NOT EXISTS idx_positions_asset_type ON positions(asset_type)",
                "CREATE INDEX IF NOT EXISTS idx_positions_stock_code ON positions(stock_code)",
                "CREATE INDEX IF NOT EXISTS idx_positions_update_time ON positions(update_time)",
                "CREATE INDEX IF NOT EXISTS idx_fund_infos_update_time ON fund_infos(update_time)"
            ]

            # 使用 get_connection 直接获取连接
            with db_service.get_connection("tradeaccount_sqlite") as conn:
                cursor = conn.connection.cursor()
                cursor.execute(create_accounts_table)
                cursor.execute(create_positions_table)
                cursor.execute(create_fund_infos_table)
                
                # 创建索引
                for index_sql in create_indexes:
                    cursor.execute(index_sql)
                
                # 执行数据库迁移，添加缺失的列
                self._migrate_database_tables(cursor)
                
                conn.connection.commit()

            logger.info("账户数据库表初始化完成")

        except Exception as e:
            logger.error(f"初始化账户数据库表失败: {e}")
            raise

    def _migrate_database_tables(self, cursor):
        """迁移数据库表，添加缺失的列"""
        try:
            # 获取accounts表的现有列
            cursor.execute("PRAGMA table_info(accounts)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            # 定义需要添加的列及其SQL定义
            columns_to_add = {
                # XTP交易接口配置
                'xtp_client_id': "INT DEFAULT 0",
                'xtp_software_key': "VARCHAR(128) DEFAULT ''",
                'xtp_md_ip': "VARCHAR(64) DEFAULT ''",
                'xtp_md_port': "INT DEFAULT 0",
                'xtp_protocol': "VARCHAR(16) DEFAULT 'tcp'",
                'xtp_buffer_size': "INT DEFAULT 0",
                'xtp_td_ip': "VARCHAR(64) DEFAULT ''",
                'xtp_td_port': "INT DEFAULT 0",
                # 币安（Binance）配置
                'binance_api_key': "VARCHAR(128) DEFAULT ''",
                'binance_secret_key': "VARCHAR(128) DEFAULT ''",
                'binance_rest_url': "VARCHAR(256) DEFAULT 'https://api.binance.com'",
                'binance_ws_url': "VARCHAR(256) DEFAULT 'wss://stream.binance.com:9443'",
                # 币安合约配置
                'binance_futures_api_key': "VARCHAR(128) DEFAULT ''",
                'binance_futures_secret_key': "VARCHAR(128) DEFAULT ''",
                'binance_futures_rest_url': "VARCHAR(256) DEFAULT 'https://fapi.binance.com'",
                'binance_futures_ws_url': "VARCHAR(256) DEFAULT 'wss://fstream.binance.com'",
                # OKX配置
                'okx_api_key': "VARCHAR(128) DEFAULT ''",
                'okx_secret_key': "VARCHAR(128) DEFAULT ''",
                'okx_passphrase': "VARCHAR(128) DEFAULT ''",
                'okx_rest_url': "VARCHAR(256) DEFAULT 'https://www.okx.com'",
                'okx_ws_url': "VARCHAR(256) DEFAULT 'wss://ws.okx.com:8443'",
                # OKX合约配置
                'okx_futures_api_key': "VARCHAR(128) DEFAULT ''",
                'okx_futures_secret_key': "VARCHAR(128) DEFAULT ''",
                'okx_futures_passphrase': "VARCHAR(128) DEFAULT ''",
                'okx_futures_rest_url': "VARCHAR(256) DEFAULT 'https://www.okx.com'",
                'okx_futures_ws_url': "VARCHAR(256) DEFAULT 'wss://ws.okx.com:8443'",
                # 火币（Huobi/HTX）配置
                'huobi_api_key': "VARCHAR(128) DEFAULT ''",
                'huobi_secret_key': "VARCHAR(128) DEFAULT ''",
                'huobi_rest_url': "VARCHAR(256) DEFAULT 'https://api.huobi.pro'",
                'huobi_ws_url': "VARCHAR(256) DEFAULT 'wss://api.huobi.pro/ws'",
                # 火币合约配置
                'huobi_futures_api_key': "VARCHAR(128) DEFAULT ''",
                'huobi_futures_secret_key': "VARCHAR(128) DEFAULT ''",
                'huobi_futures_rest_url': "VARCHAR(256) DEFAULT 'https://api.hbdm.com'",
                'huobi_futures_ws_url': "VARCHAR(256) DEFAULT 'wss://api.hbdm.com/ws'",
                # Bitget配置
                'bitget_api_key': "VARCHAR(128) DEFAULT ''",
                'bitget_secret_key': "VARCHAR(128) DEFAULT ''",
                'bitget_passphrase': "VARCHAR(128) DEFAULT ''",
                'bitget_rest_url': "VARCHAR(256) DEFAULT 'https://api.bitget.com'",
                'bitget_ws_url': "VARCHAR(256) DEFAULT 'wss://ws.bitget.com'",
                # Bybit配置
                'bybit_api_key': "VARCHAR(128) DEFAULT ''",
                'bybit_secret_key': "VARCHAR(128) DEFAULT ''",
                'bybit_rest_url': "VARCHAR(256) DEFAULT 'https://api.bybit.com'",
                'bybit_ws_url': "VARCHAR(256) DEFAULT 'wss://stream.bybit.com'"
            }
            
            # 添加缺失的列
            for column_name, column_def in columns_to_add.items():
                if column_name not in existing_columns:
                    try:
                        alter_sql = f"ALTER TABLE accounts ADD COLUMN {column_name} {column_def}"
                        cursor.execute(alter_sql)
                        logger.info(f"✓ 添加列: accounts.{column_name}")
                    except Exception as e:
                        logger.warning(f"添加列失败: accounts.{column_name}, 错误: {e}")
            
            logger.info("数据库迁移完成")
            
        except Exception as e:
            logger.error(f"数据库迁移失败: {e}")

    def save_account(self, account: Account) -> bool:
        """保存账户"""
        try:
            db_service = self._get_database_service()
            account_data = account.to_dict()

            # 加密敏感字段
            account_data = self.crypto_utils.encrypt_account_data(account_data)

            # 将 metadata 字段转换为 JSON 字符串（SQLite 不支持 dict 类型）
            if 'metadata' in account_data and isinstance(account_data['metadata'], dict):
                account_data['metadata'] = json.dumps(account_data['metadata'], ensure_ascii=False)

            sql = """
            INSERT OR REPLACE INTO accounts (
                account_id, account_name, account_type, status,
                balance, available_balance, frozen_balance, market_value, total_assets,
                profit_loss, profit_loss_ratio, create_time, update_time,
                user_id, trading_day, risk_level, margin_ratio, maintenance_margin, metadata,
                institution_name, institution_type, trading_interface_type,
                ctp_broker_id, ctp_investor_id, ctp_password, ctp_trade_front, ctp_quote_front,
                ctp_app_id, ctp_auth_code, ctp_product_info,
                xtp_account_id, xtp_password, xtp_server_address,
                xtp_md_ip, xtp_md_port, xtp_protocol, xtp_buffer_size, xtp_td_ip, xtp_td_port,
                binance_api_key, binance_secret_key, binance_rest_url, binance_ws_url,
                binance_futures_api_key, binance_futures_secret_key, binance_futures_rest_url, binance_futures_ws_url,
                okx_api_key, okx_secret_key, okx_passphrase, okx_rest_url, okx_ws_url,
                okx_futures_api_key, okx_futures_secret_key, okx_futures_passphrase, okx_futures_rest_url, okx_futures_ws_url,
                huobi_api_key, huobi_secret_key, huobi_rest_url, huobi_ws_url,
                huobi_futures_api_key, huobi_futures_secret_key, huobi_futures_rest_url, huobi_futures_ws_url,
                bitget_api_key, bitget_secret_key, bitget_passphrase, bitget_rest_url, bitget_ws_url,
                bybit_api_key, bybit_secret_key, bybit_rest_url, bybit_ws_url,
                trading_interface
            ) VALUES (
                :account_id, :account_name, :account_type, :status,
                :balance, :available_balance, :frozen_balance, :market_value, :total_assets,
                :profit_loss, :profit_loss_ratio, :create_time, :update_time,
                :user_id, :trading_day, :risk_level, :margin_ratio, :maintenance_margin, :metadata,
                :institution_name, :institution_type, :trading_interface_type,
                :ctp_broker_id, :ctp_investor_id, :ctp_password, :ctp_trade_front, :ctp_quote_front,
                :ctp_app_id, :ctp_auth_code, :ctp_product_info,
                :xtp_account_id, :xtp_password, :xtp_server_address,
                :xtp_md_ip, :xtp_md_port, :xtp_protocol, :xtp_buffer_size, :xtp_td_ip, :xtp_td_port,
                :binance_api_key, :binance_secret_key, :binance_rest_url, :binance_ws_url,
                :binance_futures_api_key, :binance_futures_secret_key, :binance_futures_rest_url, :binance_futures_ws_url,
                :okx_api_key, :okx_secret_key, :okx_passphrase, :okx_rest_url, :okx_ws_url,
                :okx_futures_api_key, :okx_futures_secret_key, :okx_futures_passphrase, :okx_futures_rest_url, :okx_futures_ws_url,
                :huobi_api_key, :huobi_secret_key, :huobi_rest_url, :huobi_ws_url,
                :huobi_futures_api_key, :huobi_futures_secret_key, :huobi_futures_rest_url, :huobi_futures_ws_url,
                :bitget_api_key, :bitget_secret_key, :bitget_passphrase, :bitget_rest_url, :bitget_ws_url,
                :bybit_api_key, :bybit_secret_key, :bybit_rest_url, :bybit_ws_url,
                :trading_interface
            )
            """

            db_service.execute_query(sql, account_data, pool_name="tradeaccount_sqlite")

            logger.info(f"账户保存成功: {account.account_id}")
            self.event_bus.publish('account_saved', account_id=account.account_id)
            return True

        except Exception as e:
            logger.error(f"保存账户失败: {e}")
            return False

    def get_account(self, account_id: str) -> Optional[Account]:
        """获取账户"""
        try:
            db_service = self._get_database_service()

            sql = "SELECT * FROM accounts WHERE account_id = :account_id"
            result = db_service.fetch_one(sql, {'account_id': account_id}, pool_name="tradeaccount_sqlite")

            if result:
                # 解密敏感字段
                result = self.crypto_utils.decrypt_account_data(result)
                return Account.from_dict(result)
            return None

        except Exception as e:
            logger.error(f"获取账户失败: {e}")
            return None

    def get_accounts(self, query: AccountQuery = None) -> List[Account]:
        """获取账户列表"""
        try:
            db_service = self._get_database_service()

            sql = "SELECT * FROM accounts WHERE 1=1"
            params = {}

            if query:
                if query.account_id:
                    sql += " AND account_id = :account_id"
                    params['account_id'] = query.account_id
                if query.user_id:
                    sql += " AND user_id = :user_id"
                    params['user_id'] = query.user_id
                if query.account_type:
                    sql += " AND account_type = :account_type"
                    params['account_type'] = query.account_type
                if query.status:
                    sql += " AND status = :status"
                    params['status'] = query.status.value

            sql += f" ORDER BY {query.sort_by if query else 'update_time'} {query.sort_order if query else 'DESC'}"
            
            if query:
                sql += f" LIMIT {query.limit} OFFSET {query.offset}"

            results = db_service.fetch_all(sql, params, pool_name="tradeaccount_sqlite")
            accounts = []
            for r in results:
                r = self.crypto_utils.decrypt_account_data(r)
                accounts.append(Account.from_dict(r))
            return accounts

        except Exception as e:
            logger.error(f"获取账户列表失败: {e}")
            return []

    def delete_account(self, account_id: str) -> bool:
        """删除账户"""
        try:
            db_service = self._get_database_service()

            sql = "DELETE FROM accounts WHERE account_id = :account_id"
            db_service.execute_query(sql, {'account_id': account_id}, pool_name="tradeaccount_sqlite")

            logger.info(f"账户删除成功: {account_id}")
            self.event_bus.publish('account_deleted', account_id=account_id)
            return True

        except Exception as e:
            logger.error(f"删除账户失败: {e}")
            return False

    def save_position(self, position: Position) -> bool:
        """保存持仓"""
        try:
            db_service = self._get_database_service()
            position_data = position.to_dict()

            # 将 metadata 字段转换为 JSON 字符串（SQLite 不支持 dict 类型）
            if 'metadata' in position_data and isinstance(position_data['metadata'], dict):
                position_data['metadata'] = json.dumps(position_data['metadata'], ensure_ascii=False)

            sql = """
            INSERT OR REPLACE INTO positions (
                position_id, account_id, asset_type, stock_code, stock_name, side,
                quantity, available_quantity, open_price, current_price, market_value,
                cost_price, cost_value, profit_loss, profit_loss_ratio,
                open_time, update_time, commission, metadata
            ) VALUES (
                :position_id, :account_id, :asset_type, :stock_code, :stock_name, :side,
                :quantity, :available_quantity, :open_price, :current_price, :market_value,
                :cost_price, :cost_value, :profit_loss, :profit_loss_ratio,
                :open_time, :update_time, :commission, :metadata
            )
            """

            db_service.execute_query(sql, position_data, pool_name="tradeaccount_sqlite")

            logger.info(f"持仓保存成功: {position.position_id}")
            self.event_bus.publish('position_saved', position_id=position.position_id)
            return True

        except Exception as e:
            logger.error(f"保存持仓失败: {e}")
            return False

    def get_positions(self, query: PositionQuery = None) -> List[Position]:
        """获取持仓列表"""
        try:
            db_service = self._get_database_service()

            sql = "SELECT * FROM positions WHERE 1=1"
            params = {}

            if query:
                if query.account_id:
                    sql += " AND account_id = :account_id"
                    params['account_id'] = query.account_id
                if query.asset_type:
                    sql += " AND asset_type = :asset_type"
                    params['asset_type'] = query.asset_type.value
                if query.stock_code:
                    sql += " AND stock_code = :stock_code"
                    params['stock_code'] = query.stock_code
                if query.side:
                    sql += " AND side = :side"
                    params['side'] = query.side.value

            sql += f" ORDER BY {query.sort_by if query else 'update_time'} {query.sort_order if query else 'DESC'}"
            
            if query:
                sql += f" LIMIT {query.limit} OFFSET {query.offset}"

            results = db_service.fetch_all(sql, params, pool_name="tradeaccount_sqlite")
            return [Position.from_dict(r) for r in results]

        except Exception as e:
            logger.error(f"获取持仓列表失败: {e}")
            return []

    def delete_position(self, position_id: str) -> bool:
        """删除持仓"""
        try:
            db_service = self._get_database_service()

            sql = "DELETE FROM positions WHERE position_id = :position_id"
            db_service.execute_query(sql, {'position_id': position_id}, pool_name="tradeaccount_sqlite")

            logger.info(f"持仓删除成功: {position_id}")
            self.event_bus.publish('position_deleted', position_id=position_id)
            return True

        except Exception as e:
            logger.error(f"删除持仓失败: {e}")
            return False

    def save_fund_info(self, fund_info: FundInfo) -> bool:
        """保存资金信息"""
        try:
            db_service = self._get_database_service()
            fund_data = fund_info.to_dict()

            # 将 metadata 字段转换为 JSON 字符串（SQLite 不支持 dict 类型）
            if 'metadata' in fund_data and isinstance(fund_data['metadata'], dict):
                fund_data['metadata'] = json.dumps(fund_data['metadata'], ensure_ascii=False)

            sql = """
            INSERT OR REPLACE INTO fund_infos (
                account_id, total_balance, available_balance, frozen_balance, market_value,
                total_assets, profit_loss, profit_loss_ratio, margin_used, margin_available,
                maintenance_margin, update_time, metadata
            ) VALUES (
                :account_id, :total_balance, :available_balance, :frozen_balance, :market_value,
                :total_assets, :profit_loss, :profit_loss_ratio, :margin_used, :margin_available,
                :maintenance_margin, :update_time, :metadata
            )
            """

            db_service.execute_query(sql, fund_data, pool_name="tradeaccount_sqlite")

            logger.info(f"资金信息保存成功: {fund_info.account_id}")
            self.event_bus.publish('fund_info_saved', account_id=fund_info.account_id)
            return True

        except Exception as e:
            logger.error(f"保存资金信息失败: {e}")
            return False

    def get_fund_info(self, account_id: str) -> Optional[FundInfo]:
        """获取资金信息"""
        try:
            db_service = self._get_database_service()

            sql = "SELECT * FROM fund_infos WHERE account_id = :account_id"
            result = db_service.fetch_one(sql, {'account_id': account_id}, pool_name="tradeaccount_sqlite")

            if result:
                return FundInfo.from_dict(result)
            return None

        except Exception as e:
            logger.error(f"获取资金信息失败: {e}")
            return None

    def get_all_fund_infos(self) -> List[FundInfo]:
        """获取所有资金信息"""
        try:
            db_service = self._get_database_service()

            sql = "SELECT * FROM fund_infos ORDER BY update_time DESC"
            results = db_service.fetch_all(sql, pool_name="tradeaccount_sqlite")
            return [FundInfo.from_dict(r) for r in results]

        except Exception as e:
            logger.error(f"获取资金信息列表失败: {e}")
            return []
