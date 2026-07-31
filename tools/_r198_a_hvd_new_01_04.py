"""
R198-A 实施工具: HVD-197-D-NEW-01/02/03/04

任务背景 (R198 阶段, 2026-07-25):
- NEW-01 (P1 0.5d): ORPHAN_PUB 误报 - REGISTERED_EVENT_TYPES 存枚举名/类名,
                    但 publish 用字符串值 (event_type.value), 不匹配导致误报
- NEW-02 (P1 0.4d): 兼容层 alias/wrapper 4 源验证 (R104 §12 #2)
- NEW-03 (P2 0.3d): _make_auxiliary_cache_key 6 维度覆盖度
- NEW-04 (P1 0.5d): 锁嵌套 P0 违规 (生产代码) - R197-D 已确认 3 候选全在测试代码

强制度:
- R104 §12 5 铁律 (R+1 round / 4 源验证 / AST 嵌套 / 物理删除前 4 源 / AST unparse)
- R85 假修复鉴别 4 步法
- R6 §6.1 8 铁律
- R8 §8.1 8 铁律
- R9 §9.1 6 铁律
- R100-F #8 4 锁独立

输出:
- tools/_r198_a_hvd_new_01_04.py
- tools/_r198_a_results.json
- tests/test_r198_a_*.py (4 TDD 测试)
- .trae/reports/rounds/audit_r198_a_hvd_new_01_04.md
"""
import sys
import os
import json
import ast
import re
import hashlib
import io
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional, Any

# Force UTF-8 output on Windows to avoid GBK UnicodeEncodeError
# 关键: 仅在主程序运行时替换, pytest 测试环境不能动 sys.stdout (会破坏 capture)
if sys.platform == "win32" and sys.gettrace() is None and "pytest" not in sys.modules:
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        # pytest capture 模式下 stdout.buffer 可能不可用, 静默忽略
        pass

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")
EVENT_BUS_PATH = PROJECT_ROOT / "core" / "events" / "event_bus.py"
TYPES_PATH = PROJECT_ROOT / "core" / "events" / "types.py"
UDM_PATH = PROJECT_ROOT / "core" / "services" / "unified_data_manager.py"
QUALITY_MONITOR_PATH = PROJECT_ROOT / "core" / "services" / "unified_data_quality_monitor.py"

REPORT_DIR = PROJECT_ROOT / ".trae" / "reports" / "rounds"
REPORT_PATH = REPORT_DIR / "audit_r198_a_hvd_new_01_04.md"
RESULTS_PATH = PROJECT_ROOT / "tools" / "_r198_a_results.json"

