import discord
from similubot.core.interfaces import SongInfo
from similubot.progress.music_progress import MusicProgressBar
from similubot.music.music_player import MusicPlayer

class PlaybackEvent:
    """
    播放事件类

    提供了处理播放相关事件的方法。
    """

    def __init__(self):
        self.progress_bar = MusicProgressBar()
        self.music_player = MusicPlayer()

    async def show_song_info(self, bot, guild_id, channel_id, song: SongInfo) -> None:
        """
        触发下一首歌曲信息事件。

        :param guild_id: 服务器ID
        :param channel_id: 频道ID
        :param song: 当前播放的歌曲信息
        """
        try:
            channel = bot.get_channel(channel_id)
            queue_info = await self.music_player.get_queue_info(guild_id)

            response = await channel.send(content="正在加载进度条...")

            success = await self.progress_bar.show_progress_bar(response, guild_id)

            if not success:
                # Fallback to static display
                embed = discord.Embed(
                    title="🎶 正在播放",
                    color=discord.Color.green()
                )

                embed.add_field(
                    name="歌曲标题",
                    value=song.title,
                    inline=False
                )

                embed.add_field(
                    name="时长",
                    value=self.music_player.youtube_client.format_duration(song.duration),
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

                # Add static status
                if queue_info["playing"]:
                    embed.add_field(
                        name="状态",
                        value="▶️ 播放中",
                        inline=True
                    )
                elif queue_info["paused"]:
                    embed.add_field(
                        name="状态",
                        value="⏸️ 已暂停",
                        inline=True
                    )

                if song.audio_info.thumbnail_url:
                    embed.set_thumbnail(url=song.audio_info.thumbnail_url)

            await response.edit(content=None, embed=embed)
        except Exception as e:
            print(f"发送歌曲信息时出错: {e}")
    
    async def song_requester_absent_skip(self, bot, guild_id, channel_id, song: SongInfo) -> None:
        """
        跳过点歌人不在语音频道的歌曲。

        :param guild_id: 服务器ID
        :param channel_id: 频道ID
        :param song: 当前播放的歌曲信息
        """
        
        try:
            embed = discord.Embed(
                title="⏭️ 歌曲已跳过",
                description=f"点歌人 {song.requester.name} 不在语音频道，已跳过歌曲: {song.title}",
                color=discord.Color.orange()
            )

            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(embed=embed)
            else:
                print(f"频道 {channel_id} 不存在，无法发送跳过通知。")
        except Exception as e:
            print(f"发送跳过通知时出错: {e}")

    async def your_song_notification(self, bot, guild_id, channel_id, song) -> None:
        """
        发送轮到你的歌的通知。

        :param guild_id: 服务器ID
        :param channel_id: 频道ID
        :param song: 当前播放的歌曲信息
        """
        try:
            embed = discord.Embed(
                title="📣 轮到你的歌了",
                description=f"下首播放: {song.title}\n",
                color=discord.Color.orange()
            )

            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(embed=embed)
            else:
                print(f"频道 {channel_id} 不存在，无法发送通知。")
        except Exception as e:
            print(f"发送轮到你的歌的通知时出错: {e}")
