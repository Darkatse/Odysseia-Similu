import logging
from aiohttp import payload
import discord
import discord.http
from typing import Optional
from similubot.core.interfaces import SongInfo
from similubot.progress.music_progress import MusicProgressBar

class PlaybackEvent:
    """
    播放事件处理器类

    负责处理播放相关的事件通知，包括：
    - 歌曲信息显示
    - 点歌人不在时的跳过通知
    - 轮到你的歌的提醒通知

    使用新的领域驱动架构，通过依赖注入获取所需的服务。
    """

    def __init__(self, music_player_adapter=None):
        """
        初始化播放事件处理器

        Args:
            music_player_adapter: 音乐播放器适配器，提供队列信息和格式化功能
        """
        self.music_player_adapter = music_player_adapter
        self.logger = logging.getLogger("similubot.playback.event")

        # 初始化进度条（如果有适配器的话）
        if music_player_adapter:
            self.progress_bar = MusicProgressBar(music_player_adapter)
        else:
            # 如果没有适配器，创建一个模拟的进度条对象
            self.progress_bar = None
            self.logger.warning("⚠️ 没有音乐播放器适配器，进度条功能将不可用")

        self.logger.debug("🎭 播放事件处理器初始化完成")

    async def show_song_info(self, bot, guild_id, channel_id, song: SongInfo) -> None:
        """
        显示当前播放歌曲的详细信息

        当歌曲开始播放时触发，显示歌曲标题、时长、上传者等信息。
        优先尝试显示动态进度条，失败时回退到静态信息显示。

        Args:
            bot: Discord机器人实例
            guild_id: 服务器ID
            channel_id: 文本频道ID
            song: 当前播放的歌曲信息
        """
        try:
            self.logger.debug(f"📺 开始显示歌曲信息 - 服务器 {guild_id}, 歌曲: {song.title}")

            channel: discord.VoiceChannel = bot.get_channel(channel_id)
            if not channel:
                self.logger.warning(f"❌ 频道 {channel_id} 不存在，无法显示歌曲信息")
                return

            # 获取队列信息（如果适配器可用）
            queue_info = {}
            if self.music_player_adapter:
                try:
                    queue_info = await self.music_player_adapter.get_queue_info(guild_id)
                    self.logger.debug(f"📊 获取队列信息成功 - 播放状态: {queue_info.get('playing', False)}")
                except Exception as e:
                    self.logger.warning(f"⚠️ 获取队列信息失败: {e}")

            # 发送初始加载消息
            response = await channel.send(content="正在加载进度条...")

            # 尝试显示动态进度条
            success = False
            if self.progress_bar:
                try:
                    success = await self.progress_bar.show_progress_bar(response, guild_id)
                    self.logger.debug(f"📊 进度条显示结果: {'成功' if success else '失败，使用静态显示'}")
                except Exception as e:
                    self.logger.warning(f"⚠️ 进度条显示失败: {e}")
            else:
                self.logger.debug("📊 没有进度条实例，使用静态显示")

            if not success:
                # 回退到静态信息显示
                embed = discord.Embed(
                    title="🎶 正在播放",
                    color=discord.Color.green()
                )

                embed.add_field(
                    name="歌曲标题",
                    value=song.title,
                    inline=False
                )

                # 格式化时长 - 使用新架构的方法
                duration_str = self._format_duration(song.duration)
                embed.add_field(
                    name="时长",
                    value=duration_str,
                    inline=True
                )

                embed.add_field(
                    name="上传者",
                    value=song.uploader,
                    inline=True
                )

                embed.add_field(
                    name="点歌人",
                    value=song.requester.display_name,
                    inline=True
                )

                # 添加播放状态信息
                if queue_info.get("playing"):
                    embed.add_field(
                        name="状态",
                        value="▶️ 播放中",
                        inline=True
                    )
                elif queue_info.get("paused"):
                    embed.add_field(
                        name="状态",
                        value="⏸️ 已暂停",
                        inline=True
                    )

                # 添加缩略图
                if song.audio_info and song.audio_info.thumbnail_url:
                    embed.set_thumbnail(url=song.audio_info.thumbnail_url)

                await response.edit(content=None, embed=embed)

            # 设置频道状态
            try:
                route = discord.http.Route("PUT", "/channels/{channel_id}/voice-status", channel_id=channel_id)
                payload = {
                    "status": f"🎵 {song.title}"
                }
                ret = await channel._state.http.request(route, json=payload)
                self.logger.info(f"✅ 频道状态设置成功 - {song.title}")
            except Exception as e:
                self.logger.warning(f"⚠️ 设置频道状态失败: {e}")

            self.logger.info(f"✅ 歌曲信息显示完成 - {song.title}")

        except Exception as e:
            self.logger.error(f"❌ 显示歌曲信息时出错: {e}", exc_info=True)

    def _format_duration(self, duration: int) -> str:
        """
        格式化时长为可读字符串

        Args:
            duration: 时长（秒）

        Returns:
            格式化的时长字符串 (例: "3:45" 或 "1:23:45")
        """
        if duration < 3600:  # 少于1小时
            minutes, seconds = divmod(duration, 60)
            return f"{minutes}:{seconds:02d}"
        else:  # 1小时或更多
            hours, remainder = divmod(duration, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours}:{minutes:02d}:{seconds:02d}"

    async def song_requester_absent_skip(self, bot, guild_id, channel_id, song: SongInfo) -> None:
        """
        发送点歌人不在语音频道时的跳过通知

        当检测到点歌人已离开语音频道时，自动跳过其歌曲并发送通知消息。
        这是队列公平性机制的一部分，确保只有在场的用户才能播放歌曲。

        Args:
            bot: Discord机器人实例
            guild_id: 服务器ID
            channel_id: 文本频道ID
            song: 被跳过的歌曲信息
        """
        try:
            self.logger.debug(f"⏭️ 发送跳过通知 - 服务器 {guild_id}, 点歌人: {song.requester.name}, 歌曲: {song.title}")

            embed = discord.Embed(
                title="⏭️ 歌曲已跳过",
                description=f"点歌人 {song.requester.name} 不在语音频道，已跳过歌曲: {song.title}",
                color=discord.Color.orange()
            )

            # 添加额外信息
            embed.add_field(
                name="原因",
                value="点歌人已离开语音频道",
                inline=True
            )

            embed.add_field(
                name="时长",
                value=self._format_duration(song.duration),
                inline=True
            )

            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(embed=embed)
                self.logger.info(f"✅ 跳过通知发送成功 - {song.title}")
            else:
                self.logger.warning(f"❌ 频道 {channel_id} 不存在，无法发送跳过通知")

        except Exception as e:
            self.logger.error(f"❌ 发送跳过通知时出错: {e}", exc_info=True)

    async def your_song_notification(self, bot, guild_id, channel_id, song, interval) -> None:
        """
        发送轮到你的歌的提醒通知

        当检测到下一首歌曲的点歌人可能已离开语音频道时，
        提前发送提醒通知，让用户有机会回到语音频道。

        Args:
            bot: Discord机器人实例
            guild_id: 服务器ID
            channel_id: 文本频道ID
            song: 即将播放的歌曲信息
            interval: 指定歌曲的距离
        """
        try:
            self.logger.debug(f"📣 发送轮到你的歌通知 - 服务器 {guild_id}, 点歌人: {song.requester.name}, 歌曲: {song.title}")

            if interval == 1:
                interval_str = "下一首"
            elif interval == 2:
                interval_str = "下下首"

            embed = discord.Embed(
                title="📣 轮到你的歌了",
                description=f"{interval_str}播放: {song.title}",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="点歌人",
                value=song.requester.mention,
                inline=True
            )

            embed.add_field(
                name="时长",
                value=self._format_duration(song.duration),
                inline=True
            )

            embed.add_field(
                name="提醒",
                value="请确保你在语音频道中，否则歌曲将被跳过",
                inline=False
            )

            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(embed=embed)
                await channel.send(content=f"{song.requester.mention}, {interval_str}就是你的歌了！请准备好。")
                self.logger.info(f"✅ 轮到你的歌通知发送成功 - {song.title}")
            else:
                self.logger.warning(f"❌ 频道 {channel_id} 不存在，无法发送通知")

        except Exception as e:
            self.logger.error(f"❌ 发送轮到你的歌通知时出错: {e}", exc_info=True)