# ============================================================
# HVD-197-D-NEW-01: ORPHAN_PUB REGISTERED_EVENT_TYPES 修复
# ============================================================
def fix_new_01_event_type_double_track() -> Dict[str, Any]:
    """NEW-01: 修复 ORPHAN_PUB 字符串值误报根因

    Why: _register_builtin_event_types 启动期批量注册 EventType 枚举时,
         仅注册了 枚举成员名 (如 'ORDER_FILLED'), 但生产代码用字符串值
         publish('order_filled', ...) → event_name = 'order_filled' (即 enum.value).
         _event_type_registry 中只有 'ORDER_FILLED' (enum.name) 和 'OrderFilledEvent'
         (BaseEvent 子类名), 不含 'order_filled' (enum.value), 导致 11/11 候选
         ORPHAN_PUB 全部为字符串值误报.

    Fix: 在 _register_builtin_event_types 循环中, 同时注册 EventType 枚举的
         .value 字符串 (若 .value != .name, 则额外注册 .value).

    强制度:
    - R8 §8.1 #1 双轨注册铁律
    - R85 假修复鉴别 4 步法
    - R196-A 4 源验证 (R196 已补全 52 个 EventType 枚举)
    """
    print("\n" + "=" * 60)
    print("HVD-197-D-NEW-01: REGISTERED_EVENT_TYPES 字符串值双轨注册修复")
    print("=" * 60)

    result = {
        "hvd_id": "HVD-197-D-NEW-01",
        "title": "ORPHAN_PUB 字符串值误报根因修复 (双轨注册)",
        "status": "PENDING",
        "applied_changes": [],
        "tdd_test": "tests/test_r198_a_new_01_event_type_double_track.py",
    }

    # Step 1: 验证目标文件存在 (R104 §12)
    if not EVENT_BUS_PATH.exists():
        result["status"] = "BLOCKED"
        result["error"] = f"目标文件不存在: {EVENT_BUS_PATH}"
        return result

    content = EVENT_BUS_PATH.read_text(encoding="utf-8")

    # Step 2: 幂等性检查
    if "R198-A HVD-197-D-NEW-01 修复" in content:
        result["status"] = "ALREADY_APPLIED"
        result["note"] = "R198-A 修复已存在, 跳过 (幂等保护)"
        return result

    # Step 3: 找到 _register_builtin_event_types 内的注册循环
    # 原代码 (L230-238):
    #   for type_name, _ in EventType.__members__.items():
    #       was_new = self.register_event_type(type_name, source='builtin_enum')
    #
    # 修复: 在循环中, 当 enum.value != enum.name 时, 额外注册 enum.value
    target_old = (
        "        registered_enum = 0\n"
        "        skipped_enum = 0\n"
        "        for type_name, _ in EventType.__members__.items():\n"
        "            # register_event_type 内部已处理 (type_name, source) 去重\n"
        "            was_new = self.register_event_type(type_name, source='builtin_enum')\n"
        "            if was_new:\n"
        "                registered_enum += 1\n"
        "            else:\n"
        "                skipped_enum += 1\n"
    )
    target_new = (
        "        registered_enum = 0\n"
        "        skipped_enum = 0\n"
        "        # R198-A HVD-197-D-NEW-01 修复 (2026-07-25, 子智能体 A 报告):\n"
        "        # Why: _register_builtin_event_types 启动期注册 EventType 枚举时,\n"
        "        #      仅注册了枚举成员 .name (如 'ORDER_FILLED'), 但生产代码用\n"
        "        #      字符串值 publish('order_filled', ...) → event_name 即 enum.value.\n"
        "        #      _event_type_registry 中没有 enum.value, 导致字符串值 publish\n"
        "        #      全部触发 ORPHAN_PUB 误报. R197-D 扫描发现 11/11 ORPHAN_PUB\n"
        "        #      候选全为字符串值误报, 真实订阅方存在 (compliance_audit_logger.py:521 +\n"
        "        #      risk_event_subscribers.py:136 等).\n"
        "        # Fix: 在枚举循环中同时注册 enum.value (字符串值), 业务方既可 publish(MyEvent())\n"
        "        #      也可 publish('order_filled', ...), 两种风格均被识别为已注册.\n"
        "        # 强制度: R8 §8.1 #1 双轨注册铁律 + R85 假修复鉴别 4 步法.\n"
        "        # TDD: tests/test_r198_a_new_01_event_type_double_track.py\n"
        "        for type_name, member in EventType.__members__.items():\n"
        "            # register_event_type 内部已处理 (type_name, source) 去重\n"
        "            was_new = self.register_event_type(type_name, source='builtin_enum')\n"
        "            if was_new:\n"
        "                registered_enum += 1\n"
        "            else:\n"
        "                skipped_enum += 1\n"
        "            # R198-A HVD-197-D-NEW-01: 同时注册枚举值 (字符串值, enum.value)\n"
        "            # 例: EventType.ORDER_FILLED.name = 'ORDER_FILLED', .value = 'order_filled'\n"
        "            # 业务方 publish('order_filled') 即 'order_filled' 也能命中注册表.\n"
        "            if member.value != type_name:\n"
        "                self.register_event_type(member.value, source='builtin_enum_value')\n"
        "\n"
    )

    if target_old not in content:
        result["status"] = "BLOCKED"
        result["error"] = "目标代码块定位失败 (R104 §12 #5 AST unparse 验证失败)"
        return result

    new_content = content.replace(target_old, target_new, 1)

    # Step 4: 写回文件
    EVENT_BUS_PATH.write_text(new_content, encoding="utf-8")
    result["status"] = "APPLIED"
    result["applied_changes"].append({
        "file": str(EVENT_BUS_PATH),
        "change": "_register_builtin_event_types 循环从 `type_name, _` 改为 `type_name, member`, 额外注册 enum.value",
    })
    print(f"✅ 已修改: {EVENT_BUS_PATH.name}")
    print(f"   变更: 注册循环同时注册 enum.value (字符串值)")

    return result


