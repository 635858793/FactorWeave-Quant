from loguru import logger
"""
DuckDB表结构定义

定义所有数据表的SQL结构，包括：
- 财务报表表结构
- 宏观经济数据表结构
- 索引和约束定义
- 分区策略

作者: FactorWeave-Quant团队
版本: 1.0
"""

from typing import Dict, List, Optional
from enum import Enum

class TableStructureType(Enum):
    """表结构类型"""
    FINANCIAL_STATEMENT = "financial_statement"
    MACRO_ECONOMIC = "macro_economic"
    KLINE_DATA = "kline_data"
    STOCK_BASIC_INFO = "stock_basic_info"

class DuckDBTableSchemas:
    """DuckDB表结构定义类"""

    @staticmethod
    def get_financial_statement_schema(plugin_name: str) -> str:
        """
        获取财务报表表结构SQL

        Args:
            plugin_name: 插件名称

        Returns:
            CREATE TABLE SQL语句
        """
        table_name = f"financial_statements_{plugin_name}"

        return f"""
CREATE TABLE {table_name} (
    -- 基础信息
    symbol VARCHAR NOT NULL,
    report_date DATE NOT NULL,
    report_type VARCHAR NOT NULL,
    report_period VARCHAR,
    fiscal_year INTEGER,
    
    -- === 资产负债表 ===
    -- 资产
    total_assets DECIMAL(20,2),
    current_assets DECIMAL(20,2),
    non_current_assets DECIMAL(20,2),
    cash_and_equivalents DECIMAL(20,2),
    short_term_investments DECIMAL(20,2),
    accounts_receivable DECIMAL(20,2),
    inventory DECIMAL(20,2),
    prepaid_expenses DECIMAL(20,2),
    fixed_assets DECIMAL(20,2),
    intangible_assets DECIMAL(20,2),
    goodwill DECIMAL(20,2),
    
    -- 负债
    total_liabilities DECIMAL(20,2),
    current_liabilities DECIMAL(20,2),
    non_current_liabilities DECIMAL(20,2),
    accounts_payable DECIMAL(20,2),
    short_term_debt DECIMAL(20,2),
    long_term_debt DECIMAL(20,2),
    accrued_expenses DECIMAL(20,2),
    
    -- 股东权益
    shareholders_equity DECIMAL(20,2),
    paid_in_capital DECIMAL(20,2),
    retained_earnings DECIMAL(20,2),
    accumulated_other_comprehensive_income DECIMAL(20,2),
    
    -- === 利润表 ===
    operating_revenue DECIMAL(20,2),
    operating_costs DECIMAL(20,2),
    gross_profit DECIMAL(20,2),
    operating_expenses DECIMAL(20,2),
    selling_expenses DECIMAL(20,2),
    admin_expenses DECIMAL(20,2),
    rd_expenses DECIMAL(20,2),
    financial_expenses DECIMAL(20,2),
    operating_profit DECIMAL(20,2),
    non_operating_income DECIMAL(20,2),
    non_operating_expenses DECIMAL(20,2),
    profit_before_tax DECIMAL(20,2),
    income_tax DECIMAL(20,2),
    net_profit DECIMAL(20,2),
    net_profit_attributable_to_parent DECIMAL(20,2),
    
    -- 每股指标
    eps DECIMAL(10,4),
    diluted_eps DECIMAL(10,4),
    book_value_per_share DECIMAL(10,4),
    
    -- === 现金流量表 ===
    operating_cash_flow DECIMAL(20,2),
    investing_cash_flow DECIMAL(20,2),
    financing_cash_flow DECIMAL(20,2),
    net_cash_flow DECIMAL(20,2),
    free_cash_flow DECIMAL(20,2),
    
    -- 经营活动现金流明细
    cash_from_operations DECIMAL(20,2),
    cash_paid_for_goods DECIMAL(20,2),
    cash_paid_to_employees DECIMAL(20,2),
    cash_paid_for_taxes DECIMAL(20,2),
    
    -- === 财务比率 ===
    -- 盈利能力比率
    roe DECIMAL(10,4),
    roa DECIMAL(10,4),
    roic DECIMAL(10,4),
    gross_profit_margin DECIMAL(10,4),
    operating_profit_margin DECIMAL(10,4),
    net_profit_margin DECIMAL(10,4),
    
    -- 偿债能力比率
    current_ratio DECIMAL(10,4),
    quick_ratio DECIMAL(10,4),
    debt_to_equity DECIMAL(10,4),
    debt_to_assets DECIMAL(10,4),
    interest_coverage DECIMAL(10,4),
    
    -- 营运能力比率
    asset_turnover DECIMAL(10,4),
    inventory_turnover DECIMAL(10,4),
    receivables_turnover DECIMAL(10,4),
    
    -- 成长能力比率
    revenue_growth DECIMAL(10,4),
    profit_growth DECIMAL(10,4),
    asset_growth DECIMAL(10,4),
    
    -- 元数据
    plugin_specific_data JSON,
    data_source VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_quality_score DECIMAL(3,2),
    
    PRIMARY KEY (symbol, report_date, report_type)
);"""

    @staticmethod
    def get_macro_economic_schema(plugin_name: str) -> str:
        """
        获取宏观经济数据表结构SQL

        Args:
            plugin_name: 插件名称

        Returns:
            CREATE TABLE SQL语句
        """
        table_name = f"macro_economic_data_{plugin_name}"

        return f"""
CREATE TABLE {table_name} (
    -- 基础信息
    indicator_code VARCHAR NOT NULL,
    indicator_name VARCHAR NOT NULL,
    data_date DATE NOT NULL,
    frequency VARCHAR NOT NULL,
    
    -- 数据值
    value DECIMAL(20,6) NOT NULL,
    unit VARCHAR,
    previous_value DECIMAL(20,6),
    forecast_value DECIMAL(20,6),
    
    -- 分类信息
    category VARCHAR,
    subcategory VARCHAR,
    indicator_type VARCHAR,
    
    -- 地理信息
    country VARCHAR DEFAULT 'CN',
    region VARCHAR,
    city VARCHAR,
    
    -- 数据属性
    seasonally_adjusted BOOLEAN DEFAULT FALSE,
    is_preliminary BOOLEAN DEFAULT FALSE,
    is_revised BOOLEAN DEFAULT FALSE,
    revision_count INTEGER DEFAULT 0,
    
    -- 发布信息
    release_date DATE,
    release_time VARCHAR,
    next_release_date DATE,
    
    -- 数据来源
    data_source VARCHAR NOT NULL,
    source_code VARCHAR,
    publisher VARCHAR,
    
    -- 统计信息
    historical_high DECIMAL(20,6),
    historical_low DECIMAL(20,6),
    historical_average DECIMAL(20,6),
    
    -- 变化率
    mom_change DECIMAL(10,4),
    yoy_change DECIMAL(10,4),
    qoq_change DECIMAL(10,4),
    
    -- 元数据
    plugin_specific_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_quality_score DECIMAL(3,2),
    
    PRIMARY KEY (indicator_code, data_date)
);"""

    @staticmethod
    def get_financial_statement_indexes(plugin_name: str) -> List[str]:
        """
        获取财务报表表索引SQL列表

        Args:
            plugin_name: 插件名称

        Returns:
            CREATE INDEX SQL语句列表
        """
        table_name = f"financial_statements_{plugin_name}"

        return [
            f"CREATE INDEX idx_{table_name}_symbol ON {table_name}(symbol);",
            f"CREATE INDEX idx_{table_name}_report_date ON {table_name}(report_date);",
            f"CREATE INDEX idx_{table_name}_report_type ON {table_name}(report_type);",
            f"CREATE INDEX idx_{table_name}_symbol_date ON {table_name}(symbol, report_date);",
            f"CREATE INDEX idx_{table_name}_fiscal_year ON {table_name}(fiscal_year);",
            f"CREATE INDEX idx_{table_name}_data_source ON {table_name}(data_source);",
            f"CREATE INDEX idx_{table_name}_created_at ON {table_name}(created_at);",
            f"CREATE INDEX idx_{table_name}_updated_at ON {table_name}(updated_at);",
            # 财务指标索引
            f"CREATE INDEX idx_{table_name}_total_assets ON {table_name}(total_assets);",
            f"CREATE INDEX idx_{table_name}_operating_revenue ON {table_name}(operating_revenue);",
            f"CREATE INDEX idx_{table_name}_net_profit ON {table_name}(net_profit);",
            f"CREATE INDEX idx_{table_name}_roe ON {table_name}(roe);",
            f"CREATE INDEX idx_{table_name}_roa ON {table_name}(roa);",
            f"CREATE INDEX idx_{table_name}_debt_to_equity ON {table_name}(debt_to_equity);"
        ]

    @staticmethod
    def get_macro_economic_indexes(plugin_name: str) -> List[str]:
        """
        获取宏观经济数据表索引SQL列表

        Args:
            plugin_name: 插件名称

        Returns:
            CREATE INDEX SQL语句列表
        """
        table_name = f"macro_economic_data_{plugin_name}"

        return [
            f"CREATE INDEX idx_{table_name}_indicator_code ON {table_name}(indicator_code);",
            f"CREATE INDEX idx_{table_name}_indicator_name ON {table_name}(indicator_name);",
            f"CREATE INDEX idx_{table_name}_data_date ON {table_name}(data_date);",
            f"CREATE INDEX idx_{table_name}_frequency ON {table_name}(frequency);",
            f"CREATE INDEX idx_{table_name}_category ON {table_name}(category);",
            f"CREATE INDEX idx_{table_name}_subcategory ON {table_name}(category, subcategory);",
            f"CREATE INDEX idx_{table_name}_country ON {table_name}(country);",
            f"CREATE INDEX idx_{table_name}_region ON {table_name}(country, region);",
            f"CREATE INDEX idx_{table_name}_data_source ON {table_name}(data_source);",
            f"CREATE INDEX idx_{table_name}_publisher ON {table_name}(publisher);",
            f"CREATE INDEX idx_{table_name}_release_date ON {table_name}(release_date);",
            f"CREATE INDEX idx_{table_name}_created_at ON {table_name}(created_at);",
            # 数值索引
            f"CREATE INDEX idx_{table_name}_value ON {table_name}(value);",
            f"CREATE INDEX idx_{table_name}_yoy_change ON {table_name}(yoy_change);",
            f"CREATE INDEX idx_{table_name}_mom_change ON {table_name}(mom_change);"
        ]

    @staticmethod
    def get_table_schema_by_type(table_type: TableStructureType, plugin_name: str) -> str:
        """
        根据表类型获取表结构SQL

        Args:
            table_type: 表类型
            plugin_name: 插件名称

        Returns:
            CREATE TABLE SQL语句
        """
        if table_type == TableStructureType.FINANCIAL_STATEMENT:
            return DuckDBTableSchemas.get_financial_statement_schema(plugin_name)
        elif table_type == TableStructureType.MACRO_ECONOMIC:
            return DuckDBTableSchemas.get_macro_economic_schema(plugin_name)
        else:
            raise ValueError(f"不支持的表类型: {table_type}")

    @staticmethod
    def get_table_indexes_by_type(table_type: TableStructureType, plugin_name: str) -> List[str]:
        """
        根据表类型获取索引SQL列表

        Args:
            table_type: 表类型
            plugin_name: 插件名称

        Returns:
            CREATE INDEX SQL语句列表
        """
        if table_type == TableStructureType.FINANCIAL_STATEMENT:
            return DuckDBTableSchemas.get_financial_statement_indexes(plugin_name)
        elif table_type == TableStructureType.MACRO_ECONOMIC:
            return DuckDBTableSchemas.get_macro_economic_indexes(plugin_name)
        else:
            raise ValueError(f"不支持的表类型: {table_type}")

    @staticmethod
    def get_all_table_schemas(plugin_name: str) -> Dict[str, str]:
        """
        获取所有表结构SQL

        Args:
            plugin_name: 插件名称

        Returns:
            表名到SQL的映射
        """
        schemas = {}

        # 财务报表表
        schemas[f"financial_statements_{plugin_name}"] = DuckDBTableSchemas.get_financial_statement_schema(plugin_name)

        # 宏观经济数据表
        schemas[f"macro_economic_data_{plugin_name}"] = DuckDBTableSchemas.get_macro_economic_schema(plugin_name)

        return schemas

    @staticmethod
    def get_all_table_indexes(plugin_name: str) -> Dict[str, List[str]]:
        """
        获取所有表索引SQL

        Args:
            plugin_name: 插件名称

        Returns:
            表名到索引SQL列表的映射
        """
        indexes = {}

        # 财务报表表索引
        indexes[f"financial_statements_{plugin_name}"] = DuckDBTableSchemas.get_financial_statement_indexes(plugin_name)

        # 宏观经济数据表索引
        indexes[f"macro_economic_data_{plugin_name}"] = DuckDBTableSchemas.get_macro_economic_indexes(plugin_name)

        return indexes

    @staticmethod
    def create_table_with_indexes(connection, table_type: TableStructureType, plugin_name: str) -> bool:
        """
        创建表及其索引

        Args:
            connection: DuckDB连接
            table_type: 表类型
            plugin_name: 插件名称

        Returns:
            创建是否成功
        """
        try:
            # 创建表
            table_sql = DuckDBTableSchemas.get_table_schema_by_type(table_type, plugin_name)
            connection.execute(table_sql)

            # 创建索引
            index_sqls = DuckDBTableSchemas.get_table_indexes_by_type(table_type, plugin_name)
            for index_sql in index_sqls:
                connection.execute(index_sql)

            return True

        except Exception as e:
            logger.info(f"创建表失败: {e}")
            return False

    @staticmethod
    def get_table_column_info(table_type: TableStructureType) -> Dict[str, str]:
        """
        获取表列信息

        Args:
            table_type: 表类型

        Returns:
            列名到数据类型的映射
        """
        if table_type == TableStructureType.FINANCIAL_STATEMENT:
            return {
                # 基础信息
                'symbol': 'VARCHAR',
                'report_date': 'DATE',
                'report_type': 'VARCHAR',
                'report_period': 'VARCHAR',
                'fiscal_year': 'INTEGER',

                # 资产负债表 - 资产
                'total_assets': 'DECIMAL(20,2)',
                'current_assets': 'DECIMAL(20,2)',
                'non_current_assets': 'DECIMAL(20,2)',
                'cash_and_equivalents': 'DECIMAL(20,2)',
                'short_term_investments': 'DECIMAL(20,2)',
                'accounts_receivable': 'DECIMAL(20,2)',
                'inventory': 'DECIMAL(20,2)',
                'prepaid_expenses': 'DECIMAL(20,2)',
                'fixed_assets': 'DECIMAL(20,2)',
                'intangible_assets': 'DECIMAL(20,2)',
                'goodwill': 'DECIMAL(20,2)',

                # 资产负债表 - 负债
                'total_liabilities': 'DECIMAL(20,2)',
                'current_liabilities': 'DECIMAL(20,2)',
                'non_current_liabilities': 'DECIMAL(20,2)',
                'accounts_payable': 'DECIMAL(20,2)',
                'short_term_debt': 'DECIMAL(20,2)',
                'long_term_debt': 'DECIMAL(20,2)',
                'accrued_expenses': 'DECIMAL(20,2)',

                # 资产负债表 - 股东权益
                'shareholders_equity': 'DECIMAL(20,2)',
                'paid_in_capital': 'DECIMAL(20,2)',
                'retained_earnings': 'DECIMAL(20,2)',
                'accumulated_other_comprehensive_income': 'DECIMAL(20,2)',

                # 利润表
                'operating_revenue': 'DECIMAL(20,2)',
                'operating_costs': 'DECIMAL(20,2)',
                'gross_profit': 'DECIMAL(20,2)',
                'operating_expenses': 'DECIMAL(20,2)',
                'selling_expenses': 'DECIMAL(20,2)',
                'admin_expenses': 'DECIMAL(20,2)',
                'rd_expenses': 'DECIMAL(20,2)',
                'financial_expenses': 'DECIMAL(20,2)',
                'operating_profit': 'DECIMAL(20,2)',
                'non_operating_income': 'DECIMAL(20,2)',
                'non_operating_expenses': 'DECIMAL(20,2)',
                'profit_before_tax': 'DECIMAL(20,2)',
                'income_tax': 'DECIMAL(20,2)',
                'net_profit': 'DECIMAL(20,2)',
                'net_profit_attributable_to_parent': 'DECIMAL(20,2)',

                # 每股指标
                'eps': 'DECIMAL(10,4)',
                'diluted_eps': 'DECIMAL(10,4)',
                'book_value_per_share': 'DECIMAL(10,4)',

                # 现金流量表
                'operating_cash_flow': 'DECIMAL(20,2)',
                'investing_cash_flow': 'DECIMAL(20,2)',
                'financing_cash_flow': 'DECIMAL(20,2)',
                'net_cash_flow': 'DECIMAL(20,2)',
                'free_cash_flow': 'DECIMAL(20,2)',

                # 经营活动现金流明细
                'cash_from_operations': 'DECIMAL(20,2)',
                'cash_paid_for_goods': 'DECIMAL(20,2)',
                'cash_paid_to_employees': 'DECIMAL(20,2)',
                'cash_paid_for_taxes': 'DECIMAL(20,2)',

                # 盈利能力比率
                'roe': 'DECIMAL(10,4)',
                'roa': 'DECIMAL(10,4)',
                'roic': 'DECIMAL(10,4)',
                'gross_profit_margin': 'DECIMAL(10,4)',
                'operating_profit_margin': 'DECIMAL(10,4)',
                'net_profit_margin': 'DECIMAL(10,4)',

                # 偿债能力比率
                'current_ratio': 'DECIMAL(10,4)',
                'quick_ratio': 'DECIMAL(10,4)',
                'debt_to_equity': 'DECIMAL(10,4)',
                'debt_to_assets': 'DECIMAL(10,4)',
                'interest_coverage': 'DECIMAL(10,4)',

                # 营运能力比率
                'asset_turnover': 'DECIMAL(10,4)',
                'inventory_turnover': 'DECIMAL(10,4)',
                'receivables_turnover': 'DECIMAL(10,4)',

                # 成长能力比率
                'revenue_growth': 'DECIMAL(10,4)',
                'profit_growth': 'DECIMAL(10,4)',
                'asset_growth': 'DECIMAL(10,4)',

                # 元数据
                'plugin_specific_data': 'JSON',
                'data_source': 'VARCHAR',
                'created_at': 'TIMESTAMP',
                'updated_at': 'TIMESTAMP',
                'data_quality_score': 'DECIMAL(3,2)'
            }

        elif table_type == TableStructureType.MACRO_ECONOMIC:
            return {
                # 基础信息
                'indicator_code': 'VARCHAR',
                'indicator_name': 'VARCHAR',
                'data_date': 'DATE',
                'frequency': 'VARCHAR',

                # 数据值
                'value': 'DECIMAL(20,6)',
                'unit': 'VARCHAR',
                'previous_value': 'DECIMAL(20,6)',
                'forecast_value': 'DECIMAL(20,6)',

                # 分类信息
                'category': 'VARCHAR',
                'subcategory': 'VARCHAR',
                'indicator_type': 'VARCHAR',

                # 地理信息
                'country': 'VARCHAR',
                'region': 'VARCHAR',
                'city': 'VARCHAR',

                # 数据属性
                'seasonally_adjusted': 'BOOLEAN',
                'is_preliminary': 'BOOLEAN',
                'is_revised': 'BOOLEAN',

                # 发布信息
                'release_date': 'DATE',
                'publisher': 'VARCHAR',

                # 变化率
                'mom_change': 'DECIMAL(10,4)',
                'yoy_change': 'DECIMAL(10,4)',
                'qoq_change': 'DECIMAL(10,4)',

                # 元数据
                'plugin_specific_data': 'JSON',
                'data_source': 'VARCHAR',
                'created_at': 'TIMESTAMP',
                'updated_at': 'TIMESTAMP',
                'data_quality_score': 'DECIMAL(3,2)'
            }

        else:
            return {}

    @staticmethod
    def validate_table_structure(connection, table_name: str, expected_columns: Dict[str, str]) -> bool:
        """
        验证表结构

        Args:
            connection: DuckDB连接
            table_name: 表名
            expected_columns: 期望的列定义

        Returns:
            结构是否正确
        """
        try:
            # 获取表结构
            result = connection.execute(f"DESCRIBE {table_name}").fetchall()
            actual_columns = {row[0]: row[1] for row in result}

            # 检查列是否匹配
            for col_name, col_type in expected_columns.items():
                if col_name not in actual_columns:
                    logger.info(f"缺少列: {col_name}")
                    return False

                # 简单的类型检查（DuckDB类型可能有变化）
                if not actual_columns[col_name].upper().startswith(col_type.split('(')[0].upper()):
                    logger.info(f"列类型不匹配: {col_name} 期望: {col_type} 实际: {actual_columns[col_name]}")
                    return False

            return True

        except Exception as e:
            logger.info(f"验证表结构失败: {e}")
            return False
