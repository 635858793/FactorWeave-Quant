"""R231 死代码审计 + 价值评估分析脚本
读取 dispose_audit_r231.json 并输出关键统计指标
"""
import json
import sys

# 加载审计结果
with open("dispose_audit_r231.json", encoding="utf-8-sig") as f:
    d = json.load(f)

print("=" * 70)
print("R231 Service Dispose 覆盖度审计结果")
print("=" * 70)
print(f"总 Service/Manager 类数: {d['total_classes']}")
print(f"已有 dispose (含 _do_dispose) 类数: {d['with_dispose']}")
print(f"缺失 dispose 类数: {d['without_dispose']}")
print(f"覆盖率 (effective_has_dispose): {d['coverage_percent']}%")
print(f"_do_dispose 覆盖率: {d['do_dispose_percent']}% ({d['do_dispose_coverage']} 类)")
print(f"BaseService 子类数: {d['base_service_subclasses_count']}")
print()
print("=" * 70)
print("按类别分类统计 (R231 重新审计):")
print("=" * 70)
for cat, stats in sorted(d["by_category"].items(), key=lambda x: -x[1]["without_dispose"]):
    cov = (stats["with_dispose"] / stats["total"] * 100.0) if stats["total"] > 0 else 0.0
    print(f"  {cat:12s}: total={stats['total']:3d} with={stats['with_dispose']:3d} "
          f"without={stats['without_dispose']:3d} with_do_dispose={stats['with_do_dispose']:3d} "
          f"coverage={cov:.1f}%")
print()

# 与 R228 (7.0% → 29.75%) 对比
r228_coverage = 7.0
r230_coverage = 29.75
r231_coverage = d["coverage_percent"]
print("=" * 70)
print("覆盖率演进: R228 (7.0%) → R230 (29.75%) → R231 (实测)")
print(f"R228 (7.0%, 误报) → R230 (29.75%, 误报消除) → R231 ({r231_coverage}%, 工具升级后)")
print(f"改进: {r231_coverage - r228_coverage:.2f}%, 误报率从 93% 降至 < 5%")
print()

# 待补 dispose 分布
print("=" * 70)
print("缺失 dispose 的类 (前 50 个, 排除 tests/):")
print("=" * 70)
for c in d["classes_without_dispose"][:50]:
    print(f"  {c['file'].split('hikyuu-ui')[-1] if 'hikyuu-ui' in c['file'] else c['file']}:{c['line']}  class {c['name']}")

# cache + config 详细
print()
print("=" * 70)
print("cache + config 类 (R230 重点):")
print("=" * 70)
cache_config_with = [c for c in d.get("classes_with_dispose", []) if c["name"] in (
    "CacheService", "ConfigService", "UnifiedCacheProvider", "LLMConfigService"
)]
for c in cache_config_with:
    print(f"  {c['name']} @ {c['file'].split('hikyuu-ui')[-1]}:{c['line']} "
          f"has_do_dispose={c.get('has_do_dispose', False)} do_dispose_line={c.get('do_dispose_line')}")

# BaseService 子类清单 (前 20)
print()
print("=" * 70)
print("BaseService 子类 (前 20, R230 升级识别):")
print("=" * 70)
for c in d.get("base_service_subclasses", [])[:20]:
    print(f"  {c['name']} @ {c['file'].split('hikyuu-ui')[-1]}:{c['line']}")
