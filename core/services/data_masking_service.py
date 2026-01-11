"""
数据脱敏服务

提供数据脱敏功能，支持多种数据类型脱敏和自定义脱敏规则。
"""

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from loguru import logger
import re

from .base_service import ConfigurableService
from ..events import EventBus


class DataMaskingService(ConfigurableService):
    """数据脱敏服务"""

    def __init__(self, config: Optional[Dict[str, Any]] = None, event_bus: Optional[EventBus] = None):
        """
        初始化数据脱敏服务

        Args:
            config: 服务配置
            event_bus: 事件总线
        """
        super().__init__(config, event_bus)
        
        self._masking_rules = {
            'phone': self._mask_phone,
            'email': self._mask_email,
            'id_card': self._mask_id_card,
            'bank_account': self._mask_bank_account,
            'name': self._mask_name,
            'address': self._mask_address,
            'credit_card': self._mask_credit_card,
            'password': self._mask_password
        }
        
        self._custom_rules: Dict[str, Callable] = {}

    def _do_initialize(self) -> None:
        """初始化服务"""
        custom_rules = self.get_config_value('custom_rules', {})
        for rule_name, rule_func in custom_rules.items():
            if callable(rule_func):
                self._custom_rules[rule_name] = rule_func
        
        logger.info(f"数据脱敏服务初始化完成，默认规则: {len(self._masking_rules)}，自定义规则: {len(self._custom_rules)}")

    def mask_data(self, data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        """
        脱敏数据

        Args:
            data: 原始数据
            fields: 需要脱敏的字段列表

        Returns:
            脱敏后的数据
        """
        try:
            self._ensure_initialized()
            self.increment_operation_count()

            masked_data = data.copy()
            
            for field in fields:
                if field not in masked_data:
                    continue
                
                value = masked_data[field]
                if value is None:
                    continue
                
                masked_value = self._apply_masking_rule(field, value)
                masked_data[field] = masked_value
            
            self._event_bus.publish(
                'data.masked',
                fields=fields,
                timestamp=datetime.now().isoformat()
            )
            
            logger.debug(f"数据脱敏完成: {fields}")
            return masked_data

        except Exception as e:
            logger.error(f"数据脱敏失败: {e}")
            self._metrics['error_count'] += 1
            self._metrics['last_error'] = str(e)
            return data

    def mask_value(self, value: Any, rule_name: str) -> Any:
        """
        脱敏单个值

        Args:
            value: 原始值
            rule_name: 脱敏规则名称

        Returns:
            脱敏后的值
        """
        try:
            self._ensure_initialized()
            self.increment_operation_count()

            if rule_name in self._custom_rules:
                return self._custom_rules[rule_name](value)
            
            if rule_name in self._masking_rules:
                return self._masking_rules[rule_name](value)
            
            logger.warning(f"未找到脱敏规则: {rule_name}")
            return value

        except Exception as e:
            logger.error(f"脱敏值失败: {e}")
            self._metrics['error_count'] += 1
            self._metrics['last_error'] = str(e)
            return value

    def _apply_masking_rule(self, field_name: str, value: Any) -> Any:
        """
        应用脱敏规则

        Args:
            field_name: 字段名称
            value: 原始值

        Returns:
            脱敏后的值
        """
        field_lower = field_name.lower()
        
        for rule_name, rule_func in self._custom_rules.items():
            if rule_name in field_lower:
                return rule_func(value)
        
        for rule_name, rule_func in self._masking_rules.items():
            if rule_name in field_lower:
                return rule_func(value)
        
        return value

    def _mask_phone(self, phone: str) -> str:
        """脱敏手机号"""
        if not phone or len(phone) < 7:
            return phone
        return phone[:3] + '****' + phone[-4:]

    def _mask_email(self, email: str) -> str:
        """脱敏邮箱"""
        if not email or '@' not in email:
            return email
        local, domain = email.split('@')
        if len(local) > 2:
            local = local[:2] + '***'
        return f"{local}@{domain}"

    def _mask_id_card(self, id_card: str) -> str:
        """脱敏身份证号"""
        if not id_card or len(id_card) < 10:
            return id_card
        return id_card[:6] + '********' + id_card[-4:]

    def _mask_bank_account(self, account: str) -> str:
        """脱敏银行账号"""
        if not account or len(account) < 8:
            return account
        return account[:4] + '****' + account[-4:]

    def _mask_name(self, name: str) -> str:
        """脱敏姓名"""
        if not name or len(name) < 2:
            return name
        if len(name) == 2:
            return name[0] + '*'
        return name[0] + '*' * (len(name) - 2) + name[-1]

    def _mask_address(self, address: str) -> str:
        """脱敏地址"""
        if not address or len(address) < 10:
            return address
        return address[:6] + '***' + address[-4:]

    def _mask_credit_card(self, card: str) -> str:
        """脱敏信用卡号"""
        if not card or len(card) < 12:
            return card
        return card[:4] + '********' + card[-4:]

    def _mask_password(self, password: str) -> str:
        """脱敏密码"""
        if not password:
            return password
        return '*' * len(password)

    def add_custom_rule(self, rule_name: str, rule_func: Callable) -> None:
        """
        添加自定义脱敏规则

        Args:
            rule_name: 规则名称
            rule_func: 规则函数
        """
        self._custom_rules[rule_name] = rule_func
        logger.info(f"添加自定义脱敏规则: {rule_name}")

    def remove_custom_rule(self, rule_name: str) -> bool:
        """
        移除自定义脱敏规则

        Args:
            rule_name: 规则名称

        Returns:
            是否移除成功
        """
        if rule_name in self._custom_rules:
            del self._custom_rules[rule_name]
            logger.info(f"移除自定义脱敏规则: {rule_name}")
            return True
        return False

    def get_available_rules(self) -> Dict[str, List[str]]:
        """
        获取可用的脱敏规则

        Returns:
            规则列表
        """
        return {
            'default': list(self._masking_rules.keys()),
            'custom': list(self._custom_rules.keys())
        }

    def _do_health_check(self) -> Optional[Dict[str, Any]]:
        """自定义健康检查"""
        return {
            'default_rules': len(self._masking_rules),
            'custom_rules': len(self._custom_rules),
            'cache_size': len(self._custom_rules)
        }
