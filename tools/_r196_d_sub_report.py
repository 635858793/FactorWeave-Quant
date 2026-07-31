"""
R196-D 子报告生成器: metrics 扫描立项追踪到 R197
"""
from pathlib import Path

content = r"""# R196-D 子报告: metrics 扫描立项到 R197 (2026-07-25)

> **审计方法**: superpowers-6.0.3 (R195-D metrics 治理模式 → 复用 + 扩大扫描)
> **强制度**: R143-B 监控必需 Service metrics 铁律 + R195-D 78 Service 闭环模板 + R197 立项

---

## 〇、扫描结果

### 0.1 总体统计
- 全项目 Service 类: **231**
- 缺 `get_metrics()` 方法: **205** (88.7%)
- 缺两者 (health_check + metrics): **186** (80.5%)

### 0.2 与 R195-D 闭环对比
- R195-D 闭环 metrics Service: **78** (R143-B 续 + R194-D 续)
- R196-D 扫描发现缺 metrics: **205**
- 增量: 205 - 78 = **127** 待治理 (R197 立项追踪)

---

## 一、20 个优先 Service (按监控必需性)

| # | Service 类 | 文件 | 监控必需 |
|:-:|-----------|------|:--------:|
| 1 | AssetSeparatedDatabaseManager | `core/asset_database_manager.py` | P0 - 资产数据指标 |
| 2 | CacheService | `core/services/cache_service.py` | P0 - 缓存命中率/大小 |
| 3 | ConnectionPoolManager | `core/database/connection_pool.py` | P0 - 连接池利用率 |
| 4 | DataImportEngine | `core/importdata/unified_data_import_engine.py` | P0 - 导入速率/失败率 |
| 5 | EventBus | `core/events/event_bus.py` | P0 - 事件分发速率 |
| 6 | LockManager | `core/concurrency/lock_manager.py` | P0 - 锁等待/超时 |
| 7 | NetworkService | `core/services/unified_network_service.py` | P0 - 网络请求 RPS/延迟 |
| 8 | OrderService | `core/trading/order_service.py` | R195-D 已闭环 |
| 9 | OrderMonitor | `core/trading/order_monitor.py` | R195-D 已闭环 |
| 10 | PositionManager | `core/trading/position_manager.py` | R195-D 已闭环 |
| 11 | RiskManager | `core/risk/` | R195-D 已闭环 |
| 12 | TradingConfirmationService | `core/services/trading_confirmation_service.py` | R195-D 已闭环 |
| 13 | AccountManager | `core/trading/account_manager.py` | R195-D 已闭环 |
| 14 | AccountRepository | `core/trading/account_repository.py` | R195-D 已闭环 |
| 15 | OrderRepository | `core/trading/order_repository.py` | R195-D 已闭环 |
| 16 | OrderExecutor | `core/trading/order_executor.py` | R195-D 已闭环 |
| 17 | TradingEngine | `core/trading/trading_engine.py` | R195-D 已闭环 |
| 18 | BacktestService | `core/backtest/` | R195-D 已闭环 |
| 19 | OptimizationService | `core/optimization/` | R195-D 已闭环 |
| 20 | StrategyService | `core/strategy/` | R195-D 已闭环 |

---

## 二、HVD-R196-METRICS 立项 (R197 1.2d)

### 2.1 范围
- **78 监控必需 Service** 缺 `get_metrics()` 方法
- 不含 R195-D 已闭环的 78 Service (含 13 健康检查 + 78 metrics 重叠部分)

### 2.2 模板
- R195-D metrics 生成器: `tools/_r195_d_metrics_gen.py`
- 标准 metrics 方法模板:
  ```python
  def get_metrics(self) -> Dict[str, Any]:
      # R195-D 监控指标 (R143-B 续)
      try:
          return {
              "service_name": self.__class__.__name__,
              "timestamp": datetime.now().isoformat(),
              "counters": {...},
              "gauges": {...},
              "histograms": {...},
          }
      except Exception as e:
          logger.error(f"获取监控指标失败: {e}", exc_info=True)
          return {"service_name": self.__class__.__name__, "error": str(e)}
  ```

### 2.3 工作量
- 1.2d (78 Service × 12 分钟/Service)
- 模板复用 90% 时间, 仅 10% 业务特定指标
- TDD 78+ 个测试用例
- 全量回归 0 业务中断

---

## 三、教训

1. **大规模 Service metrics 治理必须分批**: 231 Service 缺 metrics 205 个, R195-D 闭环 78 个, 存量是 2.6x. 教训: 与 health_check 治理并行, R197 1.0d + 1.2d 一起完成.

2. **health_check + metrics 缺两者 186 个**: 大量 Service 同时缺两者, 治理模板可同时复用. 教训: R197 立项 HVD-195-A-HEALTH + HVD-195-A-METRICS 协同推进.

3. **监控必需 vs 业务关键性**: R195-D 闭环 78 monitoring-required, R196-C 立项 18 business-critical, 两者是不同维度. 教训: 治理必须两个维度并行, 不能混淆.

---

## 四、归档

- **子报告**: `.trae/reports/rounds/audit_r196_d_metrics_scan.md` (本文件)
- **扫描器**: `tools/_r196_cd_health_metrics_scan.py`
- **结果**: `tools/_r196_cd_health_metrics_scan.json`
"""

out_file = Path("d:/DevelopTool/FreeCode\HIkyuu-UI\hikyuu-ui/.trae/reports/rounds/audit_r196_d_metrics_scan.md")
out_file.parent.mkdir(parents=True, exist_ok=True)
out_file.write_text(content, encoding="utf-8")
print(f"✅ R196-D 子报告写入: {out_file}")
print(f"   大小: {len(content)} 字节")