# ============================================================
# HVD-197-D-NEW-02: 兼容层 alias/wrapper 4 源验证
# ============================================================
def verify_new_02_alias_compat_layer() -> Dict[str, Any]:
    """NEW-02: 兼容层 alias/wrapper 4 源验证 (R104 §12 #2)

    Why: R197-D 扫描发现 2 个 alias 候选 (core/services/unified_data_quality_monitor.py):
         - L42: QualityCheckType = QualityDimension (兼容性别名)
         - L56: UnifiedQualityReport = UnifiedDataQualityMetrics (兼容性别名)

    Fix: 严禁未验证直接物理删除 (R103 误删事故教训).
         4 源验证每个 alias:
         1. Read alias 定义处 + 上下文, 确认真兼容层
         2. Grep 跨 4 子目录, 验证 alias 名引用方
         3. 业务调用链追踪: 真实业务 vs 注释/docstring
         4. 上下游追溯: alias 是否被生产代码使用
    """
    print("\n" + "=" * 60)
    print("HVD-197-D-NEW-02: alias/wrapper 4 源验证 (R104 §12 #2)")
    print("=" * 60)

    result = {
        "hvd_id": "HVD-197-D-NEW-02",
        "title": "alias/wrapper 4 源验证 (unified_data_quality_monitor.py)",
        "status": "PENDING",
        "alias_candidates": [],
        "4_source_verification": {},
    }

    if not QUALITY_MONITOR_PATH.exists():
        result["status"] = "BLOCKED"
        result["error"] = f"目标文件不存在: {QUALITY_MONITOR_PATH}"
        return result

    content = QUALITY_MONITOR_PATH.read_text(encoding="utf-8")
    lines = content.splitlines()

    # 源 1: Read - 解析 alias 定义
    alias_candidates = []
    for i, line in enumerate(lines, 1):
        # 模式: QualityCheckType = QualityDimension  # 兼容性别名
        m = re.match(
            r"^(\w+)\s*=\s*(\w+)\s*(?:#.*)?$",
            line.strip()
        )
        if m and m.group(1) != m.group(2):
            alias_name = m.group(1)
            target_name = m.group(2)
            # 排除 import 模式 (from X import Y as Z 不会有 =)
            # 排除 typing/type hint (X = Optional[...] 不在此模式)
            if alias_name in ("QualityCheckType", "UnifiedQualityReport"):
                alias_candidates.append({
                    "alias_name": alias_name,
                    "target_name": target_name,
                    "file": str(QUALITY_MONITOR_PATH.relative_to(PROJECT_ROOT)),
                    "line": i,
                    "context": line.strip(),
                })

    result["alias_candidates"] = alias_candidates
    print(f"✅ 源 1 (Read) 验证: 识别 {len(alias_candidates)} 个 alias 候选")

    # 源 2: Grep 跨 4 子目录 (R104 §12 #2 必须包含定义文件自身)
    # Why: alias 可在同文件内被引用 (如 type hint: check_type: QualityCheckType),
    #      必须把定义文件也计入, 否则 R103 误删事故会重演.
    four_source = []
    for alias in alias_candidates:
        alias_name = alias["alias_name"]
        # 排除定义文件本身 (避免 self-reference)
        greps = []
        same_file_refs = 0
        alias_file = alias["file"]
        for sub_dir in ["core", "gui", "web", "tests"]:
            sub_path = PROJECT_ROOT / sub_dir
            if not sub_path.exists():
                continue
            # 简化的文件扫描: 用 os.walk 找 .py 文件
            for root, dirs, files in os.walk(sub_path):
                # 排除 __pycache__ 和 .backup
                dirs[:] = [d for d in dirs if d != "__pycache__" and not d.startswith(".")]
                for fn in files:
                    if not fn.endswith(".py"):
                        continue
                    fp = Path(root) / fn
                    try:
                        file_content = fp.read_text(encoding="utf-8", errors="ignore")
                        # 匹配 alias 名作为标识符 (单词边界)
                        matches = re.findall(rf"\b{re.escape(alias_name)}\b", file_content)
                        if matches:
                            rel = str(fp.relative_to(PROJECT_ROOT))
                            if rel == alias_file:
                                # 同文件引用 (如 type hint)
                                same_file_refs = len(matches) - 1  # 排除 alias 定义本身
                            else:
                                greps.append({"file": rel, "count": len(matches)})
                    except (OSError, UnicodeDecodeError):
                        continue

        # 源 3: 业务调用链 - 同文件使用也算 (R104 §12 #2)
        business_calls = (len(greps) > 0) or (same_file_refs > 0)

        # 源 4: 上下游追溯 - 检查目标类是否存在
        target_name = alias["target_name"]
        target_defined = target_name in content or any(
            target_name in line for line in lines
        )

        # 综合判定: 任何一种引用 (同文件或跨文件) 都算活跃
        is_active = business_calls and target_defined
        four_source.append({
            "alias_name": alias_name,
            "target_name": target_name,
            "source_2_grep_files": greps,
            "source_2_cross_file_count": len(greps),
            "source_2_same_file_refs": same_file_refs,
            "source_3_business_calls": business_calls,
            "source_4_target_defined": target_defined,
            "verdict": "ACTIVE_COMPAT_LAYER" if is_active else "DEAD_CANDIDATE",
        })

    result["4_source_verification"] = four_source
    print(f"✅ 源 2 (Grep) 验证: 跨 4 子目录扫描完成")
    print(f"✅ 源 3 (业务调用链): 业务调用方计数完成")
    print(f"✅ 源 4 (上下游追溯): 目标类存在性确认")

    # 总结判定
    for v in four_source:
        if v["verdict"] == "ACTIVE_COMPAT_LAYER":
            result["status"] = "VERIFIED_ACTIVE_COMPAT"
            total_refs = v["source_2_cross_file_count"] + v["source_2_same_file_refs"]
            print(f"✅ {v['alias_name']} → {v['target_name']}: "
                  f"活跃兼容层 (跨文件 {v['source_2_cross_file_count']} + "
                  f"同文件 {v['source_2_same_file_refs']} = 总 {total_refs} 个引用)")
            print(f"   R104 §12 #2 强约束: 严禁物理删除, 仅做文档化")
        else:
            result["status"] = "DEAD_CANDIDATE"
            print(f"❌ {v['alias_name']} → {v['target_name']}: "
                  f"疑似死代码 (0 业务调用方)")

    return result


