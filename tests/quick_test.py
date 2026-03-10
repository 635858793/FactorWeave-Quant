#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class ResultCollector:
    def __init__(self):
        self.results = []
    
    def add(self, name, passed, msg=""):
        status = "PASS" if passed else "FAIL"
        self.results.append("[%s] %s: %s" % (status, name, msg))
    
    def print_all(self):
        for r in self.results:
            print(r)

results = ResultCollector()

try:
    from gui.widgets.trading_panel import MATPLOTLIB_AVAILABLE
    results.add("matplotlib", True, str(MATPLOTLIB_AVAILABLE))
except Exception as e:
    results.add("matplotlib", False, str(e))

try:
    from core.services.trading_service import Position
    from decimal import Decimal
    p = Position('000001.SZ', 'test', 1000, Decimal('15.50'))
    assert p.avg_cost == 15.5
    results.add("Position.avg_cost", True, str(p.avg_cost))
except Exception as e:
    results.add("Position.avg_cost", False, str(e))

try:
    from core.services.trading_service import Position
    from decimal import Decimal
    p = Position('000001.SZ', 'test', 1000, Decimal('15.50'))
    assert p.profit_loss_pct == 0.0
    results.add("Position.profit_loss_pct", True, str(p.profit_loss_pct))
except Exception as e:
    results.add("Position.profit_loss_pct", False, str(e))

try:
    from core.services.trading_service import Portfolio
    pf = Portfolio('test', 'test', cash=Decimal('100000'), total_market_value=Decimal('39800'))
    assert pf.total_assets == 139800
    results.add("Portfolio.total_assets", True, str(pf.total_assets))
except Exception as e:
    results.add("Portfolio.total_assets", False, str(e))

try:
    from core.events.types import StockSelectedEvent, TradeExecutedEvent, PositionUpdatedEvent
    results.add("Event types", True, "OK")
except Exception as e:
    results.add("Event types", False, str(e))

try:
    import inspect
    from core.services.trading_service import TradingService
    src = inspect.getsource(TradingService)
    results.add("_order_lock", '_order_lock' in src, "present" if '_order_lock' in src else "missing")
    results.add("_position_lock", '_position_lock' in src, "present" if '_position_lock' in src else "missing")
    results.add("_portfolio_lock", '_portfolio_lock' in src, "present" if '_portfolio_lock' in src else "missing")
except Exception as e:
    results.add("Lock check", False, str(e))

print("\n" + "="*50)
print("TEST RESULTS")
print("="*50)
results.print_all()
print("="*50)

passed = sum(1 for r in results.results if "[PASS]" in r)
total = len(results.results)
print("\nTotal: %d/%d tests passed" % (passed, total))

if passed == total:
    print("\n*** ALL TESTS PASSED ***\n")
else:
    print("\n*** %d TESTS FAILED ***\n" % (total - passed))
