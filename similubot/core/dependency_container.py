"""
依赖注入容器 - 现代化的依赖管理系统

提供类型安全的依赖注入，确保组件按正确顺序初始化，
避免循环依赖和初始化顺序问题。
"""

import logging
from typing import Dict, Any, TypeVar, Type, Optional, Callable
from dataclasses import dataclass
from enum import Enum


T = TypeVar('T')


class DependencyScope(Enum):
    """依赖项作用域"""
    SINGLETON = "singleton"  # 单例模式
    TRANSIENT = "transient"  # 每次创建新实例


@dataclass
class DependencyRegistration:
    """依赖项注册信息"""
    factory: Callable[..., Any]
    scope: DependencyScope
    dependencies: list[str]
    instance: Optional[Any] = None
    initialized: bool = False


class DependencyContainer:
    """
    依赖注入容器
    
    管理组件的创建、依赖关系和生命周期。
    确保依赖项按正确顺序初始化，避免循环依赖。
    """
    
    def __init__(self):
        """初始化依赖容器"""
        self.logger = logging.getLogger("similubot.core.dependency")
        self._registrations: Dict[str, DependencyRegistration] = {}
        self._initialization_order: list[str] = []
        self._initializing: set[str] = set()  # 防止循环依赖
        
    def register_singleton(
        self, 
        name: str, 
        factory: Callable[..., T], 
        dependencies: Optional[list[str]] = None
    ) -> None:
        """
        注册单例依赖项
        
        Args:
            name: 依赖项名称
            factory: 创建实例的工厂函数
            dependencies: 依赖的其他组件名称列表
        """
        self._register(name, factory, DependencyScope.SINGLETON, dependencies or [])
        
    def register_transient(
        self, 
        name: str, 
        factory: Callable[..., T], 
        dependencies: Optional[list[str]] = None
    ) -> None:
        """
        注册瞬态依赖项（每次创建新实例）
        
        Args:
            name: 依赖项名称
            factory: 创建实例的工厂函数
            dependencies: 依赖的其他组件名称列表
        """
        self._register(name, factory, DependencyScope.TRANSIENT, dependencies or [])
        
    def _register(
        self, 
        name: str, 
        factory: Callable[..., Any], 
        scope: DependencyScope, 
        dependencies: list[str]
    ) -> None:
        """内部注册方法"""
        if name in self._registrations:
            raise ValueError(f"依赖项 '{name}' 已经注册")
            
        self._registrations[name] = DependencyRegistration(
            factory=factory,
            scope=scope,
            dependencies=dependencies
        )
        
        self.logger.debug(f"📝 注册依赖项: {name} ({scope.value})")
        
    def resolve(self, name: str) -> Any:
        """
        解析依赖项
        
        Args:
            name: 依赖项名称
            
        Returns:
            依赖项实例
            
        Raises:
            ValueError: 依赖项未注册
            RuntimeError: 循环依赖或初始化失败
        """
        if name not in self._registrations:
            raise ValueError(f"依赖项 '{name}' 未注册")
            
        registration = self._registrations[name]
        
        # 检查循环依赖
        if name in self._initializing:
            raise RuntimeError(f"检测到循环依赖: {name}")
            
        # 单例模式：如果已初始化，直接返回
        if registration.scope == DependencyScope.SINGLETON and registration.initialized:
            return registration.instance
            
        try:
            self._initializing.add(name)
            self.logger.debug(f"🔧 开始解析依赖项: {name}")
            
            # 解析依赖项
            resolved_dependencies = {}
            for dep_name in registration.dependencies:
                resolved_dependencies[dep_name] = self.resolve(dep_name)
                
            # 创建实例
            instance = registration.factory(**resolved_dependencies)
            
            # 单例模式：缓存实例
            if registration.scope == DependencyScope.SINGLETON:
                registration.instance = instance
                registration.initialized = True
                
            self.logger.debug(f"✅ 依赖项解析完成: {name}")
            return instance
            
        except Exception as e:
            self.logger.error(f"❌ 依赖项解析失败: {name} - {e}", exc_info=True)
            raise RuntimeError(f"依赖项 '{name}' 解析失败: {e}") from e
        finally:
            self._initializing.discard(name)
            
    def resolve_all(self) -> Dict[str, Any]:
        """
        解析所有已注册的单例依赖项
        
        Returns:
            所有单例依赖项的字典
        """
        resolved = {}
        
        for name, registration in self._registrations.items():
            if registration.scope == DependencyScope.SINGLETON:
                try:
                    resolved[name] = self.resolve(name)
                except Exception as e:
                    self.logger.error(f"❌ 解析依赖项 {name} 失败: {e}")
                    
        return resolved
        
    def get_dependency_graph(self) -> Dict[str, list[str]]:
        """
        获取依赖关系图
        
        Returns:
            依赖关系图字典
        """
        return {
            name: registration.dependencies 
            for name, registration in self._registrations.items()
        }
        
    def validate_dependencies(self) -> bool:
        """
        验证依赖关系是否有效（无循环依赖）
        
        Returns:
            True 如果依赖关系有效
            
        Raises:
            RuntimeError: 存在循环依赖
        """
        visited = set()
        rec_stack = set()
        
        def has_cycle(node: str) -> bool:
            if node in rec_stack:
                return True
            if node in visited:
                return False
                
            visited.add(node)
            rec_stack.add(node)
            
            registration = self._registrations.get(node)
            if registration:
                for dep in registration.dependencies:
                    if dep not in self._registrations:
                        raise RuntimeError(f"依赖项 '{dep}' 未注册（被 '{node}' 依赖）")
                    if has_cycle(dep):
                        return True
                        
            rec_stack.remove(node)
            return False
            
        for name in self._registrations:
            if name not in visited:
                if has_cycle(name):
                    raise RuntimeError(f"检测到循环依赖，涉及组件: {name}")
                    
        self.logger.info("✅ 依赖关系验证通过")
        return True
        
    def clear(self) -> None:
        """清空所有依赖项"""
        self._registrations.clear()
        self._initialization_order.clear()
        self._initializing.clear()
        self.logger.debug("🧹 依赖容器已清空")
