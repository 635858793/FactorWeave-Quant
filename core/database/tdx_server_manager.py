"""
TDX服务器数据库管理器
负责TDX服务器信息的数据库存储和管理
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json

logger = logging.getLogger(__name__)

class TdxServerDatabaseManager:
    """TDX服务器数据库管理器"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            # 默认数据库路径
            db_path = Path.cwd() / "data" / "tdx_servers.sqlite"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_database()

    def _init_database(self):
        """初始化数据库表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 创建服务器信息表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tdx_servers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        host TEXT NOT NULL,
                        port INTEGER NOT NULL,
                        status TEXT DEFAULT 'unknown',
                        response_time REAL,
                        location TEXT,
                        source TEXT DEFAULT 'manual',
                        last_tested TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1,
                        priority INTEGER DEFAULT 0,
                        notes TEXT,
                        UNIQUE(host, port)
                    )
                """)

                # 创建服务器使用统计表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tdx_server_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        server_id INTEGER,
                        connection_count INTEGER DEFAULT 0,
                        success_count INTEGER DEFAULT 0,
                        failure_count INTEGER DEFAULT 0,
                        total_response_time REAL DEFAULT 0,
                        avg_response_time REAL DEFAULT 0,
                        last_used TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (server_id) REFERENCES tdx_servers (id)
                    )
                """)

                # 创建索引
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_tdx_servers_status ON tdx_servers(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_tdx_servers_response_time ON tdx_servers(response_time)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_tdx_servers_location ON tdx_servers(location)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_tdx_servers_priority ON tdx_servers(priority)")

                conn.commit()
                logger.info("TDX服务器数据库初始化完成")

        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise

    def save_tdx_server(self, host: str, port: int, status: str = 'unknown',
                        response_time: float = None, location: str = None,
                        source: str = 'manual', last_tested: str = None,
                        priority: int = 0, notes: str = None) -> bool:
        """
        保存TDX服务器信息

        Args:
            host: 服务器地址
            port: 端口
            status: 状态 (available, unavailable, unknown, error)
            response_time: 响应时间(毫秒)
            location: 地理位置
            source: 数据源 (manual, builtin, online)
            last_tested: 最后测试时间
            priority: 优先级 (数字越大优先级越高)
            notes: 备注信息

        Returns:
            是否保存成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 使用UPSERT语法（INSERT OR REPLACE）
                cursor.execute("""
                    INSERT OR REPLACE INTO tdx_servers 
                    (host, port, status, response_time, location, source, 
                     last_tested, priority, notes, updated_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (
                    host, port, status, response_time, location, source,
                    last_tested or datetime.now().isoformat(),
                    priority, notes, datetime.now().isoformat()
                ))

                server_id = cursor.lastrowid

                # 初始化统计信息（如果不存在）
                cursor.execute("""
                    INSERT OR IGNORE INTO tdx_server_stats (server_id)
                    VALUES (?)
                """, (server_id,))

                conn.commit()
                logger.debug(f"保存TDX服务器成功: {host}:{port}")
                return True

        except Exception as e:
            logger.error(f"保存TDX服务器失败 {host}:{port}: {e}")
            return False

    def get_all_servers(self, active_only: bool = True) -> List[Dict]:
        """
        获取所有服务器列表

        Args:
            active_only: 是否只返回活跃的服务器

        Returns:
            服务器列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                query = """
                    SELECT s.*, st.connection_count, st.success_count, 
                           st.failure_count, st.avg_response_time, st.last_used
                    FROM tdx_servers s
                    LEFT JOIN tdx_server_stats st ON s.id = st.server_id
                """

                if active_only:
                    query += " WHERE s.is_active = 1"

                query += " ORDER BY s.priority DESC, s.response_time ASC"

                cursor.execute(query)
                rows = cursor.fetchall()

                # 转换为字典列表
                columns = [description[0] for description in cursor.description]
                servers = []

                for row in rows:
                    server = dict(zip(columns, row))
                    servers.append(server)

                return servers

        except Exception as e:
            logger.error(f"获取服务器列表失败: {e}")
            return []

    def get_available_servers(self, limit: int = None) -> List[Dict]:
        """
        获取可用的服务器列表

        Args:
            limit: 限制返回数量

        Returns:
            可用服务器列表，按响应时间排序
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                query = """
                    SELECT s.*, st.avg_response_time, st.success_count
                    FROM tdx_servers s
                    LEFT JOIN tdx_server_stats st ON s.id = st.server_id
                    WHERE s.status = 'available' AND s.is_active = 1
                    ORDER BY s.priority DESC, 
                             COALESCE(s.response_time, st.avg_response_time, 999) ASC
                """

                if limit:
                    query += f" LIMIT {limit}"

                cursor.execute(query)
                rows = cursor.fetchall()

                columns = [description[0] for description in cursor.description]
                servers = [dict(zip(columns, row)) for row in rows]

                return servers

        except Exception as e:
            logger.error(f"获取可用服务器失败: {e}")
            return []

    def get_fastest_servers(self, limit: int = 5) -> List[Dict]:
        """获取最快的服务器"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT s.*, st.avg_response_time
                    FROM tdx_servers s
                    LEFT JOIN tdx_server_stats st ON s.id = st.server_id
                    WHERE s.status = 'available' AND s.is_active = 1
                    AND (s.response_time IS NOT NULL OR st.avg_response_time IS NOT NULL)
                    ORDER BY COALESCE(s.response_time, st.avg_response_time) ASC
                    LIMIT ?
                """, (limit,))

                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]

                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"获取最快服务器失败: {e}")
            return []

    def update_server_status(self, host: str, port: int, status: str,
                             response_time: float = None) -> bool:
        """更新服务器状态"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE tdx_servers 
                    SET status = ?, response_time = ?, 
                        last_tested = ?, updated_at = ?
                    WHERE host = ? AND port = ?
                """, (
                    status, response_time,
                    datetime.now().isoformat(), datetime.now().isoformat(),
                    host, port
                ))

                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"更新服务器状态失败 {host}:{port}: {e}")
            return False

    def record_connection_attempt(self, host: str, port: int, success: bool,
                                  response_time: float = None) -> bool:
        """记录连接尝试统计"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 获取服务器ID
                cursor.execute("SELECT id FROM tdx_servers WHERE host = ? AND port = ?", (host, port))
                result = cursor.fetchone()

                if not result:
                    logger.warning(f"服务器不存在: {host}:{port}")
                    return False

                server_id = result[0]

                # 更新统计信息
                cursor.execute("""
                    INSERT OR REPLACE INTO tdx_server_stats 
                    (server_id, connection_count, success_count, failure_count,
                     total_response_time, avg_response_time, last_used, updated_at)
                    SELECT 
                        ?,
                        COALESCE(connection_count, 0) + 1,
                        COALESCE(success_count, 0) + ?,
                        COALESCE(failure_count, 0) + ?,
                        COALESCE(total_response_time, 0) + ?,
                        CASE 
                            WHEN ? > 0 THEN (COALESCE(total_response_time, 0) + ?) / (COALESCE(connection_count, 0) + 1)
                            ELSE avg_response_time
                        END,
                        ?,
                        ?
                    FROM (
                        SELECT * FROM tdx_server_stats WHERE server_id = ?
                        UNION ALL
                        SELECT ?, 0, 0, 0, 0, 0, NULL, NULL, NULL WHERE NOT EXISTS (
                            SELECT 1 FROM tdx_server_stats WHERE server_id = ?
                        )
                    ) LIMIT 1
                """, (
                    server_id,
                    1 if success else 0,  # success_count增量
                    0 if success else 1,  # failure_count增量
                    response_time or 0,   # total_response_time增量
                    response_time or 0,   # 用于计算平均值的条件
                    response_time or 0,   # 用于计算平均值
                    datetime.now().isoformat(),  # last_used
                    datetime.now().isoformat(),  # updated_at
                    server_id,  # 子查询中的server_id
                    server_id,  # UNION ALL中的server_id
                    server_id   # NOT EXISTS中的server_id
                ))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"记录连接统计失败 {host}:{port}: {e}")
            return False

    def delete_server(self, host: str, port: int) -> bool:
        """删除服务器"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 获取服务器ID
                cursor.execute("SELECT id FROM tdx_servers WHERE host = ? AND port = ?", (host, port))
                result = cursor.fetchone()

                if not result:
                    return False

                server_id = result[0]

                # 删除统计信息
                cursor.execute("DELETE FROM tdx_server_stats WHERE server_id = ?", (server_id,))

                # 删除服务器
                cursor.execute("DELETE FROM tdx_servers WHERE id = ?", (server_id,))

                conn.commit()
                logger.info(f"删除服务器成功: {host}:{port}")
                return True

        except Exception as e:
            logger.error(f"删除服务器失败 {host}:{port}: {e}")
            return False

    def set_server_priority(self, host: str, port: int, priority: int) -> bool:
        """设置服务器优先级"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE tdx_servers 
                    SET priority = ?, updated_at = ?
                    WHERE host = ? AND port = ?
                """, (priority, datetime.now().isoformat(), host, port))

                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"设置服务器优先级失败 {host}:{port}: {e}")
            return False

    def deactivate_server(self, host: str, port: int) -> bool:
        """停用服务器（软删除）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE tdx_servers 
                    SET is_active = 0, updated_at = ?
                    WHERE host = ? AND port = ?
                """, (datetime.now().isoformat(), host, port))

                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"停用服务器失败 {host}:{port}: {e}")
            return False

    def get_server_statistics(self) -> Dict:
        """获取服务器统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 总体统计
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_servers,
                        SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available_servers,
                        SUM(CASE WHEN status = 'unavailable' THEN 1 ELSE 0 END) as unavailable_servers,
                        SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_servers,
                        AVG(response_time) as avg_response_time,
                        MIN(response_time) as min_response_time,
                        MAX(response_time) as max_response_time
                    FROM tdx_servers
                """)

                stats = dict(zip([d[0] for d in cursor.description], cursor.fetchone()))

                # 按地区统计
                cursor.execute("""
                    SELECT location, COUNT(*) as count,
                           SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available_count
                    FROM tdx_servers
                    WHERE location IS NOT NULL
                    GROUP BY location
                    ORDER BY available_count DESC
                """)

                location_stats = []
                for row in cursor.fetchall():
                    location_stats.append({
                        'location': row[0],
                        'total': row[1],
                        'available': row[2]
                    })

                stats['location_stats'] = location_stats

                return stats

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

    def export_servers(self, file_path: str) -> bool:
        """导出服务器列表到JSON文件"""
        try:
            servers = self.get_all_servers(active_only=False)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(servers, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"服务器列表导出成功: {file_path}")
            return True

        except Exception as e:
            logger.error(f"导出服务器列表失败: {e}")
            return False

    def import_servers(self, file_path: str) -> int:
        """从JSON文件导入服务器列表"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                servers = json.load(f)

            imported_count = 0
            for server in servers:
                success = self.save_tdx_server(
                    host=server.get('host'),
                    port=server.get('port'),
                    status=server.get('status', 'unknown'),
                    response_time=server.get('response_time'),
                    location=server.get('location'),
                    source=server.get('source', 'imported'),
                    priority=server.get('priority', 0),
                    notes=server.get('notes')
                )
                if success:
                    imported_count += 1

            logger.info(f"服务器列表导入完成: {imported_count}/{len(servers)}")
            return imported_count

        except Exception as e:
            logger.error(f"导入服务器列表失败: {e}")
            return 0

# 全局数据库管理器实例
_db_manager = None

def get_tdx_db_manager() -> TdxServerDatabaseManager:
    """获取TDX服务器数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = TdxServerDatabaseManager()
    return _db_manager
