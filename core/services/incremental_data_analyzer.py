"""
Incremental Data Analyzer Module

This module provides intelligent incremental download analysis by identifying
missing data ranges and generating optimal download plans.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ..data.models import QueryParams
from ..database.duckdb_manager import DuckDBConnectionManager
from ..events.event_bus import EventBus
from ..events.types import DataAnalysisEvent
from .data_completeness_checker import DataCompletenessChecker

logger = logging.getLogger(__name__)


class DownloadStrategy(Enum):
    """Download strategies for incremental updates"""
    LATEST_ONLY = "latest_only"  # Only download latest trading days
    MISSING_ONLY = "missing_only"  # Only download missing data
    GAP_FILL = "gap_fill"  # Fill all gaps in the data
    SMART_FILL = "smart_fill"  # Fill gaps based on data importance


@dataclass
class IncrementalAnalysisResult:
    """Result of incremental data analysis"""
    symbol: str
    download_strategy: DownloadStrategy
    download_range: Tuple[datetime, datetime]
    missing_dates: Set[datetime]
    skip_download: bool
    skip_reason: str
    estimated_records: int
    confidence_level: float
    analysis_timestamp: datetime


@dataclass
class DownloadPlan:
    """Download plan for multiple stocks"""
    total_symbols: int
    symbols_to_download: List[str]
    symbols_to_skip: List[str]
    symbols_to_skip_reason: Dict[str, str]
    total_missing_dates: int
    estimated_total_records: int
    download_ranges: Dict[str, Tuple[datetime, datetime]]
    analysis_timestamp: datetime


@dataclass
class GapFillPlan:
    """Plan for filling data gaps"""
    symbol: str
    gap_periods: List[Dict]  # List of gap period dictionaries
    filling_strategy: str
    estimated_records: int
    priority: int  # 1=high, 2=medium, 3=low


class IncrementalDataAnalyzer:
    """Service for analyzing incremental download requirements"""

    def __init__(self, db_manager: DuckDBConnectionManager, event_bus: EventBus, completeness_checker: DataCompletenessChecker):
        self.db_manager = db_manager
        self.event_bus = event_bus
        self.completeness_checker = completeness_checker

        # Configuration
        self.default_strategy = DownloadStrategy.LATEST_ONLY
        self.latest_days_to_download = 7  # Default: download last 7 days
        self.gap_fill_threshold = 30  # Maximum days to fill in one gap
        self.min_records_threshold = 10  # Minimum records to consider download worthwhile

    async def analyze_incremental_requirements(
        self,
        symbols: List[str],
        end_date: datetime,
        strategy: DownloadStrategy = None,
        skip_weekends: bool = True,
        skip_holidays: bool = True
    ) -> DownloadPlan:
        """
        Analyze incremental download requirements for multiple stocks

        Args:
            symbols: List of stock symbols to analyze
            end_date: End date for analysis (usually current date)
            strategy: Download strategy to use
            skip_weekends: Whether to skip weekends in calculations
            skip_holidays: Whether to skip holidays in calculations

        Returns:
            DownloadPlan with detailed analysis results
        """
        if strategy is None:
            strategy = self.default_strategy

        logger.info(f"Starting incremental analysis for {len(symbols)} stocks with strategy: {strategy.value}")

        symbols_to_download = []
        symbols_to_skip = []
        symbols_to_skip_reason = {}
        download_ranges = {}
        total_missing_dates = 0
        estimated_total_records = 0

        analysis_timestamp = datetime.now()

        # Analyze each symbol
        analysis_tasks = []
        for symbol in symbols:
            task = self._analyze_single_symbol(
                symbol, end_date, strategy, skip_weekends, skip_holidays
            )
            analysis_tasks.append(task)

        results = await asyncio.gather(*analysis_tasks, return_exceptions=True)

        for i, result in enumerate(results):
            symbol = symbols[i]
            if isinstance(result, Exception):
                logger.error(f"Error analyzing {symbol}: {str(result)}")
                symbols_to_skip_reason[symbol] = f"Analysis failed: {str(result)}"
                symbols_to_skip.append(symbol)
                continue

            if result.skip_download:
                symbols_to_skip.append(symbol)
                symbols_to_skip_reason[symbol] = result.skip_reason
            else:
                symbols_to_download.append(symbol)
                download_ranges[symbol] = result.download_range
                total_missing_dates += len(result.missing_dates)
                estimated_total_records += result.estimated_records

        # Create download plan
        download_plan = DownloadPlan(
            total_symbols=len(symbols),
            symbols_to_download=symbols_to_download,
            symbols_to_skip=symbols_to_skip,
            symbols_to_skip_reason=symbols_to_skip_reason,
            total_missing_dates=total_missing_dates,
            estimated_total_records=estimated_total_records,
            download_ranges=download_ranges,
            analysis_timestamp=analysis_timestamp
        )

        # Publish analysis event
        await self.event_bus.emit(DataAnalysisEvent(
            symbol="batch",
            analysis_type="incremental_requirements",
            total_symbols=len(symbols),
            symbols_to_download=len(symbols_to_download),
            symbols_to_skip=len(symbols_to_skip),
            estimated_records=estimated_total_records,
            strategy=strategy.value
        ))

        logger.info(f"Incremental analysis completed. Download: {len(symbols_to_download)}, Skip: {len(symbols_to_skip)}")
        return download_plan

    async def _analyze_single_symbol(
        self,
        symbol: str,
        end_date: datetime,
        strategy: DownloadStrategy,
        skip_weekends: bool,
        skip_holidays: bool
    ) -> IncrementalAnalysisResult:
        """
        Analyze incremental requirements for a single symbol

        Args:
            symbol: Stock symbol
            end_date: End date for analysis
            strategy: Download strategy
            skip_weekends: Whether to skip weekends
            skip_holidays: Whether to skip holidays

        Returns:
            IncrementalAnalysisResult with analysis results
        """
        try:
            # Get latest data date
            latest_date = await self.db_manager.get_latest_date(symbol)

            # If no data exists, download from start to end
            if latest_date is None:
                return IncrementalAnalysisResult(
                    symbol=symbol,
                    download_strategy=strategy,
                    download_range=(end_date - timedelta(days=365), end_date),  # Last year
                    missing_dates=set(),
                    skip_download=False,
                    skip_reason="",
                    estimated_records=252,  # ~252 trading days in a year
                    confidence_level=1.0,
                    analysis_timestamp=datetime.now()
                )

            # Check if data is recent enough to skip
            days_since_latest = (end_date - latest_date).days
            if days_since_latest < 1 and strategy == DownloadStrategy.LATEST_ONLY:
                return IncrementalAnalysisResult(
                    symbol=symbol,
                    download_strategy=strategy,
                    download_range=(latest_date, latest_date),
                    missing_dates=set(),
                    skip_download=True,
                    skip_reason="Data is already up to date",
                    estimated_records=0,
                    confidence_level=1.0,
                    analysis_timestamp=datetime.now()
                )

            # Determine download range based on strategy
            download_range, missing_dates = await self._calculate_download_range(
                symbol, latest_date, end_date, strategy, skip_weekends, skip_holidays
            )

            # Estimate records count
            estimated_records = await self._estimate_records_count(download_range, skip_weekends, skip_holidays)

            # Skip if too few records to download
            if estimated_records < self.min_records_threshold:
                return IncrementalAnalysisResult(
                    symbol=symbol,
                    download_strategy=strategy,
                    download_range=download_range,
                    missing_dates=missing_dates,
                    skip_download=True,
                    skip_reason=f"Only {estimated_records} records to download (threshold: {self.min_records_threshold})",
                    estimated_records=estimated_records,
                    confidence_level=0.8,
                    analysis_timestamp=datetime.now()
                )

            # Check if download range is reasonable
            days_diff = (download_range[1] - download_range[0]).days
            if days_diff > 365:  # More than a year
                logger.warning(f"Large download range detected for {symbol}: {days_diff} days")

            return IncrementalAnalysisResult(
                symbol=symbol,
                download_strategy=strategy,
                download_range=download_range,
                missing_dates=missing_dates,
                skip_download=False,
                skip_reason="",
                estimated_records=estimated_records,
                confidence_level=0.9,
                analysis_timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {str(e)}")
            raise

    async def _calculate_download_range(
        self,
        symbol: str,
        latest_date: datetime,
        end_date: datetime,
        strategy: DownloadStrategy,
        skip_weekends: bool,
        skip_holidays: bool
    ) -> Tuple[Tuple[datetime, datetime], Set[datetime]]:
        """
        Calculate the optimal download range based on strategy

        Args:
            symbol: Stock symbol
            latest_date: Latest data date
            end_date: End date for analysis
            strategy: Download strategy
            skip_weekends: Whether to skip weekends
            skip_holidays: Whether to skip holidays

        Returns:
            Tuple of (download_range, missing_dates)
        """
        if strategy == DownloadStrategy.LATEST_ONLY:
            # Download only recent data (last N trading days)
            start_date = end_date - timedelta(days=self.latest_days_to_download)
            start_date = max(start_date, latest_date + timedelta(days=1))

        elif strategy == DownloadStrategy.MISSING_ONLY:
            # Check for missing data and fill gaps
            completeness_result = await self.completeness_checker.check_completeness(
                symbol, latest_date, end_date, skip_weekends, skip_holidays
            )
            start_date = min(completeness_result.missing_dates) if completeness_result.missing_dates else latest_date
            missing_dates = completeness_result.missing_dates

            return (start_date, end_date), missing_dates

        elif strategy == DownloadStrategy.GAP_FILL:
            # Fill all gaps in the data
            completeness_result = await self.completeness_checker.check_completeness(
                symbol, latest_date, end_date, skip_weekends, skip_holidays
            )
            start_date = min(completeness_result.missing_dates) if completeness_result.missing_dates else latest_date
            missing_dates = completeness_result.missing_dates

            return (start_date, end_date), missing_dates

        elif strategy == DownloadStrategy.SMART_FILL:
            # Fill gaps based on importance (recent gaps filled first)
            gap_fill_plan = await self._create_gap_fill_plan(symbol, latest_date, end_date)
            if gap_fill_plan.gap_periods:
                start_date = gap_fill_plan.gap_periods[0]['start']
                missing_dates = set()
                for period in gap_fill_plan.gap_periods:
                    current_date = period['start']
                    while current_date <= period['end']:
                        missing_dates.add(current_date)
                        current_date += timedelta(days=1)
            else:
                start_date = latest_date + timedelta(days=1)
                missing_dates = set()

            return (start_date, end_date), missing_dates

        else:
            raise ValueError(f"Unknown download strategy: {strategy}")

        # For strategies without detailed gap analysis, estimate missing dates
        missing_dates = await self._estimate_missing_dates(symbol, start_date, end_date, skip_weekends, skip_holidays)

        return (start_date, end_date), missing_dates

    async def _create_gap_fill_plan(self, symbol: str, latest_date: datetime, end_date: datetime) -> GapFillPlan:
        """
        Create a gap fill plan based on data importance

        Args:
            symbol: Stock symbol
            latest_date: Latest data date
            end_date: End date for analysis

        Returns:
            GapFillPlan with gap filling strategy
        """
        # Get missing data report
        missing_report = await self.completeness_checker.get_missing_data_report(
            [symbol], latest_date, end_date, threshold=0.01
        )

        if symbol not in missing_report:
            return GapFillPlan(
                symbol=symbol,
                gap_periods=[],
                filling_strategy="no_gaps",
                estimated_records=0,
                priority=3
            )

        gap_info = missing_report[symbol]
        gap_periods = gap_info['missing_periods']

        # Prioritize recent gaps
        priority = 1 if end_date - gap_periods[0]['end'] < timedelta(days=30) else 2
        if len(gap_periods) > 3:
            priority = 3

        return GapFillPlan(
            symbol=symbol,
            gap_periods=gap_periods,
            filling_strategy="importance_based",
            estimated_records=gap_info['missing_count'],
            priority=priority
        )

    async def _estimate_missing_dates(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        skip_weekends: bool,
        skip_holidays: bool
    ) -> Set[datetime]:
        """
        Estimate missing dates in the download range

        Args:
            symbol: Stock symbol
            start_date: Start date for analysis
            end_date: End date for analysis
            skip_weekends: Whether to skip weekends
            skip_holidays: Whether to skip holidays

        Returns:
            Set of estimated missing dates
        """
        # Get existing dates in the range
        existing_dates = await self.completeness_checker._get_existing_data_dates(symbol, start_date, end_date)

        # Generate expected trading dates
        expected_dates = await self.completeness_checker._generate_trading_calendar(
            start_date, end_date, skip_weekends, skip_holidays
        )

        # Calculate missing dates
        missing_dates = expected_dates - existing_dates

        return missing_dates

    async def _estimate_records_count(
        self,
        download_range: Tuple[datetime, datetime],
        skip_weekends: bool,
        skip_holidays: bool
    ) -> int:
        """
        Estimate the number of records to download

        Args:
            download_range: (start_date, end_date) tuple
            skip_weekends: Whether to skip weekends
            skip_holidays: Whether to skip holidays

        Returns:
            Estimated number of records
        """
        start_date, end_date = download_range
        days_diff = (end_date - start_date).days

        # Simple estimation: about 250 trading days per year
        years = days_diff / 365.0
        estimated_trading_days = int(years * 250)

        # Adjust for weekends and holidays
        if skip_weekends or skip_holidays:
            # Rough adjustment: about 20% fewer days for weekends and holidays
            estimated_trading_days = int(estimated_trading_days * 0.8)

        return max(estimated_trading_days, 1)

    async def get_update_priority_analysis(
        self,
        symbols: List[str],
        end_date: datetime
    ) -> List[Tuple[str, int, str]]:
        """
        Analyze and prioritize symbols for update

        Args:
            symbols: List of stock symbols
            end_date: End date for analysis

        Returns:
            List of tuples (symbol, priority, reason)
        """
        priority_list = []

        for symbol in symbols:
            try:
                latest_date = await self.db_manager.get_latest_date(symbol)
                days_since_latest = (end_date - latest_date).days if latest_date else float('inf')

                # Priority scoring
                if days_since_latest > 7:
                    priority = 1  # High priority
                    reason = "Data is more than 7 days old"
                elif days_since_latest > 3:
                    priority = 2  # Medium priority
                    reason = "Data is 3-7 days old"
                elif days_since_latest > 1:
                    priority = 3  # Low priority
                    reason = "Data is 1-3 days old"
                else:
                    priority = 4  # No priority needed
                    reason = "Data is up to date"

                priority_list.append((symbol, priority, reason))

            except Exception as e:
                logger.error(f"Error analyzing priority for {symbol}: {str(e)}")
                priority_list.append((symbol, 4, f"Error: {str(e)}"))

        # Sort by priority (1=high, 4=low)
        priority_list.sort(key=lambda x: x[1])

        return priority_list

    def set_download_strategy(self, strategy: DownloadStrategy):
        """Set the default download strategy"""
        self.default_strategy = strategy
        logger.info(f"Download strategy set to: {strategy.value}")

    def set_latest_days_to_download(self, days: int):
        """Set the number of days to download for latest_only strategy"""
        self.latest_days_to_download = days
        logger.info(f"Latest days to download set to: {days}")

    def set_gap_fill_threshold(self, days: int):
        """Set the maximum days to fill in one gap"""
        self.gap_fill_threshold = days
        logger.info(f"Gap fill threshold set to: {days}")

    def set_min_records_threshold(self, threshold: int):
        """Set the minimum records threshold for download"""
        self.min_records_threshold = threshold
        logger.info(f"Minimum records threshold set to: {threshold}")