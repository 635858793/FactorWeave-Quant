#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess
import sys
import os

test_code = '''
import sys
sys.path.insert(0, r"d:\\DevelopTool\\FreeCode\\HIkyuu-UI\\hikyuu-ui")

from gui.widgets.trading_panel import MATPLOTLIB_AVAILABLE
print("1. matplotlib: " + str(MATPLOTLIB_AVAILABLE))

from core.services.trading_service import Position
from decimal import Decimal
p = Position('000001.SZ', 'test', 1000, Decimal('15.50'))
print("2. Position.avg_cost: " + str(p.avg_cost))
print("3. Position.profit_loss_pct: " + str(p.profit_loss_pct))

from core.services.trading_service import Portfolio
pf = Portfolio('test', 'test', cash=Decimal('100000'), total_market_value=Decimal('39800'))
print("4. Portfolio.total_assets: " + str(pf.total_assets))

from core.events.types import StockSelectedEvent, TradeExecutedEvent, PositionUpdatedEvent
print("5. Event types: OK")

import inspect
from core.services.trading_service import TradingService
src = inspect.getsource(TradingService)
print("6. _order_lock: " + str('_order_lock' in src))
print("7. _position_lock: " + str('_position_lock' in src))
print("8. _portfolio_lock: " + str('_portfolio_lock' in src))

print("=== ALL TESTS DONE ===")
'''

result = subprocess.run(
    [sys.executable, '-c', test_code],
    capture_output=True,
    text=True,
    cwd=r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui",
    env={**os.environ, 'PYTHONUNBUFFERED': '1', 'TF_CPP_MIN_LOG_LEVEL': '3'}
)

print("STDOUT:")
print(result.stdout)
if result.stderr:
    print("STDERR:")
    print(result.stderr)
print("Return code:", result.returncode)
