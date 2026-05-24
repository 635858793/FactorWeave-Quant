from loguru import logger
"""
数据模型转换器

提供数据模型的格式转换功能，包括：
- 财务报表数据转换器
- 宏观经济数据转换器
- 数据验证和格式化
- DuckDB记录转换

作者: FactorWeave-Quant团队
版本: 1.0
"""

import pandas as pd
from typing import Dict, Any, List, Tuple, Optional, Union
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import json

from .enhanced_models import (
    FinancialStatement, MacroEconomicData, ReportType,
    calculate_financial_ratios
)


class DataValidationError(Exception):
    """数据验证错误"""
    pass

class FinancialStatementConverter:
    """财务报表数据转换器"""

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> FinancialStatement:
        """
        从字典创建财务报表对象

        Args:
            data: 数据字典

        Returns:
            财务报表对象

        Raises:
            DataValidationError: 数据验证失败
        """
        try:
            # 验证必需字段
            required_fields = ['symbol', 'report_date', 'report_type']
            for field in required_fields:
                if field not in data or data[field] is None:
                    raise DataValidationError(f"缺少必需字段: {field}")

            # 处理日期字段
            if isinstance(data.get('report_date'), str):
                try:
                    data['report_date'] = datetime.fromisoformat(data['report_date']).date()
                except ValueError:
                    # 尝试其他日期格式
                    data['report_date'] = datetime.strptime(data['report_date'], '%Y-%m-%d').date()

            # 处理枚举字段
            if isinstance(data.get('report_type'), str):
                try:
                    data['report_type'] = ReportType(data['report_type'])
                except ValueError:
                    # 尝试映射常见的报表类型
                    report_type_mapping = {
                        '年报': ReportType.ANNUAL,
                        '半年报': ReportType.SEMI_ANNUAL,
                        '季报': ReportType.QUARTERLY,
                        '月报': ReportType.MONTHLY,
                        'annual': ReportType.ANNUAL,
                        'ANNUAL': ReportType.ANNUAL,
                        'semi-annual': ReportType.SEMI_ANNUAL,
                        'SEMI_ANNUAL': ReportType.SEMI_ANNUAL,
                        'quarterly': ReportType.QUARTERLY,
                        'QUARTERLY': ReportType.QUARTERLY,
                        'monthly': ReportType.MONTHLY,
                        'MONTHLY': ReportType.MONTHLY
                    }
                    report_type_str = data['report_type'].lower()
                    if report_type_str in report_type_mapping:
                        data['report_type'] = report_type_mapping[report_type_str]
                    else:
                        raise DataValidationError(f"无效的报表类型: {data['report_type']}")

            # 处理字段映射 (兼容不同数据源的字段名)
            field_mappings = {
                'total_revenue': 'operating_revenue',  # 总收入映射到营业收入
                'source': 'data_source',              # source映射到data_source
            }

            for old_field, new_field in field_mappings.items():
                if old_field in data and new_field not in data:
                    data[new_field] = data[old_field]
                    del data[old_field]

            # 处理Decimal字段
            decimal_fields = [
                'total_assets', 'current_assets', 'non_current_assets', 'cash_and_equivalents',
                'short_term_investments', 'accounts_receivable', 'inventory', 'prepaid_expenses',
                'fixed_assets', 'intangible_assets', 'goodwill',
                'total_liabilities', 'current_liabilities', 'non_current_liabilities',
                'accounts_payable', 'short_term_debt', 'long_term_debt', 'accrued_expenses',
                'shareholders_equity', 'paid_in_capital', 'retained_earnings',
                'accumulated_other_comprehensive_income',
                'operating_revenue', 'operating_costs', 'gross_profit', 'operating_expenses',
                'selling_expenses', 'admin_expenses', 'rd_expenses', 'financial_expenses',
                'operating_profit', 'non_operating_income', 'non_operating_expenses',
                'profit_before_tax', 'income_tax', 'net_profit', 'net_profit_attributable_to_parent',
                'eps', 'diluted_eps', 'book_value_per_share',
                'operating_cash_flow', 'investing_cash_flow', 'financing_cash_flow',
                'net_cash_flow', 'free_cash_flow', 'cash_from_operations',
                'cash_paid_for_goods', 'cash_paid_to_employees', 'cash_paid_for_taxes',
                'roe', 'roa', 'roic', 'gross_profit_margin', 'operating_profit_margin',
                'net_profit_margin', 'current_ratio', 'quick_ratio', 'debt_to_equity',
                'debt_to_assets', 'interest_coverage', 'asset_turnover', 'inventory_turnover',
                'receivables_turnover', 'revenue_growth', 'profit_growth', 'asset_growth',
                'data_quality_score'
            ]

            for field in decimal_fields:
                if field in data and data[field] is not None:
                    try:
                        data[field] = Decimal(str(data[field]))
                    except (InvalidOperation, ValueError) as e:
                        logger.warning(f"无法转换字段 {field} 为Decimal: {data[field]}, 错误: {e}")
                        data[field] = None

            # 处理时间戳字段
            datetime_fields = ['created_at', 'updated_at']
            for field in datetime_fields:
                if field in data and isinstance(data[field], str):
                    try:
                        data[field] = datetime.fromisoformat(data[field])
                    except ValueError:
                        data[field] = datetime.now()

            # 处理JSON字段
            if 'plugin_specific_data' in data and isinstance(data['plugin_specific_data'], str):
                try:
                    data['plugin_specific_data'] = json.loads(data['plugin_specific_data'])
                except json.JSONDecodeError:
                    data['plugin_specific_data'] = {}

            return FinancialStatement(**data)

        except Exception as e:
            raise DataValidationError(f"财务报表数据转换失败: {e}")

    @staticmethod
    def to_dict(statement: FinancialStatement) -> Dict[str, Any]:
        """
        转换为字典

        Args:
            statement: 财务报表对象

        Returns:
            数据字典
        """
        return statement.to_dict()

    @staticmethod
    def to_duckdb_record(statement: FinancialStatement) -> Dict[str, Any]:
        """
        转换为DuckDB插入记录

        Args:
            statement: 财务报表对象

        Returns:
            DuckDB插入记录字典
        """
        return {
            'symbol': statement.symbol,
            'report_date': statement.report_date,
            'report_type': statement.report_type.value if statement.report_type else None,
            'report_period': statement.report_period,
            'fiscal_year': statement.fiscal_year,

            # 资产负债表
            'total_assets': statement.total_assets,
            'current_assets': statement.current_assets,
            'non_current_assets': statement.non_current_assets,
            'cash_and_equivalents': statement.cash_and_equivalents,
            'short_term_investments': statement.short_term_investments,
            'accounts_receivable': statement.accounts_receivable,
            'inventory': statement.inventory,
            'prepaid_expenses': statement.prepaid_expenses,
            'fixed_assets': statement.fixed_assets,
            'intangible_assets': statement.intangible_assets,
            'goodwill': statement.goodwill,

            'total_liabilities': statement.total_liabilities,
            'current_liabilities': statement.current_liabilities,
            'non_current_liabilities': statement.non_current_liabilities,
            'accounts_payable': statement.accounts_payable,
            'short_term_debt': statement.short_term_debt,
            'long_term_debt': statement.long_term_debt,
            'accrued_expenses': statement.accrued_expenses,

            'shareholders_equity': statement.shareholders_equity,
            'paid_in_capital': statement.paid_in_capital,
            'retained_earnings': statement.retained_earnings,
            'accumulated_other_comprehensive_income': statement.accumulated_other_comprehensive_income,

            # 利润表
            'operating_revenue': statement.operating_revenue,
            'operating_costs': statement.operating_costs,
            'gross_profit': statement.gross_profit,
            'operating_expenses': statement.operating_expenses,
            'selling_expenses': statement.selling_expenses,
            'admin_expenses': statement.admin_expenses,
            'rd_expenses': statement.rd_expenses,
            'financial_expenses': statement.financial_expenses,
            'operating_profit': statement.operating_profit,
            'non_operating_income': statement.non_operating_income,
            'non_operating_expenses': statement.non_operating_expenses,
            'profit_before_tax': statement.profit_before_tax,
            'income_tax': statement.income_tax,
            'net_profit': statement.net_profit,
            'net_profit_attributable_to_parent': statement.net_profit_attributable_to_parent,

            'eps': statement.eps,
            'diluted_eps': statement.diluted_eps,
            'book_value_per_share': statement.book_value_per_share,

            # 现金流量表
            'operating_cash_flow': statement.operating_cash_flow,
            'investing_cash_flow': statement.investing_cash_flow,
            'financing_cash_flow': statement.financing_cash_flow,
            'net_cash_flow': statement.net_cash_flow,
            'free_cash_flow': statement.free_cash_flow,

            'cash_from_operations': statement.cash_from_operations,
            'cash_paid_for_goods': statement.cash_paid_for_goods,
            'cash_paid_to_employees': statement.cash_paid_to_employees,
            'cash_paid_for_taxes': statement.cash_paid_for_taxes,

            # 财务比率
            'roe': statement.roe,
            'roa': statement.roa,
            'roic': statement.roic,
            'gross_profit_margin': statement.gross_profit_margin,
            'operating_profit_margin': statement.operating_profit_margin,
            'net_profit_margin': statement.net_profit_margin,

            'current_ratio': statement.current_ratio,
            'quick_ratio': statement.quick_ratio,
            'debt_to_equity': statement.debt_to_equity,
            'debt_to_assets': statement.debt_to_assets,
            'asset_liability_ratio': statement.asset_liability_ratio,
            'interest_coverage': statement.interest_coverage,

            'asset_turnover': statement.asset_turnover,
            'inventory_turnover': statement.inventory_turnover,
            'receivables_turnover': statement.receivables_turnover,

            'revenue_growth': statement.revenue_growth,
            'profit_growth': statement.profit_growth,
            'asset_growth': statement.asset_growth,

            # 元数据
            'plugin_specific_data': statement.plugin_specific_data,
            'data_source': statement.data_source,
            'created_at': statement.created_at,
            'updated_at': statement.updated_at,
            'data_quality_score': statement.data_quality_score
        }

    @staticmethod
    def from_pandas(df: pd.DataFrame) -> List[FinancialStatement]:
        """
        从pandas DataFrame批量转换财务报表

        Args:
            df: 包含财务报表数据的DataFrame

        Returns:
            财务报表对象列表

        Raises:
            DataValidationError: 数据验证失败
        """
        return FinancialStatementConverter.from_dataframe(df)

    @staticmethod
    def from_dataframe(df: pd.DataFrame) -> List[FinancialStatement]:
        """
        从DataFrame批量创建财务报表对象

        Args:
            df: 财务数据DataFrame

        Returns:
            财务报表对象列表
        """
        statements = []

        for row_dict in df.to_dict('records'):
            try:
                statement = FinancialStatementConverter.from_dict(row_dict)
                statements.append(statement)
            except Exception as e:
                logger.error(f"转换财务报表数据失败: {e}, 数据: {row_dict}")

        return statements

    @staticmethod
    def to_dataframe(statements: List[FinancialStatement]) -> pd.DataFrame:
        """
        转换为DataFrame

        Args:
            statements: 财务报表对象列表

        Returns:
            财务数据DataFrame
        """
        data = [statement.to_dict() for statement in statements]
        return pd.DataFrame(data)

    @staticmethod
    def validate_and_calculate_ratios(statement: FinancialStatement) -> FinancialStatement:
        """
        验证数据并计算财务比率

        Args:
            statement: 财务报表对象

        Returns:
            计算完比率的财务报表对象
        """
        # 数据验证
        if not statement.symbol:
            raise DataValidationError("股票代码不能为空")

        if not statement.report_date:
            raise DataValidationError("报告日期不能为空")

        # 计算财务比率
        return calculate_financial_ratios(statement)

