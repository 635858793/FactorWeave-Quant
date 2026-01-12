"""
数据库迁移脚本 - 添加资产类型支持

为推荐相关表添加 asset_type 字段，支持多资产类型推荐。

作者: FactorWeave-Quant 开发团队
版本: 1.0
日期: 2025-01-11
"""

import sqlite3
import duckdb
from pathlib import Path
from loguru import logger
from typing import Optional


class AssetTypeMigration:
    """资产类型迁移类"""

    def __init__(self, db_path: str = None):
        """
        初始化迁移

        Args:
            db_path: 数据库路径，如果为None则使用默认路径
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "hikyuu_ui.db"
        
        self.db_path = Path(db_path)
        self.duckdb_path = Path(__file__).parent.parent / "data" / "analytics.duckdb"

    def migrate_sqlite_tables(self):
        """迁移 SQLite 表（user_preferences, user_feedback）"""
        try:
            logger.info("开始迁移 SQLite 表...")

            if not self.db_path.exists():
                logger.warning(f"数据库文件不存在: {self.db_path}")
                return

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # 迁移 user_preferences 表
            self._migrate_user_preferences_table(cursor)

            # 迁移 user_feedback 表
            self._migrate_user_feedback_table(cursor)

            conn.commit()
            conn.close()

            logger.info("SQLite 表迁移完成")

        except Exception as e:
            logger.error(f"迁移 SQLite 表失败: {e}")
            raise

    def migrate_duckdb_tables(self):
        """迁移 DuckDB 表（ai_selection_results, ai_explanations, user_profiles）"""
        try:
            logger.info("开始迁移 DuckDB 表...")

            if not self.duckdb_path.exists():
                logger.warning(f"DuckDB 数据库文件不存在: {self.duckdb_path}")
                return

            conn = duckdb.connect(str(self.duckdb_path))

            # 迁移 ai_selection_results 表
            self._migrate_ai_selection_results_table(conn)

            # 迁移 ai_explanations 表
            self._migrate_ai_explanations_table(conn)

            # 迁移 user_profiles 表
            self._migrate_user_profiles_table(conn)

            conn.close()

            logger.info("DuckDB 表迁移完成")

        except Exception as e:
            logger.error(f"迁移 DuckDB 表失败: {e}")
            raise

    def _migrate_user_preferences_table(self, cursor: sqlite3.Cursor):
        """迁移 user_preferences 表"""
        try:
            # 检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")
            if not cursor.fetchone():
                logger.info("user_preferences 表不存在，跳过迁移")
                return

            # 检查是否已有 asset_type 字段
            cursor.execute("PRAGMA table_info(user_preferences)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'asset_type' in columns:
                logger.info("user_preferences 表已有 asset_type 字段，跳过迁移")
                return

            # 添加 asset_type 字段
            logger.info("为 user_preferences 表添加 asset_type 字段")
            cursor.execute("ALTER TABLE user_preferences ADD COLUMN asset_type VARCHAR(50) DEFAULT 'stock_a'")

            # 更新现有记录的 asset_type
            logger.info("更新 user_preferences 表现有记录的 asset_type")
            cursor.execute("UPDATE user_preferences SET asset_type = 'stock_a' WHERE asset_type IS NULL")

            # 创建索引
            logger.info("为 user_preferences 表创建索引")
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_preferences_asset_type ON user_preferences(asset_type)")
            except Exception as e:
                logger.warning(f"创建索引失败（可能已存在）: {e}")

            logger.info("user_preferences 表迁移完成")

        except Exception as e:
            logger.error(f"迁移 user_preferences 表失败: {e}")
            raise

    def _migrate_user_feedback_table(self, cursor: sqlite3.Cursor):
        """迁移 user_feedback 表"""
        try:
            # 检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_feedback'")
            if not cursor.fetchone():
                logger.info("user_feedback 表不存在，跳过迁移")
                return

            # 检查是否已有 asset_type 字段
            cursor.execute("PRAGMA table_info(user_feedback)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'asset_type' in columns:
                logger.info("user_feedback 表已有 asset_type 字段，跳过迁移")
                return

            # 添加 asset_type 字段
            logger.info("为 user_feedback 表添加 asset_type 字段")
            cursor.execute("ALTER TABLE user_feedback ADD COLUMN asset_type VARCHAR(50) DEFAULT 'stock_a'")

            # 更新现有记录的 asset_type
            logger.info("更新 user_feedback 表现有记录的 asset_type")
            cursor.execute("UPDATE user_feedback SET asset_type = 'stock_a' WHERE asset_type IS NULL")

            # 创建索引
            logger.info("为 user_feedback 表创建索引")
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_feedback_asset_type ON user_feedback(asset_type)")
            except Exception as e:
                logger.warning(f"创建索引失败（可能已存在）: {e}")

            logger.info("user_feedback 表迁移完成")

        except Exception as e:
            logger.error(f"迁移 user_feedback 表失败: {e}")
            raise

    def _migrate_ai_selection_results_table(self, conn: duckdb.DuckDBPyConnection):
        """迁移 ai_selection_results 表"""
        try:
            # 检查表是否存在
            result = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_name = 'ai_selection_results'")
            if not result.fetchone():
                logger.info("ai_selection_results 表不存在，跳过迁移")
                return

            # 检查是否已有 asset_type 字段
            result = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'ai_selection_results' AND column_name = 'asset_type'")
            if result.fetchone():
                logger.info("ai_selection_results 表已有 asset_type 字段，跳过迁移")
                return

            # 添加 asset_type 字段
            logger.info("为 ai_selection_results 表添加 asset_type 字段")
            conn.execute("ALTER TABLE ai_selection_results ADD COLUMN asset_type VARCHAR(50) DEFAULT 'stock_a'")

            # 更新现有记录的 asset_type
            logger.info("更新 ai_selection_results 表现有记录的 asset_type")
            conn.execute("UPDATE ai_selection_results SET asset_type = 'stock_a' WHERE asset_type IS NULL")

            # 创建索引
            logger.info("为 ai_selection_results 表创建索引")
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_results_asset_type ON ai_selection_results(asset_type)")
            except Exception as e:
                logger.warning(f"创建索引失败（可能已存在）: {e}")

            logger.info("ai_selection_results 表迁移完成")

        except Exception as e:
            logger.error(f"迁移 ai_selection_results 表失败: {e}")
            raise

    def _migrate_ai_explanations_table(self, conn: duckdb.DuckDBPyConnection):
        """迁移 ai_explanations 表"""
        try:
            # 检查表是否存在
            result = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_name = 'ai_explanations'")
            if not result.fetchone():
                logger.info("ai_explanations 表不存在，跳过迁移")
                return

            # 检查是否已有 asset_type 字段
            result = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'ai_explanations' AND column_name = 'asset_type'")
            if result.fetchone():
                logger.info("ai_explanations 表已有 asset_type 字段，跳过迁移")
                return

            # 添加 asset_type 字段
            logger.info("为 ai_explanations 表添加 asset_type 字段")
            conn.execute("ALTER TABLE ai_explanations ADD COLUMN asset_type VARCHAR(50) DEFAULT 'stock_a'")

            # 更新现有记录的 asset_type
            logger.info("更新 ai_explanations 表现有记录的 asset_type")
            conn.execute("UPDATE ai_explanations SET asset_type = 'stock_a' WHERE asset_type IS NULL")

            # 创建索引
            logger.info("为 ai_explanations 表创建索引")
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_explain_asset_type ON ai_explanations(asset_type)")
            except Exception as e:
                logger.warning(f"创建索引失败（可能已存在）: {e}")

            logger.info("ai_explanations 表迁移完成")

        except Exception as e:
            logger.error(f"迁移 ai_explanations 表失败: {e}")
            raise

    def _migrate_user_profiles_table(self, conn: duckdb.DuckDBPyConnection):
        """迁移 user_profiles 表"""
        try:
            # 检查表是否存在
            result = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_name = 'user_profiles'")
            if not result.fetchone():
                logger.info("user_profiles 表不存在，跳过迁移")
                return

            # 检查是否已有 asset_type 字段
            result = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'user_profiles' AND column_name = 'asset_type'")
            if result.fetchone():
                logger.info("user_profiles 表已有 asset_type 字段，跳过迁移")
                return

            # 添加 asset_type 字段
            logger.info("为 user_profiles 表添加 asset_type 字段")
            conn.execute("ALTER TABLE user_profiles ADD COLUMN asset_type VARCHAR(50) DEFAULT 'stock_a'")

            # 更新现有记录的 asset_type
            logger.info("更新 user_profiles 表现有记录的 asset_type")
            conn.execute("UPDATE user_profiles SET asset_type = 'stock_a' WHERE asset_type IS NULL")

            # 创建索引
            logger.info("为 user_profiles 表创建索引")
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_profiles_asset_type ON user_profiles(asset_type)")
            except Exception as e:
                logger.warning(f"创建索引失败（可能已存在）: {e}")

            logger.info("user_profiles 表迁移完成")

        except Exception as e:
            logger.error(f"迁移 user_profiles 表失败: {e}")
            raise

    def migrate_all(self):
        """执行所有迁移"""
        try:
            logger.info("=" * 60)
            logger.info("开始资产类型迁移")
            logger.info("=" * 60)

            # 迁移 SQLite 表
            self.migrate_sqlite_tables()

            # 迁移 DuckDB 表
            self.migrate_duckdb_tables()

            logger.info("=" * 60)
            logger.info("资产类型迁移完成")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"迁移失败: {e}")
            raise


def main():
    """主函数"""
    try:
        migration = AssetTypeMigration()
        migration.migrate_all()
        print("✓ 数据库迁移成功完成")
    except Exception as e:
        print(f"✗ 数据库迁移失败: {e}")
        raise


if __name__ == "__main__":
    main()