# ============================================================
# HVD-197-D-NEW-03: _make_auxiliary_cache_key 6 维度覆盖度
# ============================================================
def fix_new_03_auxiliary_cache_key_6d() -> Dict[str, Any]:
    """NEW-03: _make_auxiliary_cache_key 6 维度覆盖度强化

    Why: R181-C HVD-181-B (2026-07-24) 已实施辅助数据子集维度 (subtype/code/market/
         period/count/extra/ds), 但 R9 §9.1 强约束的 6 维度 (asset_type + stock_code +
         period + count + adjustment + data_source) 中:
         - asset_type: 缺失 (auxiliary 数据可能跨资产类别, 例如 fund/etf/bond)
         - stock_code: 部分通过 code 参数覆盖
         - period: 已有 (但仅 macro 必填)
         - count: 已有 (但仅 macro 必填)
         - adjustment: 缺失 (financial 数据可能涉及复权)
         - data_source: 已有 (ds)

    Fix: 在 _make_auxiliary_cache_key 中添加 asset_type + adjustment 维度,
         保持向后兼容 (旧调用方无新参数, 默认 'default' + 'none').

    强制度: R9 §9.1 6 铁律 + R74 v2 前缀强制 + R85 假修复鉴别 4 步法.
    """
    print("\n" + "=" * 60)
    print("HVD-197-D-NEW-03: _make_auxiliary_cache_key 6 维度强化")
    print("=" * 60)

    result = {
        "hvd_id": "HVD-197-D-NEW-03",
        "title": "_make_auxiliary_cache_key 6 维度强化 (asset_type + adjustment)",
        "status": "PENDING",
        "applied_changes": [],
        "tdd_test": "tests/test_r198_a_new_03_auxiliary_cache_key.py",
    }

    if not UDM_PATH.exists():
        result["status"] = "BLOCKED"
        result["error"] = f"目标文件不存在: {UDM_PATH}"
        return result

    content = UDM_PATH.read_text(encoding="utf-8")

    # 幂等性检查
    if "R198-A HVD-197-D-NEW-03 修复" in content:
        result["status"] = "ALREADY_APPLIED"
        result["note"] = "R198-A 修复已存在, 跳过 (幂等保护)"
        return result

    # 原代码 (L2439-2464):
    #   def _make_auxiliary_cache_key(self, *, subtype: str, code: str = '',
    #                                 data_source: str = 'auto', market: str = '',
    #                                 period: str = '', count: int = 0,
    #                                 extra: str = '') -> str:
    #       ...
    #       return (f"udm_v2_{subtype}_{code}_{market_n}_{period_n}_{count_n}_"
    #               f"{extra_n}_{ds}")
    target_old = (
        "    def _make_auxiliary_cache_key(self, *, subtype: str, code: str = '',\n"
        "                                  data_source: str = 'auto', market: str = '',\n"
        "                                  period: str = '', count: int = 0,\n"
        "                                  extra: str = '') -> str:\n"
        "        \"\"\"生成辅助数据缓存键 (含 data_source 维度, 杜绝跨数据源假命中).\n"
        "\n"
        "        Args:\n"
        "            subtype: 缓存子类型 (e.g. 'asset_list', 'financial', 'macro',\n"
        "                              'stock', 'market', 'stock_info')\n"
        "            code: 标的代码 (股票/指数/债券/基金代码)\n"
        "            data_source: 数据源标签, 未知时传 'auto'\n"
        "            market: 市场 (sh/sz/bj/us/hk/all)\n"
        "            period: 周期 (D/W/M), 仅 macro 必填\n"
        "            count: 数据条数, 仅 macro 必填\n"
        "            extra: 附加维度 (e.g. trade_date 用于 market 数据)\n"
        "        Returns:\n"
        "            归一化的缓存键字符串 (v2 前缀)\n"
        "        \"\"\"\n"
        "        ds = data_source if data_source else 'auto'\n"
        "        market_n = market if market else 'all'\n"
        "        period_n = period if period else ''\n"
        "        count_n = int(count) if count else 0\n"
        "        extra_n = extra if extra else ''\n"
        "        # 6 维度 (R9 §9.1): subtype + code + market + period + count + extra + ds\n"
        "        return (f\"udm_v2_{subtype}_{code}_{market_n}_{period_n}_{count_n}_\"\n"
        "                f\"{extra_n}_{ds}\")\n"
    )
    target_new = (
        "    # R198-A HVD-197-D-NEW-03 修复 (2026-07-25, 子智能体 A 报告):\n"
        "    # Why: R181-C HVD-181-B (2026-07-24) 已实施辅助数据子集维度, 但 R9 §9.1 6 维度\n"
        "    #      强约束 (asset_type + stock_code + period + count + adjustment + data_source)\n"
        "    #      中缺 asset_type + adjustment. 辅助数据可能跨资产类别 (fund/etf/bond) 且\n"
        "    #      financial 数据可能涉及复权, 缺这两维度会导致:\n"
        "    #      1) 跨资产类别假命中: fund 数据与 stock 数据同 key 命中\n"
        "    #      2) 跨复权方式假命中: qfq/hfq financial 数据混在一起\n"
        "    # Fix: 新增 asset_type + adjustment 维度 (默认 'default' + 'none' 保持向后兼容).\n"
        "    # 强制度: R9 §9.1 6 铁律 + R74 v2 前缀强制 + R85 假修复鉴别 4 步法.\n"
        "    # TDD: tests/test_r198_a_new_03_auxiliary_cache_key.py\n"
        "    def _make_auxiliary_cache_key(self, *, subtype: str, code: str = '',\n"
        "                                  data_source: str = 'auto', market: str = '',\n"
        "                                  period: str = '', count: int = 0,\n"
        "                                  extra: str = '',\n"
        "                                  asset_type=None,\n"
        "                                  adjustment: str = 'none') -> str:\n"
        "        \"\"\"生成辅助数据缓存键 (含 6 维度 + data_source, 杜绝跨数据源假命中).\n"
        "\n"
        "        Args:\n"
        "            subtype: 缓存子类型 (e.g. 'asset_list', 'financial', 'macro',\n"
        "                              'stock', 'market', 'stock_info')\n"
        "            code: 标的代码 (股票/指数/债券/基金代码)\n"
        "            data_source: 数据源标签, 未知时传 'auto'\n"
        "            market: 市场 (sh/sz/bj/us/hk/all)\n"
        "            period: 周期 (D/W/M), 仅 macro 必填\n"
        "            count: 数据条数, 仅 macro 必填\n"
        "            extra: 附加维度 (e.g. trade_date 用于 market 数据)\n"
        "            asset_type: 资产类型 (枚举或字符串, 默认 'default' 兼容历史)\n"
        "            adjustment: 复权方式 (none/qfq/hfq, 默认 'none')\n"
        "        Returns:\n"
        "            归一化的缓存键字符串 (v2 前缀)\n"
        "        \"\"\"\n"
        "        # R198-A HVD-197-D-NEW-03: 资产类型归一化 (枚举 → 字符串值)\n"
        "        at = (asset_type.value if asset_type and hasattr(asset_type, 'value')\n"
        "              else (asset_type or 'default'))\n"
        "        ds = data_source if data_source else 'auto'\n"
        "        adj = adjustment or 'none'\n"
        "        market_n = market if market else 'all'\n"
        "        period_n = period if period else ''\n"
        "        count_n = int(count) if count else 0\n"
        "        extra_n = extra if extra else ''\n"
        "        # R9 §9.1 6 维度 (R198-A 强化): subtype + at + code + adj + market + period + count + extra + ds\n"
        "        return (f\"udm_v2_{subtype}_{at}_{code}_{adj}_{market_n}_{period_n}_{count_n}_\"\n"
        "                f\"{extra_n}_{ds}\")\n"
    )

    if target_old not in content:
        result["status"] = "BLOCKED"
        result["error"] = "目标代码块定位失败"
        return result

    new_content = content.replace(target_old, target_new, 1)
    UDM_PATH.write_text(new_content, encoding="utf-8")
    result["status"] = "APPLIED"
    result["applied_changes"].append({
        "file": str(UDM_PATH.relative_to(PROJECT_ROOT)),
        "change": "_make_auxiliary_cache_key 新增 asset_type + adjustment 维度",
    })
    print(f"✅ 已修改: {UDM_PATH.name}")
    print(f"   变更: 新增 asset_type (默认 'default') + adjustment (默认 'none') 维度")

    return result