class MacroEconomicDataConverter:
    """宏观经济数据转换器"""

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> MacroEconomicData:
        """
        从字典创建宏观经济数据对象

        Args:
            data: 数据字典

        Returns:
            宏观经济数据对象

        Raises:
            DataValidationError: 数据验证失败
        """
        try:
            # 处理字段映射 (兼容不同数据源的字段名)
            field_mappings = {
                'source': 'data_source',              # source映射到data_source
            }

            for old_field, new_field in field_mappings.items():
                if old_field in data and new_field not in data:
                    data[new_field] = data[old_field]
                    del data[old_field]

            # 如果没有提供category，尝试从indicator_code推断
            if 'category' not in data or data['category'] is None:
                indicator_code = data.get('indicator_code', '').upper()
                if 'GDP' in indicator_code:
                    data['category'] = 'GDP'
                elif 'CPI' in indicator_code:
                    data['category'] = 'CPI'
                elif 'PMI' in indicator_code:
                    data['category'] = 'PMI'
                elif 'RATE' in indicator_code or 'INTEREST' in indicator_code:
                    data['category'] = '利率'
                else:
                    data['category'] = '其他'  # 默认分类

            # 验证必需字段
            required_fields = ['indicator_code', 'indicator_name', 'data_date', 'frequency', 'value', 'unit', 'category']
            for field in required_fields:
                if field not in data or data[field] is None:
                    raise DataValidationError(f"缺少必需字段: {field}")

            # 处理日期字段
            date_fields = ['data_date', 'release_date', 'next_release_date']
            for field in date_fields:
                if field in data and isinstance(data[field], str):
                    try:
                        data[field] = datetime.fromisoformat(data[field]).date()
                    except ValueError:
                        try:
                            data[field] = datetime.strptime(data[field], '%Y-%m-%d').date()
                        except ValueError:
                            logger.warning(f"无法解析日期字段 {field}: {data[field]}")
                            data[field] = None

            # 处理Decimal字段
            decimal_fields = [
                'value', 'previous_value', 'forecast_value', 'historical_high',
                'historical_low', 'historical_average', 'mom_change', 'yoy_change',
                'qoq_change', 'data_quality_score'
            ]

            for field in decimal_fields:
                if field in data and data[field] is not None:
                    try:
                        data[field] = Decimal(str(data[field]))
                    except (InvalidOperation, ValueError) as e:
                        logger.warning(f"无法转换字段 {field} 为Decimal: {data[field]}, 错误: {e}")
                        data[field] = None

            # 处理时间戳字段
            datetime_fields = ['created_at', 'updated_at']
            for field in datetime_fields:
                if field in data and isinstance(data[field], str):
                    try:
                        data[field] = datetime.fromisoformat(data[field])
                    except ValueError:
                        data[field] = datetime.now()

            # 处理JSON字段
            if 'plugin_specific_data' in data and isinstance(data['plugin_specific_data'], str):
                try:
                    data['plugin_specific_data'] = json.loads(data['plugin_specific_data'])
                except json.JSONDecodeError:
                    data['plugin_specific_data'] = {}

            # 处理布尔字段
            bool_fields = ['seasonally_adjusted', 'is_preliminary', 'is_revised']
            for field in bool_fields:
                if field in data and isinstance(data[field], str):
                    data[field] = data[field].lower() in ['true', '1', 'yes', 'y']

            return MacroEconomicData(**data)

        except Exception as e:
            raise DataValidationError(f"宏观经济数据转换失败: {e}")

    @staticmethod
    def to_dict(macro_data: MacroEconomicData) -> Dict[str, Any]:
        """
        转换为字典

        Args:
            macro_data: 宏观经济数据对象

        Returns:
            数据字典
        """
        return macro_data.to_dict()

    @staticmethod
    def to_duckdb_record(macro_data: MacroEconomicData) -> Dict[str, Any]:
        """
        转换为DuckDB插入记录

        Args:
            macro_data: 宏观经济数据对象

        Returns:
            DuckDB插入记录字典
        """
        return {
            'indicator_code': macro_data.indicator_code,
            'indicator_name': macro_data.indicator_name,
            'data_date': macro_data.data_date,
            'frequency': macro_data.frequency,

            'value': macro_data.value,
            'unit': macro_data.unit,
            'previous_value': macro_data.previous_value,
            'forecast_value': macro_data.forecast_value,

            'category': macro_data.category,
            'subcategory': macro_data.subcategory,
            'indicator_type': macro_data.indicator_type,

            'country': macro_data.country,
            'region': macro_data.region,
            'city': macro_data.city,

            'seasonally_adjusted': macro_data.seasonally_adjusted,
            'is_preliminary': macro_data.is_preliminary,
            'is_revised': macro_data.is_revised,
            'revision_count': macro_data.revision_count,

            'release_date': macro_data.release_date,
            'release_time': macro_data.release_time,
            'next_release_date': macro_data.next_release_date,

            'data_source': macro_data.data_source,
            'source_code': macro_data.source_code,
            'publisher': macro_data.publisher,

            'historical_high': macro_data.historical_high,
            'historical_low': macro_data.historical_low,
            'historical_average': macro_data.historical_average,

            'mom_change': macro_data.mom_change,
            'yoy_change': macro_data.yoy_change,
            'qoq_change': macro_data.qoq_change,

            'plugin_specific_data': macro_data.plugin_specific_data,
            'created_at': macro_data.created_at,
            'updated_at': macro_data.updated_at,
            'data_quality_score': macro_data.data_quality_score
        }

    @staticmethod
    def from_pandas(df: pd.DataFrame) -> List[MacroEconomicData]:
        """
        从pandas DataFrame批量转换宏观经济数据

        Args:
            df: 包含宏观经济数据的DataFrame

        Returns:
            宏观经济数据对象列表

        Raises:
            DataValidationError: 数据验证失败
        """
        return MacroEconomicDataConverter.from_dataframe(df)

    @staticmethod
    def from_dataframe(df: pd.DataFrame) -> List[MacroEconomicData]:
        """
        从DataFrame批量创建宏观经济数据对象

        Args:
            df: 宏观经济数据DataFrame

        Returns:
            宏观经济数据对象列表
        """
        macro_data_list = []

        for row_dict in df.to_dict('records'):
            try:
                macro_data = MacroEconomicDataConverter.from_dict(row_dict)
                macro_data_list.append(macro_data)
            except Exception as e:
                logger.error(f"转换宏观经济数据失败: {e}, 数据: {row_dict}")

        return macro_data_list

    @staticmethod
    def to_dataframe(macro_data_list: List[MacroEconomicData]) -> pd.DataFrame:
        """
        转换为DataFrame

        Args:
            macro_data_list: 宏观经济数据对象列表

        Returns:
            宏观经济数据DataFrame
        """
        data = [macro_data.to_dict() for macro_data in macro_data_list]
        return pd.DataFrame(data)

    @staticmethod
    def validate_and_calculate_changes(macro_data: MacroEconomicData,
                                       previous_period_value: Optional[Decimal] = None,
                                       same_period_last_year_value: Optional[Decimal] = None) -> MacroEconomicData:
        """
        验证数据并计算变化率

        Args:
            macro_data: 宏观经济数据对象
            previous_period_value: 上期值
            same_period_last_year_value: 去年同期值

        Returns:
            计算完变化率的宏观经济数据对象
        """
        # 数据验证
        if not macro_data.indicator_code:
            raise DataValidationError("指标代码不能为空")

        if not macro_data.indicator_name:
            raise DataValidationError("指标名称不能为空")

        if not macro_data.data_date:
            raise DataValidationError("数据日期不能为空")

        if macro_data.value is None:
            raise DataValidationError("指标值不能为空")

        # 计算变化率
        macro_data.calculate_changes(previous_period_value, same_period_last_year_value)

        return macro_data

