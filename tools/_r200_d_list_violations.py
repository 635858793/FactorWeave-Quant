"""R200-D 违规清单生成器 (提取 f-string/str_concat/format_call 违规)"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from _r200_d_cache_audit import CacheKeyAuditor, PROJECT_ROOT


def main():
    auditor = CacheKeyAuditor()
    summary = auditor.scan_project()
    violations = auditor.report_violations(summary)

    # 按文件分组
    by_file = {}
    for v in violations:
        f = v["file"]
        if f not in by_file:
            by_file[f] = []
        by_file[f].append(v)

    # 统计
    print("=" * 80)
    print("R200-D 违规清单 (详细)")
    print("=" * 80)
    print(f"总违规: {len(violations)} 处")
    print(f"涉及文件: {len(by_file)} 个")
    print()

    # 修复可行性分类
    high_fix = []  # 高修复价值 (有可识别的维度)
    low_fix = []   # 低修复价值 (静态维度, 不需要工厂)

    for f, vlist in by_file.items():
        for v in vlist:
            expr = v["key_expr"]
            # 评分: 含 {} 占位符 → 高价值
            if "{" in expr and "}" in expr:
                high_fix.append(v)
            else:
                low_fix.append(v)

    print(f"高修复价值 (有占位符): {len(high_fix)} 处")
    print(f"低修复价值 (静态): {len(low_fix)} 处")
    print()

    # 按文件输出
    for f, vlist in sorted(by_file.items()):
        print(f"\n{f}: {len(vlist)} 处")
        for v in vlist:
            print(f"  L{v['line']} [{v['op_type']:>10}] {v['key_expr'][:80]}")

    # 保存
    output_path = PROJECT_ROOT / "tools" / "_r200_d_violations.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_violations": len(violations),
            "high_fix_count": len(high_fix),
            "low_fix_count": len(low_fix),
            "by_file": by_file,
            "violations": violations,
        }, f, indent=2, ensure_ascii=False)
    print(f"\n\n违规清单已保存到: {output_path}")


if __name__ == "__main__":
    main()
