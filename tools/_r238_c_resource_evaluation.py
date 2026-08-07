"""R238 C 子智能体: 业务影响评估 - 0 dispose 链 Service 资源识别."""
import re
from pathlib import Path

# 32 个 0 dispose 链候选
CANDIDATES = [
    "AIExplainabilityService", "AnalysisService", "BondService", "CacheService",
    "ChartService", "ConfigService", "DataMaskingService", "DataService",
    "DatabaseMonitoringService", "DatabaseService", "DividendDataService",
    "EnvironmentService", "FundService", "FundingRateAnalysisService",
    "IndexService", "IndustryService", "IntegratedSignalAggregatorService",
    "LifecycleService", "LLMConfigService", "MarketService", "ModelTrainingService",
    "NetworkService", "NotificationService", "PerformanceService", "PluginService",
    "PredictionTrackingService", "SecurityService", "StockService", "StrategyService",
    "SystemOptimizerService", "TradingConfirmationService", "TradingService",
]

# 重要资源特征
RESOURCE_PATTERNS = {
    "connection_pool": (r"connection_pool|ConnectionPool|conn_pool|_pool\b", "连接池"),
    "aiohttp_session": (r"aiohttp\.ClientSession|httpx\.AsyncClient|_async_session", "aiohttp Session"),
    "thread": (r"_thread|Thread\(|\.start\(\)|_monitor_thread|_health_check_thread", "线程"),
    "executor": (r"ThreadPoolExecutor|ProcessPoolExecutor|_executor", "执行器"),
    "cache": (r"_cache\s*[:=]|_l1_cache|_l2_cache|_stock_cache|self\._cache\s*=", "缓存"),
    "subscription": (r"subscribe|register_callback|add_listener", "事件订阅"),
    "file_handle": (r"open\(|file_handle|_file_path|with\s+open", "文件句柄"),
    "lock": (r"RLock|Lock\(\)|_lock\s*=", "锁"),
}

CORE_DIR = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services")


def classify_risk(candidate_name, file_path):
    """评估候选业务核心度"""
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    found_resources = []
    for key, (pattern, label) in RESOURCE_PATTERNS.items():
        if re.search(pattern, text):
            found_resources.append(f"{label}")
    # 业务核心判定: 多个资源 + 多个引用
    is_core = len(found_resources) >= 3
    return found_resources, is_core


def main():
    print("=== 32 候选 Service 业务核心度评估 ===\n")
    p0 = []  # 业务核心
    p1 = []  # 业务重要
    p2 = []  # 业务边缘
    for c in CANDIDATES:
        py = CORE_DIR / (snake_case(c) + ".py")
        if not py.exists():
            print(f"  [缺] {c}: 文件不存在")
            continue
        resources, is_core = classify_risk(c, py)
        if is_core:
            p0.append((c, resources))
        elif len(resources) >= 1:
            p1.append((c, resources))
        else:
            p2.append((c, resources))

    print(f"\n=== P0 业务核心 (>=3 资源) ===")
    for c, r in p0:
        print(f"  {c:40s} | {','.join(r)}")
    print(f"  P0 Total: {len(p0)}")

    print(f"\n=== P1 业务重要 (1-2 资源) ===")
    for c, r in p1:
        print(f"  {c:40s} | {','.join(r)}")
    print(f"  P1 Total: {len(p1)}")

    print(f"\n=== P2 业务边缘 (0 资源/纯逻辑) ===")
    for c, r in p2:
        print(f"  {c:40s} | {','.join(r) if r else '(纯业务逻辑)'}")
    print(f"  P2 Total: {len(p2)}")


def snake_case(name):
    """CamelCase to snake_case"""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


if __name__ == "__main__":
    main()
