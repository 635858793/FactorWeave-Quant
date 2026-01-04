from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FactorWeave-Quant 完整数据库初始化脚本

本脚本负责初始化系统所需的所有数据库表和初始数据：
1. SQLite数据库 - 用于OLTP操作（配置、用户数据、插件管理等）
2. DuckDB数据库 - 用于OLAP操作（分析、回测、性能监控等）

执行顺序：
1. 创建SQLite数据库表结构
2. 插入SQLite初始数据
3. 创建DuckDB数据库表结构
4. 插入DuckDB初始数据
5. 验证数据库完整性
"""

import sqlite3
import duckdb
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional


class CompleteDatabaseInitializer:
    """完整数据库初始化器"""

    def __init__(self):
        self.db_dir = Path(__file__).parent.parent / "data"
        self.sqlite_db_path = self.db_dir / "factorweave_system.sqlite"
        self.factorweave_db_path = self.db_dir / "factorweave_system.sqlite"
        self.duckdb_analytics_path = self.db_dir / "factorweave_analytics.duckdb"

    def initialize_all_databases(self):
        """初始化所有数据库"""
        logger.info("开始初始化FactorWeave-Quant完整数据库系统")

        try:
            # 1. 初始化SQLite数据库
            self.initialize_sqlite_databases()

            # 2. 初始化DuckDB分析数据库
            self.initialize_duckdb_database()

            # 3. 验证数据库完整性
            self.verify_database_integrity()

            logger.info("SUCCESS 数据库系统初始化完成")
            return True

        except Exception as e:
            logger.error(f"ERROR 数据库初始化失败: {e}")
            return False

    def initialize_sqlite_databases(self):
        """初始化SQLite数据库"""
        logger.info("初始化SQLite数据库...")

        # 初始化主系统数据库
        self._init_factorweave_system_db()

        # 初始化FactorWeave系统数据库
        self._init_factorweave_system_db()

        logger.info("SUCCESS SQLite数据库初始化完成")

    def _init_factorweave_system_db(self):
        """初始化FactorWeave-Quant系统数据库（已移除hikyuu依赖）"""
        logger.info("创建FactorWeave-Quant系统数据库表...")

        with sqlite3.connect(self.sqlite_db_path) as conn:
            cursor = conn.cursor()

            # 1. 系统配置表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 2. 数据源表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_source (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                config TEXT,
                is_active INTEGER DEFAULT 0,
                priority INTEGER DEFAULT 50,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 3. 用户收藏表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                fav_type TEXT NOT NULL,
                fav_key TEXT NOT NULL,
                fav_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 4. 行业表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS industry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER,
                level INTEGER DEFAULT 1,
                code TEXT UNIQUE,
                extra TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 5. 市场表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS market (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT UNIQUE NOT NULL,
                region TEXT DEFAULT 'CN',
                timezone TEXT DEFAULT 'Asia/Shanghai',
                extra TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 6. 股票表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                market_code TEXT NOT NULL,
                type TEXT DEFAULT 'stock',
                valid INTEGER DEFAULT 1,
                start_date TEXT,
                end_date TEXT,
                industry_id INTEGER,
                extra TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (industry_id) REFERENCES industry (id),
                FOREIGN KEY (market_code) REFERENCES market (code)
            )''')

            # 7. 概念表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS concept (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                extra TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 8. 指标表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS indicator (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                params TEXT,
                description TEXT,
                formula TEXT,
                extra TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 9. 用户日志表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 10. 历史记录表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                record_type TEXT NOT NULL,
                record_key TEXT NOT NULL,
                record_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 11. 指标组合表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS indicator_combination (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                user_id TEXT NOT NULL,
                indicators TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                extra TEXT
            )''')

            # 12. 主题表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS themes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                origin TEXT DEFAULT 'system',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )''')

            # 13. 形态模式表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS pattern_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                english_name TEXT,
                category TEXT NOT NULL,
                signal_type TEXT,
                description TEXT,
                min_periods INTEGER DEFAULT 5,
                max_periods INTEGER DEFAULT 60,
                confidence_threshold REAL DEFAULT 0.5,
                algorithm_code TEXT,
                parameters TEXT,
                success_rate REAL DEFAULT 0.7,
                risk_level TEXT DEFAULT 'medium',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 14. 形态历史表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS pattern_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                trigger_date TEXT NOT NULL,
                trigger_price REAL NOT NULL,
                result_date TEXT,
                result_price REAL,
                return_rate REAL,
                is_successful INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 15. 插件表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS plugins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                version TEXT NOT NULL,
                plugin_type TEXT NOT NULL,
                category TEXT,
                description TEXT,
                author TEXT,
                status TEXT DEFAULT 'disabled',
                config TEXT,
                metadata TEXT,
                file_path TEXT,
                class_name TEXT,
                priority INTEGER DEFAULT 50,
                last_enabled_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 16. AI预测配置表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_prediction_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT NOT NULL,
                config_type TEXT NOT NULL DEFAULT 'json',
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1
            )''')

            # 17. AI配置历史表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_config_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                changed_by TEXT DEFAULT 'system',
                changed_at TEXT NOT NULL
            )''')

            # 18. DuckDB配置表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS duckdb_config_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_name TEXT UNIQUE NOT NULL,
                description TEXT,
                workload_type TEXT DEFAULT 'OLAP',
                
                -- 内存配置
                memory_limit TEXT DEFAULT '4.0GB',
                max_memory TEXT DEFAULT '4.4GB',
                buffer_pool_size TEXT DEFAULT '1GB',
                temp_memory_limit TEXT DEFAULT '2GB',
                
                -- 线程配置
                threads INTEGER DEFAULT 4,
                io_threads INTEGER DEFAULT 2,
                parallel_tasks INTEGER DEFAULT 4,
                worker_threads INTEGER DEFAULT 3,
                
                -- 存储配置
                checkpoint_threshold TEXT DEFAULT '512MB',
                wal_autocheckpoint INTEGER DEFAULT 5000,
                temp_directory_size TEXT DEFAULT '20GB',
                enable_fsync BOOLEAN DEFAULT 1,
                enable_mmap BOOLEAN DEFAULT 1,
                
                -- 查询配置
                enable_optimizer BOOLEAN DEFAULT 1,
                enable_profiling BOOLEAN DEFAULT 0,
                enable_progress_bar BOOLEAN DEFAULT 1,
                enable_object_cache BOOLEAN DEFAULT 1,
                max_expression_depth INTEGER DEFAULT 1000,
                enable_external_access BOOLEAN DEFAULT 1,
                enable_httpfs BOOLEAN DEFAULT 1,
                enable_parquet_statistics BOOLEAN DEFAULT 1,
                preserve_insertion_order BOOLEAN DEFAULT 0,
                enable_verification BOOLEAN DEFAULT 0,
                
                -- 高级配置
                force_parallelism BOOLEAN DEFAULT 1,
                enable_join_order_optimizer BOOLEAN DEFAULT 1,
                enable_unnest_rewriter BOOLEAN DEFAULT 1,
                enable_object_cache_map BOOLEAN DEFAULT 1,
                enable_auto_analyze BOOLEAN DEFAULT 1,
                auto_analyze_sample_size INTEGER DEFAULT 100000,
                enable_compression BOOLEAN DEFAULT 1,
                compression_level INTEGER DEFAULT 6,
                http_timeout INTEGER DEFAULT 30000,
                http_retries INTEGER DEFAULT 3,
                
                -- 元数据
                is_active BOOLEAN DEFAULT 0,
                is_default BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT DEFAULT 'system'
            )''')

            # 19. DuckDB配置历史表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS duckdb_config_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                old_config TEXT,
                new_config TEXT,
                changed_by TEXT DEFAULT 'system',
                changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES duckdb_config_profiles (id)
            )''')

            # 20. 数据源插件配置表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_source_plugin_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plugin_id TEXT NOT NULL,
                config_data TEXT NOT NULL,
                priority INTEGER DEFAULT 50,
                weight REAL DEFAULT 1.0,
                enabled BOOLEAN DEFAULT 1,
                health_check_interval INTEGER DEFAULT 30,
                timeout_seconds INTEGER DEFAULT 30,
                retry_count INTEGER DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(plugin_id)
            )''')

            # 21. 数据源路由配置表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_source_routing_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_type TEXT NOT NULL,
                plugin_priorities TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(asset_type)
            )''')

            # 22. 策略表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                strategy_type TEXT NOT NULL,
                version TEXT NOT NULL DEFAULT '1.0.0',
                author TEXT DEFAULT '',
                description TEXT DEFAULT '',
                category TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                metadata TEXT DEFAULT '{}',
                class_path TEXT NOT NULL
            )''')

            # 23. 策略参数表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_parameters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER NOT NULL,
                param_name TEXT NOT NULL,
                param_value TEXT NOT NULL,
                param_type TEXT NOT NULL,
                description TEXT DEFAULT '',
                min_value TEXT DEFAULT NULL,
                max_value TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (strategy_id) REFERENCES strategies (id) ON DELETE CASCADE,
                UNIQUE(strategy_id, param_name)
            )''')

            conn.commit()

        # 插入初始数据
        self._insert_sqlite_initial_data()

    def _init_factorweave_system_db(self):
        """初始化FactorWeave系统数据库"""
        logger.info("创建FactorWeave系统数据库表...")

        with sqlite3.connect(self.factorweave_db_path) as conn:
            cursor = conn.cursor()

            # FactorWeave特有的系统配置表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS factorweave_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module TEXT NOT NULL,
                config_key TEXT NOT NULL,
                config_value TEXT NOT NULL,
                config_type TEXT DEFAULT 'string',
                description TEXT,
                is_encrypted BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(module, config_key)
            )''')

            # 系统监控配置表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_monitor_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                monitor_type TEXT NOT NULL,
                config_data TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                check_interval INTEGER DEFAULT 60,
                alert_threshold TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            conn.commit()

    def _insert_sqlite_initial_data(self):
        """插入SQLite初始数据"""
        logger.info("插入SQLite初始数据...")

        with sqlite3.connect(self.sqlite_db_path) as conn:
            cursor = conn.cursor()

            # 插入系统配置
            config_data = [
                ('system.version', '2.0.0', 'FactorWeave-Quant系统版本'),
                ('system.initialized', 'true', '系统是否已初始化'),
                ('system.theme', 'default', '系统默认主题'),
                ('database.sqlite_path', str(self.sqlite_db_path), 'SQLite数据库路径'),
                ('database.duckdb_path', str(self.duckdb_analytics_path), 'DuckDB数据库路径'),
                ('ui.language', 'zh_CN', '界面语言'),
                ('ui.auto_refresh', 'true', '自动刷新'),
                ('performance.enable_cache', 'true', '启用缓存'),
                ('performance.cache_size', '1000', '缓存大小'),
            ]

            cursor.executemany('''
                INSERT OR IGNORE INTO config (key, value, description) 
                VALUES (?, ?, ?)
            ''', config_data)

            # 插入市场数据
            market_data = [
                ('SH', '上海证券交易所', 'CN', 'Asia/Shanghai', '{}'),
                ('SZ', '深圳证券交易所', 'CN', 'Asia/Shanghai', '{}'),
                ('BJ', '北京证券交易所', 'CN', 'Asia/Shanghai', '{}'),
                ('HK', '香港交易所', 'HK', 'Asia/Hong_Kong', '{}'),
                ('US', '美国股市', 'US', 'America/New_York', '{}'),
            ]

            cursor.executemany('''
                INSERT OR IGNORE INTO market (code, name, region, timezone, extra) 
                VALUES (?, ?, ?, ?, ?)
            ''', market_data)

            # 插入形态类型数据
            pattern_data = [
                # 反转形态 - 顶部
                ('双顶', 'double_top', '反转形态', 'sell',
                 '双顶是一种看跌反转形态，当价格形成两个相近的高点后，通常会向下突破', 15, 40, 0.6, 0.75, 'medium', 1),
                ('头肩顶', 'head_shoulders_top', '反转形态', 'sell',
                 '头肩顶是最可靠的看跌反转形态，由左肩、头部、右肩三个高点组成', 20, 60, 0.7, 0.8, 'high', 1),
                ('三重顶', 'triple_top', '反转形态', 'sell',
                 '三重顶由三个相近的高点组成，是强烈的看跌信号', 25, 50, 0.65, 0.7, 'medium', 1),

                # 反转形态 - 底部
                ('双底', 'double_bottom', '反转形态', 'buy',
                 '双底是一种看涨反转形态，当价格形成两个相近的低点后，通常会向上突破', 15, 40, 0.6, 0.75, 'medium', 1),
                ('头肩底', 'head_shoulders_bottom', '反转形态', 'buy',
                 '头肩底是最可靠的看涨反转形态，由左肩、头部、右肩三个低点组成', 20, 60, 0.7, 0.8, 'high', 1),

                # 持续形态
                ('上升三角形', 'ascending_triangle', '持续形态', 'buy',
                 '上升三角形是看涨的持续形态，表示价格将继续上涨', 10, 30, 0.6, 0.7, 'medium', 1),
                ('下降三角形', 'descending_triangle', '持续形态', 'sell',
                 '下降三角形是看跌的持续形态，表示价格将继续下跌', 10, 30, 0.6, 0.7, 'medium', 1),

                # 单K线形态
                ('锤头线', 'hammer', '单K线形态', 'buy',
                 '锤头线是看涨反转信号，具有小实体和长下影线', 1, 1, 0.5, 0.6, 'low', 1),
                ('上吊线', 'hanging_man', '单K线形态', 'sell',
                 '上吊线是看跌反转信号，出现在上升趋势的顶部', 1, 1, 0.5, 0.6, 'low', 1),
            ]

            cursor.executemany('''
                INSERT OR IGNORE INTO pattern_types 
                (name, english_name, category, signal_type, description, min_periods, max_periods, 
                 confidence_threshold, success_rate, risk_level, is_active) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', pattern_data)

            # 插入默认主题
            theme_data = [
                ('default', 'theme', '{"colors": {"primary": "#1976d2", "secondary": "#dc004e"}}', 'system'),
                ('dark', 'theme', '{"colors": {"primary": "#90caf9", "secondary": "#f48fb1"}}', 'system'),
            ]

            cursor.executemany('''
                INSERT OR IGNORE INTO themes (name, type, content, origin) 
                VALUES (?, ?, ?, ?)
            ''', theme_data)

            # 插入AI预测配置
            ai_config_data = [
                ('model.pattern.enabled', 'true', 'boolean', '是否启用形态识别模型'),
                ('model.trend.enabled', 'true', 'boolean', '是否启用趋势预测模型'),
                ('model.sentiment.enabled', 'true', 'boolean', '是否启用情绪分析模型'),
                ('model.price.enabled', 'true', 'boolean', '是否启用价格预测模型'),
                ('training.batch_size', '32', 'integer', '训练批次大小'),
                ('training.epochs', '100', 'integer', '训练轮数'),
                ('training.learning_rate', '0.001', 'float', '学习率'),
                ('prediction.confidence_threshold', '0.7', 'float', '预测置信度阈值'),
            ]

            current_time = datetime.now().isoformat()
            for key, value, config_type, desc in ai_config_data:
                cursor.execute('''
                    INSERT OR IGNORE INTO ai_prediction_config 
                    (config_key, config_value, config_type, description, created_at, updated_at) 
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (key, value, config_type, desc, current_time, current_time))

            # 插入DuckDB配置
            duckdb_config_data = [
                ('default', '默认OLAP配置', 'OLAP', '4.0GB', '4.4GB', '1GB', '2GB',
                 4, 2, 4, 3, '512MB', 5000, '20GB', 1, 1, 1, 0, 1, 1, 1000, 1, 1, 1, 0, 0,
                 1, 1, 1, 1, 1, 100000, 1, 6, 30000, 3, 1, 1),
                ('high_performance', '高性能配置', 'OLAP', '8.0GB', '8.8GB', '2GB', '4GB',
                 8, 4, 8, 6, '1GB', 10000, '40GB', 1, 1, 1, 0, 1, 1, 2000, 1, 1, 1, 0, 0,
                 1, 1, 1, 1, 1, 200000, 1, 9, 60000, 5, 0, 0),
            ]

            cursor.executemany('''
                INSERT OR IGNORE INTO duckdb_config_profiles 
                (profile_name, description, workload_type, memory_limit, max_memory, buffer_pool_size, temp_memory_limit,
                 threads, io_threads, parallel_tasks, worker_threads, checkpoint_threshold, wal_autocheckpoint, 
                 temp_directory_size, enable_fsync, enable_mmap, enable_optimizer, enable_profiling, enable_progress_bar,
                 enable_object_cache, max_expression_depth, enable_external_access, enable_httpfs, 
                 enable_parquet_statistics, preserve_insertion_order, enable_verification, force_parallelism,
                 enable_join_order_optimizer, enable_unnest_rewriter, enable_object_cache_map, enable_auto_analyze,
                 auto_analyze_sample_size, enable_compression, compression_level, http_timeout, http_retries,
                 is_active, is_default)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', duckdb_config_data)

            # 设置默认配置为激活状态
            cursor.execute("UPDATE duckdb_config_profiles SET is_active = 1, is_default = 1 WHERE profile_name = 'default'")

            conn.commit()

    def initialize_duckdb_database(self):
        """初始化DuckDB分析数据库"""
        logger.info("初始化DuckDB分析数据库...")

        conn = duckdb.connect(str(self.duckdb_analytics_path))

        try:
            # 创建序列
            sequences = [
                'strategy_execution_results_seq',
                'indicator_calculation_results_seq',
                'pattern_recognition_results_seq',
                'backtest_metrics_history_seq',
                'backtest_alerts_history_seq',
                'performance_metrics_seq',
                'optimization_logs_seq',
                'analysis_cache_seq'
            ]

            for seq_name in sequences:
                conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq_name}")

            # 1. 策略执行结果表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_execution_results (
                    id INTEGER PRIMARY KEY DEFAULT nextval('strategy_execution_results_seq'),
                    strategy_name VARCHAR NOT NULL,
                    symbol VARCHAR NOT NULL,
                    execution_time TIMESTAMP NOT NULL,
                    signal_type VARCHAR NOT NULL,
                    price DOUBLE,
                    quantity INTEGER,
                    confidence DOUBLE,
                    reason TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. 技术指标计算结果表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS indicator_calculation_results (
                    id INTEGER PRIMARY KEY DEFAULT nextval('indicator_calculation_results_seq'),
                    symbol VARCHAR NOT NULL,
                    indicator_name VARCHAR NOT NULL,
                    calculation_time TIMESTAMP NOT NULL,
                    timeframe VARCHAR NOT NULL,
                    value DOUBLE,
                    signal VARCHAR,
                    confidence DOUBLE,
                    parameters TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 3. 形态识别结果表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pattern_recognition_results (
                    id INTEGER PRIMARY KEY DEFAULT nextval('pattern_recognition_results_seq'),
                    symbol VARCHAR NOT NULL,
                    pattern_type VARCHAR NOT NULL,
                    recognition_time TIMESTAMP NOT NULL,
                    timeframe VARCHAR NOT NULL,
                    confidence DOUBLE NOT NULL,
                    signal_type VARCHAR NOT NULL,
                    start_index INTEGER,
                    end_index INTEGER,
                    key_points TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 4. 回测指标历史表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backtest_metrics_history (
                    id INTEGER PRIMARY KEY DEFAULT nextval('backtest_metrics_history_seq'),
                    strategy_name VARCHAR NOT NULL,
                    symbol VARCHAR NOT NULL,
                    backtest_start_date DATE NOT NULL,
                    backtest_end_date DATE NOT NULL,
                    total_return DOUBLE,
                    annual_return DOUBLE,
                    max_drawdown DOUBLE,
                    sharpe_ratio DOUBLE,
                    sortino_ratio DOUBLE,
                    win_rate DOUBLE,
                    profit_factor DOUBLE,
                    total_trades INTEGER,
                    winning_trades INTEGER,
                    losing_trades INTEGER,
                    avg_win DOUBLE,
                    avg_loss DOUBLE,
                    largest_win DOUBLE,
                    largest_loss DOUBLE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 5. 回测警报历史表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backtest_alerts_history (
                    id INTEGER PRIMARY KEY DEFAULT nextval('backtest_alerts_history_seq'),
                    strategy_name VARCHAR NOT NULL,
                    symbol VARCHAR NOT NULL,
                    alert_type VARCHAR NOT NULL,
                    alert_time TIMESTAMP NOT NULL,
                    message TEXT NOT NULL,
                    severity VARCHAR DEFAULT 'info',
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 6. 性能指标表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY DEFAULT nextval('performance_metrics_seq'),
                    version_id INTEGER NOT NULL,
                    pattern_name VARCHAR NOT NULL,
                    test_dataset_id VARCHAR,
                    test_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    true_positives INTEGER DEFAULT 0,
                    false_positives INTEGER DEFAULT 0,
                    true_negatives INTEGER DEFAULT 0,
                    false_negatives INTEGER DEFAULT 0,
                    precision DOUBLE,
                    recall DOUBLE,
                    f1_score DOUBLE,
                    accuracy DOUBLE,
                    execution_time DOUBLE,
                    memory_usage DOUBLE,
                    cpu_usage DOUBLE,
                    signal_quality DOUBLE,
                    confidence_avg DOUBLE,
                    confidence_std DOUBLE,
                    patterns_found INTEGER DEFAULT 0,
                    robustness_score DOUBLE,
                    parameter_sensitivity DOUBLE,
                    overall_score DOUBLE,
                    test_conditions TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 7. 优化日志表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS optimization_logs (
                    id INTEGER PRIMARY KEY DEFAULT nextval('optimization_logs_seq'),
                    pattern_name VARCHAR NOT NULL,
                    optimization_session_id VARCHAR UNIQUE NOT NULL,
                    optimization_method VARCHAR NOT NULL,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    status VARCHAR DEFAULT 'running',
                    initial_version_id INTEGER,
                    final_version_id INTEGER,
                    iterations INTEGER DEFAULT 0,
                    best_score DOUBLE,
                    improvement_percentage DOUBLE,
                    optimization_config TEXT,
                    optimization_log TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 8. 分析缓存表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    id INTEGER PRIMARY KEY DEFAULT nextval('analysis_cache_seq'),
                    cache_key VARCHAR UNIQUE NOT NULL,
                    cache_type VARCHAR NOT NULL,
                    data TEXT NOT NULL,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建索引
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_strategy_execution_symbol ON strategy_execution_results(symbol)",
                "CREATE INDEX IF NOT EXISTS idx_strategy_execution_time ON strategy_execution_results(execution_time)",
                "CREATE INDEX IF NOT EXISTS idx_indicator_calculation_symbol ON indicator_calculation_results(symbol)",
                "CREATE INDEX IF NOT EXISTS idx_indicator_calculation_time ON indicator_calculation_results(calculation_time)",
                "CREATE INDEX IF NOT EXISTS idx_pattern_recognition_symbol ON pattern_recognition_results(symbol)",
                "CREATE INDEX IF NOT EXISTS idx_pattern_recognition_time ON pattern_recognition_results(recognition_time)",
                "CREATE INDEX IF NOT EXISTS idx_backtest_metrics_strategy ON backtest_metrics_history(strategy_name)",
                "CREATE INDEX IF NOT EXISTS idx_backtest_alerts_strategy ON backtest_alerts_history(strategy_name)",
                "CREATE INDEX IF NOT EXISTS idx_performance_metrics_pattern ON performance_metrics(pattern_name)",
                "CREATE INDEX IF NOT EXISTS idx_optimization_logs_session ON optimization_logs(optimization_session_id)",
                "CREATE INDEX IF NOT EXISTS idx_analysis_cache_type ON analysis_cache(cache_type)",
                "CREATE INDEX IF NOT EXISTS idx_analysis_cache_expires ON analysis_cache(expires_at)",
                "CREATE INDEX IF NOT EXISTS idx_analysis_cache_key ON analysis_cache(cache_key)",
            ]

            for index_sql in indexes:
                conn.execute(index_sql)

            conn.commit()

            # 插入初始测试数据
            self._insert_duckdb_initial_data(conn)

        finally:
            conn.close()

        logger.info("SUCCESS DuckDB分析数据库初始化完成")

    def _insert_duckdb_initial_data(self, conn):
        """插入DuckDB初始数据"""
        logger.info("插入DuckDB初始数据...")

        # 插入测试分析缓存数据（移除智能性能洞察相关数据）
        test_cache_data = [
            # 基础缓存数据保留
            ("test_analysis_1", "technical_analysis",
             '{"indicators": {"RSI": 65.5, "MACD": 0.25}, "signals": ["BUY"]}',
             datetime.now() + timedelta(hours=1)),
            ("test_analysis_2", "pattern_recognition",
             '{"patterns": ["double_bottom", "ascending_triangle"], "confidence": 0.85}',
             datetime.now() + timedelta(hours=2)),
            ("test_analysis_3", "market_sentiment",
             '{"sentiment_score": 0.72, "news_count": 15, "social_mentions": 245}',
             datetime.now() + timedelta(hours=1)),
        ]

        for data in test_cache_data:
            conn.execute("""
                INSERT INTO analysis_cache 
                (cache_key, cache_type, data, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, data)

        conn.commit()

    def verify_database_integrity(self):
        """验证数据库完整性"""
        logger.info("验证数据库完整性...")

        # 验证SQLite数据库
        with sqlite3.connect(self.sqlite_db_path) as conn:
            cursor = conn.cursor()

            # 检查表数量
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            logger.info(f"  SQLite数据库表数量: {table_count}")

            # 检查关键表的记录数
            key_tables = ['config', 'market', 'pattern_types', 'ai_prediction_config', 'duckdb_config_profiles']
            for table in key_tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    logger.info(f"    {table}: {count} 条记录")
                except sqlite3.OperationalError as e:
                    logger.warning(f"    {table}: 表不存在或查询失败 - {e}")

        # 验证DuckDB数据库
        conn = duckdb.connect(str(self.duckdb_analytics_path))
        try:
            # 检查表数量
            result = conn.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'main'").fetchone()
            table_count = result[0] if result else 0
            logger.info(f"  DuckDB数据库表数量: {table_count}")

            # 检查关键表的记录数
            key_tables = ['analysis_cache', 'performance_metrics', 'optimization_logs']
            for table in key_tables:
                try:
                    result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                    count = result[0] if result else 0
                    logger.info(f"    {table}: {count} 条记录")
                except Exception as e:
                    logger.warning(f"    {table}: 表不存在或查询失败 - {e}")
        finally:
            conn.close()

        logger.info("SUCCESS 数据库完整性验证完成")

    def create_indexes(self):
        """创建性能优化索引"""
        logger.info("创建性能优化索引...")

        # SQLite索引
        with sqlite3.connect(self.sqlite_db_path) as conn:
            cursor = conn.cursor()

            sqlite_indexes = [
                "CREATE INDEX IF NOT EXISTS idx_config_key ON config(key)",
                "CREATE INDEX IF NOT EXISTS idx_stock_code ON stock(code)",
                "CREATE INDEX IF NOT EXISTS idx_stock_market ON stock(market_code)",
                "CREATE INDEX IF NOT EXISTS idx_pattern_types_category ON pattern_types(category)",
                "CREATE INDEX IF NOT EXISTS idx_pattern_types_signal ON pattern_types(signal_type)",
                "CREATE INDEX IF NOT EXISTS idx_plugins_type ON plugins(plugin_type)",
                "CREATE INDEX IF NOT EXISTS idx_plugins_status ON plugins(status)",
                "CREATE INDEX IF NOT EXISTS idx_ai_config_key ON ai_prediction_config(config_key)",
                "CREATE INDEX IF NOT EXISTS idx_duckdb_profiles_active ON duckdb_config_profiles(is_active)",
            ]

            for index_sql in sqlite_indexes:
                try:
                    cursor.execute(index_sql)
                except sqlite3.OperationalError as e:
                    logger.warning(f"创建SQLite索引失败: {e}")

            conn.commit()

        logger.info("索引创建完成")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("FactorWeave-Quant 完整数据库初始化系统")
    logger.info("=" * 60)

    initializer = CompleteDatabaseInitializer()

    if initializer.initialize_all_databases():
        logger.info("\n 数据库系统初始化成功！")
        logger.info("\n 初始化内容:")
        logger.info(" SQLite系统数据库 (OLTP)")
        logger.info(" DuckDB分析数据库 (OLAP)")
        logger.info(" 完整表结构和索引")
        logger.info(" 初始配置和数据")
        logger.info(" 性能优化配置")

        logger.info("\n 数据库文件:")
        logger.info(f"   SQLite: {initializer.sqlite_db_path}")
        logger.info(f"   FactorWeave: {initializer.factorweave_db_path}")
        logger.info(f"   DuckDB: {initializer.duckdb_analytics_path}")

        return True
    else:
        logger.info("\n 数据库系统初始化失败！")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