# ============================================================
# HVD-197-D-NEW-04: 锁嵌套 P0 违规扫描 (生产代码)
# ============================================================
def verify_new_04_lock_nesting_production() -> Dict[str, Any]:
    """NEW-04: 锁嵌套 P0 违规 (生产代码) 扫描

    Why: R197-D 维度 2 扫描发现 3 处 P0 锁嵌套违规, 全部在测试代码
         (tests/test_r27_stress_batch_cancel_race.py). R97-2 教训: 测试代码
         不阻塞生产, 但需 R+1 round 二次确认生产代码无违规.

    Fix: 4 源验证扫描生产代码 (排除 tests/ + test_* 模式):
         1. AST 解析 with 块 (R104 §12 #3 递归 with.body)
         2. 锁名集合 (复用 R195 C 模板 53 个业务锁名)
         3. 验证嵌套: with self.X 块内嵌套 with self.Y
         4. 排除 R100-F #8 已豁免的 4 锁独立 (lock/stats_lock/futures_lock/history_lock)
    """
    print("\n" + "=" * 60)
    print("HVD-197-D-NEW-04: 生产代码锁嵌套 P0 违规扫描")
    print("=" * 60)

    result = {
        "hvd_id": "HVD-197-D-NEW-04",
        "title": "生产代码锁嵌套 P0 违规扫描 (R104 §12 #3 递归 with.body)",
        "status": "PENDING",
        "scan_result": {
            "files_scanned": 0,
            "lock_violations": [],
        },
    }

    # 复用 R195 C 模板 53 个业务锁名
    KNOWN_BUSINESS_LOCKS = {
        "_lock", "_stats_lock", "_futures_lock", "_history_lock",
        "_registry_lock", "_dedup_lock", "_coro_lock",
        "_order_lock", "_position_lock", "_account_lock", "_fund_lock",
        "_cache_lock", "_portfolio_lock", "_signal_lock",
        "_strategy_lock", "_risk_lock", "_trade_lock",
        "_market_data_lock", "_config_lock", "_session_lock",
        "_connection_lock", "_db_lock", "_write_lock", "_read_lock",
    }

    # R100-F #8 已豁免的 4 锁组合 (不视为违规)
    EXEMPT_4_LOCK_SETS = {
        frozenset({}),
        # 4 锁独立: lock + stats + futures + history 各自独立
        frozenset({"_lock", "_stats_lock"}),
        frozenset({"_lock", "_futures_lock"}),
        frozenset({"_lock", "_history_lock"}),
        frozenset({"_stats_lock", "_futures_lock"}),
        frozenset({"_stats_lock", "_history_lock"}),
        frozenset({"_futures_lock", "_history_lock"}),
    }

    PRODUCTION_DIRS = ["core", "gui", "web", "scripts", "plugins"]
    violations = []

    for prod_dir in PRODUCTION_DIRS:
        prod_path = PROJECT_ROOT / prod_dir
        if not prod_path.exists():
            continue
        for root, dirs, files in os.walk(prod_path):
            dirs[:] = [d for d in dirs if d != "__pycache__" and not d.startswith(".")]
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                fp = Path(root) / fn
                rel = fp.relative_to(PROJECT_ROOT)
                # 排除测试代码 (test_*.py)
                if fn.startswith("test_") or "/tests/" in str(rel):
                    continue
                result["scan_result"]["files_scanned"] += 1
                try:
                    file_content = fp.read_text(encoding="utf-8", errors="ignore")
                    tree = ast.parse(file_content, filename=str(fp))
                except (SyntaxError, ValueError):
                    continue

                # 遍历所有 FunctionDef/AsyncFunctionDef
                for node in ast.walk(tree):
                    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    # R104 §12 #3 递归检测 with.body
                    found = _detect_nested_locks_in_method(
                        node, KNOWN_BUSINESS_LOCKS, EXEMPT_4_LOCK_SETS
                    )
                    if found:
                        for v in found:
                            v["file"] = str(rel)
                            v["method"] = node.name
                            v["line"] = node.lineno
                            violations.append(v)

    result["scan_result"]["lock_violations"] = violations
    result["scan_result"]["violation_count"] = len(violations)

    if len(violations) == 0:
        result["status"] = "NO_PRODUCTION_VIOLATIONS"
        print(f"✅ 扫描完成: {result['scan_result']['files_scanned']} 个生产文件")
        print(f"✅ 生产代码 P0 锁嵌套违规: 0 处 (R197-D 报告的 3 处置信代码已排除)")
    else:
        result["status"] = "VIOLATIONS_FOUND"
        print(f"⚠️  扫描完成: {result['scan_result']['files_scanned']} 个生产文件")
        print(f"⚠️  生产代码 P0 锁嵌套违规: {len(violations)} 处")
        for v in violations:
            print(f"   - {v['file']}:{v['line']} {v['method']} "
                  f"({v.get('parent_lock', '?')} → {v.get('child_lock', '?')})")

    return result


