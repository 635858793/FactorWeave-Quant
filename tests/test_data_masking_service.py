"""
数据脱敏服务测试

测试 DataMaskingService 的各项功能
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from core.services.data_masking_service import DataMaskingService
from core.containers import ServiceContainer
from core.events import EventBus


class TestDataMaskingService:
    """数据脱敏服务测试"""

    @pytest.fixture
    def service_container(self):
        """创建服务容器"""
        return ServiceContainer()

    @pytest.fixture
    def event_bus(self):
        """创建事件总线"""
        return EventBus()

    @pytest.fixture
    def data_masking_service(self, service_container, event_bus):
        """创建数据脱敏服务实例"""
        service = DataMaskingService(
            config={},
            event_bus=event_bus
        )
        service.initialize()
        return service

    def test_service_initialization(self, data_masking_service):
        """测试服务初始化"""
        assert data_masking_service is not None
        assert data_masking_service.initialized
        assert data_masking_service.metrics['operation_count'] == 0

    def test_mask_phone_number(self, data_masking_service):
        """测试手机号脱敏"""
        data = {
            'name': '张三',
            'phone': '13800138000'
        }
        
        masked_data = data_masking_service.mask_data(data, ['phone'])
        
        assert masked_data['name'] == '张三'
        assert masked_data['phone'] == '138****8000'
        assert len(masked_data['phone']) == len(data['phone'])

    def test_mask_id_card(self, data_masking_service):
        """测试身份证号脱敏"""
        data = {
            'name': '李四',
            'id_card': '110101199001011234'
        }
        
        masked_data = data_masking_service.mask_data(data, ['id_card'])
        
        assert masked_data['name'] == '李四'
        assert masked_data['id_card'] == '110101********1234'
        assert len(masked_data['id_card']) == len(data['id_card'])

    def test_mask_email(self, data_masking_service):
        """测试邮箱脱敏"""
        data = {
            'name': '王五',
            'email': 'test@example.com'
        }
        
        masked_data = data_masking_service.mask_data(data, ['email'])
        
        assert masked_data['name'] == '王五'
        assert masked_data['email'] == 'te***@example.com'

    def test_mask_bank_card(self, data_masking_service):
        """测试银行卡号脱敏"""
        data = {
            'name': '赵六',
            'credit_card': '6222021234567890123'
        }
        
        masked_data = data_masking_service.mask_data(data, ['credit_card'])
        
        assert masked_data['name'] == '赵六'
        assert masked_data['credit_card'] == '6222********0123'
        assert len(masked_data['credit_card']) == 16

    def test_mask_multiple_fields(self, data_masking_service):
        """测试多字段脱敏"""
        data = {
            'name': '张三',
            'phone': '13800138000',
            'id_card': '110101199001011234',
            'email': 'test@example.com'
        }
        
        masked_data = data_masking_service.mask_data(
            data, 
            ['phone', 'id_card', 'email']
        )
        
        assert masked_data['name'] == '张三'
        assert masked_data['phone'] == '138****8000'
        assert masked_data['id_card'] == '110101********1234'
        assert masked_data['email'] == 'te***@example.com'

    def test_mask_with_custom_rule(self, data_masking_service):
        """测试自定义脱敏规则"""
        def custom_mask(value):
            return value[:3] + '***'
        
        data_masking_service.add_custom_rule('custom_field', custom_mask)
        
        data = {
            'custom_field': 'test123456'
        }
        
        masked_data = data_masking_service.mask_data(data, ['custom_field'])
        
        assert masked_data['custom_field'] == 'tes***'

    def test_mask_nonexistent_field(self, data_masking_service):
        """测试脱敏不存在的字段"""
        data = {
            'name': '张三',
            'phone': '13800138000'
        }
        
        masked_data = data_masking_service.mask_data(data, ['email'])
        
        assert masked_data['name'] == '张三'
        assert masked_data['phone'] == '13800138000'

    def test_mask_none_value(self, data_masking_service):
        """测试脱敏 None 值"""
        data = {
            'name': '张三',
            'phone': None
        }
        
        masked_data = data_masking_service.mask_data(data, ['phone'])
        
        assert masked_data['name'] == '张三'
        assert masked_data['phone'] is None

    def test_get_metrics(self, data_masking_service):
        """测试获取指标"""
        data = {
            'phone': '13800138000',
            'id_card': '110101199001011234'
        }
        
        data_masking_service.mask_data(data, ['phone', 'id_card'])
        
        metrics = data_masking_service.metrics
        
        assert metrics['operation_count'] == 1

    def test_reset_metrics(self, data_masking_service):
        """测试重置指标"""
        data = {
            'phone': '13800138000'
        }
        
        data_masking_service.mask_data(data, ['phone'])
        assert data_masking_service.metrics['operation_count'] == 1
        
        data_masking_service._metrics['operation_count'] = 0

    def test_batch_mask(self, data_masking_service):
        """测试批量脱敏"""
        data_list = [
            {'name': '张三', 'phone': '13800138000'},
            {'name': '李四', 'phone': '13900139000'},
            {'name': '王五', 'phone': '13700137000'}
        ]
        
        masked_list = [
            data_masking_service.mask_data(data, ['phone'])
            for data in data_list
        ]
        
        assert len(masked_list) == 3
        assert masked_list[0]['phone'] == '138****8000'
        assert masked_list[1]['phone'] == '139****9000'
        assert masked_list[2]['phone'] == '137****7000'

    def test_mask_preserves_original_data(self, data_masking_service):
        """测试脱敏不修改原始数据"""
        data = {
            'name': '张三',
            'phone': '13800138000'
        }
        original_phone = data['phone']
        
        masked_data = data_masking_service.mask_data(data, ['phone'])
        
        assert data['phone'] == original_phone
        assert masked_data['phone'] != original_phone
