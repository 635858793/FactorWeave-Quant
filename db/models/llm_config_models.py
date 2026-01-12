"""
LLM配置数据库模型

用于在数据库中存储和管理LLM配置
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from cryptography.fernet import Fernet
from loguru import logger


class LLMConfigManager:
    """LLM配置管理器"""

    def __init__(self, db_path: str = "data/factorweave_system.sqlite", key_path: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            db_path: 数据库路径
            key_path: 加密密钥文件路径，如果为None则使用默认路径
        """
        self.db_path = db_path
        self._key_path = key_path
        self._init_database()
        self._init_encryption()

    def _init_database(self):
        """初始化数据库表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 创建LLM配置表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS llm_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        provider TEXT UNIQUE NOT NULL,
                        api_key_encrypted TEXT NOT NULL,
                        api_secret_encrypted TEXT,
                        base_url TEXT,
                        model TEXT NOT NULL,
                        temperature REAL NOT NULL DEFAULT 0.7,
                        max_tokens INTEGER NOT NULL DEFAULT 2000,
                        timeout INTEGER NOT NULL DEFAULT 30,
                        enabled BOOLEAN DEFAULT 1,
                        proxy TEXT,
                        extra_params TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)

                # 创建LLM全局配置表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS llm_global_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_key TEXT UNIQUE NOT NULL,
                        config_value TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)

                # 创建LLM配置历史表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS llm_config_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        provider TEXT NOT NULL,
                        old_config TEXT,
                        new_config TEXT,
                        changed_by TEXT DEFAULT 'system',
                        changed_at TEXT NOT NULL,
                        operation TEXT NOT NULL
                    )
                """)

                conn.commit()
                logger.info("LLM配置数据库表初始化完成")

        except Exception as e:
            logger.error(f"初始化LLM配置数据库失败: {e}")
            logger.warning("🗄️ LLM配置数据库文件缺失或无法访问")
            logger.info("💡 系统将使用默认配置运行")
            logger.info("📁 数据库文件将在首次使用时自动创建")
            raise

    def _init_encryption(self):
        """初始化加密"""
        try:
            key_file = Path(self._key_path) if self._key_path else Path("config/.llm_key")
            
            if key_file.exists():
                with open(key_file, 'rb') as f:
                    key = f.read()
            else:
                key = Fernet.generate_key()
                key_file.parent.mkdir(parents=True, exist_ok=True)
                with open(key_file, 'wb') as f:
                    f.write(key)
                logger.info("LLM加密密钥已生成")
            
            self.cipher = Fernet(key)
            logger.debug("LLM加密初始化成功")

        except Exception as e:
            logger.error(f"初始化LLM加密失败: {e}")
            raise

    def _safe_json_loads(self, json_str: Optional[str]) -> Any:
        """安全的JSON解析，处理空字符串和None"""
        if not json_str or not json_str.strip():
            return {}
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}, 使用空字典")
            return {}

    def _encrypt(self, data: str) -> str:
        """加密数据"""
        try:
            if not data:
                return ""
            encrypted = self.cipher.encrypt(data.encode('utf-8'))
            return encrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"加密失败: {e}")
            raise

    def _decrypt(self, encrypted_data: str) -> str:
        """解密数据"""
        try:
            if not encrypted_data:
                return ""
            decrypted = self.cipher.decrypt(encrypted_data.encode('utf-8'))
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"解密失败: {e}")
            raise

    def save_config(self, config: Dict[str, Any], changed_by: str = "user") -> bool:
        """
        保存LLM配置

        Args:
            config: 配置字典
            changed_by: 修改者

        Returns:
            是否成功
        """
        try:
            provider = config.get('provider')
            if not provider:
                raise ValueError("provider不能为空")

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 获取旧配置
                cursor.execute("SELECT * FROM llm_config WHERE provider = ?", (provider,))
                old_row = cursor.fetchone()

                current_time = datetime.now().isoformat()

                # 加密敏感信息
                api_key_encrypted = self._encrypt(config.get('api_key', ''))
                api_secret_encrypted = self._encrypt(config.get('api_secret', '')) if config.get('api_secret') else None

                # 序列化额外参数 - 确保空字典也被序列化
                extra_params = config.get('extra_params')
                if extra_params is None:
                    extra_params_json = None
                else:
                    extra_params_json = json.dumps(extra_params, ensure_ascii=False)

                if old_row:
                    # 记录历史
                    old_config = {
                        'provider': old_row[1],
                        'base_url': old_row[3],
                        'model': old_row[4],
                        'temperature': old_row[5],
                        'max_tokens': old_row[6],
                        'timeout': old_row[7],
                        'enabled': bool(old_row[8]),
                        'proxy': old_row[9],
                        'extra_params': self._safe_json_loads(old_row[10])
                    }
                    cursor.execute("""
                        INSERT INTO llm_config_history (provider, old_config, new_config, changed_by, changed_at, operation)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (provider, json.dumps(old_config, ensure_ascii=False), json.dumps(config, ensure_ascii=False), changed_by, current_time, 'update'))

                    # 更新配置
                    cursor.execute("""
                        UPDATE llm_config 
                        SET api_key_encrypted = ?, api_secret_encrypted = ?, base_url = ?, model = ?,
                            temperature = ?, max_tokens = ?, timeout = ?, enabled = ?, proxy = ?, extra_params = ?, updated_at = ?
                        WHERE provider = ?
                    """, (
                        api_key_encrypted, api_secret_encrypted, config.get('base_url'), config.get('model'),
                        config.get('temperature', 0.7), config.get('max_tokens', 2000), config.get('timeout', 30),
                        1 if config.get('enabled', True) else 0, config.get('proxy'), extra_params_json, current_time, provider
                    ))
                else:
                    # 记录历史
                    cursor.execute("""
                        INSERT INTO llm_config_history (provider, old_config, new_config, changed_by, changed_at, operation)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (provider, None, json.dumps(config, ensure_ascii=False), changed_by, current_time, 'create'))

                    # 插入新配置
                    cursor.execute("""
                        INSERT INTO llm_config 
                        (provider, api_key_encrypted, api_secret_encrypted, base_url, model, temperature, max_tokens, timeout, enabled, proxy, extra_params, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        provider, api_key_encrypted, api_secret_encrypted, config.get('base_url'), config.get('model'),
                        config.get('temperature', 0.7), config.get('max_tokens', 2000), config.get('timeout', 30),
                        1 if config.get('enabled', True) else 0, config.get('proxy'), extra_params_json, current_time, current_time
                    ))

                conn.commit()
                logger.info(f"LLM配置 {provider} 已保存")
                return True

        except Exception as e:
            logger.error(f"保存LLM配置失败: {e}", exc_info=True)
            raise  # 抛出异常而不是返回 False

    def get_config(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        获取LLM配置

        Args:
            provider: 提供商名称

        Returns:
            配置字典，如果不存在返回None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT provider, api_key_encrypted, api_secret_encrypted, base_url, model, temperature, max_tokens, timeout, enabled, proxy, extra_params
                    FROM llm_config 
                    WHERE provider = ?
                """, (provider,))

                row = cursor.fetchone()
                if row:
                    return {
                        'provider': row[0],
                        'api_key': self._decrypt(row[1]),
                        'api_secret': self._decrypt(row[2]) if row[2] else None,
                        'base_url': row[3],
                        'model': row[4],
                        'temperature': row[5],
                        'max_tokens': row[6],
                        'timeout': row[7],
                        'enabled': bool(row[8]),
                        'proxy': row[9],
                        'extra_params': self._safe_json_loads(row[10])
                    }
                return None

        except Exception as e:
            logger.error(f"获取LLM配置失败: {e}")
            return None

    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有LLM配置

        Returns:
            配置字典
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT provider, api_key_encrypted, api_secret_encrypted, base_url, model, temperature, max_tokens, timeout, enabled, proxy, extra_params
                    FROM llm_config
                """)

                configs = {}
                for row in cursor.fetchall():
                    provider = row[0]
                    configs[provider] = {
                        'provider': provider,
                        'api_key': self._decrypt(row[1]),
                        'api_secret': self._decrypt(row[2]) if row[2] else None,
                        'base_url': row[3],
                        'model': row[4],
                        'temperature': row[5],
                        'max_tokens': row[6],
                        'timeout': row[7],
                        'enabled': bool(row[8]),
                        'proxy': row[9],
                        'extra_params': self._safe_json_loads(row[10])
                    }

                return configs

        except Exception as e:
            logger.error(f"获取所有LLM配置失败: {e}")
            return {}

    def delete_config(self, provider: str, changed_by: str = "user") -> bool:
        """
        删除LLM配置

        Args:
            provider: 提供商名称
            changed_by: 修改者

        Returns:
            是否成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 获取旧配置
                cursor.execute("SELECT * FROM llm_config WHERE provider = ?", (provider,))
                old_row = cursor.fetchone()

                if old_row:
                    # 记录历史
                    old_config = {
                        'provider': old_row[1],
                        'base_url': old_row[3],
                        'model': old_row[4],
                        'temperature': old_row[5],
                        'max_tokens': old_row[6],
                        'timeout': old_row[7],
                        'enabled': bool(old_row[8]),
                        'proxy': old_row[9],
                        'extra_params': self._safe_json_loads(old_row[10])
                    }
                    current_time = datetime.now().isoformat()
                    cursor.execute("""
                        INSERT INTO llm_config_history (provider, old_config, new_config, changed_by, changed_at, operation)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (provider, json.dumps(old_config, ensure_ascii=False), None, changed_by, current_time, 'delete'))

                    # 删除配置
                    cursor.execute("DELETE FROM llm_config WHERE provider = ?", (provider,))
                    conn.commit()
                    logger.info(f"LLM配置 {provider} 已删除")
                    return True
                else:
                    logger.warning(f"LLM配置 {provider} 不存在")
                    return False

        except Exception as e:
            logger.error(f"删除LLM配置失败: {e}")
            return False

    def get_config_history(self, provider: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取配置历史

        Args:
            provider: 提供商名称，None表示获取所有配置的历史
            limit: 限制返回数量

        Returns:
            历史记录列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if provider:
                    cursor.execute("""
                        SELECT provider, old_config, new_config, changed_by, changed_at, operation
                        FROM llm_config_history 
                        WHERE provider = ?
                        ORDER BY changed_at DESC
                        LIMIT ?
                    """, (provider, limit))
                else:
                    cursor.execute("""
                        SELECT provider, old_config, new_config, changed_by, changed_at, operation
                        FROM llm_config_history 
                        ORDER BY changed_at DESC
                        LIMIT ?
                    """, (limit,))

                history = []
                for row in cursor.fetchall():
                    history.append({
                        'provider': row[0],
                        'old_config': self._safe_json_loads(row[1]) if row[1] else None,
                        'new_config': self._safe_json_loads(row[2]) if row[2] else None,
                        'changed_by': row[3],
                        'changed_at': row[4],
                        'operation': row[5]
                    })

                return history

        except Exception as e:
            logger.error(f"获取配置历史失败: {e}")
            return []

    def get_current_provider(self) -> Optional[str]:
        """
        获取当前提供商

        Returns:
            当前提供商名称，如果未设置返回None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT config_value FROM llm_global_config 
                    WHERE config_key = 'current_provider'
                """)

                row = cursor.fetchone()
                if row:
                    return row[0]
                return None

        except Exception as e:
            logger.error(f"获取当前提供商失败: {e}")
            return None

    def set_current_provider(self, provider: str) -> bool:
        """
        设置当前提供商

        Args:
            provider: 提供商名称

        Returns:
            是否成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                current_time = datetime.now().isoformat()

                # 检查是否存在
                cursor.execute("SELECT config_value FROM llm_global_config WHERE config_key = 'current_provider'")
                existing = cursor.fetchone()

                if existing:
                    # 更新
                    cursor.execute("""
                        UPDATE llm_global_config 
                        SET config_value = ?, updated_at = ?
                        WHERE config_key = 'current_provider'
                    """, (provider, current_time))
                else:
                    # 插入
                    cursor.execute("""
                        INSERT INTO llm_global_config (config_key, config_value, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                    """, ('current_provider', provider, current_time, current_time))

                conn.commit()
                logger.info(f"当前提供商已设置为 {provider}")
                return True

        except Exception as e:
            logger.error(f"设置当前提供商失败: {e}")
            return False

    def get_enabled_providers(self) -> List[str]:
        """
        获取已启用的提供商列表

        Returns:
            提供商名称列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT provider FROM llm_config WHERE enabled = 1
                """)

                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"获取已启用的提供商失败: {e}")
            return []

    def export_config(self, file_path: str) -> bool:
        """
        导出配置到文件

        Args:
            file_path: 文件路径

        Returns:
            是否成功
        """
        try:
            configs = self.get_all_configs()
            current_provider = self.get_current_provider()
            
            export_data = {
                'current_provider': current_provider,
                'providers': configs
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"LLM配置已导出到: {file_path}")
            return True

        except Exception as e:
            logger.error(f"导出LLM配置失败: {e}")
            return False

    def import_config(self, file_path: str, changed_by: str = "import") -> bool:
        """
        从文件导入配置

        Args:
            file_path: 文件路径
            changed_by: 修改者

        Returns:
            是否成功
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            # 导入提供商配置
            if 'providers' in import_data:
                for provider, config in import_data['providers'].items():
                    self.save_config(config, changed_by)

            # 设置当前提供商
            if 'current_provider' in import_data:
                self.set_current_provider(import_data['current_provider'])

            logger.info(f"LLM配置已从 {file_path} 导入")
            return True

        except Exception as e:
            logger.error(f"导入LLM配置失败: {e}")
            return False


# 全局配置管理器实例
_config_manager = None

def get_llm_config_manager() -> LLMConfigManager:
    """获取全局LLM配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = LLMConfigManager()
    return _config_manager
