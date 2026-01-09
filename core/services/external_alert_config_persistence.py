#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
外部告警渠道配置持久化服务

提供外部告警渠道配置的保存、加载和管理功能
"""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger


class ExternalAlertConfigPersistence:
    """外部告警渠道配置持久化管理"""

    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化配置持久化管理

        Args:
            config_dir: 配置目录路径，默认为项目config目录
        """
        if config_dir is None:
            # 默认配置目录
            project_root = Path(__file__).parent.parent.parent
            config_dir = project_root / 'config' / 'external_alerts'

        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # 配置文件路径
        self.config_file = self.config_dir / 'channel_configs.json'
        self.backup_dir = self.config_dir / 'backups'
        self.backup_dir.mkdir(exist_ok=True)

        logger.info(f"外部告警渠道配置持久化初始化完成: {self.config_dir}")

    def save_channel_config(self, channel_type: str, config: Dict[str, Any]) -> bool:
        """
        保存单个渠道配置

        Args:
            channel_type: 渠道类型 (email, sms, webhook, dingtalk)
            config: 渠道配置

        Returns:
            是否保存成功
        """
        try:
            # 读取现有配置
            all_configs = self.load_all_configs()

            # 更新指定渠道配置
            all_configs[channel_type] = config

            # 保存所有配置
            return self._save_all_configs(all_configs)

        except Exception as e:
            logger.error(f"保存渠道配置失败 [{channel_type}]: {e}")
            return False

    def load_channel_config(self, channel_type: str) -> Optional[Dict[str, Any]]:
        """
        加载单个渠道配置

        Args:
            channel_type: 渠道类型 (email, sms, webhook, dingtalk)

        Returns:
            渠道配置，如果不存在返回None
        """
        try:
            all_configs = self.load_all_configs()
            return all_configs.get(channel_type)

        except Exception as e:
            logger.error(f"加载渠道配置失败 [{channel_type}]: {e}")
            return None

    def save_all_configs(self, configs: Dict[str, Dict[str, Any]]) -> bool:
        """
        保存所有渠道配置

        Args:
            configs: 所有渠道配置字典

        Returns:
            是否保存成功
        """
        try:
            # 创建备份
            self._create_backup()

            # 保存配置
            return self._save_all_configs(configs)

        except Exception as e:
            logger.error(f"保存所有渠道配置失败: {e}")
            return False

    def load_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        加载所有渠道配置

        Returns:
            所有渠道配置字典
        """
        try:
            if not self.config_file.exists():
                return {}

            with open(self.config_file, 'r', encoding='utf-8') as f:
                configs = json.load(f)

            logger.debug(f"加载外部告警渠道配置成功: {list(configs.keys())}")
            return configs

        except json.JSONDecodeError as e:
            logger.error(f"配置文件JSON格式错误: {e}")
            # 尝试从备份恢复
            return self._restore_from_backup()
        except Exception as e:
            logger.error(f"加载所有渠道配置失败: {e}")
            return {}

    def delete_channel_config(self, channel_type: str) -> bool:
        """
        删除单个渠道配置

        Args:
            channel_type: 渠道类型 (email, sms, webhook, dingtalk)

        Returns:
            是否删除成功
        """
        try:
            # 读取现有配置
            all_configs = self.load_all_configs()

            # 删除指定渠道配置
            if channel_type in all_configs:
                del all_configs[channel_type]

                # 保存剩余配置
                return self._save_all_configs(all_configs)

            return True

        except Exception as e:
            logger.error(f"删除渠道配置失败 [{channel_type}]: {e}")
            return False

    def export_config(self, export_path: str) -> bool:
        """
        导出配置到指定路径

        Args:
            export_path: 导出文件路径

        Returns:
            是否导出成功
        """
        try:
            configs = self.load_all_configs()

            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(configs, f, indent=2, ensure_ascii=False)

            logger.info(f"配置导出成功: {export_path}")
            return True

        except Exception as e:
            logger.error(f"导出配置失败: {e}")
            return False

    def import_config(self, import_path: str) -> bool:
        """
        从指定路径导入配置

        Args:
            import_path: 导入文件路径

        Returns:
            是否导入成功
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                configs = json.load(f)

            # 验证配置格式
            if not isinstance(configs, dict):
                raise ValueError("配置格式错误：必须是字典类型")

            # 保存配置
            return self.save_all_configs(configs)

        except Exception as e:
            logger.error(f"导入配置失败: {e}")
            return False

    def _save_all_configs(self, configs: Dict[str, Dict[str, Any]]) -> bool:
        """
        保存所有配置到文件

        Args:
            configs: 配置字典

        Returns:
            是否保存成功
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(configs, f, indent=2, ensure_ascii=False)

            logger.debug(f"保存外部告警渠道配置成功: {list(configs.keys())}")
            return True

        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False

    def _create_backup(self):
        """创建配置备份"""
        try:
            if not self.config_file.exists():
                return

            # 生成备份文件名（带时间戳）
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = self.backup_dir / f'channel_configs_{timestamp}.json'

            # 复制文件
            import shutil
            shutil.copy2(self.config_file, backup_file)

            logger.debug(f"创建配置备份: {backup_file}")

            # 清理旧备份（保留最近10个）
            self._cleanup_old_backups()

        except Exception as e:
            logger.warning(f"创建配置备份失败: {e}")

    def _cleanup_old_backups(self):
        """清理旧备份文件，保留最近10个"""
        try:
            backup_files = sorted(self.backup_dir.glob('channel_configs_*.json'), reverse=True)

            # 删除超过10个的备份
            for old_backup in backup_files[10:]:
                old_backup.unlink()
                logger.debug(f"删除旧备份: {old_backup}")

        except Exception as e:
            logger.warning(f"清理旧备份失败: {e}")

    def _restore_from_backup(self) -> Dict[str, Dict[str, Any]]:
        """
        从备份恢复配置

        Returns:
            恢复的配置字典
        """
        try:
            # 获取最新的备份文件
            backup_files = sorted(self.backup_dir.glob('channel_configs_*.json'), reverse=True)

            if not backup_files:
                logger.warning("没有可用的备份文件")
                return {}

            # 使用最新的备份
            latest_backup = backup_files[0]

            with open(latest_backup, 'r', encoding='utf-8') as f:
                configs = json.load(f)

            logger.info(f"从备份恢复配置: {latest_backup}")
            return configs

        except Exception as e:
            logger.error(f"从备份恢复配置失败: {e}")
            return {}

    def get_config_info(self) -> Dict[str, Any]:
        """
        获取配置信息

        Returns:
            配置信息字典
        """
        try:
            configs = self.load_all_configs()

            # 获取备份文件列表
            backup_files = list(self.backup_dir.glob('channel_configs_*.json'))
            backup_count = len(backup_files)

            # 获取配置文件修改时间
            config_mtime = None
            if self.config_file.exists():
                config_mtime = self.config_file.stat().st_mtime

            return {
                'config_file': str(self.config_file),
                'config_exists': self.config_file.exists(),
                'config_mtime': config_mtime,
                'backup_dir': str(self.backup_dir),
                'backup_count': backup_count,
                'configured_channels': list(configs.keys()),
                'channel_count': len(configs)
            }

        except Exception as e:
            logger.error(f"获取配置信息失败: {e}")
            return {}


# 全局配置持久化实例
_persistence_instance: Optional[ExternalAlertConfigPersistence] = None


def get_alert_config_persistence() -> ExternalAlertConfigPersistence:
    """
    获取外部告警渠道配置持久化实例（单例）

    Returns:
        配置持久化实例
    """
    global _persistence_instance

    if _persistence_instance is None:
        _persistence_instance = ExternalAlertConfigPersistence()

    return _persistence_instance
