#!/usr/bin/env python3
"""直接修复 sentiment_agent.py 剩余违规 - Python 字符串替换"""
from pathlib import Path

fp = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/agents/sentiment_agent.py")
content = fp.read_text(encoding="utf-8")

# 修复 L256: 舆情分析失败
old1 = 'logger.error(f"舆情分析失败: {stock_code}, 错误: {e}")'
new1 = 'logger.error(f"舆情分析失败: {stock_code}, 错误: {e}", exc_info=True)'
if old1 in content:
    content = content.replace(old1, new1, 1)
    print(f"[OK] L256 舆情分析失败已修复")
else:
    print(f"[WARN] L256 字符串未找到")

# 修复 L487: 论坛情绪代理获取失败
old2 = 'logger.warning(f"论坛情绪代理获取失败 {stock_code}: {e}")'
new2 = 'logger.warning(f"论坛情绪代理获取失败 {stock_code}: {e}", exc_info=True)'
if old2 in content:
    content = content.replace(old2, new2, 1)
    print(f"[OK] L487 论坛情绪代理获取失败已修复")
else:
    print(f"[WARN] L487 字符串未找到")

fp.write_text(content, encoding="utf-8")
print("Done")
