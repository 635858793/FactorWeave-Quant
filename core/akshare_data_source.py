import akshare as ak
import pandas as pd
from datetime import datetime
from typing import List, Optional
from .data_source import DataSource, DataSourceType, DataFrequency, MarketDataType
from loguru import logger

class AkshareDataSource(DataSource):
    """Akshare数据源"""

    def __init__(self):
        super().__init__(DataSourceType.LOCAL)
        self.logger = logger.bind(module=self.__class__.__name__)

    def connect(self) -> bool:
        return True

    def disconnect(self) -> None:
        pass

    def subscribe(self, symbols: List[str], data_types: List[MarketDataType]) -> bool:
        return True

    def unsubscribe(self, symbols: List[str], data_types: List[MarketDataType]) -> bool:
        return True

    def get_kdata(self, symbol: str, freq: DataFrequency,
                  start_date: Optional[datetime] = None,
                  end_date: Optional[datetime] = None) -> pd.DataFrame:
        # 这里只实现日线，其他频率可扩展
        try:
            if freq == DataFrequency.DAY:
                start = start_date.strftime(
                    "%Y%m%d") if start_date else "20100101"
                end = end_date.strftime(
                    "%Y%m%d") if end_date else datetime.now().strftime("%Y%m%d")
                df = ak.stock_zh_a_hist(
                    symbol=symbol, period="daily", start_date=start, end_date=end, adjust="")
                df.rename(columns={"日期": "datetime", "开盘": "open", "收盘": "close",
                          "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount"}, inplace=True)
                df["datetime"] = pd.to_datetime(df["datetime"])
                return df[["datetime", "open", "high", "low", "close", "volume", "amount"]]
            else:
                self.logger.warning(f"暂不支持的K线频率: {freq}")
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Akshare获取K线数据失败: {str(e)}")
            return pd.DataFrame()

    def get_real_time_quotes(self, symbols: List[str]) -> pd.DataFrame:
        # 这里只做简单实现
        try:
            dfs = []
            for symbol in symbols:
                df = ak.stock_zh_a_spot(symbol=symbol)
                dfs.append(df)
            if dfs:
                return pd.concat(dfs, ignore_index=True)
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Akshare获取实时行情失败: {str(e)}")
            return pd.DataFrame()

    def get_stock_sector_fund_flow_rank(self, indicator: str = "今日") -> pd.DataFrame:
        """获取股票板块资金流排行

        Args:
            indicator: 时间周期，支持 "今日", "3日", "5日", "10日", "20日"

        Returns:
            pd.DataFrame: 板块资金流排行数据
        """
        try:
            df = ak.stock_sector_fund_flow_rank(indicator=indicator)
            self.logger.info(f"获取板块资金流排行成功，数据条数: {len(df)}")
            return df
        except Exception as e:
            self.logger.error(f"获取板块资金流排行失败: {str(e)}")
            return pd.DataFrame()

    def get_stock_sector_fund_flow_summary(self, symbol: str, indicator: str = "今日") -> pd.DataFrame:
        """获取股票板块资金流汇总

        Args:
            symbol: 板块名称
            indicator: 时间周期，支持 "今日", "3日", "5日", "10日", "20日"

        Returns:
            pd.DataFrame: 板块资金流汇总数据
        """
        try:
            df = ak.stock_sector_fund_flow_summary(symbol=symbol, indicator=indicator)
            self.logger.info(f"获取板块资金流汇总成功，数据条数: {len(df)}")
            return df
        except Exception as e:
            self.logger.error(f"获取板块资金流汇总失败: {str(e)}")
            return pd.DataFrame()

    def get_stock_sector_fund_flow_hist(self, symbol: str, period: str = "近6月") -> pd.DataFrame:
        """获取股票板块资金流历史数据

        Args:
            symbol: 板块名称
            period: 时间周期，支持 "近6月", "近1年", "近2年", "近3年"

        Returns:
            pd.DataFrame: 板块资金流历史数据
        """
        try:
            df = ak.stock_sector_fund_flow_hist(symbol=symbol, period=period)
            self.logger.info(f"获取板块资金流历史数据成功，数据条数: {len(df)}")
            return df
        except Exception as e:
            self.logger.error(f"获取板块资金流历史数据失败: {str(e)}")
            return pd.DataFrame()

    def get_real_time_fund_flow(self, symbols: List[str]) -> pd.DataFrame:
        """获取实时资金流数据

        Args:
            symbols: 股票代码列表

        Returns:
            pd.DataFrame: 实时资金流数据
        """
        try:
            dfs = []
            for symbol in symbols:
                # 获取个股资金流数据
                df = ak.stock_individual_fund_flow_rank(indicator="今日")
                if not df.empty:
                    # 筛选指定股票
                    symbol_df = df[df['代码'] == symbol] if '代码' in df.columns else df
                    if not symbol_df.empty:
                        dfs.append(symbol_df)

            if dfs:
                result_df = pd.concat(dfs, ignore_index=True)
                self.logger.info(f"获取实时资金流数据成功，数据条数: {len(result_df)}")
                return result_df
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"获取实时资金流数据失败: {str(e)}")
            return pd.DataFrame()

    def get_sector_data(self, sector_type: str = "行业板块") -> pd.DataFrame:
        """获取板块数据

        Args:
            sector_type: 板块类型，支持 "行业板块", "概念板块"

        Returns:
            pd.DataFrame: 板块数据
        """
        try:
            if sector_type == "行业板块":
                # 获取行业板块实时行情
                df = ak.stock_board_industry_spot_em()
            elif sector_type == "概念板块":
                # 获取概念板块实时行情
                df = ak.stock_board_concept_spot_em()
            else:
                # 默认获取行业板块
                df = ak.stock_board_industry_spot_em()

            self.logger.info(f"获取{sector_type}数据成功，数据条数: {len(df)}")
            return df
        except Exception as e:
            self.logger.error(f"获取{sector_type}数据失败: {str(e)}")
            return pd.DataFrame()

    def get_technical_indicators(self, symbol: str, period: str = "daily") -> pd.DataFrame:
        """获取技术指标数据

        Args:
            symbol: 股票代码
            period: 周期，支持 "daily", "weekly", "monthly"

        Returns:
            pd.DataFrame: 技术指标数据
        """
        try:
            # 先获取K线数据
            kdata = self.get_kdata(symbol, DataFrequency.DAY)
            if kdata.empty:
                return pd.DataFrame()

            # 计算技术指标
            indicators_df = kdata.copy()

            # 计算移动平均线
            indicators_df['ma5'] = kdata['close'].rolling(window=5).mean()
            indicators_df['ma10'] = kdata['close'].rolling(window=10).mean()
            indicators_df['ma20'] = kdata['close'].rolling(window=20).mean()

            # 计算RSI
            delta = kdata['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            indicators_df['rsi'] = 100 - (100 / (1 + rs))

            self.logger.info(f"计算技术指标成功，数据条数: {len(indicators_df)}")
            return indicators_df
        except Exception as e:
            self.logger.error(f"计算技术指标失败: {str(e)}")
            return pd.DataFrame()

    def get_main_fund_flow(self, indicator: str = "今日") -> pd.DataFrame:
        """获取主力资金流数据

        Args:
            indicator: 时间周期，支持 "今日", "3日", "5日", "10日", "20日"

        Returns:
            pd.DataFrame: 主力资金流数据
        """
        try:
            df = ak.stock_main_fund_flow(indicator=indicator)
            self.logger.info(f"获取主力资金流数据成功，数据条数: {len(df)}")
            return df
        except Exception as e:
            self.logger.error(f"获取主力资金流数据失败: {str(e)}")
            return pd.DataFrame()

    def get_individual_fund_flow(self, symbol: str, indicator: str = "今日") -> pd.DataFrame:
        """获取个股资金流数据

        Args:
            symbol: 股票代码
            indicator: 时间周期，支持 "今日", "3日", "5日", "10日", "20日"

        Returns:
            pd.DataFrame: 个股资金流数据
        """
        try:
            df = ak.stock_individual_fund_flow(symbol=symbol, indicator=indicator)
            self.logger.info(f"获取个股资金流数据成功，数据条数: {len(df)}")
            return df
        except Exception as e:
            self.logger.error(f"获取个股资金流数据失败: {str(e)}")
            return pd.DataFrame()
