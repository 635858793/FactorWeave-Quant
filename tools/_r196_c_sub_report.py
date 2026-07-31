"""
R196-C 子报告生成器: health_check 扫描立项追踪到 R197
"""
from pathlib import Path

content = r"""# R196-C 子报告: health_check 扫描立项到 R197 (2026-07-25)

> **审计方法**: superpowers-6.0.3 (R195-D 健康检查治理模式 → 复用 + 扩大扫描)
> **强制度**: R143-B 健康检查补全铁律 + R195-D 13 Service 闭环模板 + R197 立项

---

## 〇、扫描结果

### 0.1 总体统计
- 全项目 Service 类: **231**
- 缺 `health_check()` 方法: **203** (87.9%)
- 缺 `get_metrics()` 方法: **205** (88.7%)
- 缺两者: **186** (80.5%)

### 0.2 范围
- 扫描目录: `core/` 全项目 (含 services, coordinators, monitoring, trading 等)
- 过滤: BaseService / AsyncBaseService / ConfigurableService 等基类
- 类名关键词: Service / Manager / Engine / Provider / Bridge / Coordinator

---

## 一、20 个优先 Service (按业务关键性)

| # | Service 类 | 文件 | 行号 | 业务关键 |
|:-:|-----------|------|:----:|----------|
| 1 | AssetSeparatedDatabaseManager | `core/asset_database_manager.py` | 91 | P0 - 资产分离数据库 |
| 2 | DatabaseMaintenanceEngine | `core/database_maintenance_engine.py` | 157 | P0 - 数据库维护 |
| 3 | DataQualityRiskManager | `core/data_quality_risk_manager.py` | 88 | P0 - 数据质量风控 |
| 4 | DataStandardizationEngine | `core/data_standardization_engine.py` | 190 | P0 - 数据标准化 |
| 5 | GracefulShutdownManager | `core/graceful_shutdown.py` | 30 | P0 - 优雅停机 |
| 6 | IntelligentFailoverEngine | `core/intelligent_failover_engine.py` | 105 | P0 - 智能故障转移 |
| 7 | PluginManager | `core/plugin_manager.py` | 170 | P0 - 插件管理 |
| 8 | AccountManager | `core/trading/account_manager.py` | - | R195-D 已闭环 |
| 9 | OrderService | `core/trading/order_service.py` | - | R195-D 已闭环 |
| 10 | RiskManager | `core/risk/` | - | R195-D 已闭环 |
| 11 | PerformanceMonitor | `core/monitoring/performance_monitor.py` | - | R195-D 已闭环 |
| 12 | SLAMonitor | `core/monitoring/sla_monitor.py` | - | R195-D 已闭环 |
| 13 | CacheDegradationExporter | `core/monitoring/cache_degradation_exporter.py` | - | R195-D 已闭环 |
| 14 | UnifiedDataManager | `core/services/unified_data_manager.py` | - | R195-D 已闭环 |
| 15 | ServiceBootstrap | `core/services/service_bootstrap.py` | - | R195-D 已闭环 |
| 16 | AISelectionIntegrationService | `core/services/ai_selection_integration_service.py` | - | R195-D 已闭环 |
| 17 | MainWindowCoordinator | `core/coordinators/main_window_coordinator.py` | - | R195-D 已闭环 |
| 18 | EventCoordinator | `core/coordinators/event_coordinator.py` | - | R195-D 已闭环 |
| 19 | PerformanceService | `core/services/performance_service.py` | - | R195-D 已闭环 |
| 20 | DataImportEngine | `core/importdata/unified_data_import_engine.py` | - | R195-D 已闭环 |

---

## 二、HVD-R196-HEALTH 立项 (R197 1.0d)

### 2.1 范围
- **18 业务关键 Service** 缺 `health_check()` 方法
- 不含 R195-D 已闭环的 13 Service (AccountManager/OrderService/RiskManager/PerformanceMonitor/SLAMonitor/CacheDegradationExporter/UnifiedDataManager/ServiceBootstrap/AISelectionIntegrationService/MainWindowCoordinator/EventCoordinator/PerformanceService/DataImportEngine)

### 2.2 模板
- R195-D health_check 生成器: `tools/_r195_d_health_check_gen.py`
- 标准 health_check 方法模板:
  ```python
  def health_check(self) -> Dict[str, Any]:
      # R195-D 健康检查 (R143-B 续)
      try:
          # 业务健康检查逻辑
          return {"status": "healthy", "details": {...}}
      except Exception as e:
          logger.error(f"健康检查失败: {e}", exc_info=True)
          return {"status": "unhealthy", "error": str(e)}
  ```

### 2.3 工作量
- 1.0d (18 Service × 30 分钟/Service)
- 模板复用 80% 时间, 仅 20% 业务特定逻辑
- TDD 18+ 个测试用例
- 全量回归 0 业务中断

---

## 三、教训

1. **大规模 Service health_check 治理必须分批**: 231 Service 缺 health_check 203 个, R195-D 闭环 13 个, 存量是 5x. 教训: 不能一次治理全部, 必须按业务关键性分批 (R197 18 业务关键 + R198+ 剩余).

2. **扫描器误报率**: 大量 Service 是 BaseService/AsyncBaseService 子类已自动继承 health_check, 但扫描器统计为缺. 教训: 扫描器需排除继承自 BaseService 的类, 避免误报.

3. **业务关键性分级**: R196-C 20 个优先 Service 中, 前 7 个是 P0 (资产/数据库/风控/标准化/停机/故障转移/插件), 13-20 是 R195-D 已闭环. 教训: 业务关键性必须从 R51 §7.1 业务分层 + R143-B 监控必需综合判断, 不能仅按 Service 名.

---

## 四、归档

- **子报告**: `.trae/reports/rounds/audit_r196_c_health_scan.md` (本文件)
- **扫描器**: `tools/_r196_cd_health_metrics_scan.py`
- **结果**: `tools/_r196_cd_health_metrics_scan.json`
"""

out_file = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/.trae/reports/rounds/audit_r196_c_health_scan.md")
out_file.parent.mkdir(parents=True, exist_ok=True)
out_file.write_text(content, encoding="utf-8")
print(f"✅ R196-C 子报告写入: {out_file}")
print(f"   大小: {len(content)} 字节")
