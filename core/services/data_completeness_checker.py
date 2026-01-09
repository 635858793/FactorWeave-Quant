"""
Data Completeness Checker Module

This module provides functionality to check the completeness of K-line data
by identifying missing dates and gaps in the data timeline.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass

from ..data.models import KlineData, QueryParams
from ..database.duckdb_manager import DuckDBConnectionManager
from ..events.event_bus import EventBus
from ..events.types import DataIntegrityEvent

logger = logging.getLogger(__name__)


@dataclass
class CompletenessCheckResult:
    """Result of data completeness check"""
    symbol: str
    start_date: datetime
    end_date: datetime
    missing_dates: Set[datetime]
    completeness_percentage: float
    status: str  # 'complete', 'partial', 'missing'
    latest_data_date: Optional[datetime] = None
    earliest_data_date: Optional[datetime] = None


@dataclass
class StockStatus:
    """Status information for a stock"""
    symbol: str
    name: str
    latest_date: datetime
    completeness: float
    status: str
    missing_dates_count: int
    total_trading_days: int


class DataCompletenessChecker:
    """Service to check the completeness of K-line data"""

    def __init__(self, db_manager: DuckDBConnectionManager, event_bus: EventBus, db_path: str = None):
        self.db_manager = db_manager
        self.event_bus = event_bus
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        # Use provided db_path or default to system database
        self.db_path = db_path or "data/factorweave_system.sqlite"

    async def check_completeness(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        skip_weekends: bool = True,
        skip_holidays: bool = True
    ) -> CompletenessCheckResult:
        """
        Check data completeness for a single stock

        Args:
            symbol: Stock symbol
            start_date: Start date for completeness check
            end_date: End date for completeness check
            skip_weekends: Whether to skip weekends in trading calendar
            skip_holidays: Whether to skip holidays in trading calendar

        Returns:
            CompletenessCheckResult with detailed information about data completeness
        """
        try:
            # Get existing data dates
            existing_dates = await self._get_existing_data_dates(symbol, start_date, end_date)

            # Generate expected trading dates
            expected_dates = await self._generate_trading_calendar(start_date, end_date, skip_weekends, skip_holidays)

            # Calculate missing dates
            missing_dates = expected_dates - existing_dates
            completeness_percentage = (len(expected_dates) - len(missing_dates)) / len(expected_dates) * 100 if expected_dates else 0

            # Determine status
            if len(missing_dates) == 0:
                status = 'complete'
            elif len(missing_dates) < len(expected_dates) * 0.1:  # Less than 10% missing
                status = 'partial'
            else:
                status = 'missing'

            # Get latest and earliest data dates
            latest_date = max(existing_dates) if existing_dates else None
            earliest_date = min(existing_dates) if existing_dates else None

            result = CompletenessCheckResult(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                missing_dates=missing_dates,
                completeness_percentage=completeness_percentage,
                status=status,
                latest_data_date=latest_date,
                earliest_data_date=earliest_date
            )

            # Publish event
            await self.event_bus.publish(DataIntegrityEvent(
                symbol=symbol,
                completeness=completeness_percentage,
                missing_count=len(missing_dates),
                total_count=len(expected_dates)
            ))

            logger.info(f"Data completeness check completed for {symbol}: {completeness_percentage:.2f}% complete")
            return result

        except Exception as e:
            logger.error(f"Error checking completeness for {symbol}: {str(e)}")
            raise

    async def check_multiple_stocks_completeness(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        skip_weekends: bool = True,
        skip_holidays: bool = True
    ) -> Dict[str, CompletenessCheckResult]:
        """
        Check completeness for multiple stocks concurrently

        Args:
            symbols: List of stock symbols
            start_date: Start date for check
            end_date: End date for check
            skip_weekends: Whether to skip weekends
            skip_holidays: Whether to skip holidays

        Returns:
            Dictionary mapping symbols to their completeness results
        """
        tasks = []
        for symbol in symbols:
            task = self.check_completeness(symbol, start_date, end_date, skip_weekends, skip_holidays)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return_results = {}
        for i, result in enumerate(results):
            symbol = symbols[i]
            if isinstance(result, Exception):
                logger.error(f"Error checking completeness for {symbol}: {str(result)}")
                continue
            return_results[symbol] = result

        return return_results

    async def get_stock_status_batch(self, symbols: List[str], end_date: datetime) -> List[StockStatus]:
        """
        Get status information for multiple stocks

        Args:
            symbols: List of stock symbols
            end_date: End date for status check (defaults to today)

        Returns:
            List of StockStatus objects
        """
        status_list = []

        for symbol in symbols:
            try:
                # Get latest data date for this symbol
                latest_date = await self.db_manager.get_latest_date(symbol)

                # Get recent 30 days for completeness calculation
                start_date = end_date - timedelta(days=30)
                completeness_result = await self.check_completeness(
                    symbol, start_date, end_date, skip_holidays=True
                )

                # Estimate total trading days in the period
                trading_days = await self._estimate_trading_days_count(start_date, end_date)

                status = StockStatus(
                    symbol=symbol,
                    name="",  # To be populated by caller
                    latest_date=latest_date or end_date,
                    completeness=completeness_result.completeness_percentage,
                    status=completeness_result.status,
                    missing_dates_count=len(completeness_result.missing_dates),
                    total_trading_days=trading_days
                )

                status_list.append(status)

            except Exception as e:
                logger.error(f"Error getting status for {symbol}: {str(e)}")
                # Add placeholder for failed stocks
                status_list.append(StockStatus(
                    symbol=symbol,
                    name="",
                    latest_date=None,
                    completeness=0.0,
                    status="error",
                    missing_dates_count=0,
                    total_trading_days=0
                ))

        return status_list

    async def get_missing_data_report(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        threshold: float = 0.1  # Only show stocks with more than 10% missing data
    ) -> Dict[str, Dict]:
        """
        Generate a detailed missing data report

        Args:
            symbols: List of stock symbols
            start_date: Start date for report
            end_date: End date for report
            threshold: Minimum missing percentage to include in report

        Returns:
            Dictionary with detailed missing data information
        """
        completeness_results = await self.check_multiple_stocks_completeness(
            symbols, start_date, end_date, skip_holidays=True
        )

        report = {}

        for symbol, result in completeness_results.items():
            if result.completeness_percentage < (1 - threshold) * 100:  # Above threshold missing
                missing_dates_list = sorted(list(result.missing_dates))

                # Group missing dates by contiguous periods
                missing_periods = self._group_missing_dates(missing_dates_list)

                report[symbol] = {
                    'completeness': result.completeness_percentage,
                    'missing_count': len(missing_dates_list),
                    'total_trading_days': len(missing_dates_list) + len(set(result.missing_dates)),
                    'missing_periods': missing_periods,
                    'latest_date': result.latest_data_date,
                    'earliest_date': result.earliest_data_date,
                    'status': result.status
                }

        return report

    async def _get_existing_data_dates(self, symbol: str, start_date: datetime, end_date: datetime) -> Set[datetime]:
        """Get existing data dates for a symbol within date range"""
        query = """
        SELECT DISTINCT datetime
        FROM kline_data
        WHERE symbol = ?
        AND datetime >= ?
        AND datetime <= ?
        """

        with self.db_manager.get_connection(self.db_path) as conn:
            results = conn.execute(query, (symbol, start_date, end_date)).fetchall()

        existing_dates = set()

        for row in results:
            existing_dates.add(row[0])

        return existing_dates

    async def _generate_trading_calendar(
        self,
        start_date: datetime,
        end_date: datetime,
        skip_weekends: bool,
        skip_holidays: bool
    ) -> Set[datetime]:
        """
        Generate trading calendar for the date range

        Args:
            start_date: Start date
            end_date: End date
            skip_weekends: Whether to skip weekends
            skip_holidays: Whether to skip holidays

        Returns:
            Set of expected trading dates
        """
        trading_dates = set()
        current_date = start_date

        while current_date <= end_date:
            # Skip weekends if requested
            if skip_weekends and current_date.weekday() >= 5:  # Saturday=5, Sunday=6
                current_date += timedelta(days=1)
                continue

            # Skip holidays if requested (simplified - add holiday logic as needed)
            if skip_holidays and self._is_holiday(current_date):
                current_date += timedelta(days=1)
                continue

            trading_dates.add(current_date)
            current_date += timedelta(days=1)

        return trading_dates

    def _is_holiday(self, date: datetime) -> bool:
        """
        Check if a date is a holiday (simplified implementation)

        Args:
            date: Date to check

        Returns:
            True if date is a holiday, False otherwise
        """
        # Simplified holiday detection - should be enhanced with proper holiday calendar
        # For now, check some major holidays
        if date.month == 1 and date.day == 1:  # New Year's Day
            return True
        if date.month == 10 and 1 <= date.day <= 7:  # Chinese National Day (simplified)
            return True

        return False

    def _group_missing_dates(self, missing_dates: List[datetime]) -> List[Dict]:
        """
        Group missing dates into contiguous periods

        Args:
            missing_dates: List of sorted missing dates

        Returns:
            List of dictionaries with period info
        """
        if not missing_dates:
            return []

        periods = []
        current_period_start = missing_dates[0]
        previous_date = missing_dates[0]

        for date in missing_dates[1:]:
            if (date - previous_date).days > 1:  # Gap found
                periods.append({
                    'start': current_period_start,
                    'end': previous_date,
                    'duration': (previous_date - current_period_start).days + 1
                })
                current_period_start = date
            previous_date = date

        # Add the last period
        periods.append({
            'start': current_period_start,
            'end': previous_date,
            'duration': (previous_date - current_period_start).days + 1
        })

        return periods

    async def _estimate_trading_days_count(self, start_date: datetime, end_date: datetime) -> int:
        """
        Estimate the number of trading days in a period

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Estimated number of trading days
        """
        # Simple estimation: about 250 trading days per year
        days_diff = (end_date - start_date).days
        years = days_diff / 365.0
        return int(years * 250)  # Approximately 250 trading days per year

    def clear_cache(self):
        """Clear the internal cache"""
        self._cache.clear()
        logger.info("Data completeness checker cache cleared")

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'cache_size': len(self._cache),
            'cache_ttl': self._cache_ttl
        }