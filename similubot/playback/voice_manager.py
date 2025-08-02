"""
语音管理器 - 管理Discord语音连接和播放控制

负责Discord语音频道的连接、断开和音频播放控制。
提供统一的语音操作接口，隔离Discord API的复杂性。
"""

import logging
import asyncio
from typing import Optional, Dict, Tuple, Any, Callable
import discord
from discord.ext import commands

from similubot.core.interfaces import IVoiceManager


class VoiceManager(IVoiceManager):
    """
    语音管理器实现
    
    管理Discord语音连接，提供播放控制功能。
    支持多服务器同时连接和播放。
    """
    
    def __init__(self, bot: commands.Bot):
        """
        初始化语音管理器
        
        Args:
            bot: Discord机器人实例
        """
        self.bot = bot
        self.logger = logging.getLogger("similubot.playback.voice_manager")
        
        # 语音连接缓存
        self._voice_clients: Dict[int, discord.VoiceClient] = {}
        
        self.logger.debug("语音管理器初始化完成")
    
    def get_voice_client(self, guild_id: int) -> Optional[discord.VoiceClient]:
        """
        获取指定服务器的语音客户端
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            语音客户端，如果不存在则返回None
        """
        # 首先检查缓存
        if guild_id in self._voice_clients:
            voice_client = self._voice_clients[guild_id]
            if voice_client.is_connected():
                return voice_client
            else:
                # 清理无效连接
                del self._voice_clients[guild_id]
        
        # 从bot获取语音客户端
        guild = self.bot.get_guild(guild_id)
        if guild and guild.voice_client:
            self._voice_clients[guild_id] = guild.voice_client
            return guild.voice_client
        
        return None
    
    async def connect_to_channel(self, channel: discord.VoiceChannel) -> Tuple[bool, Optional[str]]:
        """
        连接到语音频道
        
        Args:
            channel: 要连接的语音频道
            
        Returns:
            (成功标志, 错误消息)
        """
        try:
            guild_id = channel.guild.id
            
            # 检查是否已经连接到该服务器
            existing_client = self.get_voice_client(guild_id)
            if existing_client:
                if existing_client.channel == channel:
                    self.logger.debug(f"已连接到频道: {channel.name}")
                    return True, None
                else:
                    # 移动到新频道
                    await existing_client.move_to(channel)
                    self.logger.info(f"移动到频道: {channel.name}")
                    return True, None
            
            # 连接到新频道
            voice_client = await channel.connect()
            self._voice_clients[guild_id] = voice_client
            
            self.logger.info(f"成功连接到语音频道: {channel.name} (服务器: {channel.guild.name})")
            return True, None
            
        except discord.ClientException as e:
            error_msg = f"Discord客户端错误: {e}"
            self.logger.error(error_msg)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"连接语音频道时发生未知错误: {e}"
            self.logger.error(error_msg)
            return False, error_msg
    
    async def connect_to_user_channel(self, user: discord.Member) -> Tuple[bool, Optional[str]]:
        """
        连接到用户所在的语音频道
        
        Args:
            user: Discord用户
            
        Returns:
            (成功标志, 错误消息)
        """
        if not user.voice or not user.voice.channel:
            return False, "用户不在语音频道中"
        
        return await self.connect_to_channel(user.voice.channel)
    
    async def disconnect_from_guild(self, guild_id: int) -> bool:
        """
        从服务器断开语音连接
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            断开是否成功
        """
        try:
            voice_client = self.get_voice_client(guild_id)
            if voice_client:
                await voice_client.disconnect()
                if guild_id in self._voice_clients:
                    del self._voice_clients[guild_id]
                
                self.logger.info(f"已断开语音连接 - 服务器 {guild_id}")
                return True
            else:
                self.logger.debug(f"服务器 {guild_id} 没有语音连接")
                return True
                
        except Exception as e:
            self.logger.error(f"断开语音连接失败 - 服务器 {guild_id}: {e}")
            return False
    
    async def play_audio(
        self, 
        guild_id: int, 
        source: discord.AudioSource, 
        after_callback: Optional[Callable[[Optional[Exception]], None]] = None
    ) -> bool:
        """
        播放音频
        
        Args:
            guild_id: 服务器ID
            source: 音频源
            after_callback: 播放完成后的回调函数
            
        Returns:
            播放是否成功开始
        """
        try:
            voice_client = self.get_voice_client(guild_id)
            if not voice_client:
                self.logger.error(f"服务器 {guild_id} 没有语音连接")
                return False
            
            if not voice_client.is_connected():
                self.logger.error(f"服务器 {guild_id} 语音连接已断开")
                return False
            
            # 停止当前播放（如果有）
            if voice_client.is_playing():
                voice_client.stop()
            
            # 开始播放
            voice_client.play(source, after=after_callback)
            
            self.logger.debug(f"开始播放音频 - 服务器 {guild_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"播放音频失败 - 服务器 {guild_id}: {e}")
            return False
    
    def stop_audio(self, guild_id: int) -> bool:
        """
        停止音频播放
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            停止是否成功
        """
        try:
            voice_client = self.get_voice_client(guild_id)
            if voice_client and voice_client.is_playing():
                voice_client.stop()
                self.logger.debug(f"停止音频播放 - 服务器 {guild_id}")
                return True
            return True
            
        except Exception as e:
            self.logger.error(f"停止音频播放失败 - 服务器 {guild_id}: {e}")
            return False
    
    def pause_audio(self, guild_id: int) -> bool:
        """
        暂停音频播放
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            暂停是否成功
        """
        try:
            voice_client = self.get_voice_client(guild_id)
            if voice_client and voice_client.is_playing():
                voice_client.pause()
                self.logger.debug(f"暂停音频播放 - 服务器 {guild_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"暂停音频播放失败 - 服务器 {guild_id}: {e}")
            return False
    
    def resume_audio(self, guild_id: int) -> bool:
        """
        恢复音频播放
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            恢复是否成功
        """
        try:
            voice_client = self.get_voice_client(guild_id)
            if voice_client and voice_client.is_paused():
                voice_client.resume()
                self.logger.debug(f"恢复音频播放 - 服务器 {guild_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"恢复音频播放失败 - 服务器 {guild_id}: {e}")
            return False
    
    def is_playing(self, guild_id: int) -> bool:
        """
        检查是否正在播放音频
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            如果正在播放则返回True
        """
        voice_client = self.get_voice_client(guild_id)
        return voice_client is not None and voice_client.is_playing()
    
    def is_paused(self, guild_id: int) -> bool:
        """
        检查是否暂停播放
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            如果暂停则返回True
        """
        voice_client = self.get_voice_client(guild_id)
        return voice_client is not None and voice_client.is_paused()
    
    def is_connected(self, guild_id: int) -> bool:
        """
        检查是否已连接到语音频道
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            如果已连接则返回True
        """
        voice_client = self.get_voice_client(guild_id)
        return voice_client is not None and voice_client.is_connected()
    
    def is_idle(self, guild_id: int) -> bool:
        """
        检查是否空闲（已连接但未播放）
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            如果空闲则返回True
        """
        voice_client = self.get_voice_client(guild_id)
        if not voice_client or not voice_client.is_connected():
            return False
        
        return not voice_client.is_playing() and not voice_client.is_paused()
    
    def get_connection_info(self, guild_id: int) -> Dict[str, Any]:
        """
        获取语音连接信息
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            连接信息字典
        """
        voice_client = self.get_voice_client(guild_id)
        
        if not voice_client:
            return {
                'connected': False,
                'channel': None,
                'playing': False,
                'paused': False
            }
        
        return {
            'connected': voice_client.is_connected(),
            'channel': voice_client.channel.name if voice_client.channel else None,
            'playing': voice_client.is_playing(),
            'paused': voice_client.is_paused(),
            'latency': voice_client.latency,
            'average_latency': voice_client.average_latency
        }
    
    async def cleanup_all_connections(self) -> None:
        """清理所有语音连接"""
        try:
            for guild_id in list(self._voice_clients.keys()):
                await self.disconnect_from_guild(guild_id)
            
            self.logger.info("所有语音连接已清理")
            
        except Exception as e:
            self.logger.error(f"清理语音连接时发生错误: {e}")
