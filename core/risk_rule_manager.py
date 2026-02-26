#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险规则管理器
负责风险告警规则的存储、管理和执行
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from loguru import logger

@dataclass
class RiskRule:
    """风险规则数据类"""
    id: Optional[int] = None
    name: str = ""
    rule_type: str = "VaR风险"
    priority: str = "中"
    enabled: bool = True
    description: str = ""

    # 触发条件
    metric_name: str = "VaR(95%)"
    operator: str = ">"
    threshold_value: float = 80.0
    threshold_unit: str = "%"
    duration: int = 60

    # 高级设置
    check_interval: int = 60
    silence_period: int = 300
    max_alerts: int = 10

    # 通知设置（默认值：桌面和声音通知启用，其他禁用）
    email_notification: bool = False
    sms_notification: bool = False
    desktop_notification: bool = True
    sound_notification: bool = True
    webhook_notification: bool = False
    dingtalk_notification: bool = False
    message_template: str = ""
    email_recipients: str = ""
    sms_recipients: str = ""
    webhook_url: str = ""
    dingtalk_webhook_url: str = ""

    # 元数据
    created_at: str = ""
    updated_at: str = ""
    last_triggered: str = ""
    trigger_count: int = 0

@dataclass
class RiskAlert:
    """风险告警记录"""
    id: Optional[int] = None
    rule_id: int = 0
    rule_name: str = ""
    metric_name: str = ""
    metric_value: float = 0.0
    threshold_value: float = 0.0
    alert_level: str = "中"
    message: str = ""
    status: str = "active"  # active, acknowledged, resolved
    created_at: str = ""
    acknowledged_at: str = ""
    resolved_at: str = ""
    
    # 通知配置字段（从规则复制）
    email_notification: bool = False
    sms_notification: bool = False
    desktop_notification: bool = True
    sound_notification: bool = True
    webhook_notification: bool = False
    dingtalk_notification: bool = False
    email_recipients: str = ""
    sms_recipients: str = ""
    webhook_url: str = ""
    dingtalk_webhook_url: str = ""

