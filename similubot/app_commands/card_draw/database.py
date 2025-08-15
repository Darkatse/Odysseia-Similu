"""
歌曲历史数据库管理

负责存储和管理所有队列歌曲的历史记录，用于随机抽卡功能。
包括歌曲元数据、用户信息、时间戳、来源平台等信息。
"""

import sqlite3
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from similubot.core.interfaces import AudioInfo
import discord


@dataclass
class SongHistoryEntry:
    """歌曲历史记录条目"""
    id: Optional[int]
    title: str
    artist: str
    url: str
    user_id: int
    user_name: str
    guild_id: int
    timestamp: datetime
    source_platform: str
    duration: int
    thumbnail_url: Optional[str] = None
    file_format: Optional[str] = None


class SongHistoryDatabase:
    """
    歌曲历史数据库管理器
    
    使用SQLite存储所有队列歌曲的历史记录，支持：
    - 歌曲记录的增删改查
    - 按用户、服务器、时间范围查询
    - 随机选择支持
    - 数据库自动初始化和迁移
    """
    
    def __init__(self, data_dir: str = "data"):
        """
        初始化歌曲历史数据库
        
        Args:
            data_dir: 数据存储目录
        """
        self.logger = logging.getLogger("similubot.card_draw.database")
        self.data_dir = Path(data_dir)
        self.db_path = self.data_dir / "song_history.db"
        
        # 创建数据目录
        self.data_dir.mkdir(exist_ok=True)
        
        # 数据库连接锁
        self._db_lock = asyncio.Lock()
        
        self.logger.info(f"歌曲历史数据库初始化 - 路径: {self.db_path}")
    
    async def initialize(self) -> bool:
        """
        初始化数据库表结构
        
        Returns:
            初始化是否成功
        """
        async with self._db_lock:
            try:
                await self._create_tables()
                self.logger.info("歌曲历史数据库表结构初始化完成")
                return True
            except Exception as e:
                self.logger.error(f"数据库初始化失败: {e}", exc_info=True)
                return False
    
    async def _create_tables(self) -> None:
        """创建数据库表结构"""
        def create_tables():
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                
                # 创建歌曲历史表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS song_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        artist TEXT NOT NULL,
                        url TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        user_name TEXT NOT NULL,
                        guild_id INTEGER NOT NULL,
                        timestamp DATETIME NOT NULL,
                        source_platform TEXT NOT NULL,
                        duration INTEGER NOT NULL,
                        thumbnail_url TEXT,
                        file_format TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 创建索引以提高查询性能
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_song_history_user_id 
                    ON song_history(user_id)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_song_history_guild_id 
                    ON song_history(guild_id)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_song_history_timestamp 
                    ON song_history(timestamp)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_song_history_source_platform 
                    ON song_history(source_platform)
                ''')
                
                conn.commit()
                
            finally:
                conn.close()
        
        # 在线程池中执行数据库操作
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, create_tables)
    
    async def add_song_record(
        self,
        audio_info: AudioInfo,
        requester: discord.Member,
        guild_id: int,
        source_platform: str = "unknown"
    ) -> bool:
        """
        添加歌曲记录到历史数据库（支持按用户去重）

        实现按用户去重逻辑：
        - 如果同一用户在同一服务器已添加过相同URL的歌曲，则更新现有记录的时间戳
        - 不同用户可以添加相同的歌曲

        Args:
            audio_info: 音频信息
            requester: 请求用户
            guild_id: 服务器ID
            source_platform: 来源平台

        Returns:
            添加是否成功
        """
        async with self._db_lock:
            try:
                def upsert_record():
                    conn = sqlite3.connect(self.db_path)
                    try:
                        cursor = conn.cursor()

                        # 检查是否存在相同用户的相同歌曲记录
                        cursor.execute('''
                            SELECT id FROM song_history
                            WHERE user_id = ? AND url = ? AND guild_id = ?
                        ''', (requester.id, audio_info.url, guild_id))

                        existing_record = cursor.fetchone()

                        if existing_record:
                            # 更新现有记录的时间戳和其他可能变化的信息
                            cursor.execute('''
                                UPDATE song_history
                                SET timestamp = ?, user_name = ?, title = ?, artist = ?,
                                    source_platform = ?, duration = ?, thumbnail_url = ?, file_format = ?
                                WHERE id = ?
                            ''', (
                                datetime.now(),
                                requester.display_name,
                                audio_info.title,
                                audio_info.uploader,
                                source_platform,
                                audio_info.duration,
                                audio_info.thumbnail_url,
                                audio_info.file_format,
                                existing_record[0]
                            ))
                            conn.commit()
                            self.logger.debug(f"更新现有歌曲记录 - ID: {existing_record[0]}, 标题: {audio_info.title}")
                            return existing_record[0], True  # 返回记录ID和是否为更新操作
                        else:
                            # 插入新记录
                            cursor.execute('''
                                INSERT INTO song_history
                                (title, artist, url, user_id, user_name, guild_id,
                                 timestamp, source_platform, duration, thumbnail_url, file_format)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                audio_info.title,
                                audio_info.uploader,
                                audio_info.url,
                                requester.id,
                                requester.display_name,
                                guild_id,
                                datetime.now(),
                                source_platform,
                                audio_info.duration,
                                audio_info.thumbnail_url,
                                audio_info.file_format
                            ))
                            conn.commit()
                            record_id = cursor.lastrowid
                            self.logger.debug(f"添加新歌曲记录 - ID: {record_id}, 标题: {audio_info.title}")
                            return record_id, False  # 返回记录ID和是否为更新操作

                    finally:
                        conn.close()

                loop = asyncio.get_event_loop()
                record_id, was_update = await loop.run_in_executor(None, upsert_record)

                if was_update:
                    self.logger.info(f"更新歌曲记录成功 - 用户: {requester.display_name}, 歌曲: {audio_info.title}")
                else:
                    self.logger.info(f"添加新歌曲记录成功 - 用户: {requester.display_name}, 歌曲: {audio_info.title}")

                return True

            except Exception as e:
                self.logger.error(f"添加/更新歌曲记录失败: {e}", exc_info=True)
                return False

    async def get_random_songs(
        self,
        guild_id: int,
        user_id: Optional[int] = None,
        limit: int = 10
    ) -> List[SongHistoryEntry]:
        """
        获取随机歌曲记录

        Args:
            guild_id: 服务器ID
            user_id: 用户ID（可选，如果指定则只返回该用户的歌曲）
            limit: 返回数量限制

        Returns:
            随机歌曲记录列表
        """
        async with self._db_lock:
            try:
                def query_random_songs():
                    conn = sqlite3.connect(self.db_path)
                    try:
                        cursor = conn.cursor()

                        if user_id:
                            # 查询指定用户的歌曲
                            cursor.execute('''
                                SELECT id, title, artist, url, user_id, user_name, guild_id,
                                       timestamp, source_platform, duration, thumbnail_url, file_format
                                FROM song_history
                                WHERE guild_id = ? AND user_id = ?
                                ORDER BY RANDOM()
                                LIMIT ?
                            ''', (guild_id, user_id, limit))
                        else:
                            # 查询所有用户的歌曲
                            cursor.execute('''
                                SELECT id, title, artist, url, user_id, user_name, guild_id,
                                       timestamp, source_platform, duration, thumbnail_url, file_format
                                FROM song_history
                                WHERE guild_id = ?
                                ORDER BY RANDOM()
                                LIMIT ?
                            ''', (guild_id, limit))

                        rows = cursor.fetchall()
                        return [self._row_to_entry(row) for row in rows]

                    finally:
                        conn.close()

                loop = asyncio.get_event_loop()
                songs = await loop.run_in_executor(None, query_random_songs)

                self.logger.debug(f"获取随机歌曲 - 服务器: {guild_id}, 用户: {user_id}, 数量: {len(songs)}")
                return songs

            except Exception as e:
                self.logger.error(f"获取随机歌曲失败: {e}", exc_info=True)
                return []

    async def get_user_song_count(self, guild_id: int, user_id: int) -> int:
        """
        获取用户在指定服务器的歌曲数量

        Args:
            guild_id: 服务器ID
            user_id: 用户ID

        Returns:
            歌曲数量
        """
        async with self._db_lock:
            try:
                def count_user_songs():
                    conn = sqlite3.connect(self.db_path)
                    try:
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT COUNT(*) FROM song_history
                            WHERE guild_id = ? AND user_id = ?
                        ''', (guild_id, user_id))
                        return cursor.fetchone()[0]
                    finally:
                        conn.close()

                loop = asyncio.get_event_loop()
                count = await loop.run_in_executor(None, count_user_songs)
                return count

            except Exception as e:
                self.logger.error(f"获取用户歌曲数量失败: {e}", exc_info=True)
                return 0

    async def get_total_song_count(self, guild_id: int) -> int:
        """
        获取服务器的总歌曲数量

        Args:
            guild_id: 服务器ID

        Returns:
            总歌曲数量
        """
        async with self._db_lock:
            try:
                def count_total_songs():
                    conn = sqlite3.connect(self.db_path)
                    try:
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT COUNT(*) FROM song_history
                            WHERE guild_id = ?
                        ''', (guild_id,))
                        return cursor.fetchone()[0]
                    finally:
                        conn.close()

                loop = asyncio.get_event_loop()
                count = await loop.run_in_executor(None, count_total_songs)
                return count

            except Exception as e:
                self.logger.error(f"获取总歌曲数量失败: {e}", exc_info=True)
                return 0

    def _row_to_entry(self, row: Tuple) -> SongHistoryEntry:
        """将数据库行转换为SongHistoryEntry对象"""
        return SongHistoryEntry(
            id=row[0],
            title=row[1],
            artist=row[2],
            url=row[3],
            user_id=row[4],
            user_name=row[5],
            guild_id=row[6],
            timestamp=datetime.fromisoformat(row[7]) if isinstance(row[7], str) else row[7],
            source_platform=row[8],
            duration=row[9],
            thumbnail_url=row[10],
            file_format=row[11]
        )
