from loguru import logger
"""
指标组合管理器

功能：
1. 存储和管理指标组合
2. 支持组合的增删改查
3. 支持导入导出功能
4. 提供搜索和过滤功能
"""

import os
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from threading import Lock
from datetime import datetime


@dataclass
class IndicatorCombination:
    """指标组合数据类"""
    name: str
    indicators: List[Dict[str, Any]]
    description: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IndicatorCombination':
        """从字典创建实例"""
        return cls(**data)


class IndicatorCombinationManager:
    """指标组合管理器"""
    
    def __init__(self):
        """初始化指标组合管理器"""
        self._combinations: Dict[str, IndicatorCombination] = {}
        self._lock = Lock()
        
        self._persistence_dir = os.path.join("data", "indicator_combinations")
        self._init_persistence_dir()
        
        self.load_combinations()
        
        logger.info("IndicatorCombinationManager初始化完成")
    
    def _init_persistence_dir(self) -> None:
        """初始化持久化目录"""
        try:
            if not os.path.exists(self._persistence_dir):
                os.makedirs(self._persistence_dir)
        except Exception as e:
            logger.error(f"初始化持久化目录失败: {e}")
    
    def _get_file_path(self) -> str:
        """获取存储文件路径"""
        return os.path.join(self._persistence_dir, "combinations.json")
    
    def load_combinations(self) -> None:
        """加载保存的指标组合"""
        try:
            file_path = self._get_file_path()
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, combo_data in data.items():
                        self._combinations[name] = IndicatorCombination.from_dict(combo_data)
                logger.info(f"已加载 {len(self._combinations)} 个指标组合")
        except Exception as e:
            logger.error(f"加载指标组合失败: {e}")
    
    def save_combinations(self) -> None:
        """保存指标组合到文件"""
        try:
            file_path = self._get_file_path()
            data = {name: combo.to_dict() for name, combo in self._combinations.items()}
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存指标组合失败: {e}")
    
    def save_combination(self, name: str, indicators: List[Dict[str, Any]], 
                         description: str = "", tags: List[str] = None) -> bool:
        """保存指标组合
        
        Args:
            name: 组合名称
            indicators: 指标列表
            description: 组合描述
            tags: 标签列表
            
        Returns:
            是否保存成功
        """
        try:
            with self._lock:
                if name in self._combinations:
                    existing = self._combinations[name]
                    combo = IndicatorCombination(
                        name=name,
                        indicators=indicators,
                        description=description or existing.description,
                        tags=tags or existing.tags,
                        created_at=existing.created_at,
                        updated_at=datetime.now().isoformat()
                    )
                else:
                    combo = IndicatorCombination(
                        name=name,
                        indicators=indicators,
                        description=description or "",
                        tags=tags or []
                    )
                
                self._combinations[name] = combo
                self.save_combinations()
                
            logger.info(f"指标组合已保存: {name}")
            return True
        except Exception as e:
            logger.error(f"保存指标组合失败: {e}")
            return False
    
    def get_combination(self, name: str) -> Optional[IndicatorCombination]:
        """获取指标组合
        
        Args:
            name: 组合名称
            
        Returns:
            指标组合实例，如果不存在则返回None
        """
        return self._combinations.get(name)
    
    def get_all_combinations(self) -> Dict[str, IndicatorCombination]:
        """获取所有指标组合
        
        Returns:
            所有指标组合的字典
        """
        return self._combinations.copy()
    
    def delete_combination(self, name: str) -> bool:
        """删除指标组合
        
        Args:
            name: 组合名称
            
        Returns:
            是否删除成功
        """
        try:
            with self._lock:
                if name in self._combinations:
                    del self._combinations[name]
                    self.save_combinations()
                    logger.info(f"指标组合已删除: {name}")
                    return True
                return False
        except Exception as e:
            logger.error(f"删除指标组合失败: {e}")
            return False
    
    def search_combinations(self, query: str = "", tags: List[str] = None) -> Dict[str, IndicatorCombination]:
        """搜索指标组合
        
        Args:
            query: 搜索关键词
            tags: 标签列表
            
        Returns:
            匹配的指标组合字典
        """
        results = {}
        
        for name, combo in self._combinations.items():
            matches = True
            
            if query:
                query_lower = query.lower()
                if (query_lower not in name.lower() and 
                    query_lower not in combo.description.lower()):
                    matches = False
            
            if tags and matches:
                if not any(tag in combo.tags for tag in tags):
                    matches = False
            
            if matches:
                results[name] = combo
        
        return results
    
    def get_combination_stats(self) -> Dict[str, Any]:
        """获取指标组合统计信息
        
        Returns:
            统计信息字典
        """
        total_count = len(self._combinations)
        total_indicators = sum(len(c.indicators) for c in self._combinations.values())
        
        indicator_counts = {}
        all_tags = set()
        for combo in self._combinations.values():
            for tag in combo.tags:
                all_tags.add(tag)
            for indicator in combo.indicators:
                indicator_name = indicator.get('name', 'Unknown')
                indicator_counts[indicator_name] = indicator_counts.get(indicator_name, 0) + 1
        
        return {
            "total_combinations": total_count,
            "total_indicators": total_indicators,
            "average_indicators": total_indicators / total_count if total_count > 0 else 0,
            "most_used_indicators": indicator_counts,
            "tags": list(all_tags)
        }
    
    def import_combinations(self, file_path: str) -> bool:
        """导入指标组合
        
        Args:
            file_path: 导入文件路径
            
        Returns:
            是否导入成功
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            with self._lock:
                for name, combo_data in data.items():
                    self._combinations[name] = IndicatorCombination.from_dict(combo_data)
            
            self.save_combinations()
            logger.info(f"成功导入指标组合: {len(data)} 个")
            return True
        except Exception as e:
            logger.error(f"导入指标组合失败: {e}")
            return False
    
    def export_combinations(self, file_path: str) -> bool:
        """导出指标组合
        
        Args:
            file_path: 导出文件路径
            
        Returns:
            是否导出成功
        """
        try:
            data = {name: combo.to_dict() for name, combo in self._combinations.items()}
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"成功导出指标组合: {len(data)} 个")
            return True
        except Exception as e:
            logger.error(f"导出指标组合失败: {e}")
            return False


_instance: Optional[IndicatorCombinationManager] = None


def get_combination_manager() -> IndicatorCombinationManager:
    """获取指标组合管理器的单例实例
    
    Returns:
        IndicatorCombinationManager实例
    """
    global _instance
    if _instance is None:
        _instance = IndicatorCombinationManager()
    return _instance
