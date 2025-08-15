"""
嵌入消息构建器

提供统一的嵌入消息构建功能：
- 标准化的消息格式
- 主题色彩管理
- 常用消息模板
"""

import discord
from typing import Optional, Dict, Any
from similubot.core.interfaces import AudioInfo, NetEaseSearchResult


class EmbedBuilder:
    """
    嵌入消息构建器

    提供统一的嵌入消息构建方法，确保UI一致性
    """

    # 主题色彩
    COLORS = {
        'success': discord.Color.green(),
        'error': discord.Color.red(),
        'warning': discord.Color.orange(),
        'info': discord.Color.blue(),
        'neutral': discord.Color.light_grey()
    }

    @classmethod
    def create_success_embed(cls, title: str, description: str) -> discord.Embed:
        """
        创建成功消息嵌入

        Args:
            title: 标题
            description: 描述

        Returns:
            Discord嵌入消息
        """
        return discord.Embed(
            title=f"✅ {title}",
            description=description,
            color=cls.COLORS['success']
        )

    @classmethod
    def create_error_embed(cls, title: str, description: str) -> discord.Embed:
        """
        创建错误消息嵌入

        Args:
            title: 标题
            description: 描述

        Returns:
            Discord嵌入消息
        """
        return discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=cls.COLORS['error']
        )

    @classmethod
    def create_warning_embed(cls, title: str, description: str) -> discord.Embed:
        """
        创建警告消息嵌入

        Args:
            title: 标题
            description: 描述

        Returns:
            Discord嵌入消息
        """
        return discord.Embed(
            title=f"⚠️ {title}",
            description=description,
            color=cls.COLORS['warning']
        )

    @classmethod
    def create_info_embed(cls, title: str, description: str) -> discord.Embed:
        """
        创建信息消息嵌入

        Args:
            title: 标题
            description: 描述

        Returns:
            Discord嵌入消息
        """
        return discord.Embed(
            title=f"ℹ️ {title}",
            description=description,
            color=cls.COLORS['info']
        )

    @classmethod
    def create_song_added_embed(
        cls,
        audio_info: AudioInfo,
        position: int,
        requester_name: str
    ) -> discord.Embed:
        """
        创建歌曲添加成功嵌入

        Args:
            audio_info: 音频信息
            position: 队列位置
            requester_name: 点歌人名称

        Returns:
            Discord嵌入消息
        """
        embed = cls.create_success_embed("歌曲已添加到队列", "")

        embed.add_field(
            name="歌曲标题",
            value=audio_info.title,
            inline=False
        )

        # 格式化时长
        if hasattr(audio_info, 'duration') and audio_info.duration > 0:
            duration_str = cls._format_duration(audio_info.duration)
        else:
            duration_str = "未知"

        embed.add_field(
            name="时长",
            value=duration_str,
            inline=True
        )

        embed.add_field(
            name="来源",
            value=audio_info.uploader,
            inline=True
        )

        embed.add_field(
            name="队列位置",
            value=f"#{position}",
            inline=True
        )

        embed.add_field(
            name="点歌人",
            value=requester_name,
            inline=True
        )

        if hasattr(audio_info, 'thumbnail_url') and audio_info.thumbnail_url:
            embed.set_thumbnail(url=audio_info.thumbnail_url)

        return embed

    @classmethod
    def create_netease_song_added_embed(
        cls,
        search_result: NetEaseSearchResult,
        position: int,
        requester_name: str
    ) -> discord.Embed:
        """
        创建NetEase歌曲添加成功嵌入

        Args:
            search_result: 搜索结果
            position: 队列位置
            requester_name: 点歌人名称

        Returns:
            Discord嵌入消息
        """
        embed = cls.create_success_embed("歌曲已添加到队列", "")

        embed.add_field(
            name="歌曲信息",
            value=f"**{search_result.get_display_name()}**\n专辑: {search_result.album}",
            inline=False
        )

        if search_result.duration:
            embed.add_field(
                name="时长",
                value=search_result.format_duration(),
                inline=True
            )

        embed.add_field(
            name="队列位置",
            value=f"#{position}",
            inline=True
        )

        embed.add_field(
            name="点歌人",
            value=requester_name,
            inline=True
        )

        if search_result.cover_url:
            embed.set_thumbnail(url=search_result.cover_url)

        return embed

    @classmethod
    def create_queue_fairness_embed(
        cls,
        current_song_title: str,
        queue_position: int
    ) -> discord.Embed:
        """
        创建队列公平性限制嵌入

        Args:
            current_song_title: 当前队列中的歌曲标题
            queue_position: 队列位置

        Returns:
            Discord嵌入消息
        """
        embed = cls.create_warning_embed(
            "队列公平性限制",
            "您已经有歌曲在队列中，请等待播放完成后再添加新歌曲。"
        )

        embed.add_field(
            name="🎵 您的歌曲",
            value=f"**{current_song_title}**",
            inline=False
        )

        embed.add_field(
            name="📍 队列位置",
            value=f"第 {queue_position} 位",
            inline=True
        )

        embed.add_field(
            name="📋 队列规则",
            value="为了保证所有用户的公平使用，每位用户同时只能有一首歌曲在队列中等待播放。",
            inline=False
        )

        embed.add_field(
            name="💡 建议",
            value="使用 `/我的队列` 命令查看您当前的队列状态和预计播放时间。",
            inline=False
        )

        return embed

    @classmethod
    def create_queue_display_embed(cls, queue_info: Dict[str, Any]) -> discord.Embed:
        """
        创建队列显示嵌入

        Args:
            queue_info: 队列信息字典

        Returns:
            Discord嵌入消息
        """
        if queue_info["is_empty"] and not queue_info["current_song"]:
            return cls.create_info_embed("音乐队列", "队列为空")

        embed = discord.Embed(
            title="🎵 音乐队列",
            color=cls.COLORS['info']
        )

        # 添加当前歌曲信息
        if queue_info["current_song"]:
            current = queue_info["current_song"]
            embed.add_field(
                name="🎶 正在播放",
                value=f"**{current.title}**\n"
                      f"时长: {cls._format_duration(current.duration)}\n"
                      f"点歌人: {current.requester.display_name}",
                inline=False
            )

        return embed

    @classmethod
    def create_user_queue_status_embed(
        cls,
        has_queued_song: bool,
        is_currently_playing: bool = False,
        song_title: Optional[str] = None,
        queue_position: Optional[int] = None,
        estimated_time: Optional[str] = None
    ) -> discord.Embed:
        """
        创建用户队列状态嵌入

        Args:
            has_queued_song: 是否有歌曲在队列中
            is_currently_playing: 是否正在播放
            song_title: 歌曲标题
            queue_position: 队列位置
            estimated_time: 预计播放时间

        Returns:
            Discord嵌入消息
        """
        if not has_queued_song:
            embed = cls.create_info_embed(
                "我的队列状态",
                "您当前没有歌曲在队列中。"
            )
            embed.add_field(
                name="💡 提示",
                value="使用 `/点歌` 命令来添加歌曲到队列。",
                inline=False
            )
            return embed

        if is_currently_playing:
            embed = cls.create_success_embed(
                "我的队列状态",
                "您的歌曲正在播放中！"
            )
            embed.add_field(
                name="🎶 正在播放",
                value=f"**{song_title}**",
                inline=False
            )
        else:
            embed = cls.create_warning_embed(
                "我的队列状态",
                "您有歌曲在队列中等待播放。"
            )
            embed.add_field(
                name="🎶 排队歌曲",
                value=f"**{song_title}**",
                inline=False
            )

            if queue_position:
                embed.add_field(
                    name="📍 队列位置",
                    value=f"第 {queue_position} 位",
                    inline=True
                )

            if estimated_time:
                embed.add_field(
                    name="⏰ 预计播放时间",
                    value=f"{estimated_time} 后",
                    inline=True
                )

        return embed

    @classmethod
    def _format_duration(cls, duration_seconds: int) -> str:
        """
        格式化时长显示

        Args:
            duration_seconds: 时长（秒）

        Returns:
            格式化的时长字符串
        """
        if duration_seconds < 60:
            return f"{duration_seconds}秒"
        elif duration_seconds < 3600:
            minutes = duration_seconds // 60
            seconds = duration_seconds % 60
            return f"{minutes}:{seconds:02d}"
        else:
            hours = duration_seconds // 3600
            minutes = (duration_seconds % 3600) // 60
            seconds = duration_seconds % 60
            return f"{hours}:{minutes:02d}:{seconds:02d}"