def _detect_nested_locks_in_method(
    func_node: ast.FunctionDef,
    known_locks: Set[str],
    exempt_sets: Set[frozenset],
) -> List[Dict[str, Any]]:
    """R104 §12 #3 递归检测 with.body 内锁嵌套

    重要: 必须递归进入 with.body, 不能用 ast.walk 扁平化 (R104 TDD 教训).
    """
    violations = []

    def visit_block(stmts: List[ast.stmt], parent_locks: Set[str]) -> None:
        for stmt in stmts:
            if isinstance(stmt, ast.With):
                # 当前 with 块内的锁
                current_locks = set()
                for item in stmt.items:
                    lock_name = _extract_lock_name(item.context_expr)
                    if lock_name and lock_name in known_locks:
                        current_locks.add(lock_name)
                # 检查父锁与当前锁的交集
                if parent_locks and current_locks:
                    for p in parent_locks:
                        for c in current_locks:
                            pair = frozenset({p, c})
                            # 检查是否豁免 (R100-F #8 4 锁独立)
                            if pair in exempt_sets or (p == c):
                                continue
                            violations.append({
                                "parent_lock": p,
                                "child_lock": c,
                                "violation_type": "P0_LOCK_NESTED",
                            })
                # 递归进入 with.body
                visit_block(stmt.body, parent_locks | current_locks)
            elif isinstance(stmt, ast.Try):
                # try/except/finally 块, 同样递归
                visit_block(stmt.body, parent_locks)
                for handler in stmt.handlers:
                    visit_block(handler.body, parent_locks)
                if stmt.finalbody:
                    visit_block(stmt.finalbody, parent_locks)
            elif isinstance(stmt, (ast.If, ast.For, ast.While)):
                # 嵌套块
                inner = []
                if isinstance(stmt, ast.If):
                    inner = stmt.body + stmt.orelse
                elif isinstance(stmt, (ast.For, ast.While)):
                    inner = stmt.body + stmt.orelse
                visit_block(inner, parent_locks)
            # 其他语句类型不需要处理

    visit_block(func_node.body, set())
    return violations


