"""
全局字体管理器
提供全局字体缩放功能，支持快捷键和用户自定义
"""

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtCore import QObject, pyqtSignal, QSettings
from loguru import logger
from typing import Optional


class GlobalFontManager(QObject):
    """全局字体管理器"""
    
    # 字体大小改变信号
    font_size_changed = pyqtSignal(float)
    
    # 单例实例
    _instance: Optional['GlobalFontManager'] = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化全局字体管理器"""
        if self._initialized:
            return
        
        super().__init__()
        
        # 默认字体大小
        self.default_font_size = 10.0
        self.current_font_size = self.default_font_size
        
        # 字体大小范围
        self.min_font_size = 8.0
        self.max_font_size = 24.0
        self.font_size_step = 1.0
        
        # 加载用户设置
        self._load_settings()
        
        self._initialized = True
        logger.info(f"全局字体管理器初始化完成，当前字体大小: {self.current_font_size}")
    
    def _load_settings(self):
        """加载用户设置"""
        try:
            settings = QSettings("HikyuuUI", "FontSettings")
            saved_size = settings.value("font_size", self.default_font_size, type=float)
            
            # 验证字体大小范围
            if self.min_font_size <= saved_size <= self.max_font_size:
                self.current_font_size = saved_size
                logger.info(f"从设置加载字体大小: {self.current_font_size}")
            else:
                logger.warning(f"保存的字体大小超出范围: {saved_size}，使用默认值")
        except Exception as e:
            logger.error(f"加载字体设置失败: {e}")
    
    def _save_settings(self):
        """保存用户设置"""
        try:
            settings = QSettings("HikyuuUI", "FontSettings")
            settings.setValue("font_size", self.current_font_size)
            logger.info(f"字体大小已保存: {self.current_font_size}")
        except Exception as e:
            logger.error(f"保存字体设置失败: {e}")
    
    def increase_font_size(self):
        """增大字体大小"""
        new_size = min(self.current_font_size + self.font_size_step, self.max_font_size)
        if new_size != self.current_font_size:
            self.set_font_size(new_size)
    
    def decrease_font_size(self):
        """减小字体大小"""
        new_size = max(self.current_font_size - self.font_size_step, self.min_font_size)
        if new_size != self.current_font_size:
            self.set_font_size(new_size)
    
    def reset_font_size(self):
        """重置字体大小为默认值"""
        if self.current_font_size != self.default_font_size:
            self.set_font_size(self.default_font_size)
    
    def set_font_size(self, size: float):
        """设置字体大小
        
        Args:
            size: 字体大小（像素）
        """
        # 验证字体大小范围
        if size < self.min_font_size or size > self.max_font_size:
            logger.warning(f"字体大小超出范围: {size}，范围: {self.min_font_size}-{self.max_font_size}")
            return
        
        self.current_font_size = size
        
        # 应用到应用程序
        app = QApplication.instance()
        if app:
            font = app.font()
            font.setPointSizeF(self.current_font_size)
            app.setFont(font)
            logger.info(f"应用程序字体大小已设置为: {self.current_font_size}")
        
        # 保存设置
        self._save_settings()
        
        # 发送信号
        self.font_size_changed.emit(self.current_font_size)
    
    def get_font_size(self) -> float:
        """获取当前字体大小
        
        Returns:
            当前字体大小（像素）
        """
        return self.current_font_size
    
    def get_default_font_size(self) -> float:
        """获取默认字体大小
        
        Returns:
            默认字体大小（像素）
        """
        return self.default_font_size
    
    def get_font_size_range(self) -> tuple:
        """获取字体大小范围
        
        Returns:
            (最小值, 最大值, 步长)
        """
        return (self.min_font_size, self.max_font_size, self.font_size_step)


# 全局访问函数
def get_global_font_manager() -> GlobalFontManager:
    """获取全局字体管理器实例
    
    Returns:
        GlobalFontManager 实例
    """
    return GlobalFontManager()
