from loguru import logger
"""
告警配置数据库模型

包含告警通知配置、告警规则和告警历史的数据库表结构
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logger

@dataclass
class NotificationConfig:
    """通知配置数据类"""
    # 邮件配置
    email_enabled: bool = False
    email_provider: str = "SMTP"
    sender_email: str = ""
    sender_name: str = "FactorWeave-Quant 系统"
    email_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    email_address: str = ""

    # 短信配置
    sms_enabled: bool = False
    sms_provider: str = "云片"
    sms_api_key: str = ""
    sms_api_secret: str = ""
    phone_number: str = ""

    # 其他通知配置
    desktop_enabled: bool = True
    sound_enabled: bool = True

    # 元数据
    created_at: str = ""
    updated_at: str = ""

@dataclass
class AlertRule:
    """告警规则数据类"""
    # 基本信息
    id: Optional[int] = None
    name: str = ""
    rule_type: str = "系统资源"
    priority: str = "中等"
    enabled: bool = True
    description: str = ""

    # 触发条件
    metric_name: str = ""
    operator: str = ">"
    threshold_value: float = 0.0
    threshold_unit: str = "%"
    duration: int = 60  # 持续时间（秒）

    # 高级条件
    check_interval: int = 60  # 检查频率（秒）
    silence_period: int = 300  # 静默期（秒）
    max_alerts: int = 10  # 最大告警次数

    # 通知设置
    email_notification: bool = True
    sms_notification: bool = False
    webhook_notification: bool = False
    dingtalk_notification: bool = False
    desktop_notification: bool = True
    sound_notification: bool = True
    email_recipients: str = ""
    sms_recipients: str = ""
    webhook_url: str = ""
    dingtalk_webhook_url: str = ""
    message_template: str = ""

    # 元数据
    created_at: str = ""
    updated_at: str = ""

@dataclass
class AlertHistory:
    """告警历史数据类"""
    id: Optional[int] = None
    timestamp: str = ""
    level: str = ""
    category: str = ""
    message: str = ""
    status: str = ""
    rule_id: Optional[int] = None
    metric_name: str = ""
    current_value: float = 0.0
    threshold_value: float = 0.0
    recommendation: str = ""


@dataclass
class RiskHistoryRecord:
    """风险历史记录数据类"""
    id: Optional[int] = None
    timestamp: str = ""
    overall_risk_score: float = 0.0
    risk_level: str = ""
    var_95: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    status: str = ""


class AlertConfigDatabase:
    """告警配置数据库管理类"""

    def __init__(self, db_path: str = None):
        """初始化数据库连接"""
        if db_path is None:
            # 默认数据库路径
            db_dir = Path(__file__).parent.parent.parent
            db_path = db_dir / "data/alert_config.sqlite"

        self.db_path = str(db_path)
        self.init_database()

    def init_database(self):
        """初始化数据库表结构"""
        try:
            # 确保数据库目录存在
            import os
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 创建通知配置表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS alert_notification_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_name TEXT UNIQUE NOT NULL DEFAULT 'default',
                        
                        -- 邮件配置
                        email_enabled BOOLEAN DEFAULT 0,
                        email_provider TEXT DEFAULT 'SMTP',
                        sender_email TEXT DEFAULT '',
                        sender_name TEXT DEFAULT 'FactorWeave-Quant 系统',
                        email_api_key TEXT DEFAULT '',
                        smtp_host TEXT DEFAULT '',
                        smtp_port INTEGER DEFAULT 587,
                        email_address TEXT DEFAULT '',
                        
                        -- 短信配置
                        sms_enabled BOOLEAN DEFAULT 0,
                        sms_provider TEXT DEFAULT '云片',
                        sms_api_key TEXT DEFAULT '',
                        sms_api_secret TEXT DEFAULT '',
                        phone_number TEXT DEFAULT '',
                        
                        -- 其他通知配置
                        desktop_enabled BOOLEAN DEFAULT 1,
                        sound_enabled BOOLEAN DEFAULT 1,
                        
                        -- 元数据
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 创建告警规则表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS alert_rules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        rule_type TEXT DEFAULT '系统资源',
                        priority TEXT DEFAULT '中等',
                        enabled BOOLEAN DEFAULT 1,
                        description TEXT DEFAULT '',
                        
                        -- 触发条件
                        metric_name TEXT DEFAULT '',
                        operator TEXT DEFAULT '>',
                        threshold_value REAL DEFAULT 0.0,
                        threshold_unit TEXT DEFAULT '%',
                        duration INTEGER DEFAULT 60,
                        
                        -- 高级条件
                        check_interval INTEGER DEFAULT 60,
                        silence_period INTEGER DEFAULT 300,
                        max_alerts INTEGER DEFAULT 10,
                        
                        -- 通知设置
                        email_notification BOOLEAN DEFAULT 1,
                        sms_notification BOOLEAN DEFAULT 0,
                        webhook_notification BOOLEAN DEFAULT 0,
                        dingtalk_notification BOOLEAN DEFAULT 0,
                        desktop_notification BOOLEAN DEFAULT 1,
                        sound_notification BOOLEAN DEFAULT 1,
                        email_recipients TEXT DEFAULT '',
                        sms_recipients TEXT DEFAULT '',
                        webhook_url TEXT DEFAULT '',
                        dingtalk_webhook_url TEXT DEFAULT '',
                        message_template TEXT DEFAULT '',
                        
                        -- 元数据
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 数据库迁移：添加新字段（如果不存在）
                try:
                    cursor.execute("ALTER TABLE alert_rules ADD COLUMN webhook_notification BOOLEAN DEFAULT 0")
                except sqlite3.OperationalError:
                    pass  # 字段已存在

                try:
                    cursor.execute("ALTER TABLE alert_rules ADD COLUMN dingtalk_notification BOOLEAN DEFAULT 0")
                except sqlite3.OperationalError:
                    pass  # 字段已存在

                try:
                    cursor.execute("ALTER TABLE alert_rules ADD COLUMN email_recipients TEXT DEFAULT ''")
                except sqlite3.OperationalError:
                    pass  # 字段已存在

                try:
                    cursor.execute("ALTER TABLE alert_rules ADD COLUMN sms_recipients TEXT DEFAULT ''")
                except sqlite3.OperationalError:
                    pass  # 字段已存在

                try:
                    cursor.execute("ALTER TABLE alert_rules ADD COLUMN webhook_url TEXT DEFAULT ''")
                except sqlite3.OperationalError:
                    pass  # 字段已存在

                try:
                    cursor.execute("ALTER TABLE alert_rules ADD COLUMN dingtalk_webhook_url TEXT DEFAULT ''")
                except sqlite3.OperationalError:
                    pass  # 字段已存在

                # 创建风险历史表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS risk_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        overall_risk_score REAL NOT NULL,
                        risk_level TEXT NOT NULL,
                        var_95 REAL DEFAULT 0.0,
                        max_drawdown REAL DEFAULT 0.0,
                        volatility REAL DEFAULT 0.0,
                        status TEXT DEFAULT '正常'
                    )
                """)

                # 创建告警历史表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS alert_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        level TEXT NOT NULL,
                        category TEXT NOT NULL,
                        message TEXT NOT NULL,
                        status TEXT DEFAULT '活跃',
                        rule_id INTEGER,
                        metric_name TEXT DEFAULT '',
                        current_value REAL DEFAULT 0.0,
                        threshold_value REAL DEFAULT 0.0,
                        recommendation TEXT DEFAULT '',
                        
                        FOREIGN KEY (rule_id) REFERENCES alert_rules (id)
                    )
                """)

                # 创建索引
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_history_timestamp ON risk_history(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_timestamp ON alert_history(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_level ON alert_history(level)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_rule_id ON alert_history(rule_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled)")

                conn.commit()
                logger.info(f"告警配置数据库初始化完成: {self.db_path}")

        except Exception as e:
            logger.error(f"初始化告警配置数据库失败: {e}")
            raise

    # ==================== 通知配置管理 ====================

    def save_notification_config(self, config: NotificationConfig) -> bool:
        """保存通知配置"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                config.updated_at = datetime.now().isoformat()
                if not config.created_at:
                    config.created_at = config.updated_at

                # 使用 INSERT OR REPLACE 来更新或插入配置
                cursor.execute("""
                    INSERT OR REPLACE INTO alert_notification_config (
                        config_name, email_enabled, email_provider, sender_email, sender_name,
                        email_api_key, smtp_host, smtp_port, email_address,
                        sms_enabled, sms_provider, sms_api_key, sms_api_secret, phone_number,
                        desktop_enabled, sound_enabled, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    'default', config.email_enabled, config.email_provider, config.sender_email,
                    config.sender_name, config.email_api_key, config.smtp_host, config.smtp_port,
                    config.email_address, config.sms_enabled, config.sms_provider, config.sms_api_key,
                    config.sms_api_secret, config.phone_number, config.desktop_enabled,
                    config.sound_enabled, config.created_at, config.updated_at
                ))

                conn.commit()
                logger.info("通知配置保存成功")
                return True

        except Exception as e:
            logger.error(f"保存通知配置失败: {e}")
            return False

    def load_notification_config(self) -> Optional[NotificationConfig]:
        """加载通知配置"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM alert_notification_config WHERE config_name = 'default'")
                row = cursor.fetchone()

                if row:
                    # 获取列名
                    columns = [description[0] for description in cursor.description]
                    config_dict = dict(zip(columns, row))

                    # 移除不需要的字段
                    config_dict.pop('id', None)
                    config_dict.pop('config_name', None)

                    return NotificationConfig(**config_dict)
                else:
                    # 返回默认配置
                    return NotificationConfig()

        except Exception as e:
            logger.error(f"加载通知配置失败: {e}")
            return NotificationConfig()

    # ==================== 告警规则管理 ====================

    def save_alert_rule(self, rule: AlertRule) -> Optional[int]:
        """保存告警规则"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                rule.updated_at = datetime.now().isoformat()

                if rule.id:
                    # 更新现有规则
                    cursor.execute("""
                        UPDATE alert_rules SET
                            name=?, rule_type=?, priority=?, enabled=?, description=?,
                            metric_name=?, operator=?, threshold_value=?, threshold_unit=?, duration=?,
                            check_interval=?, silence_period=?, max_alerts=?,
                            email_notification=?, sms_notification=?, webhook_notification=?, dingtalk_notification=?, desktop_notification=?,
                            sound_notification=?, email_recipients=?, sms_recipients=?, webhook_url=?, dingtalk_webhook_url=?,
                            message_template=?, updated_at=?
                        WHERE id=?
                    """, (
                        rule.name, rule.rule_type, rule.priority, rule.enabled, rule.description,
                        rule.metric_name, rule.operator, rule.threshold_value, rule.threshold_unit,
                        rule.duration, rule.check_interval, rule.silence_period, rule.max_alerts,
                        rule.email_notification, rule.sms_notification, rule.webhook_notification,
                        rule.dingtalk_notification, rule.desktop_notification, rule.sound_notification,
                        rule.email_recipients, rule.sms_recipients, rule.webhook_url, rule.dingtalk_webhook_url,
                        rule.message_template, rule.updated_at, rule.id
                    ))
                    rule_id = rule.id
                else:
                    # 插入新规则
                    rule.created_at = rule.updated_at
                    cursor.execute("""
                        INSERT INTO alert_rules (
                            name, rule_type, priority, enabled, description,
                            metric_name, operator, threshold_value, threshold_unit, duration,
                            check_interval, silence_period, max_alerts,
                            email_notification, sms_notification, webhook_notification, dingtalk_notification, desktop_notification,
                            sound_notification, email_recipients, sms_recipients, webhook_url, dingtalk_webhook_url,
                            message_template, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        rule.name, rule.rule_type, rule.priority, rule.enabled, rule.description,
                        rule.metric_name, rule.operator, rule.threshold_value, rule.threshold_unit,
                        rule.duration, rule.check_interval, rule.silence_period, rule.max_alerts,
                        rule.email_notification, rule.sms_notification, rule.webhook_notification,
                        rule.dingtalk_notification, rule.desktop_notification, rule.sound_notification,
                        rule.email_recipients, rule.sms_recipients, rule.webhook_url, rule.dingtalk_webhook_url,
                        rule.message_template, rule.created_at, rule.updated_at
                    ))
                    rule_id = cursor.lastrowid

                conn.commit()
                logger.info(f"告警规则保存成功，ID: {rule_id}")
                return rule_id

        except Exception as e:
            logger.error(f"保存告警规则失败: {e}")
            return None

    def load_alert_rules(self) -> List[AlertRule]:
        """加载所有告警规则"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM alert_rules ORDER BY created_at DESC")
                rows = cursor.fetchall()

                rules = []
                columns = [description[0] for description in cursor.description]

                for row in rows:
                    rule_dict = dict(zip(columns, row))
                    rules.append(AlertRule(**rule_dict))

                return rules

        except Exception as e:
            logger.error(f"加载告警规则失败: {e}")
            return []

    def delete_alert_rule(self, rule_id: int) -> bool:
        """删除告警规则"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM alert_rules WHERE id=?", (rule_id,))
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"告警规则删除成功，ID: {rule_id}")
                    return True
                else:
                    logger.warning(f"未找到要删除的告警规则，ID: {rule_id}")
                    return False

        except Exception as e:
            logger.error(f"删除告警规则失败: {e}")
            return False

    # ==================== 告警历史管理 ====================

    def save_alert_history(self, history: AlertHistory) -> Optional[int]:
        """保存告警历史"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if not history.timestamp:
                    history.timestamp = datetime.now().isoformat()

                cursor.execute("""
                    INSERT INTO alert_history (
                        timestamp, level, category, message, status, rule_id,
                        metric_name, current_value, threshold_value, recommendation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    history.timestamp, history.level, history.category, history.message,
                    history.status, history.rule_id, history.metric_name, history.current_value,
                    history.threshold_value, history.recommendation
                ))

                history_id = cursor.lastrowid
                conn.commit()
                logger.info(f"告警历史保存成功，ID: {history_id}")
                return history_id

        except Exception as e:
            logger.error(f"保存告警历史失败: {e}")
            return None

    def load_alert_history(self, limit: int = 100, hours: int = 24) -> List[AlertHistory]:
        """加载告警历史"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 计算时间范围
                from datetime import datetime, timedelta
                cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()

                cursor.execute("""
                    SELECT * FROM alert_history 
                    WHERE timestamp >= ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (cutoff_time, limit))

                rows = cursor.fetchall()

                history_list = []
                columns = [description[0] for description in cursor.description]

                for row in rows:
                    history_dict = dict(zip(columns, row))
                    history_list.append(AlertHistory(**history_dict))

                return history_list

        except Exception as e:
            logger.error(f"加载告警历史失败: {e}")
            return []

    def save_risk_history(self, record: RiskHistoryRecord) -> Optional[int]:
        """保存风险历史记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if not record.timestamp:
                    record.timestamp = datetime.now().isoformat()

                cursor.execute("""
                    INSERT INTO risk_history (
                        timestamp, overall_risk_score, risk_level, var_95,
                        max_drawdown, volatility, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.timestamp, record.overall_risk_score, record.risk_level,
                    record.var_95, record.max_drawdown, record.volatility, record.status
                ))

                record_id = cursor.lastrowid
                conn.commit()
                logger.info(f"风险历史记录保存成功，ID: {record_id}")
                return record_id

        except Exception as e:
            logger.error(f"保存风险历史记录失败: {e}")
            return None

    def load_risk_history(self, limit: int = 100, hours: int = 24) -> List[RiskHistoryRecord]:
        """加载风险历史记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 构建查询条件
                query = "SELECT * FROM risk_history"
                params = []

                if hours:
                    from datetime import datetime, timedelta
                    cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
                    query += " WHERE timestamp >= ?"
                    params.append(cutoff_time)

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                history_list = []
                columns = [description[0] for description in cursor.description]

                for row in rows:
                    history_dict = dict(zip(columns, row))
                    history_list.append(RiskHistoryRecord(**history_dict))

                return history_list

        except Exception as e:
            logger.error(f"加载风险历史记录失败: {e}")
            return []

    def clear_alert_history(self, hours: int = None) -> bool:
        """清空告警历史"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if hours:
                    # 只删除指定时间之前的记录
                    from datetime import datetime, timedelta
                    cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
                    cursor.execute("DELETE FROM alert_history WHERE timestamp < ?", (cutoff_time,))
                else:
                    # 删除所有记录
                    cursor.execute("DELETE FROM alert_history")

                deleted_count = cursor.rowcount
                conn.commit()
                logger.info(f"告警历史清空成功，删除 {deleted_count} 条记录")
                return True

        except Exception as e:
            logger.error(f"清空告警历史失败: {e}")
            return False

    # ==================== 数据迁移 ====================

    def migrate_from_json_config(self, config_file_path: str) -> bool:
        """从JSON配置文件迁移数据到数据库"""
        try:
            import os
            if not os.path.exists(config_file_path):
                logger.info(f"配置文件不存在，跳过迁移: {config_file_path}")
                return True

            with open(config_file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # 迁移通知配置
            if 'notifications' in config_data:
                notifications = config_data['notifications']
                notification_config = NotificationConfig(**notifications)
                self.save_notification_config(notification_config)
                logger.info("通知配置迁移完成")

            # 迁移告警规则
            if 'rules' in config_data:
                rules = config_data['rules']
                for rule_data in rules:
                    # 转换规则数据格式
                    alert_rule = AlertRule(
                        name=rule_data.get('name', ''),
                        rule_type=rule_data.get('type', '系统资源'),
                        priority=rule_data.get('priority', '中等'),
                        enabled=rule_data.get('enabled', True),
                        description=rule_data.get('description', ''),
                        # 从conditions中提取触发条件
                        metric_name=rule_data.get('conditions', {}).get('metric_name', ''),
                        operator=rule_data.get('conditions', {}).get('operator', '>'),
                        threshold_value=rule_data.get('conditions', {}).get('threshold_value', 0.0),
                        threshold_unit=rule_data.get('conditions', {}).get('threshold_unit', '%'),
                        duration=rule_data.get('conditions', {}).get('duration', 60),
                        # 从notifications中提取通知设置
                        email_notification=rule_data.get('notifications', {}).get('email', True),
                        sms_notification=rule_data.get('notifications', {}).get('sms', False),
                        desktop_notification=rule_data.get('notifications', {}).get('desktop', True),
                        sound_notification=rule_data.get('notifications', {}).get('sound', True),
                        message_template=rule_data.get('notifications', {}).get('message_template', '')
                    )
                    self.save_alert_rule(alert_rule)

                logger.info(f"告警规则迁移完成，共 {len(rules)} 条规则")

            logger.info("配置文件迁移完成")
            return True

        except Exception as e:
            logger.error(f"配置文件迁移失败: {e}")
            return False

# 全局数据库实例
_alert_config_db = None

def get_alert_config_database() -> AlertConfigDatabase:
    """获取告警配置数据库实例（单例模式）"""
    global _alert_config_db
    if _alert_config_db is None:
        _alert_config_db = AlertConfigDatabase()
    return _alert_config_db