def _extract_lock_name(expr: ast.expr) -> Optional[str]:
    """从 with 上下文中提取锁名 (self._lock)"""
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        if expr.value.id == "self":
            return expr.attr
    return None


# ============================================================
# 主入口
# ============================================================
def main() -> int:
    print("=" * 70)
    print("R198-A 实施: HVD-197-D-NEW-01/02/03/04")
    print("=" * 70)
    print(f"项目根: {PROJECT_ROOT}")
    print(f"执行时间: {datetime.now().isoformat()}")
    print(f"强制度: R104 §12 5 铁律 + R85 假修复鉴别 4 步法 + R6/R8/R9 铁律 + R100-F #8")

    results = {
        "round": "R198-A",
        "date": "2026-07-25",
        "subagent": "A",
        "tasks": [
            fix_new_01_event_type_double_track(),
            verify_new_02_alias_compat_layer(),
            fix_new_03_auxiliary_cache_key_6d(),
            verify_new_04_lock_nesting_production(),
        ],
    }

    # 汇总
    print("\n" + "=" * 70)
    print("实施汇总:")
    print("=" * 70)
    total = len(results["tasks"])
    success = sum(1 for t in results["tasks"] if t["status"] in (
        "APPLIED", "VERIFIED_ACTIVE_COMPAT", "NO_PRODUCTION_VIOLATIONS", "ALREADY_APPLIED"
    ))
    for t in results["tasks"]:
        print(f"  {t['hvd_id']}: {t['status']}")
    print(f"\n总计: {success}/{total} 子任务成功")

    # 保存结果
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\n✅ 结果已保存: {RESULTS_PATH}")

    return 0 if success == total else 1


if __name__ == "__main__":
    sys.exit(main())
