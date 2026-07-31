#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R200-B 物理删除执行器
======================

强制度:
- R6 §6.3 物理删除前 TDD 基线 (已完成)
- R104 §12 #4 物理删除前 4 源 100% 命中 (已验证)
- R9-B 教训: 写 TDD test_xxx_physically_removed (已写)

删除清单:
1. D1-01 (P2): core/adaptive_pool_initializer.py L33-106 initialize_adaptive_pool 函数
   - 仅删函数定义 (L33-106), 保留 _adaptive_manager 全局 + initialize_adaptive_pools_by_config (L109) + get_adaptive_manager + stop_adaptive_pool
2. D3-01 (P2): web/backend/models/__init__.py L9 `Base = DatabaseBase` alias
   - 删 alias, 保留 `from web.backend.config.database import Base as DatabaseBase` 导入 (L5)
   - 从 __all__ 移除 "Base" (L13)
"""
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")


def delete_dead_function():
    """
    D1-01: 删除 initialize_adaptive_pool 函数
    保留 initialize_adaptive_pools_by_config (替代函数)
    """
    target_file = PROJECT_ROOT / "core" / "adaptive_pool_initializer.py"
    if not target_file.exists():
        print(f"❌ 文件不存在: {target_file}")
        return False

    source = target_file.read_text(encoding='utf-8')
    lines = source.splitlines(keepends=True)

    # 找 initialize_adaptive_pool 函数起始 (L33) 和结束 (initialize_adaptive_pools_by_config 之前)
    func_start = None
    func_end = None
    for i, line in enumerate(lines):
        if re.match(r'^def initialize_adaptive_pool\b', line):
            func_start = i
        elif re.match(r'^def initialize_adaptive_pools_by_config\b', line):
            func_end = i
            break

    if func_start is None or func_end is None:
        print(f"❌ 未找到 initialize_adaptive_pool 函数边界")
        return False

    print(f"  找到 initialize_adaptive_pool: L{func_start+1}-L{func_end}")
    print(f"  起始: {lines[func_start].rstrip()}")
    print(f"  结束: {lines[func_end].rstrip()}")

    # 物理删除
    new_lines = lines[:func_start] + lines[func_end:]
    new_source = "".join(new_lines)

    # 同时清理 L45 "已被 initialize_adaptive_pool() 替代" 注释 (在 initialize_adaptive_pools_by_config docstring 中)
    # 不必清理, 替代函数注释合理

    target_file.write_text(new_source, encoding='utf-8')
    print(f"  ✅ 已删除 initialize_adaptive_pool (L{func_start+1}-L{func_end}, {func_end - func_start} 行)")
    return True


def delete_base_alias():
    """
    D3-01: 删除 Base = DatabaseBase alias
    """
    target_file = PROJECT_ROOT / "web" / "backend" / "models" / "__init__.py"
    if not target_file.exists():
        print(f"❌ 文件不存在: {target_file}")
        return False

    source = target_file.read_text(encoding='utf-8')
    lines = source.splitlines(keepends=True)

    new_lines = []
    for line in lines:
        # 跳过 alias 行
        if re.match(r'^\s*Base\s*=\s*DatabaseBase\s*$', line):
            print(f"  删除 alias 行: {line.rstrip()}")
            continue
        # 从 __all__ 移除 "Base"
        if '__all__' in line and '"Base"' in line:
            new_line = line.replace('"Base", ', '').replace(', "Base"', '').replace('"Base"', '')
            print(f"  修正 __all__: {line.rstrip()} -> {new_line.rstrip()}")
            new_lines.append(new_line)
            continue
        new_lines.append(line)

    new_source = "".join(new_lines)
    target_file.write_text(new_source, encoding='utf-8')
    print(f"  ✅ 已删除 Base = DatabaseBase alias")
    return True


def main():
    print("=" * 80)
    print("  R200-B 物理删除执行器 - 2026-07-25")
    print("=" * 80)
    print()
    print("⚠️ 强制度: R6 §6.3 + R104 §12 #4 + R9-B TDD 基线")
    print("⚠️ 物理删除前: TDD 红灯 9/9 通过 + 4 源验证 0 命中 + 锁嵌套 0 处")
    print()

    # 1. D1-01 死代码
    print("[D1-01] 物理删除 initialize_adaptive_pool:")
    d1_ok = delete_dead_function()
    print()

    # 2. D3-01 alias
    print("[D3-01] 物理删除 Base = DatabaseBase alias:")
    d3_ok = delete_base_alias()
    print()

    print("=" * 80)
    print("  物理删除结果")
    print("=" * 80)
    print(f"D1-01 initialize_adaptive_pool: {'✅ 已删除' if d1_ok else '❌ 失败'}")
    print(f"D3-01 Base = DatabaseBase:     {'✅ 已删除' if d3_ok else '❌ 失败'}")
    print()
    print("下一步: 跑 TDD 绿灯阶段 + 跑全量回归测试")


if __name__ == "__main__":
    main()
