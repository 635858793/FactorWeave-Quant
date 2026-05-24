from typing import Optional, Dict, Any, List
import pandas as pd
from .base_service import BaseService, CacheableService, ConfigurableService
from loguru import logger


class BondService(CacheableService, ConfigurableService):
    """
    债券服务
    
    负责债券数据的获取、缓存和管理，包括：
    - 国债（国债期货、国债ETF）
    - 企业债（公司债、可转债）
    - 地方政府债
    - 债券行情数据
    - 债券基本信息查询
    - 债券收益率曲线
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, cache_size: int = 100,
                 service_container=None, **kwargs):
        self.service_container = service_container
        
        filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'service_container'}
        CacheableService.__init__(self, cache_size=cache_size, namespace='bond_service', **filtered_kwargs)
        ConfigurableService.__init__(self, config=config, **filtered_kwargs)
        
        self._unified_data_manager = None
        self._bond_list = []
        self._no_data_cache = set()
        self._last_query_time = {}
        
    def _do_initialize(self) -> None:
        try:
            from .unified_data_manager import get_unified_data_manager
            self._unified_data_manager = get_unified_data_manager()
            if self._unified_data_manager:
                logger.info("BondService 初始化成功，连接到 UnifiedDataManager")
            else:
                logger.warning("UnifiedDataManager 不可用，BondService 将使用降级模式")
        except Exception as e:
            logger.warning(f"BondService 初始化失败: {e}")
    
    def _ensure_initialized(self):
        if not self._initialized:
            self.initialize()
    
    def get_bond_list(self, bond_type: Optional[str] = None,
                     market: str = 'all') -> List[Dict[str, Any]]:
        self._ensure_initialized()
        
        cache_key = f"bond_list_{bond_type}_{market}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            if self._unified_data_manager:
                df = self._unified_data_manager.get_asset_list(asset_type='bond', market=market)
                if df is not None and not df.empty:
                    bond_list = df.to_dict('records')
                    if bond_type:
                        bond_list = [b for b in bond_list if b.get('type') == bond_type]
                    self.set_to_cache(cache_key, bond_list)
                    self._bond_list = bond_list
                    return bond_list
            
            return self._get_default_bond_list(bond_type)
        except Exception as e:
            logger.error(f"获取债券列表失败: {e}")
            return self._get_default_bond_list(bond_type)
    
    def _get_default_bond_list(self, bond_type: Optional[str] = None) -> List[Dict[str, Any]]:
        default_bonds = [
            {'code': '019203', 'name': '21国债10', 'type': '国债', 'price': 100.45, 'yield': 2.89, 'maturity': 10.5},
            {'code': '019215', 'name': '21国债15', 'type': '国债', 'price': 101.23, 'yield': 3.12, 'maturity': 15.2},
            {'code': '019225', 'name': '22国债5', 'type': '国债', 'price': 99.87, 'yield': 2.56, 'maturity': 5.3},
            {'code': '113009', 'name': '广汽转债', 'type': '可转债', 'price': 128.45, 'yield': 0.85, 'maturity': 5.8},
            {'code': '128095', 'name': '恩捷转债', 'type': '可转债', 'price': 115.67, 'yield': 1.23, 'maturity': 5.2},
            {'code': '127012', 'name': '招路转债', 'type': '可转债', 'price': 108.34, 'yield': 1.89, 'maturity': 6.1},
            {'code': '136028', 'name': '华新水泥公司债', 'type': '企业债', 'price': 103.56, 'yield': 3.45, 'maturity': 7.5},
            {'code': '136076', 'name': '国药控股公司债', 'type': '企业债', 'price': 102.34, 'yield': 3.12, 'maturity': 5.8},
            {'code': '147592', 'name': '21深圳债', 'type': '地方政府债', 'price': 100.89, 'yield': 2.78, 'maturity': 10.0},
            {'code': '155688', 'name': '22湖北债', 'type': '地方政府债', 'price': 101.12, 'yield': 2.95, 'maturity': 15.0},
            {'code': '511010', 'name': '上证5年期国债ETF', 'type': '国债ETF', 'price': 1.234, 'yield': 2.45, 'maturity': 5.0},
            {'code': '511880', 'name': '上证10年期国债ETF', 'type': '国债ETF', 'price': 2.345, 'yield': 2.89, 'maturity': 10.0},
        ]
        
        if bond_type:
            return [b for b in default_bonds if b.get('type') == bond_type]
        return default_bonds
    
    def get_kline_data(self, bond_code: str, period: str = 'D',
                       count: int = 365) -> pd.DataFrame:
        self._ensure_initialized()
        
        cache_key = f"bond_kline_{bond_code}_{period}_{count}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        if bond_code in self._no_data_cache:
            return pd.DataFrame()
        
        try:
            if self._unified_data_manager:
                df = self._unified_data_manager.get_kline_data(
                    stock_code=bond_code,
                    period=period,
                    count=count,
                    asset_type='bond'
                )
                if df is not None and not df.empty:
                    self.set_to_cache(cache_key, df)
                    return df
                else:
                    self._no_data_cache.add(bond_code)
            
            return self._generate_mock_kline_data(bond_code, period, count)
        except Exception as e:
            logger.error(f"获取债券K线数据失败: {bond_code}, {e}")
            return self._generate_mock_kline_data(bond_code, period, count)
    
    def _generate_mock_kline_data(self, bond_code: str, period: str, count: int) -> pd.DataFrame:
        logger.warning(f"债券K线数据不可用({bond_code})，返回空DataFrame。请配置数据源以获取真实数据。")
        return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume', 'amount'])
    
    def get_bond_info(self, bond_code: str) -> Optional[Dict[str, Any]]:
        self._ensure_initialized()
        
        cache_key = f"bond_info_{bond_code}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            bond_list = self.get_bond_list()
            for bond in bond_list:
                if bond.get('code') == bond_code:
                    self.set_to_cache(cache_key, bond)
                    return bond
            
            for bond in self._get_default_bond_list(None):
                if bond.get('code') == bond_code:
                    self.set_to_cache(cache_key, bond)
                    return bond
            
            return None
        except Exception as e:
            logger.error(f"获取债券信息失败: {bond_code}, {e}")
            return None
    
    def search_bonds(self, keyword: str) -> List[Dict[str, Any]]:
        self._ensure_initialized()
        
        if not keyword:
            return []
        
        keyword = keyword.lower()
        bond_list = self.get_bond_list()
        
        results = [
            bond for bond in bond_list
            if keyword in bond.get('name', '').lower() or keyword in bond.get('code', '').lower()
        ]
        
        if not results:
            default_list = self._get_default_bond_list(None)
            results = [
                bond for bond in default_list
                if keyword in bond.get('name', '').lower() or keyword in bond.get('code', '').lower()
            ]
        
        return results
    
    def get_yield_curve(self, bond_type: Optional[str] = None) -> pd.DataFrame:
        self._ensure_initialized()
        
        cache_key = f"yield_curve_{bond_type}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            bonds = self.get_bond_list(bond_type=bond_type)
            if not bonds:
                bonds = self._get_default_bond_list(bond_type)
            
            yield_data = []
            for bond in bonds:
                if 'yield' in bond and 'maturity' in bond:
                    yield_data.append({
                        'maturity': bond['maturity'],
                        'yield': bond['yield'],
                        'bond_code': bond['code'],
                        'bond_name': bond['name'],
                        'bond_type': bond.get('type', '未知'),
                    })
            
            df = pd.DataFrame(yield_data)
            if not df.empty:
                df = df.sort_values('maturity')
                self.set_to_cache(cache_key, df)
            return df
        except Exception as e:
            logger.error(f"获取收益率曲线失败: {e}")
            return pd.DataFrame()
    
    def calculate_bond_duration(self, bond_code: str,
                               yield_to_maturity: Optional[float] = None) -> Optional[Dict[str, Any]]:
        self._ensure_initialized()
        
        try:
            bond_info = self.get_bond_info(bond_code)
            if not bond_info:
                return None
            
            maturity = bond_info.get('maturity', 0)
            coupon = bond_info.get('yield', 0) * 0.01
            ytm = yield_to_maturity or bond_info.get('yield', 0)
            
            if maturity <= 0:
                return None
            
            duration = maturity * (1 + coupon / ytm) / (1 + ytm)
            
            return {
                'bond_code': bond_code,
                'bond_name': bond_info.get('name', bond_code),
                'maturity': maturity,
                'coupon': coupon * 100,
                'yield_to_maturity': ytm,
                'duration': round(duration, 2),
                'modified_duration': round(duration / (1 + ytm), 2),
            }
        except Exception as e:
            logger.error(f"计算债券久期失败: {bond_code}, {e}")
            return None
    
    def get_bond_conversion_price(self, convertible_code: str) -> Optional[Dict[str, Any]]:
        self._ensure_initialized()
        
        conversion_map = {
            '113009': {'stock_code': '601238', 'conversion_ratio': 18.52, 'conversion_price': 5.40},
            '128095': {'stock_code': '002812', 'conversion_ratio': 15.21, 'conversion_price': 6.58},
            '127012': {'stock_code': '601965', 'conversion_ratio': 20.15, 'conversion_price': 4.96},
        }
        
        conversion_info = conversion_map.get(convertible_code)
        if conversion_info:
            bond_info = self.get_bond_info(convertible_code)
            return {
                'bond_code': convertible_code,
                'bond_name': bond_info.get('name', convertible_code) if bond_info else convertible_code,
                'stock_code': conversion_info['stock_code'],
                'conversion_ratio': conversion_info['conversion_ratio'],
                'conversion_price': conversion_info['conversion_price'],
                'current_price': bond_info.get('price', 0) if bond_info else 0,
                'conversion_value': conversion_info['conversion_ratio'] * 100 / conversion_info['conversion_price'] if conversion_info.get('conversion_price') else 0,
            }
        
        return None
    
    def get_realtime_quote(self, bond_code: str) -> Optional[Dict[str, Any]]:
        self._ensure_initialized()
        
        try:
            kline_df = self.get_kline_data(bond_code, period='D', count=1)
            if kline_df is not None and not kline_df.empty:
                latest = kline_df.iloc[-1]
                bond_info = self.get_bond_info(bond_code)
                return {
                    'code': bond_code,
                    'name': bond_info.get('name', bond_code) if bond_info else bond_code,
                    'price': latest.get('close', 0),
                    'yield': bond_info.get('yield', 0) if bond_info else 0,
                    'pct_change': ((latest.get('close', 0) - latest.get('open', 0)) / latest.get('open', 1) * 100) if latest.get('open', 0) else 0,
                    'volume': latest.get('volume', 0),
                    'amount': latest.get('amount', 0),
                }
            return None
        except Exception as e:
            logger.error(f"获取债券实时行情失败: {bond_code}, {e}")
            return None
    
    def calculate_bond_return(self, bond_code: str,
                            days: int = 30) -> Optional[Dict[str, Any]]:
        self._ensure_initialized()
        
        try:
            df = self.get_kline_data(bond_code, period='D', count=days + 1)
            if df is None or df.empty or len(df) < 2:
                return None
            
            latest = df.iloc[-1]
            oldest = df.iloc[0]
            
            start_price = oldest.get('close', 0)
            end_price = latest.get('close', 0)
            
            if start_price == 0:
                return None
            
            total_return = (end_price - start_price) / start_price * 100
            bond_info = self.get_bond_info(bond_code)
            
            return {
                'bond_code': bond_code,
                'bond_name': bond_info.get('name', bond_code) if bond_info else bond_code,
                'start_date': oldest.get('date'),
                'end_date': latest.get('date'),
                'start_price': start_price,
                'end_price': end_price,
                'total_return': round(total_return, 2),
                'annual_yield': bond_info.get('yield', 0) if bond_info else 0,
                'days': days,
            }
        except Exception as e:
            logger.error(f"计算债券收益失败: {bond_code}, {e}")
            return None
    
    def clear_cache(self, bond_code: Optional[str] = None):
        if bond_code:
            self._no_data_cache.discard(bond_code)
        else:
            self._no_data_cache.clear()
            self._bond_list = []
        super().clear_cache()


_bond_service_instance = None


def get_bond_service() -> BondService:
    global _bond_service_instance
    if _bond_service_instance is None:
        _bond_service_instance = BondService()
    return _bond_service_instance


def reset_bond_service():
    global _bond_service_instance
    if _bond_service_instance:
        _bond_service_instance.clear_cache()
    _bond_service_instance = None
