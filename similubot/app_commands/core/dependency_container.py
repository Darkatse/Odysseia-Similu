"""
依赖注入容器

管理应用程序的依赖关系，提供：
- 服务注册和解析
- 单例模式支持
- 生命周期管理
- 配置驱动的依赖注入
"""

import logging
from typing import Any, Dict, Type, TypeVar, Optional, Callable
from similubot.utils.config_manager import ConfigManager

T = TypeVar('T')


class DependencyContainer:
    """
    依赖注入容器

    管理应用程序中所有服务的创建和生命周期
    """

    def __init__(self):
        """初始化依赖容器"""
        self._services: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable[[], Any]] = {}
        self._singletons: Dict[Type, Any] = {}
        self.logger = logging.getLogger("similubot.app_commands.dependency_container")

        self.logger.debug("依赖注入容器已初始化")

    def register_singleton(self, service_type: Type[T], instance: T) -> None:
        """
        注册单例服务

        Args:
            service_type: 服务类型
            instance: 服务实例
        """
        self._singletons[service_type] = instance
        self.logger.debug(f"注册单例服务: {service_type.__name__}")

    def register_factory(self, service_type: Type[T], factory: Callable[[], T]) -> None:
        """
        注册工厂方法

        Args:
            service_type: 服务类型
            factory: 工厂方法
        """
        self._factories[service_type] = factory
        self.logger.debug(f"注册工厂方法: {service_type.__name__}")

    def register_transient(self, service_type: Type[T], implementation: Type[T]) -> None:
        """
        注册瞬态服务

        Args:
            service_type: 服务类型
            implementation: 实现类型
        """
        self._services[service_type] = implementation
        self.logger.debug(f"注册瞬态服务: {service_type.__name__} -> {implementation.__name__}")

    def resolve(self, service_type: Type[T]) -> T:
        """
        解析服务实例

        Args:
            service_type: 服务类型

        Returns:
            服务实例

        Raises:
            ValueError: 如果服务未注册
        """
        # 检查单例
        if service_type in self._singletons:
            return self._singletons[service_type]

        # 检查工厂方法
        if service_type in self._factories:
            return self._factories[service_type]()

        # 检查瞬态服务
        if service_type in self._services:
            implementation = self._services[service_type]
            return implementation()

        raise ValueError(f"服务未注册: {service_type.__name__}")

    def try_resolve(self, service_type: Type[T]) -> Optional[T]:
        """
        尝试解析服务实例

        Args:
            service_type: 服务类型

        Returns:
            服务实例或None
        """
        try:
            return self.resolve(service_type)
        except ValueError:
            return None

    def is_registered(self, service_type: Type) -> bool:
        """
        检查服务是否已注册

        Args:
            service_type: 服务类型

        Returns:
            True if registered, False otherwise
        """
        return (service_type in self._singletons or
                service_type in self._factories or
                service_type in self._services)

    def clear(self) -> None:
        """清空所有注册的服务"""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()
        self.logger.debug("依赖容器已清空")


class ServiceProvider:
    """
    服务提供者

    为App Commands提供预配置的依赖注入容器
    """

    def __init__(self, config: ConfigManager, music_player: Any):
        """
        初始化服务提供者

        Args:
            config: 配置管理器
            music_player: 音乐播放器实例
        """
        self.container = DependencyContainer()
        self.logger = logging.getLogger("similubot.app_commands.service_provider")

        # 注册核心服务
        self._register_core_services(config, music_player)

        self.logger.debug("服务提供者已初始化")

    def _register_core_services(self, config: ConfigManager, music_player: Any) -> None:
        """
        注册核心服务

        Args:
            config: 配置管理器
            music_player: 音乐播放器实例
        """
        # 注册配置管理器
        self.container.register_singleton(ConfigManager, config)

        # 注册音乐播放器
        self.container.register_singleton(type(music_player), music_player)

        self.logger.debug("核心服务已注册")

    def get_container(self) -> DependencyContainer:
        """
        获取依赖容器

        Returns:
            依赖注入容器实例
        """
        return self.container