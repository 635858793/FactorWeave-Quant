"""
响应式计算辅助函数单元测试
测试 ResponsiveHelper 类的各种计算函数
"""

import unittest
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt

from gui.utils.responsive_helper import (
    ResponsiveHelper,
    get_responsive_helper,
    calculate_spacing,
    calculate_margins,
    calculate_percentage_height,
    calculate_font_size,
    get_device_pixel_ratio
)


class TestResponsiveHelper(unittest.TestCase):
    """ResponsiveHelper 类单元测试"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """每个测试方法前的初始化"""
        self.helper = ResponsiveHelper()
    
    def test_get_device_pixel_ratio(self):
        """测试获取设备像素比"""
        dpr = self.helper.get_device_pixel_ratio()
        
        self.assertIsInstance(dpr, float)
        self.assertGreater(dpr, 0)
        self.assertLess(dpr, 10)
    
    def test_get_device_pixel_ratio_caching(self):
        """测试设备像素比缓存机制"""
        dpr1 = self.helper.get_device_pixel_ratio()
        dpr2 = self.helper.get_device_pixel_ratio()
        
        self.assertEqual(dpr1, dpr2)
    
    def test_invalidate_cache(self):
        """测试缓存失效"""
        dpr1 = self.helper.get_device_pixel_ratio()
        self.helper.invalidate_cache()
        dpr2 = self.helper.get_device_pixel_ratio()
        
        self.assertEqual(dpr1, dpr2)
    
    def test_calculate_spacing(self):
        """测试间距计算"""
        base_value = 5
        result = self.helper.calculate_spacing(base_value)
        
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 1)
        self.assertGreaterEqual(result, base_value)
    
    def test_calculate_spacing_zero(self):
        """测试零值间距计算"""
        base_value = 0
        result = self.helper.calculate_spacing(base_value)
        
        self.assertEqual(result, 1)
    
    def test_calculate_margin(self):
        """测试边距计算"""
        base_value = 10
        result = self.helper.calculate_margin(base_value)
        
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 1)
    
    def test_calculate_margins(self):
        """测试四个方向边距计算"""
        top, right, bottom, left = self.helper.calculate_margins(5, 10, 15, 20)
        
        self.assertIsInstance(top, int)
        self.assertIsInstance(right, int)
        self.assertIsInstance(bottom, int)
        self.assertIsInstance(left, int)
        
        self.assertGreaterEqual(top, 1)
        self.assertGreaterEqual(right, 1)
        self.assertGreaterEqual(bottom, 1)
        self.assertGreaterEqual(left, 1)
    
    def test_calculate_percentage_height_with_widget(self):
        """测试基于父窗口的高度百分比计算"""
        parent_widget = QWidget()
        parent_widget.resize(1000, 800)
        
        percentage = 0.5
        result = self.helper.calculate_percentage_height(parent_widget, percentage)
        
        self.assertEqual(result, 400)
    
    def test_calculate_percentage_height_without_widget(self):
        """测试无父窗口时的高度计算"""
        result = self.helper.calculate_percentage_height(None, 0.5)
        
        self.assertEqual(result, 100)
    
    def test_calculate_percentage_height_invalid_percentage(self):
        """测试无效百分比值"""
        parent_widget = QWidget()
        parent_widget.resize(1000, 800)
        
        result1 = self.helper.calculate_percentage_height(parent_widget, -0.1)
        self.assertEqual(result1, 400)
        
        result2 = self.helper.calculate_percentage_height(parent_widget, 1.5)
        self.assertEqual(result2, 400)
    
    def test_calculate_percentage_height_minimum(self):
        """测试最小高度限制"""
        parent_widget = QWidget()
        parent_widget.resize(100, 50)
        
        percentage = 0.1
        result = self.helper.calculate_percentage_height(parent_widget, percentage)
        
        self.assertGreaterEqual(result, 50)
    
    def test_calculate_font_size(self):
        """测试字体大小计算"""
        base_size = 12
        result = self.helper.calculate_font_size(base_size)
        
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 8)
    
    def test_calculate_font_size_minimum(self):
        """测试最小字体大小"""
        base_size = 1
        result = self.helper.calculate_font_size(base_size)
        
        self.assertGreaterEqual(result, 8)
    
    def test_calculate_icon_size(self):
        """测试图标大小计算"""
        base_size = 24
        result = self.helper.calculate_icon_size(base_size)
        
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 16)
    
    def test_calculate_icon_size_minimum(self):
        """测试最小图标大小"""
        base_size = 1
        result = self.helper.calculate_icon_size(base_size)
        
        self.assertGreaterEqual(result, 16)
    
    def test_calculate_table_row_height(self):
        """测试表格行高计算"""
        base_height = 30
        row_count = 5
        result = self.helper.calculate_table_row_height(base_height, row_count)
        
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 100)
    
    def test_calculate_border_radius(self):
        """测试边框圆角计算"""
        base_radius = 4
        result = self.helper.calculate_border_radius(base_radius)
        
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 1)
    
    def test_get_em_value(self):
        """测试 em 单位计算"""
        base_font_size = 16
        result = self.helper.get_em_value(base_font_size)
        
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 8)


class TestConvenienceFunctions(unittest.TestCase):
    """便捷函数单元测试"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def test_get_responsive_helper_singleton(self):
        """测试全局单例获取"""
        helper1 = get_responsive_helper()
        helper2 = get_responsive_helper()
        
        self.assertIs(helper1, helper2)
    
    def test_calculate_spacing_convenience(self):
        """测试便捷间距计算函数"""
        base_value = 8
        result = calculate_spacing(base_value)
        
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 1)
    
    def test_calculate_margins_convenience(self):
        """测试便捷边距计算函数"""
        top, right, bottom, left = calculate_margins(5, 10, 15, 20)
        
        self.assertIsInstance(top, int)
        self.assertIsInstance(right, int)
        self.assertIsInstance(bottom, int)
        self.assertIsInstance(left, int)
    
    def test_calculate_percentage_height_convenience(self):
        """测试便捷高度百分比计算函数"""
        parent_widget = QWidget()
        parent_widget.resize(1000, 800)
        
        result = calculate_percentage_height(parent_widget, 0.5)
        
        self.assertEqual(result, 400)
    
    def test_calculate_font_size_convenience(self):
        """测试便捷字体大小计算函数"""
        base_size = 14
        result = calculate_font_size(base_size)
        
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 8)
    
    def test_get_device_pixel_ratio_convenience(self):
        """测试便捷设备像素比获取函数"""
        dpr = get_device_pixel_ratio()
        
        self.assertIsInstance(dpr, float)
        self.assertGreater(dpr, 0)