class RiskRuleManager:
    """风险规则管理器"""

    def __init__(self, db_path: str = 'data/factorweave_system.sqlite'):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()
        self._active_alerts = {}  # 活跃告警缓存
        self._last_check_time = {}  # 上次检查时间

    def _init_tables(self):
        """初始化数据库表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 创建风险规则表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS risk_rules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        rule_type TEXT NOT NULL,
                        priority TEXT DEFAULT '中',
                        enabled BOOLEAN DEFAULT 1,
                        description TEXT DEFAULT '',
                        
                        metric_name TEXT NOT NULL,
                        operator TEXT NOT NULL,
                        threshold_value REAL NOT NULL,
                        threshold_unit TEXT DEFAULT '%',
                        duration INTEGER DEFAULT 60,
                        
                        check_interval INTEGER DEFAULT 60,
                        silence_period INTEGER DEFAULT 300,
                        max_alerts INTEGER DEFAULT 10,
                        
                        email_notification BOOLEAN DEFAULT 1,
                        sms_notification BOOLEAN DEFAULT 0,
                        desktop_notification BOOLEAN DEFAULT 1,
                        sound_notification BOOLEAN DEFAULT 1,
                        webhook_notification BOOLEAN DEFAULT 0,
                        dingtalk_notification BOOLEAN DEFAULT 0,
                        message_template TEXT DEFAULT '',
                        email_recipients TEXT DEFAULT '',
                        sms_recipients TEXT DEFAULT '',
                        webhook_url TEXT DEFAULT '',
                        dingtalk_webhook_url TEXT DEFAULT '',
                        
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        last_triggered TEXT DEFAULT '',
                        trigger_count INTEGER DEFAULT 0
                    )
                ''')

                # 创建风险告警表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS risk_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rule_id INTEGER NOT NULL,
                        rule_name TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        metric_value REAL NOT NULL,
                        threshold_value REAL NOT NULL,
                        alert_level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        status TEXT DEFAULT 'active',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        acknowledged_at TEXT DEFAULT '',
                        resolved_at TEXT DEFAULT '',
                        FOREIGN KEY (rule_id) REFERENCES risk_rules (id)
                    )
                ''')

                # 创建索引
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_risk_rules_enabled ON risk_rules(enabled)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_risk_alerts_status ON risk_alerts(status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_risk_alerts_created ON risk_alerts(created_at)')

                # 数据库迁移：添加新字段（如果不存在）
                self._migrate_database(cursor)

                conn.commit()
                logger.info("风险规则数据表初始化完成")

        except Exception as e:
            logger.error(f"初始化风险规则数据表失败: {e}")

    def _migrate_database(self, cursor: sqlite3.Cursor) -> None:
        """数据库迁移：添加新字段"""
        try:
            # 获取 risk_rules 表的列信息
            cursor.execute("PRAGMA table_info(risk_rules)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # 添加新字段（如果不存在）
            new_columns = {
                'dingtalk_notification': 'BOOLEAN DEFAULT 0',
                'email_recipients': 'TEXT DEFAULT \'\'',
                'sms_recipients': 'TEXT DEFAULT \'\'',
                'webhook_url': 'TEXT DEFAULT \'\'',
                'dingtalk_webhook_url': 'TEXT DEFAULT \'\''
            }
            
            for column_name, column_def in new_columns.items():
                if column_name not in columns:
                    try:
                        cursor.execute(f'ALTER TABLE risk_rules ADD COLUMN {column_name} {column_def}')
                        logger.info(f"已添加新字段: {column_name}")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" not in str(e):
                            logger.warning(f"添加字段 {column_name} 失败: {e}")
            
        except Exception as e:
            logger.warning(f"数据库迁移失败: {e}")

    def add_rule(self, rule: RiskRule) -> bool:
        """添加风险规则"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO risk_rules (
                        name, rule_type, priority, enabled, description,
                        metric_name, operator, threshold_value, threshold_unit, duration,
                        check_interval, silence_period, max_alerts,
                        email_notification, sms_notification, desktop_notification,
                        sound_notification, webhook_notification, dingtalk_notification,
                        message_template, email_recipients, sms_recipients,
                        webhook_url, dingtalk_webhook_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    rule.name, rule.rule_type, rule.priority, rule.enabled, rule.description,
                    rule.metric_name, rule.operator, rule.threshold_value, rule.threshold_unit, rule.duration,
                    rule.check_interval, rule.silence_period, rule.max_alerts,
                    rule.email_notification, rule.sms_notification, rule.desktop_notification,
                    rule.sound_notification, rule.webhook_notification, rule.dingtalk_notification,
                    rule.message_template, rule.email_recipients, rule.sms_recipients,
                    rule.webhook_url, rule.dingtalk_webhook_url
                ))

                rule.id = cursor.lastrowid
                conn.commit()

                logger.info(f"风险规则已添加: {rule.name}")
                return True

        except sqlite3.IntegrityError:
            logger.error(f"风险规则名称已存在: {rule.name}")
            return False
        except Exception as e:
            logger.error(f"添加风险规则失败: {e}")
            return False

    def update_rule(self, rule: RiskRule) -> bool:
        """更新风险规则"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE risk_rules SET
                        name = ?, rule_type = ?, priority = ?, enabled = ?, description = ?,
                        metric_name = ?, operator = ?, threshold_value = ?, threshold_unit = ?, duration = ?,
                        check_interval = ?, silence_period = ?, max_alerts = ?,
                        email_notification = ?, sms_notification = ?, desktop_notification = ?,
                        sound_notification = ?, webhook_notification = ?, dingtalk_notification = ?,
                        message_template = ?, email_recipients = ?, sms_recipients = ?,
                        webhook_url = ?, dingtalk_webhook_url = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    rule.name, rule.rule_type, rule.priority, rule.enabled, rule.description,
                    rule.metric_name, rule.operator, rule.threshold_value, rule.threshold_unit, rule.duration,
                    rule.check_interval, rule.silence_period, rule.max_alerts,
                    rule.email_notification, rule.sms_notification, rule.desktop_notification,
                    rule.sound_notification, rule.webhook_notification, rule.dingtalk_notification,
                    rule.message_template, rule.email_recipients, rule.sms_recipients,
                    rule.webhook_url, rule.dingtalk_webhook_url,
                    rule.id
                ))

                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"风险规则已更新: {rule.name}")
                    return True
                else:
                    logger.warning(f"未找到要更新的风险规则: {rule.id}")
                    return False

        except Exception as e:
            logger.error(f"更新风险规则失败: {e}")
            return False

    def delete_rule(self, rule_id: int) -> bool:
        """删除风险规则"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 先删除相关的告警记录
                cursor.execute('DELETE FROM risk_alerts WHERE rule_id = ?', (rule_id,))

                # 删除规则
                cursor.execute('DELETE FROM risk_rules WHERE id = ?', (rule_id,))

                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"风险规则已删除: {rule_id}")
                    return True
                else:
                    logger.warning(f"未找到要删除的风险规则: {rule_id}")
                    return False

        except Exception as e:
            logger.error(f"删除风险规则失败: {e}")
            return False

    def get_rule(self, rule_id: int) -> Optional[RiskRule]:
        """获取单个风险规则"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT * FROM risk_rules WHERE id = ?', (rule_id,))
                row = cursor.fetchone()

                if row:
                    return self._row_to_rule(row)
                return None

        except Exception as e:
            logger.error(f"获取风险规则失败: {e}")
            return None

    def get_all_rules(self, enabled_only: bool = False) -> List[RiskRule]:
        """获取所有风险规则"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if enabled_only:
                    cursor.execute('SELECT * FROM risk_rules WHERE enabled = 1 ORDER BY priority DESC, name')
                else:
                    cursor.execute('SELECT * FROM risk_rules ORDER BY priority DESC, name')

                rows = cursor.fetchall()
                return [self._row_to_rule(row) for row in rows]

        except Exception as e:
            logger.error(f"获取风险规则列表失败: {e}")
            return []

    def check_rules(self, risk_metrics: Dict[str, float]) -> List[RiskAlert]:
        """检查风险规则并生成告警"""
        alerts = []
        current_time = datetime.now()

        try:
            enabled_rules = self.get_all_rules(enabled_only=True)

            for rule in enabled_rules:
                # 检查是否需要检查这个规则
                last_check = self._last_check_time.get(rule.id, datetime.min)
                if (current_time - last_check).total_seconds() < rule.check_interval:
                    continue

                # 更新检查时间
                self._last_check_time[rule.id] = current_time

                # 检查规则条件
                if self._check_rule_condition(rule, risk_metrics):
                    # 检查静默期
                    if self._is_in_silence_period(rule):
                        continue

                    # 检查最大告警次数
                    if rule.trigger_count >= rule.max_alerts:
                        continue

                    # 生成告警
                    alert = self._create_alert(rule, risk_metrics)
                    if alert:
                        alerts.append(alert)
                        self._save_alert(alert)
                        self._update_rule_trigger_info(rule)

            return alerts

        except Exception as e:
            logger.error(f"检查风险规则失败: {e}")
            return []

    def _check_rule_condition(self, rule: RiskRule, risk_metrics: Dict[str, float]) -> bool:
        """检查规则条件是否满足"""
        try:
            metric_value = risk_metrics.get(rule.metric_name, 0.0)
            threshold = rule.threshold_value

            if rule.operator == ">":
                return metric_value > threshold
            elif rule.operator == ">=":
                return metric_value >= threshold
            elif rule.operator == "<":
                return metric_value < threshold
            elif rule.operator == "<=":
                return metric_value <= threshold
            elif rule.operator == "==":
                return abs(metric_value - threshold) < 0.001
            elif rule.operator == "!=":
                return abs(metric_value - threshold) >= 0.001

            return False

        except Exception as e:
            logger.error(f"检查规则条件失败: {e}")
            return False

    def _is_in_silence_period(self, rule: RiskRule) -> bool:
        """检查是否在静默期内"""
        if not rule.last_triggered:
            return False

        try:
            last_triggered = datetime.fromisoformat(rule.last_triggered)
            silence_end = last_triggered + timedelta(seconds=rule.silence_period)
            is_in_silence = datetime.now() < silence_end
            if is_in_silence:
                remaining = (silence_end - datetime.now()).total_seconds()
                logger.debug(f"规则 {rule.name} 在静默期内，剩余 {remaining:.0f} 秒")
            return is_in_silence
        except (ValueError, TypeError) as e:
            logger.error(f"解析时间失败: {e}, last_triggered={rule.last_triggered}")
            return False
        except Exception as e:
            logger.error(f"检查静默期失败: {e}")
            return False

    def _create_alert(self, rule: RiskRule, risk_metrics: Dict[str, float]) -> Optional[RiskAlert]:
        """创建告警记录"""
        try:
            metric_value = risk_metrics.get(rule.metric_name, 0.0)

            # 生成告警消息
            message = rule.message_template or f"风险指标 {rule.metric_name} 当前值 {metric_value:.2f}{rule.threshold_unit}，{rule.operator} 阈值 {rule.threshold_value:.2f}{rule.threshold_unit}"

            # 替换消息模板中的变量
            message = message.format(
                rule_name=rule.name,
                metric=rule.metric_name,
                value=f"{metric_value:.2f}{rule.threshold_unit}",
                threshold=f"{rule.threshold_value:.2f}{rule.threshold_unit}",
                time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            alert = RiskAlert(
                rule_id=rule.id,
                rule_name=rule.name,
                metric_name=rule.metric_name,
                metric_value=metric_value,
                threshold_value=rule.threshold_value,
                alert_level=rule.priority,
                message=message,
                status="active",
                created_at=datetime.now().isoformat(),
                
                # 从规则复制通知配置
                email_notification=rule.email_notification,
                sms_notification=rule.sms_notification,
                desktop_notification=rule.desktop_notification,
                sound_notification=rule.sound_notification,
                webhook_notification=rule.webhook_notification,
                dingtalk_notification=rule.dingtalk_notification,
                email_recipients=rule.email_recipients,
                sms_recipients=rule.sms_recipients,
                webhook_url=rule.webhook_url,
                dingtalk_webhook_url=rule.dingtalk_webhook_url
            )

            return alert

        except Exception as e:
            logger.error(f"创建告警记录失败: {e}")
            return None

    def _save_alert(self, alert: RiskAlert) -> bool:
        """保存告警记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO risk_alerts (
                        rule_id, rule_name, metric_name, metric_value, threshold_value,
                        alert_level, message, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    alert.rule_id, alert.rule_name, alert.metric_name, alert.metric_value,
                    alert.threshold_value, alert.alert_level, alert.message, alert.status,
                    alert.created_at
                ))

                alert.id = cursor.lastrowid
                conn.commit()

                return True

        except Exception as e:
            logger.error(f"保存告警记录失败: {e}")
            return False

    def _update_rule_trigger_info(self, rule: RiskRule):
        """更新规则触发信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE risk_rules SET
                        last_triggered = ?,
                        trigger_count = trigger_count + 1
                    WHERE id = ?
                ''', (datetime.now().isoformat(), rule.id))

                conn.commit()

        except Exception as e:
            logger.error(f"更新规则触发信息失败: {e}")

    def get_alerts(self, status: str = None, limit: int = 100) -> List[RiskAlert]:
        """获取告警记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if status:
                    cursor.execute(
                        'SELECT * FROM risk_alerts WHERE status = ? ORDER BY created_at DESC LIMIT ?',
                        (status, limit)
                    )
                else:
                    cursor.execute(
                        'SELECT * FROM risk_alerts ORDER BY created_at DESC LIMIT ?',
                        (limit,)
                    )

                rows = cursor.fetchall()
                return [self._row_to_alert(row) for row in rows]

        except Exception as e:
            logger.error(f"获取告警记录失败: {e}")
            return []

    def acknowledge_alert(self, alert_id: int) -> bool:
        """确认告警"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE risk_alerts SET
                        status = 'acknowledged',
                        acknowledged_at = ?
                    WHERE id = ?
                ''', (datetime.now().isoformat(), alert_id))

                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"确认告警失败: {e}")
            return False

    def resolve_alert(self, alert_id: int) -> bool:
        """解决告警"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE risk_alerts SET
                        status = 'resolved',
                        resolved_at = ?
                    WHERE id = ?
                ''', (datetime.now().isoformat(), alert_id))

                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"解决告警失败: {e}")
            return False

    def _row_to_rule(self, row) -> RiskRule:
        """将数据库行转换为RiskRule对象"""
        return RiskRule(
            id=row[0], name=row[1], rule_type=row[2], priority=row[3], enabled=bool(row[4]),
            description=row[5], metric_name=row[6], operator=row[7], threshold_value=row[8],
            threshold_unit=row[9], duration=row[10], check_interval=row[11], silence_period=row[12],
            max_alerts=row[13], email_notification=bool(row[14]), sms_notification=bool(row[15]),
            desktop_notification=bool(row[16]), sound_notification=bool(row[17]),
            webhook_notification=bool(row[18]), message_template=row[19], created_at=row[20],
            updated_at=row[21], last_triggered=row[22], trigger_count=row[23]
        )

    def _row_to_alert(self, row) -> RiskAlert:
        """将数据库行转换为RiskAlert对象"""
        return RiskAlert(
            id=row[0], rule_id=row[1], rule_name=row[2], metric_name=row[3],
            metric_value=row[4], threshold_value=row[5], alert_level=row[6],
            message=row[7], status=row[8], created_at=row[9],
            acknowledged_at=row[10], resolved_at=row[11]
        )

# 全局实例
_risk_rule_manager = None

def get_risk_rule_manager() -> RiskRuleManager:
    """获取风险规则管理器实例"""
    global _risk_rule_manager
    if _risk_rule_manager is None:
        _risk_rule_manager = RiskRuleManager()
    return _risk_rule_manager
