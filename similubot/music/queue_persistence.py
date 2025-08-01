"""
队列持久化管理器 - 轻量级音乐队列状态保存和恢复

实现音乐队列的持久化存储，防止机器人重启时丢失队列数据。
使用 JSON 格式存储，专注于核心功能，保持简单高效。
"""

import json
import logging
import os
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import discord

from .audio_source import UnifiedAudioInfo, AudioSourceType


class QueuePersistence:
    """
    队列持久化管理器
    
    负责将音乐队列状态保存到磁盘并在机器人重启时恢复。
    使用 JSON 格式存储，专注于核心功能。
    """

    def __init__(self, data_dir: str = "data"):
        """
        初始化队列持久化管理器
        
        Args:
            data_dir: 数据存储目录
        """
        self.logger = logging.getLogger("similubot.music.queue_persistence")
        self.data_dir = Path(data_dir)
        self.queues_dir = self.data_dir / "queues"
        
        # 创建必要的目录
        self._ensure_directories()
        
        # 保存锁，防止并发写入
        self._save_lock = asyncio.Lock()
        
        self.logger.info(f"队列持久化管理器初始化完成 - 数据目录: {self.data_dir}")

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

    def _song_to_dict(self, song) -> Dict[str, Any]:
        """将 Song 对象转换为字典"""
        try:
            # 获取音频源类型
            source_type = "youtube"  # 默认值
            if hasattr(song.audio_info, 'source_type'):
                source_type = song.audio_info.source_type.value
            elif "catbox.moe" in song.url:
                source_type = "catbox"

            return {
                "title": song.title,
                "duration": song.duration,
                "url": song.url,
                "uploader": song.uploader,
                "source_type": source_type,
                "requester_id": song.requester.id,
                "requester_name": song.requester.display_name,
                "added_at": song.added_at.isoformat()
            }
        except Exception as e:
            self.logger.error(f"转换歌曲到字典失败: {e}")
            return None

    def _dict_to_song(self, data: Dict[str, Any], guild: discord.Guild):
        """将字典转换为 Song 对象"""
        try:
            # 获取请求者
            requester = guild.get_member(data["requester_id"])
            if not requester:
                # 创建虚拟成员对象
                class MockMember:
                    def __init__(self, user_id: int, name: str, guild_obj: discord.Guild):
                        self.id = user_id
                        self.display_name = name
                        self.guild = guild_obj
                
                requester = MockMember(data["requester_id"], data["requester_name"], guild)

            # 创建音频信息对象
            audio_info = UnifiedAudioInfo(
                title=data["title"],
                duration=data["duration"],
                file_path=data["url"],
                url=data["url"],
                uploader=data["uploader"],
                source_type=AudioSourceType(data.get("source_type", "youtube"))
            )

            # 导入 Song 类（避免循环导入）
            from .queue_manager import Song
            
            return Song(
                audio_info=audio_info,
                requester=requester,
                added_at=datetime.fromisoformat(data["added_at"])
            )

        except Exception as e:
            self.logger.error(f"转换字典到歌曲失败: {e}")
            return None

    async def save_queue_state(self, guild_id: int, current_song, queue: List, current_position: float = 0.0) -> bool:
        """
        保存队列状态到磁盘
        
        Args:
            guild_id: 服务器 ID
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
                    song_dict = self._song_to_dict(song)
                    if song_dict:
                        queue_data.append(song_dict)

                current_song_data = None
                if current_song:
                    current_song_data = self._song_to_dict(current_song)

                # 创建保存数据
                save_data = {
                    "guild_id": guild_id,
                    "current_song": current_song_data,
                    "queue": queue_data,
                    "current_position": current_position,
                    "last_updated": datetime.now().isoformat(),
                    "version": "1.0"
                }

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
            guild_id: 服务器 ID
            guild: Discord 服务器对象
            
        Returns:
            包含队列状态的字典，如果加载失败则返回 None
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

            # 转换为 Song 对象
            restored_queue = []
            invalid_songs = []
            
            for song_data in data.get("queue", []):
                song = self._dict_to_song(song_data, guild)
                if song and self._validate_song_url(song):
                    restored_queue.append(song)
                else:
                    invalid_songs.append(song_data.get("title", "Unknown"))

            current_song = None
            if data.get("current_song"):
                current_song = self._dict_to_song(data["current_song"], guild)

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

    def _validate_song_url(self, song) -> bool:
        """验证歌曲 URL 是否有效（简单检查）"""
        try:
            url = song.url.lower()
            return ("youtube.com" in url or "youtu.be" in url or "catbox.moe" in url)
        except:
            return False

    async def delete_queue_state(self, guild_id: int) -> bool:
        """删除指定服务器的队列状态文件"""
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
        """获取所有有保存队列状态的服务器 ID"""
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
            self.logger.error(f"获取服务器 ID 列表失败: {e}")
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
                'auto_save_enabled': True,
                'queue_files': len(list(self.queues_dir.glob("guild_*.json"))),
                'backup_files': 0  # 简化版本不支持备份
            }
            return stats
        except Exception as e:
            self.logger.error(f"获取持久化统计信息失败: {e}")
            return {'persistence_enabled': False}
