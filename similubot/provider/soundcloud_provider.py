"""
SoundCloud 音频提供者 - 处理 SoundCloud 曲目的信息提取与下载

结合 soundcloud-lib 提供的异步 API，实现对 SoundCloud 链接的解析、验证以及音频保存。
遵循项目的模块化设计原则，保持与其他音频提供者一致的接口与日志风格。
"""

import asyncio
import os
import re
from typing import Optional, Tuple

import aiohttp

from similubot.core.interfaces import AudioInfo
from similubot.progress.base import ProgressCallback, ProgressInfo, ProgressStatus
from .base import BaseAudioProvider

try:
    from sclib.asyncio import SoundcloudAPI, Track, Playlist
    from sclib.sync import UnsupportedFormatError
    from sclib import util as soundcloud_util

    SOUNDCLOUD_LIB_AVAILABLE = True
except ImportError:
    SOUNDCLOUD_LIB_AVAILABLE = False


class SoundCloudProvider(BaseAudioProvider):
    """
    SoundCloud 音频提供者

    支持解析常见的 SoundCloud 曲目链接与短链，能够提取基础信息并下载为 MP3 文件。
    """

    # 常规曲目链接模式，例如 https://soundcloud.com/artist/track-name
    TRACK_URL_PATTERN = re.compile(
        r"^https?://(?:m\.)?soundcloud\.com/[^/]+/[^/?#]+",
        re.IGNORECASE,
    )
    # 官方短链与推广链接，例如 https://on.soundcloud.com/xxxx
    SHORT_URL_PATTERN = re.compile(
        r"^https?://(?:on\.soundcloud\.com|soundcloud\.app\.goo\.gl|snd\.sc)/[^?#]+",
        re.IGNORECASE,
    )

    def __init__(self, temp_dir: str = "./temp"):
        """
        初始化 SoundCloud 提供者

        Args:
            temp_dir: 临时文件目录
        """
        if not SOUNDCLOUD_LIB_AVAILABLE:
            raise ImportError("缺少 soundcloud-lib 依赖，无法启用 SoundCloud 提供者。")

        super().__init__("SoundCloud", temp_dir)
        os.makedirs(temp_dir, exist_ok=True)

        # SoundcloudAPI 会在首次使用时自动获取公开的 client_id
        self._api = SoundcloudAPI()

    def is_supported_url(self, url: str) -> bool:
        """
        判断链接是否为支持的 SoundCloud 曲目或短链

        Args:
            url: 待检测的 URL

        Returns:
            如果链接符合 SoundCloud 曲目格式则返回 True
        """
        if not url:
            return False

        candidate = url.strip()
        return bool(
            self.TRACK_URL_PATTERN.match(candidate)
            or self.SHORT_URL_PATTERN.match(candidate)
        )

    async def _extract_audio_info_impl(self, url: str) -> Optional[AudioInfo]:
        """
        提取 SoundCloud 音频信息

        Args:
            url: SoundCloud 链接

        Returns:
            解析成功则返回 AudioInfo，否则返回 None
        """
        track = await self._resolve_track(url)
        if not track:
            return None

        return self._create_audio_info(track, original_url=url, file_path=None)

    async def _download_audio_impl(
        self,
        url: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Tuple[bool, Optional[AudioInfo], Optional[str]]:
        """
        下载 SoundCloud 音频并保存为 MP3

        Args:
            url: SoundCloud 链接
            progress_callback: 进度回调

        Returns:
            (成功标志, 音频信息, 错误消息)
        """
        operation = "soundcloud_download"
        await self._emit_progress(
            progress_callback,
            operation,
            ProgressStatus.STARTING,
            "正在准备 SoundCloud 下载...",
            percentage=0.0,
            details={"url": url},
        )

        try:
            track = await self._resolve_track(url)
            if not track:
                await self._emit_progress(
                    progress_callback,
                    operation,
                    ProgressStatus.FAILED,
                    "SoundCloud 链接解析失败",
                    percentage=0.0,
                )
                return False, None, "SoundCloud 链接解析失败"

            await self._emit_progress(
                progress_callback,
                operation,
                ProgressStatus.IN_PROGRESS,
                "正在下载音频文件...",
                percentage=15.0,
                details={"track_id": track.id},
            )

            safe_filename = self._build_file_name(track)
            file_path = os.path.join(self.temp_dir, safe_filename)

            # 调用 soundcloud-lib 写入 MP3 文件
            async with self._open_temp_file(file_path) as temp_file:
                await track.write_mp3_to(temp_file)

            await self._emit_progress(
                progress_callback,
                operation,
                ProgressStatus.IN_PROGRESS,
                "正在整理音频元数据...",
                percentage=80.0,
            )

            audio_info = self._create_audio_info(track, original_url=url, file_path=file_path)

            await self._emit_progress(
                progress_callback,
                operation,
                ProgressStatus.COMPLETED,
                "SoundCloud 音频下载完成",
                percentage=100.0,
                details={"file_path": file_path},
            )

            return True, audio_info, None

        except UnsupportedFormatError:
            message = "该 SoundCloud 音频不支持 Progressive 下载"
            await self._emit_progress(
                progress_callback,
                operation,
                ProgressStatus.FAILED,
                message,
                percentage=0.0,
            )
            return False, None, message

        except Exception as exc:  # pylint: disable=broad-except
            error_msg = f"下载 SoundCloud 音频时发生错误: {exc}"
            self.logger.error(error_msg)
            await self._emit_progress(
                progress_callback,
                operation,
                ProgressStatus.FAILED,
                "SoundCloud 音频下载失败",
                percentage=0.0,
                details={"error": str(exc)},
            )
            return False, None, error_msg

    async def _resolve_track(self, url: str) -> Optional[Track]:
        """
        解析 SoundCloud 链接为 Track 对象

        Args:
            url: 原始链接

        Returns:
            Track 对象或 None
        """
        normalized_url = await self._prepare_url(url)
        if not normalized_url:
            return None

        try:
            resolved = await self._api.resolve(normalized_url)
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.error(f"解析 SoundCloud 链接失败: {exc}")
            return None

        if isinstance(resolved, Track):
            return resolved

        if isinstance(resolved, Playlist):
            # 播放列表暂不直接支持，日志提示后返回第一首曲目作为近似
            try:
                await resolved.clean_attributes()
                if resolved.tracks:
                    self.logger.info("检测到 SoundCloud 播放列表，默认选择第一首曲目进行处理")
                    track = resolved.tracks[0]
                    if isinstance(track, Track):
                        return track
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.warning(f"处理 SoundCloud 播放列表时失败: {exc}")
                return None

        self.logger.warning("SoundCloud 链接未解析为 Track 对象")
        return None

    async def _prepare_url(self, url: str) -> Optional[str]:
        """
        规范化 SoundCloud 链接，处理短链及多余参数

        Args:
            url: 原始链接

        Returns:
            可用于 API 解析的链接，失败时返回 None
        """
        if not url:
            return None

        candidate = url.strip()
        if not candidate:
            return None

        if self.SHORT_URL_PATTERN.match(candidate):
            expanded = await self._expand_short_url(candidate)
            if expanded:
                candidate = expanded

        # 去除片段标识，SoundCloud API 不需要 # 之后的内容
        fragment_index = candidate.find("#")
        if fragment_index != -1:
            candidate = candidate[:fragment_index]

        return candidate

    async def _expand_short_url(self, url: str) -> Optional[str]:
        """
        通过网络请求解开 SoundCloud 短链

        Args:
            url: 短链 URL

        Returns:
            解析后的完整链接
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, allow_redirects=True) as response:
                    final_url = str(response.url)
                    if final_url and final_url != url:
                        return final_url
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.warning(f"解析 SoundCloud 短链失败: {exc}")

        return None

    def _create_audio_info(
        self,
        track: Track,
        *,
        original_url: str,
        file_path: Optional[str],
    ) -> AudioInfo:
        """
        根据 Track 对象构建 AudioInfo

        Args:
            track: SoundCloud Track 对象
            original_url: 用户提供的原始链接
            file_path: 下载后的文件路径（提取信息时可为空）

        Returns:
            AudioInfo 对象
        """
        duration_ms = getattr(track, "duration", None) or getattr(track, "full_duration", 0)
        duration_seconds = int(duration_ms / 1000) if duration_ms else 0
        uploader = getattr(track, "artist", None) or self._extract_uploader(track)
        artwork_url = self._normalize_artwork_url(getattr(track, "artwork_url", None))

        file_size = None
        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)

        return AudioInfo(
            title=self._build_title(track),
            duration=duration_seconds,
            url=original_url,
            uploader=uploader or "SoundCloud Creator",
            thumbnail_url=artwork_url,
            file_path=file_path,
            file_size=file_size,
            file_format="mp3" if file_path else None,
        )

    def _build_title(self, track: Track) -> str:
        """
        构建适合展示的音频标题

        Args:
            track: SoundCloud Track 对象
        """
        primary = getattr(track, "title", None)
        if primary:
            return primary

        permalink = getattr(track, "permalink", None)
        if permalink:
            return permalink.replace("-", " ").strip()

        return "SoundCloud Track"

    def _extract_uploader(self, track: Track) -> Optional[str]:
        """
        从 Track 对象中提取上传者名称
        """
        user = getattr(track, "user", None) or {}
        username = user.get("username") if isinstance(user, dict) else None
        if isinstance(username, str) and username.strip():
            return username.strip()
        return None

    def _normalize_artwork_url(self, artwork_url: Optional[str]) -> Optional[str]:
        """
        统一处理封面链接，优先使用大图版本
        """
        if not artwork_url:
            return None

        try:
            return soundcloud_util.get_large_artwork_url(artwork_url)
        except Exception:  # pylint: disable=broad-except
            return artwork_url

    def _build_file_name(self, track: Track) -> str:
        """
        根据 Track 信息生成安全的文件名
        """
        track_id = getattr(track, "id", "unknown")
        title = self._build_title(track)
        safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")
        safe_title = safe_title[:80] if safe_title else "soundcloud_track"
        return f"soundcloud_{track_id}_{safe_title}.mp3"

    async def _emit_progress(
        self,
        callback: Optional[ProgressCallback],
        operation: str,
        status: ProgressStatus,
        message: str,
        *,
        percentage: float,
        details: Optional[dict] = None,
    ) -> None:
        """
        将进度信息发送给回调函数
        """
        if not callback:
            return

        info = ProgressInfo(
            operation=operation,
            status=status,
            percentage=percentage,
            message=message,
            details=details or {},
        )

        try:
            result = callback(info)
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.debug(f"SoundCloud 进度回调执行失败: {exc}")

    class _AsyncFileWrapper:
        """
        异步上下文管理器，封装对本地文件的打开与关闭。

        soundcloud-lib 需要一个可读写的二进制文件句柄，因此这里提供轻量级包装。
        """

        def __init__(self, file_path: str):
            self._file_path = file_path
            self._file = None

        async def __aenter__(self):
            self._file = open(self._file_path, "wb+")  # pylint: disable=consider-using-with
            return self._file

        async def __aexit__(self, exc_type, exc, tb):
            if self._file:
                self._file.close()
            if exc_type:
                # 出错时清理不完整文件
                try:
                    if os.path.exists(self._file_path):
                        os.remove(self._file_path)
                except OSError:
                    pass

    def _open_temp_file(self, file_path: str) -> "_AsyncFileWrapper":
        """
        返回异步文件上下文管理器，供下载流程使用
        """
        return self._AsyncFileWrapper(file_path)