class BatchDataConverter:
    """批量数据转换器"""

    @staticmethod
    def convert_financial_statements_batch(data_list: List[Dict[str, Any]],
                                           calculate_ratios: bool = True) -> List[FinancialStatement]:
        """
        批量转换财务报表数据

        Args:
            data_list: 数据字典列表
            calculate_ratios: 是否计算财务比率

        Returns:
            财务报表对象列表
        """
        statements = []
        errors = []

        for i, data in enumerate(data_list):
            try:
                statement = FinancialStatementConverter.from_dict(data)

                if calculate_ratios:
                    statement = FinancialStatementConverter.validate_and_calculate_ratios(statement)

                statements.append(statement)

            except Exception as e:
                error_msg = f"第 {i+1} 条财务数据转换失败: {e}"
                errors.append(error_msg)
                logger.error(error_msg)

        if errors:
            logger.warning(f"批量转换完成，成功: {len(statements)}, 失败: {len(errors)}")

        return statements

    @staticmethod
    def convert_macro_economic_data_batch(data_list: List[Dict[str, Any]]) -> List[MacroEconomicData]:
        """
        批量转换宏观经济数据

        Args:
            data_list: 数据字典列表

        Returns:
            宏观经济数据对象列表
        """
        macro_data_list = []
        errors = []

        for i, data in enumerate(data_list):
            try:
                macro_data = MacroEconomicDataConverter.from_dict(data)
                macro_data_list.append(macro_data)

            except Exception as e:
                error_msg = f"第 {i+1} 条宏观经济数据转换失败: {e}"
                errors.append(error_msg)
                logger.error(error_msg)

        if errors:
            logger.warning(f"批量转换完成，成功: {len(macro_data_list)}, 失败: {len(errors)}")

        return macro_data_list

    @staticmethod
    def prepare_for_duckdb_insert(data_objects: List[Union[FinancialStatement, MacroEconomicData]]) -> List[Tuple]:
        """
        准备DuckDB批量插入数据

        Args:
            data_objects: 数据对象列表

        Returns:
            DuckDB插入记录列表
        """
        records = []

        for obj in data_objects:
            try:
                if isinstance(obj, FinancialStatement):
                    record = FinancialStatementConverter.to_duckdb_record(obj)
                elif isinstance(obj, MacroEconomicData):
                    record = MacroEconomicDataConverter.to_duckdb_record(obj)
                else:
                    logger.warning(f"不支持的数据类型: {type(obj)}")
                    continue

                records.append(record)

            except Exception as e:
                logger.error(f"准备DuckDB插入记录失败: {e}")

        return records
