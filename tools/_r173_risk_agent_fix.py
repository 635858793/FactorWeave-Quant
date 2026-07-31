#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R173 修复 risk_agent.py 中所有 f-string {str(e}) 错位问题 + 添加缺失闭合.

原错误: logger.error(f"text {str(e})")  错误  (e} 不是 })
正确: logger.error(f"text {str(e)}")
"""
import re
from pathlib import Path

fp = Path('d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/agents/risk_agent.py')
raw = fp.read_bytes()

# 1) 修复 {str(e}) 错误 -> {str(e)} 正确
old1 = b'{str(e})'
new1 = b'{str(e)}'
count1 = raw.count(old1)
raw = raw.replace(old1, new1)
print("[FIX1] 修复 " + str(count1) + " 处 e}) 错位为 e)}")

# 2) 修复 logger.X(f"..."\r  在 换行符前的引号缺失
# 模式: logger.X(f"text {var}")\r  (已是正确)
# 模式: logger.X(f"text {var})\r  (缺 ")  修复为 logger.X(f"text {var}")\r
# 模式: logger.X(f"text")\r  (已是正确)
# 模式: logger.X(f"text)\r  (缺 ")  修复为 logger.X(f"text")\r

pattern2 = re.compile(
    rb'(logger\.(?:error|warning|critical|debug|info)\(f"[^"\n]*?\{[^}]*?)\)\r',
)
def repl2(m):
    return m.group(1) + b'")\r'
new_raw, n2 = pattern2.subn(repl2, raw)
print(f"[FIX2] 修复 {n2} 处 f-string 闭合 \") 缺失")
raw = new_raw

# 写回
fp.write_bytes(raw)
print(f"[DONE] risk_agent.py 已修复")
