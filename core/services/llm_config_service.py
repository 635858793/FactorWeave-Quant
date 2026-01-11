"""
LLM配置服务

提供统一的LLM配置管理，支持多个大模型提供商：
- OpenAI (GPT系列)
- Anthropic (Claude系列)
- Google (Gemini系列)
- Azure OpenAI
- 国内大模型（通义千问、文心一言、智谱AI等）

使用数据库存储配置，支持加密存储API密钥
"""

from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum

from loguru import logger
from .base_service import ConfigurableService
from ..events import EventBus
from db.models.llm_config_models import get_llm_config_manager


class LLMProvider(Enum):
    """LLM提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE_OPENAI = "azure_openai"
    QIANWEN = "qianwen"  # 通义千问
    ERNIE = "ernie"  # 文心一言
    ZHIPU = "zhipu"  # 智谱AI
    DEEPSEEK = "deepseek"  # DeepSeek
    BAICHUAN = "baichuan"  # 百川智能
    MOONSHOT = "moonshot"  # 月之暗面


@dataclass
class LLMConfig:
    """LLM配置"""
    provider: LLMProvider
    api_key: str
    api_secret: Optional[str] = None
    base_url: Optional[str] = None
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 30
    enabled: bool = True
    proxy: Optional[str] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result['provider'] = self.provider.value if isinstance(self.provider, LLMProvider) else self.provider
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LLMConfig':
        """从字典创建"""
        provider_data = data.get('provider')
        if isinstance(provider_data, str):
            provider = LLMProvider(provider_data)
        else:
            provider = provider_data
        
        return cls(
            provider=provider,
            api_key=data.get('api_key', ''),
            api_secret=data.get('api_secret'),
            base_url=data.get('base_url'),
            model=data.get('model', 'gpt-3.5-turbo'),
            temperature=data.get('temperature', 0.7),
            max_tokens=data.get('max_tokens', 2000),
            timeout=data.get('timeout', 30),
            enabled=data.get('enabled', True),
            proxy=data.get('proxy'),
            extra_params=data.get('extra_params', {})
        )


@dataclass
class LLMProviderInfo:
    """LLM提供商信息"""
    provider: LLMProvider
    name: str
    description: str
    models: List[str]
    default_model: str
    base_url: Optional[str] = None
    requires_api_secret: bool = False
    pricing_url: Optional[str] = None
    documentation_url: Optional[str] = None


class LLMConfigService(ConfigurableService):
    """LLM配置服务"""

    # 默认提供商信息
    PROVIDER_INFO = {
        LLMProvider.OPENAI: LLMProviderInfo(
            provider=LLMProvider.OPENAI,
            name="OpenAI",
            description="OpenAI GPT系列模型",
            models=["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-3.5-turbo-16k"],
            default_model="gpt-3.5-turbo",
            base_url="https://api.openai.com/v1",
            pricing_url="https://openai.com/pricing",
            documentation_url="https://platform.openai.com/docs"
        ),
        LLMProvider.ANTHROPIC: LLMProviderInfo(
            provider=LLMProvider.ANTHROPIC,
            name="Anthropic",
            description="Anthropic Claude系列模型",
            models=["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
            default_model="claude-3-sonnet-20240229",
            base_url="https://api.anthropic.com/v1",
            pricing_url="https://www.anthropic.com/pricing",
            documentation_url="https://docs.anthropic.com"
        ),
        LLMProvider.GOOGLE: LLMProviderInfo(
            provider=LLMProvider.GOOGLE,
            name="Google",
            description="Google Gemini系列模型",
            models=["gemini-pro", "gemini-pro-vision"],
            default_model="gemini-pro",
            base_url="https://generativelanguage.googleapis.com/v1",
            pricing_url="https://ai.google.dev/pricing",
            documentation_url="https://ai.google.dev/docs"
        ),
        LLMProvider.AZURE_OPENAI: LLMProviderInfo(
            provider=LLMProvider.AZURE_OPENAI,
            name="Azure OpenAI",
            description="Azure OpenAI服务",
            models=["gpt-4", "gpt-35-turbo"],
            default_model="gpt-35-turbo",
            requires_api_secret=True,
            pricing_url="https://azure.microsoft.com/pricing/details/cognitive-services/openai-service",
            documentation_url="https://learn.microsoft.com/azure/ai-services/openai"
        ),
        LLMProvider.QIANWEN: LLMProviderInfo(
            provider=LLMProvider.QIANWEN,
            name="通义千问",
            description="阿里云通义千问大模型",
            models=["qwen-turbo", "qwen-plus", "qwen-max"],
            default_model="qwen-plus",
            base_url="https://dashscope.aliyuncs.com/api/v1",
            pricing_url="https://help.aliyun.com/zh/dashscope/developer-reference/price",
            documentation_url="https://help.aliyun.com/zh/dashscope/"
        ),
        LLMProvider.ERNIE: LLMProviderInfo(
            provider=LLMProvider.ERNIE,
            name="文心一言",
            description="百度文心一言大模型",
            models=["ernie-bot-4", "ernie-bot-turbo"],
            default_model="ernie-bot-turbo",
            base_url="https://aip.baidubce.com/rpc/2.0/ai_custom/v1",
            pricing_url="https://cloud.baidu.com/product/wenxinworkshop",
            documentation_url="https://cloud.baidu.com/doc/WENXINWORKSHOP/index.html"
        ),
        LLMProvider.ZHIPU: LLMProviderInfo(
            provider=LLMProvider.ZHIPU,
            name="智谱AI",
            description="智谱AI大模型",
            models=["glm-4", "glm-3-turbo"],
            default_model="glm-3-turbo",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            pricing_url="https://open.bigmodel.cn/pricing",
            documentation_url="https://open.bigmodel.cn/dev/api"
        ),
        LLMProvider.DEEPSEEK: LLMProviderInfo(
            provider=LLMProvider.DEEPSEEK,
            name="DeepSeek",
            description="DeepSeek大模型",
            models=["deepseek-chat", "deepseek-coder"],
            default_model="deepseek-chat",
            base_url="https://api.deepseek.com/v1",
            pricing_url="https://platform.deepseek.com/pricing",
            documentation_url="https://platform.deepseek.com/docs"
        ),
        LLMProvider.BAICHUAN: LLMProviderInfo(
            provider=LLMProvider.BAICHUAN,
            name="百川智能",
            description="百川智能大模型",
            models=["Baichuan2-Turbo", "Baichuan2-53B"],
            default_model="Baichuan2-Turbo",
            base_url="https://api.baichuan-ai.com/v1",
            pricing_url="https://platform.baichuan-ai.com/price",
            documentation_url="https://platform.baichuan-ai.com/docs"
        ),
        LLMProvider.MOONSHOT: LLMProviderInfo(
            provider=LLMProvider.MOONSHOT,
            name="月之暗面",
            description="Moonshot AI大模型",
            models=["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
            default_model="moonshot-v1-8k",
            base_url="https://api.moonshot.cn/v1",
            pricing_url="https://platform.moonshot.cn/pricing",
            documentation_url="https://platform.moonshot.cn/docs"
        )
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None, event_bus: Optional[EventBus] = None):
        """
        初始化LLM配置服务

        Args:
            config: 服务配置
            event_bus: 事件总线
        """
        super().__init__(config, event_bus)
        
        self._config_manager = None
        self._configs: Dict[LLMProvider, LLMConfig] = {}
        self._current_provider: Optional[LLMProvider] = None

    def _do_initialize(self) -> None:
        """初始化服务"""
        try:
            self._config_manager = get_llm_config_manager()
            self._load_configs()
            logger.info(f"LLM配置服务初始化完成，已加载 {len(self._configs)} 个配置")
        except Exception as e:
            logger.error(f"LLM配置服务初始化失败: {e}")
            raise

    def _load_configs(self) -> None:
        """从数据库加载配置"""
        try:
            configs_dict = self._config_manager.get_all_configs()
            
            self._configs.clear()
            for provider_str, config_data in configs_dict.items():
                try:
                    provider = LLMProvider(provider_str)
                    self._configs[provider] = LLMConfig.from_dict(config_data)
                except Exception as e:
                    logger.warning(f"加载 {provider_str} 配置失败: {e}")
            
            current_provider_str = self._config_manager.get_current_provider()
            if current_provider_str:
                self._current_provider = LLMProvider(current_provider_str)
                
        except Exception as e:
            logger.error(f"从数据库加载LLM配置失败: {e}")

    def get_provider_info(self, provider: LLMProvider) -> Optional[LLMProviderInfo]:
        """获取提供商信息"""
        return self.PROVIDER_INFO.get(provider)

    def get_all_providers(self) -> List[LLMProviderInfo]:
        """获取所有提供商信息"""
        return list(self.PROVIDER_INFO.values())

    def get_config(self, provider: LLMProvider) -> Optional[LLMConfig]:
        """获取指定提供商的配置"""
        return self._configs.get(provider)

    def set_config(self, config: LLMConfig) -> None:
        """设置提供商配置"""
        config_dict = config.to_dict()
        
        if self._config_manager.save_config(config_dict):
            self._configs[config.provider] = config
            logger.info(f"已更新 {config.provider.value} 配置")
        else:
            raise Exception(f"保存 {config.provider.value} 配置失败")

    def remove_config(self, provider: LLMProvider) -> None:
        """删除提供商配置"""
        if self._config_manager.delete_config(provider.value):
            if provider in self._configs:
                del self._configs[provider]
            if self._current_provider == provider:
                self._current_provider = None
            logger.info(f"已删除 {provider.value} 配置")
        else:
            raise Exception(f"删除 {provider.value} 配置失败")

    def get_current_provider(self) -> Optional[LLMProvider]:
        """获取当前使用的提供商"""
        return self._current_provider

    def set_current_provider(self, provider: LLMProvider) -> None:
        """设置当前使用的提供商"""
        if provider not in self._configs:
            logger.warning(f"提供商 {provider.value} 未配置")
            return
        
        if self._config_manager.set_current_provider(provider.value):
            self._current_provider = provider
            logger.info(f"已切换到 {provider.value}")
        else:
            raise Exception(f"设置当前提供商 {provider.value} 失败")

    def get_current_config(self) -> Optional[LLMConfig]:
        """获取当前配置"""
        if not self._current_provider:
            return None
        return self._configs.get(self._current_provider)

    def test_connection(self, provider: LLMProvider) -> Dict[str, Any]:
        """测试连接"""
        config = self._configs.get(provider)
        if not config:
            return {
                'success': False,
                'error': '配置不存在'
            }
        
        try:
            if provider == LLMProvider.OPENAI:
                return self._test_openai_connection(config)
            elif provider == LLMProvider.ANTHROPIC:
                return self._test_anthropic_connection(config)
            elif provider == LLMProvider.GOOGLE:
                return self._test_google_connection(config)
            elif provider == LLMProvider.QIANWEN:
                return self._test_qianwen_connection(config)
            else:
                return {
                    'success': False,
                    'error': '暂不支持该提供商的连接测试'
                }
        except Exception as e:
            logger.error(f"测试 {provider.value} 连接失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _test_openai_connection(self, config: LLMConfig) -> Dict[str, Any]:
        """测试OpenAI连接"""
        try:
            from openai import OpenAI
            
            client = OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout
            )
            
            response = client.chat.completions.create(
                model=config.model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10
            )
            
            return {
                'success': True,
                'model': config.model,
                'response': response.choices[0].message.content[:50]
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _test_anthropic_connection(self, config: LLMConfig) -> Dict[str, Any]:
        """测试Anthropic连接"""
        try:
            from anthropic import Anthropic
            
            client = Anthropic(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout
            )
            
            response = client.messages.create(
                model=config.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
            
            return {
                'success': True,
                'model': config.model,
                'response': response.content[0].text[:50]
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _test_google_connection(self, config: LLMConfig) -> Dict[str, Any]:
        """测试Google连接"""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=config.api_key)
            model = genai.GenerativeModel(config.model)
            
            response = model.generate_content("Hi")
            
            return {
                'success': True,
                'model': config.model,
                'response': response.text[:50]
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _test_qianwen_connection(self, config: LLMConfig) -> Dict[str, Any]:
        """测试通义千问连接"""
        try:
            import dashscope
            from dashscope import Generation
            
            dashscope.api_key = config.api_key
            
            response = Generation.call(
                model=config.model,
                prompt='Hi',
                max_tokens=10
            )
            
            return {
                'success': True,
                'model': config.model,
                'response': response.output.text[:50]
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_api_key_for_provider(self, provider: LLMProvider) -> Optional[str]:
        """获取指定提供商的API密钥"""
        config = self._configs.get(provider)
        return config.api_key if config else None

    def get_api_key_for_current_provider(self) -> Optional[str]:
        """获取当前提供商的API密钥"""
        return self.get_api_key_for_provider(self._current_provider) if self._current_provider else None

    def is_configured(self, provider: LLMProvider) -> bool:
        """检查提供商是否已配置"""
        return provider in self._configs

    def get_available_providers(self) -> List[LLMProvider]:
        """获取已配置的提供商列表"""
        return list(self._configs.keys())

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            'service': 'LLMConfigService',
            'status': 'healthy',
            'current_provider': self._current_provider.value if self._current_provider else None,
            'configured_providers': len(self._configs),
            'providers': [p.value for p in self._configs.keys()]
        }

    def get_config_history(self, provider: Optional[LLMProvider] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取配置历史

        Args:
            provider: 提供商，None表示获取所有配置的历史
            limit: 限制返回数量

        Returns:
            历史记录列表
        """
        try:
            provider_str = provider.value if provider else None
            return self._config_manager.get_config_history(provider_str, limit)
        except Exception as e:
            logger.error(f"获取配置历史失败: {e}")
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
            return self._config_manager.export_config(file_path)
        except Exception as e:
            logger.error(f"导出配置失败: {e}")
            return False

    def import_config(self, file_path: str) -> bool:
        """
        从文件导入配置

        Args:
            file_path: 文件路径

        Returns:
            是否成功
        """
        try:
            success = self._config_manager.import_config(file_path)
            if success:
                self._load_configs()
            return success
        except Exception as e:
            logger.error(f"导入配置失败: {e}")
            return False
