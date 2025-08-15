"""
随机歌曲选择器

实现加权随机选择算法，支持从不同来源池中选择歌曲：
- 全局池（所有用户的歌曲历史）
- 个人池（用户自己的歌曲历史）
- 指定用户池（特定用户的歌曲历史）
"""

import logging
import random
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass

from .database import SongHistoryDatabase, SongHistoryEntry
from similubot.core.interfaces import AudioInfo
import discord


class CardDrawSource(Enum):
    """抽卡来源类型"""
    GLOBAL = "global"  # 全局池
    PERSONAL = "personal"  # 个人池
    SPECIFIC_USER = "specific_user"  # 指定用户池


@dataclass
class CardDrawConfig:
    """抽卡配置"""
    source: CardDrawSource
    target_user_id: Optional[int] = None  # 当source为SPECIFIC_USER时使用
    max_redraws: int = 3
    timeout_seconds: int = 60


class RandomSongSelector:
    """
    随机歌曲选择器
    
    负责从歌曲历史数据库中根据配置的来源和权重策略选择歌曲。
    支持多种选择策略和权重分配算法。
    """
    
    def __init__(self, database: SongHistoryDatabase):
        """
        初始化随机选择器
        
        Args:
            database: 歌曲历史数据库实例
        """
        self.database = database
        self.logger = logging.getLogger("similubot.card_draw.selector")
        
        # 权重配置
        self.weight_config = {
            "recent_bonus": 1.2,  # 最近歌曲的权重加成
            "frequency_penalty": 0.8,  # 高频歌曲的权重惩罚
            "user_diversity_bonus": 1.1,  # 用户多样性加成
        }
        
        self.logger.debug("随机歌曲选择器初始化完成")
    
    async def select_random_song(
        self, 
        guild_id: int, 
        config: CardDrawConfig,
        exclude_recent: bool = True
    ) -> Optional[SongHistoryEntry]:
        """
        根据配置选择随机歌曲
        
        Args:
            guild_id: 服务器ID
            config: 抽卡配置
            exclude_recent: 是否排除最近播放的歌曲
            
        Returns:
            选中的歌曲记录，如果没有可选歌曲则返回None
        """
        try:
            # 根据来源类型获取候选歌曲
            candidates = await self._get_candidates(guild_id, config)
            
            if not candidates:
                self.logger.warning(f"没有找到候选歌曲 - 服务器: {guild_id}, 来源: {config.source}")
                return None
            
            # 应用权重算法选择歌曲
            selected_song = self._weighted_random_selection(candidates)
            
            self.logger.info(f"随机选择歌曲: {selected_song.title} - 来源: {config.source}")
            return selected_song
            
        except Exception as e:
            self.logger.error(f"随机选择歌曲失败: {e}", exc_info=True)
            return None
    
    async def _get_candidates(
        self, 
        guild_id: int, 
        config: CardDrawConfig
    ) -> List[SongHistoryEntry]:
        """
        根据配置获取候选歌曲列表
        
        Args:
            guild_id: 服务器ID
            config: 抽卡配置
            
        Returns:
            候选歌曲列表
        """
        if config.source == CardDrawSource.GLOBAL:
            # 全局池：所有用户的歌曲
            return await self.database.get_random_songs(guild_id, user_id=None, limit=100)
            
        elif config.source == CardDrawSource.PERSONAL:
            # 个人池：需要在调用时传入用户ID
            raise ValueError("个人池模式需要在上层调用中处理用户ID")
            
        elif config.source == CardDrawSource.SPECIFIC_USER:
            # 指定用户池
            if not config.target_user_id:
                raise ValueError("指定用户池模式需要提供target_user_id")
            return await self.database.get_random_songs(
                guild_id, 
                user_id=config.target_user_id, 
                limit=100
            )
        
        return []
    
    async def get_candidates_for_user(
        self, 
        guild_id: int, 
        user_id: int, 
        config: CardDrawConfig
    ) -> List[SongHistoryEntry]:
        """
        为特定用户获取候选歌曲（处理个人池模式）
        
        Args:
            guild_id: 服务器ID
            user_id: 用户ID
            config: 抽卡配置
            
        Returns:
            候选歌曲列表
        """
        if config.source == CardDrawSource.PERSONAL:
            return await self.database.get_random_songs(guild_id, user_id=user_id, limit=100)
        else:
            return await self._get_candidates(guild_id, config)
    
    def _weighted_random_selection(self, candidates: List[SongHistoryEntry]) -> SongHistoryEntry:
        """
        使用权重算法进行随机选择
        
        Args:
            candidates: 候选歌曲列表
            
        Returns:
            选中的歌曲
        """
        if not candidates:
            raise ValueError("候选歌曲列表为空")
        
        if len(candidates) == 1:
            return candidates[0]
        
        # 计算每首歌曲的权重
        weights = []
        for song in candidates:
            weight = self._calculate_song_weight(song, candidates)
            weights.append(weight)
        
        # 使用权重进行随机选择
        selected_song = random.choices(candidates, weights=weights, k=1)[0]
        
        self.logger.debug(f"权重选择完成 - 选中: {selected_song.title}")
        return selected_song
    
    def _calculate_song_weight(
        self, 
        song: SongHistoryEntry, 
        all_candidates: List[SongHistoryEntry]
    ) -> float:
        """
        计算歌曲的选择权重
        
        Args:
            song: 目标歌曲
            all_candidates: 所有候选歌曲
            
        Returns:
            歌曲权重值
        """
        base_weight = 1.0
        
        # 基础权重：所有歌曲起始权重相同
        weight = base_weight
        
        # 时间因子：较新的歌曲获得轻微加成
        # 这里简化处理，实际可以根据timestamp计算
        
        # 用户多样性：鼓励不同用户的歌曲被选中
        user_song_count = sum(1 for s in all_candidates if s.user_id == song.user_id)
        if user_song_count > 1:
            diversity_factor = 1.0 / (user_song_count ** 0.5)
            weight *= diversity_factor
        
        # 确保权重为正数
        return max(weight, 0.1)
    
    async def get_source_statistics(
        self, 
        guild_id: int, 
        config: CardDrawConfig
    ) -> Dict[str, Any]:
        """
        获取指定来源的统计信息
        
        Args:
            guild_id: 服务器ID
            config: 抽卡配置
            
        Returns:
            统计信息字典
        """
        try:
            if config.source == CardDrawSource.GLOBAL:
                total_count = await self.database.get_total_song_count(guild_id)
                return {
                    "source": "全局池",
                    "total_songs": total_count,
                    "description": f"包含服务器内所有用户的 {total_count} 首歌曲"
                }
                
            elif config.source == CardDrawSource.SPECIFIC_USER and config.target_user_id:
                user_count = await self.database.get_user_song_count(guild_id, config.target_user_id)
                return {
                    "source": "指定用户池",
                    "total_songs": user_count,
                    "target_user_id": config.target_user_id,
                    "description": f"包含指定用户的 {user_count} 首歌曲"
                }
            
            return {"source": "未知", "total_songs": 0}
            
        except Exception as e:
            self.logger.error(f"获取来源统计信息失败: {e}", exc_info=True)
            return {"source": "错误", "total_songs": 0}