class TestEdgeCases(unittest.TestCase):
    """边界情况测试"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """每个测试方法前的初始化"""
        self.helper = ResponsiveHelper()
    
    def test_negative_spacing(self):
        """测试负值间距"""
        result = self.helper.calculate_spacing(-5)
        
        self.assertGreaterEqual(result, 1)
    
    def test_large_spacing(self):
        """测试大值间距"""
        result = self.helper.calculate_spacing(1000)
        
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 1000)
    
    def test_zero_percentage(self):
        """测试零百分比"""
        parent_widget = QWidget()
        parent_widget.resize(1000, 800)
        
        result = self.helper.calculate_percentage_height(parent_widget, 0.0)
        
        self.assertEqual(result, 400)
    
    def test_one_percentage(self):
        """测试 100% 百分比"""
        parent_widget = QWidget()
        parent_widget.resize(1000, 800)
        
        result = self.helper.calculate_percentage_height(parent_widget, 1.0)
        
        self.assertEqual(result, 800)
    
    def test_very_small_widget(self):
        """测试非常小的父窗口"""
        parent_widget = QWidget()
        parent_widget.resize(10, 10)
        
        result = self.helper.calculate_percentage_height(parent_widget, 0.5)
        
        self.assertGreaterEqual(result, 50)


if __name__ == '__main__':
    unittest.main()
