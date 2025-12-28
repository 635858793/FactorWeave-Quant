# 策略管理器主题管理器修复记录

## 问题
2025-12-27 21:41:15 报错：`name 'theme_manager' is not defined`

## 根本原因
之前修复时删除了本地的 `ThemeManager` 类和 `theme_manager` 实例（340行代码），但文件中9处直接使用 `theme_manager.xxx()` 调用：
- 行1559, 1701, 1710, 1712, 1748, 1844, 1972, 2006, 3735

## 解决方案
在文件末尾恢复全局 `theme_manager` 实例：
```python
# 全局主题管理器实例（用于向后兼容）
theme_manager = get_theme_manager()
```

## 文件位置
`gui/dialogs/enhanced_strategy_manager_dialog.py` 第4479-4481行

## 验证
✅ 语法检查通过
