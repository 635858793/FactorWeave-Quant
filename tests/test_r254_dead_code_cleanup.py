#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R254 回归测试: 统一数据管理器死代码清理 + right_panel 行业 tab 条件跳过

覆盖 (R254 交叉验证, 全项目 Grep 引用数实证):
- T1: unified_data_manager.py 不含 _generate_mock_fund_flow_data /
      get_asset_list_legacy_tet / _create_fallback_data_source_DEPRECATED 定义
      (三者均为 0 调用者的死方法, 源码级断言)
- T2: unified_data_manager.py 不含 _get_fund_flow_legacy 定义与其唯一调用点
      (降级冗余: 返回空结构与 get_fund_flow 开头初始化空结构逐字段相同, 源码级断言)
- T3: right_panel.py 行业 tab 创建改为条件跳过 (if not PROFESSIONAL_TABS_AVAILABLE),
      且 "AI选股" 不再残留于 tabs_to_remove (源码级断言)
- T4: get_fund_flow 降级路径 (TET 不可用) 返回空结构且不抛异常 (行为断言,
      轻量构造 UnifiedDataManager 绕过重型 __init__, 与 test_r251 一致)
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_UNIFIED_SRC = os.path.join(ROOT, 'core', 'services', 'unified_data_manager.py')
_RIGHT_PANEL_SRC = os.path.join(ROOT, 'core', 'ui', 'panels', 'right_panel.py')


class TestUnifiedDataManagerDeadCodeRemoved(unittest.TestCase):
    """T1/T2: unified_data_manager.py 死代码已清理 (源码级断言)"""

    @classmethod
    def setUpClass(cls):
        with open(_UNIFIED_SRC, encoding='utf-8') as f:
            cls.src = f.read()

    def test_no_mock_fund_flow_data(self):
        """T1: _generate_mock_fund_flow_data (0 调用者, 含误导性 mock 命名) 已删除"""
        self.assertNotIn('def _generate_mock_fund_flow_data(', self.src,
                         '_generate_mock_fund_flow_data 死代码未清理')

    def test_no_asset_list_legacy_tet(self):
        """T1: get_asset_list_legacy_tet (0 调用者) 已删除"""
        self.assertNotIn('def get_asset_list_legacy_tet(', self.src,
                         'get_asset_list_legacy_tet 死代码未清理')

    def test_no_fallback_data_source_deprecated(self):
        """T1: _create_fallback_data_source_DEPRECATED (0 调用者, 命名已自标 DEPRECATED) 已删除"""
        self.assertNotIn('def _create_fallback_data_source_DEPRECATED(', self.src,
                         '_create_fallback_data_source_DEPRECATED 死代码未清理')

    def test_no_fund_flow_legacy_definition(self):
        """T2: _get_fund_flow_legacy 定义已删除 (冗余降级)"""
        self.assertNotIn('def _get_fund_flow_legacy(', self.src,
                         '_get_fund_flow_legacy 定义未清理')

    def test_no_fund_flow_legacy_call(self):
        """T2: get_fund_flow 内 _get_fund_flow_legacy 唯一调用点已删除"""
        self.assertNotIn('self._get_fund_flow_legacy()', self.src,
                         'get_fund_flow 仍调用 _get_fund_flow_legacy')


class TestRightPanelIndustryTabConditional(unittest.TestCase):
    """T3: right_panel.py 行业 tab 条件跳过 (源码级断言, 与 R253 测试共存)"""

    @classmethod
    def setUpClass(cls):
        with open(_RIGHT_PANEL_SRC, encoding='utf-8') as f:
            cls.src = f.read()

    def test_industry_tab_call_guarded_by_professional_flag(self):
        """T3: _create_industry_tab 仅在非专业模式 (PROFESSIONAL_TABS_AVAILABLE=False) 下创建"""
        self.assertIn('if not PROFESSIONAL_TABS_AVAILABLE:', self.src,
                      '行业 tab 创建缺少专业模式条件跳过')
        self.assertIn('self._create_industry_tab(tab_widget)', self.src,
                      '_create_industry_tab 调用缺失')

    def test_ai_stock_removed_from_tabs_to_remove(self):
        """T3: "AI选股" 已随 R253 删除创建逻辑, 不应残留在 tabs_to_remove"""
        self.assertNotIn('"AI选股"', self.src,
                         '"AI选股" 字符串仍残留在 tabs_to_remove')


class TestGetFundFlowFallbackBehavior(unittest.TestCase):
    """T4: get_fund_flow 降级路径返回空结构且不抛异常 (行为断言)"""

    def test_fallback_returns_empty_structure(self):
        """T4: TET 管道不可用 (tet_enabled=False) 时返回标准空结构, 不再注入模拟数据"""
        from core.services.unified_data_manager import UnifiedDataManager

        udm = object.__new__(UnifiedDataManager)
        udm.tet_enabled = False
        udm.tet_pipeline = None

        result = udm.get_fund_flow()
        self.assertIn('sector_flow_rank', result)
        self.assertIn('individual_flow', result)
        self.assertIn('market_flow', result)
        self.assertTrue(result['sector_flow_rank'].empty)
        self.assertTrue(result['individual_flow'].empty)


if __name__ == '__main__':
    unittest.main()
