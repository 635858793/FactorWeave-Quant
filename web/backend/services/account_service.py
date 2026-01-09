"""
账户服务
"""

from sqlalchemy.orm import Session
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.schemas.account import AccountCreate, AccountUpdate, AccountFilter
from web.backend.models.account import AccountGroup, Position, Balance
from core.trading.account_manager import AccountManager
from core.containers.service_container import ServiceContainer


class AccountService:
    """
    账户服务类
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.service_container = ServiceContainer()
        self.account_manager = AccountManager(self.service_container)
    
    def get_accounts(
        self,
        page: int = 1,
        page_size: int = 20,
        filter_params: AccountFilter = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取账户列表
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = "SELECT * FROM accounts WHERE 1=1"
        params = {}
        
        if filter_params:
            if filter_params.institution:
                query += " AND institution = :institution"
                params["institution"] = filter_params.institution
            
            if filter_params.account_type:
                query += " AND account_type = :account_type"
                params["account_type"] = filter_params.account_type
            
            if filter_params.status:
                query += " AND is_active = :is_active"
                params["is_active"] = (filter_params.status == "active")
        
        query += " ORDER BY created_at DESC"
        
        offset = (page - 1) * page_size
        query += f" LIMIT {page_size} OFFSET {offset}"
        
        accounts = duckdb_manager.execute_query(query, params)
        
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        count_query = count_query.split("ORDER BY")[0]
        total = duckdb_manager.execute_query(count_query, params)[0]["count"]
        
        return accounts, total
    
    def get_account_by_id(self, account_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取账户
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = "SELECT * FROM accounts WHERE id = :account_id"
        params = {"account_id": account_id}
        
        accounts = duckdb_manager.execute_query(query, params)
        
        if accounts:
            return accounts[0]
        
        return None
    
    def create_account(self, account_data: AccountCreate) -> Dict[str, Any]:
        """
        创建账户
        """
        from core.trading.account import Account
        
        account = Account(
            account_name=account_data.account_name,
            account_type=account_data.account_type,
            institution=account_data.institution,
            account_code=account_data.account_code
        )
        
        self.account_manager.add_account(account)
        
        return self.get_account_by_id(account.id)
    
    def update_account(self, account_id: int, account_data: AccountUpdate) -> Optional[Dict[str, Any]]:
        """
        修改账户
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        updates = {}
        if account_data.account_name is not None:
            updates["account_name"] = account_data.account_name
        if account_data.account_type is not None:
            updates["account_type"] = account_data.account_type
        if account_data.institution is not None:
            updates["institution"] = account_data.institution
        if account_data.account_code is not None:
            updates["account_code"] = account_data.account_code
        if account_data.is_active is not None:
            updates["is_active"] = account_data.is_active
        
        if updates:
            updates["updated_at"] = datetime.now()
            
            set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
            query = f"UPDATE accounts SET {set_clause} WHERE id = :account_id"
            params = {**updates, "account_id": account_id}
            
            duckdb_manager.execute_query(query, params)
        
        return self.get_account_by_id(account_id)
    
    def delete_account(self, account_id: int) -> bool:
        """
        删除账户
        """
        account = self.account_manager.get_account(account_id)
        if account:
            self.account_manager.remove_account(account_id)
            return True
        
        return False
    
    def test_connection(self, account_id: int) -> Tuple[bool, str]:
        """
        测试账户连接
        """
        try:
            account = self.account_manager.get_account(account_id)
            if account:
                return True, "连接成功"
            else:
                return False, "账户不存在"
        except Exception as e:
            return False, f"连接失败: {str(e)}"
    
    def get_positions(self, account_id: int) -> List[Dict[str, Any]]:
        """
        获取账户持仓信息
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = "SELECT * FROM positions WHERE account_id = :account_id ORDER BY updated_at DESC"
        params = {"account_id": account_id}
        
        positions = duckdb_manager.execute_query(query, params)
        
        return positions
    
    def get_balance(self, account_id: int) -> Dict[str, Any]:
        """
        获取账户余额信息
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = "SELECT * FROM balances WHERE account_id = :account_id ORDER BY updated_at DESC LIMIT 1"
        params = {"account_id": account_id}
        
        balances = duckdb_manager.execute_query(query, params)
        
        if balances:
            return balances[0]
        
        return {}
    
    def create_account_group(self, user_id: int, group_data: Dict[str, Any]) -> AccountGroup:
        """
        创建账户分组
        """
        group = AccountGroup(
            user_id=user_id,
            name=group_data.get("name"),
            description=group_data.get("description")
        )
        
        self.db.add(group)
        self.db.commit()
        self.db.refresh(group)
        
        return group
    
    def get_account_groups(self, user_id: int) -> List[AccountGroup]:
        """
        获取账户分组
        """
        return self.db.query(AccountGroup).filter(
            AccountGroup.user_id == user_id
        ).all()
    
    def add_accounts_to_group(self, group_id: int, account_ids: List[int]) -> bool:
        """
        将账户添加到分组
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        for account_id in account_ids:
            query = "UPDATE accounts SET group_id = :group_id WHERE id = :account_id"
            params = {"group_id": group_id, "account_id": account_id}
            duckdb_manager.execute_query(query, params)
        
        return True
    
    def remove_accounts_from_group(self, group_id: int, account_ids: List[int]) -> bool:
        """
        将账户从分组中移除
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        for account_id in account_ids:
            query = "UPDATE accounts SET group_id = NULL WHERE id = :account_id"
            params = {"account_id": account_id}
            duckdb_manager.execute_query(query, params)
        
        return True
    
    def get_accounts_by_group(self, group_id: int, page: int = 1, page_size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取分组中的账户
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = "SELECT * FROM accounts WHERE group_id = :group_id ORDER BY created_at DESC"
        params = {"group_id": group_id}
        
        offset = (page - 1) * page_size
        query += f" LIMIT {page_size} OFFSET {offset}"
        
        accounts = duckdb_manager.execute_query(query, params)
        
        count_query = "SELECT COUNT(*) as count FROM accounts WHERE group_id = :group_id"
        total = duckdb_manager.execute_query(count_query, params)[0]["count"]
        
        return accounts, total
    
    def get_position_history(
        self,
        account_id: int,
        symbol: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取持仓历史
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = "SELECT * FROM position_history WHERE account_id = :account_id"
        params = {"account_id": account_id}
        
        if symbol:
            query += " AND symbol = :symbol"
            params["symbol"] = symbol
        
        if start_time:
            query += " AND created_at >= :start_time"
            params["start_time"] = start_time
        
        if end_time:
            query += " AND created_at <= :end_time"
            params["end_time"] = end_time
        
        query += " ORDER BY created_at DESC"
        
        offset = (page - 1) * page_size
        query += f" LIMIT {page_size} OFFSET {offset}"
        
        positions = duckdb_manager.execute_query(query, params)
        
        count_query = query.split("ORDER BY")[0].replace("SELECT *", "SELECT COUNT(*)")
        total = duckdb_manager.execute_query(count_query, params)[0]["count"]
        
        return positions, total
    
    def get_balance_history(
        self,
        account_id: int,
        start_time: datetime = None,
        end_time: datetime = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取余额历史
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = "SELECT * FROM balance_history WHERE account_id = :account_id"
        params = {"account_id": account_id}
        
        if start_time:
            query += " AND created_at >= :start_time"
            params["start_time"] = start_time
        
        if end_time:
            query += " AND created_at <= :end_time"
            params["end_time"] = end_time
        
        query += " ORDER BY created_at DESC"
        
        offset = (page - 1) * page_size
        query += f" LIMIT {page_size} OFFSET {offset}"
        
        balances = duckdb_manager.execute_query(query, params)
        
        count_query = query.split("ORDER BY")[0].replace("SELECT *", "SELECT COUNT(*)")
        total = duckdb_manager.execute_query(count_query, params)[0]["count"]
        
        return balances, total
    
    def get_account_statistics(self, account_id: int) -> Dict[str, Any]:
        """
        获取账户统计信息
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = """
            SELECT 
                COUNT(DISTINCT symbol) as position_count,
                SUM(CASE WHEN quantity > 0 THEN quantity ELSE 0 END) as long_quantity,
                SUM(CASE WHEN quantity < 0 THEN ABS(quantity) ELSE 0 END) as short_quantity,
                SUM(market_value) as total_market_value,
                SUM(unrealized_pnl) as total_unrealized_pnl
            FROM positions 
            WHERE account_id = :account_id
        """
        
        params = {"account_id": account_id}
        stats = duckdb_manager.execute_query(query, params)[0]
        
        return stats
    
    def get_all_positions(self, page: int = 1, page_size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取所有持仓
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = "SELECT * FROM positions ORDER BY updated_at DESC"
        
        offset = (page - 1) * page_size
        query += f" LIMIT {page_size} OFFSET {offset}"
        
        positions = duckdb_manager.execute_query(query)
        
        count_query = "SELECT COUNT(*) as count FROM positions"
        total = duckdb_manager.execute_query(count_query)[0]["count"]
        
        return positions, total
    
    def get_position_by_symbol(self, account_id: int, symbol: str) -> Optional[Dict[str, Any]]:
        """
        根据代码获取持仓
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = "SELECT * FROM positions WHERE account_id = :account_id AND symbol = :symbol"
        params = {"account_id": account_id, "symbol": symbol}
        
        positions = duckdb_manager.execute_query(query, params)
        
        if positions:
            return positions[0]
        
        return None
    
    def sync_account_data(self, account_id: int) -> Tuple[bool, str]:
        """
        同步账户数据
        """
        try:
            account = self.account_manager.get_account(account_id)
            if not account:
                return False, "账户不存在"
            
            self.account_manager.sync_account(account_id)
            
            return True, "同步成功"
        except Exception as e:
            return False, f"同步失败: {str(e)}"
    
    def get_account_trades(
        self,
        account_id: int,
        start_time: datetime = None,
        end_time: datetime = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取账户交易记录
        """
        duckdb_manager = self.db.get_duckdb_manager()
        
        query = """
            SELECT f.*, o.symbol, o.side 
            FROM fills f 
            JOIN orders o ON f.order_id = o.order_id 
            WHERE o.account_id = :account_id
        """
        params = {"account_id": account_id}
        
        if start_time:
            query += " AND f.fill_time >= :start_time"
            params["start_time"] = start_time
        
        if end_time:
            query += " AND f.fill_time <= :end_time"
            params["end_time"] = end_time
        
        query += " ORDER BY f.fill_time DESC"
        
        offset = (page - 1) * page_size
        query += f" LIMIT {page_size} OFFSET {offset}"
        
        trades = duckdb_manager.execute_query(query, params)
        
        count_query = query.split("ORDER BY")[0].replace("SELECT f.*, o.symbol, o.side", "SELECT COUNT(*)")
        total = duckdb_manager.execute_query(count_query, params)[0]["count"]
        
        return trades, total
