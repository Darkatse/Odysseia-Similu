"""
持久化管理器 - 处理队列状态的持久化存储

负责将队列状态保存到磁盘并在需要时恢复。
使用JSON格式存储，提供完整的错误处理和数据验证。
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import discord

from similubot.core.interfaces import IPersistenceManager, SongInfo
from .song import Song


class PersistenceManager(IPersistenceManager):
    """
    持久化管理器实现
    
    负责队列状态的保存和恢复，使用JSON格式存储。
    提供数据验证、错误处理和备份机制。
    """
    
    def __init__(self, data_dir: str = "data"):
        """
        初始化持久化管理器
        
        Args:
            data_dir: 数据存储目录
        """
        self.logger = logging.getLogger("similubot.queue.persistence")
        self.data_dir = Path(data_dir)
        self.queues_dir = self.data_dir / "queues"
        
        # 创建必要的目录
        self._ensure_directories()
        
        # 保存锁，防止并发写入
        self._save_lock = asyncio.Lock()
        
        self.logger.info(f"持久化管理器初始化完成 - 数据目录: {self.data_dir}")
    
    def _ensure_directories(self) -> None:
        """确保所有必要的目录存在"""
        try:
            self.data_dir.mkdir(exist_ok=True)
            self.queues_dir.mkdir(exist_ok=True)
            self.logger.debug("持久化目录创建完成")
        except Exception as e:
            self.logger.error(f"创建持久化目录失败: {e}")
            raise
    
    def _get_queue_file_path(self, guild_id: int) -> Path:
        """获取指定服务器的队列文件路径"""
        return self.queues_dir / f"guild_{guild_id}.json"
    
    def _validate_song_data(self, song_data: Dict[str, Any]) -> bool:
        """验证歌曲数据的完整性"""
        required_fields = ['title', 'duration', 'url', 'uploader', 'requester_id', 'requester_name', 'added_at']
        return all(field in song_data for field in required_fields)
    
    def _validate_queue_state_data(self, data: Dict[str, Any]) -> bool:
        """验证队列状态数据的完整性"""
        try:
            # 检查必要字段
            if not isinstance(data.get('guild_id'), int):
                return False
            if not isinstance(data.get('queue'), list):
                return False
            if not isinstance(data.get('current_position'), (int, float)):
                return False
            
            # 验证队列中的歌曲数据
            for song_data in data.get('queue', []):
                if not self._validate_song_data(song_data):
                    return False
            
            # 验证当前歌曲数据（如果存在）
            current_song = data.get('current_song')
            if current_song and not self._validate_song_data(current_song):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"验证队列状态数据时发生错误: {e}")
            return False
    
    def _validate_song_url(self, song: Song) -> bool:
        """验证歌曲URL是否有效（简单检查）"""
        try:
            url = song.url.lower()
            return ("youtube.com" in url or "youtu.be" in url or "catbox.moe" in url)
        except:
            return False
    
    async def save_queue_state(
        self, 
        guild_id: int, 
        current_song: Optional[SongInfo], 
        queue: List[SongInfo], 
        current_position: float = 0.0
    ) -> bool:
        """
        保存队列状态到磁盘
        
        Args:
            guild_id: 服务器ID
            current_song: 当前播放的歌曲
            queue: 队列中的歌曲列表
            current_position: 当前播放位置（秒）
            
        Returns:
            保存是否成功
        """
        async with self._save_lock:
            try:
                # 转换数据为可序列化格式
                queue_data = []
                for song in queue:
                    if isinstance(song, Song):
                        song_dict = song.to_dict()
                        if song_dict:
                            queue_data.append(song_dict)

                current_song_data = None
                if current_song and isinstance(current_song, Song):
                    current_song_data = current_song.to_dict()

                # 创建保存数据
                save_data = {
                    "guild_id": guild_id,
                    "current_song": current_song_data,
                    "queue": queue_data,
                    "current_position": current_position,
                    "last_updated": datetime.now().isoformat(),
                    "version": "1.0"
                }

                # 验证数据完整性
                if not self._validate_queue_state_data(save_data):
                    self.logger.error(f"队列状态数据验证失败 - 服务器 {guild_id}")
                    return False

                # 写入文件
                file_path = self._get_queue_file_path(guild_id)
                
                def write_file():
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(save_data, f, ensure_ascii=False, indent=2)

                # 在线程池中执行文件写入
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, write_file)

                self.logger.debug(f"队列状态保存成功 - 服务器 {guild_id}, 队列长度: {len(queue)}")
                return True

            except Exception as e:
                self.logger.error(f"保存队列状态失败 - 服务器 {guild_id}: {e}")
                return False
    
    async def load_queue_state(self, guild_id: int, guild: discord.Guild) -> Optional[Dict[str, Any]]:
        """
        从磁盘加载队列状态
        
        Args:
            guild_id: 服务器ID
            guild: Discord服务器对象
            
        Returns:
            包含队列状态的字典，如果加载失败则返回None
        """
        try:
            file_path = self._get_queue_file_path(guild_id)
            if not file_path.exists():
                return None

            # 读取文件
            def read_file():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, read_file)

            # 验证数据完整性
            if not self._validate_queue_state_data(data):
                self.logger.warning(f"队列状态数据验证失败 - 服务器 {guild_id}")
                return None

            # 转换为Song对象
            restored_queue = []
            invalid_songs = []
            
            for song_data in data.get("queue", []):
                song = Song.from_dict(song_data, guild)
                if song and self._validate_song_url(song):
                    restored_queue.append(song)
                else:
                    invalid_songs.append(song_data.get("title", "Unknown"))

            current_song = None
            current_song_data = data.get("current_song")
            if current_song_data:
                current_song = Song.from_dict(current_song_data, guild)
                if current_song and not self._validate_song_url(current_song):
                    invalid_songs.append(current_song.title)
                    current_song = None

            result = {
                'current_song': current_song,
                'queue': restored_queue,
                'current_position': data.get('current_position', 0.0),
                'invalid_songs': invalid_songs
            }

            self.logger.info(f"队列状态加载成功 - 服务器 {guild_id}, 恢复 {len(restored_queue)} 首歌曲")
            if invalid_songs:
                self.logger.warning(f"发现 {len(invalid_songs)} 首无效歌曲: {invalid_songs}")

            return result

        except Exception as e:
            self.logger.error(f"加载队列状态失败 - 服务器 {guild_id}: {e}")
            return None
    
    async def delete_queue_state(self, guild_id: int) -> bool:
        """
        删除指定服务器的队列状态文件
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            删除是否成功
        """
        try:
            file_path = self._get_queue_file_path(guild_id)
            if file_path.exists():
                file_path.unlink()
                self.logger.debug(f"队列状态文件删除成功 - 服务器 {guild_id}")
            return True
        except Exception as e:
            self.logger.error(f"删除队列状态文件失败 - 服务器 {guild_id}: {e}")
            return False
    
    async def get_all_guild_ids(self) -> List[int]:
        """
        获取所有有保存队列状态的服务器ID
        
        Returns:
            服务器ID列表
        """
        try:
            guild_ids = []
            for file_path in self.queues_dir.glob("guild_*.json"):
                try:
                    guild_id_str = file_path.stem.replace("guild_", "")
                    guild_id = int(guild_id_str)
                    guild_ids.append(guild_id)
                except ValueError:
                    continue
            return guild_ids
        except Exception as e:
            self.logger.error(f"获取服务器ID列表失败: {e}")
            return []
    
    def get_persistence_stats(self) -> Dict[str, Any]:
        """
        获取持久化系统统计信息
        
        Returns:
            统计信息字典
        """
        try:
            stats = {
                'persistence_enabled': True,
                'data_directory': str(self.data_dir),
                'queue_files': len(list(self.queues_dir.glob("guild_*.json"))),
                'total_size_bytes': sum(f.stat().st_size for f in self.queues_dir.glob("guild_*.json"))
            }
            return stats
        except Exception as e:
            self.logger.error(f"获取持久化统计信息失败: {e}")
            return {'persistence_enabled': False}
