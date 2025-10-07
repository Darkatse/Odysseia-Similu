"""
SoundCloud 提供者单元测试

验证 SoundCloudProvider 的 URL 检测、信息提取与下载逻辑，确保在不访问真实网络的情况下保持稳定行为。
"""

import os
import shutil
import tempfile
from typing import List

import pytest

from similubot.progress.base import ProgressInfo, ProgressStatus

try:
    from similubot.provider.soundcloud_provider import (
        SoundCloudProvider,
        SOUNDCLOUD_LIB_AVAILABLE,
    )
    from sclib.sync import UnsupportedFormatError
except ImportError:  # pragma: no cover - 如果依赖缺失则跳过测试
    SoundCloudProvider = None  # type: ignore
    SOUNDCLOUD_LIB_AVAILABLE = False  # type: ignore
    UnsupportedFormatError = Exception  # type: ignore

pytestmark = pytest.mark.skipif(
    not SOUNDCLOUD_LIB_AVAILABLE,
    reason="soundcloud-lib 未安装，跳过 SoundCloudProvider 测试",
)


class _FakeTrack:
    """用于隔离网络请求的 SoundCloud Track 替身"""

    def __init__(self):
        self.title = "测试曲目"
        self.duration = 245000  # 毫秒
        self.artist = "测试歌手"
        self.id = 123456789
        self.permalink = "test-track"
        self.artwork_url = "https://example.com/artwork-large.jpg"
        self.user = {"username": "测试上传者"}

    async def write_mp3_to(self, file_obj):
        """模拟将音频写入本地文件"""
        file_obj.write(b"fake-audio-data")
        file_obj.seek(0)
        return file_obj


@pytest.fixture()
def provider():
    """构建带有独立临时目录的 SoundCloudProvider 实例"""
    temp_dir = tempfile.mkdtemp()
    instance = SoundCloudProvider(temp_dir=temp_dir)
    try:
        yield instance
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_is_supported_url(provider: SoundCloudProvider):
    """验证常见 SoundCloud 链接格式均被识别"""
    valid_urls = [
        "https://soundcloud.com/artist-name/track-name",
        "https://m.soundcloud.com/artist-name/track-name",
        "https://on.soundcloud.com/xyz123",
        "https://soundcloud.app.goo.gl/abc456",
        "https://snd.sc/shortlink",
    ]

    for url in valid_urls:
        assert provider.is_supported_url(url), f"URL 未被识别: {url}"


def test_is_supported_url_invalid(provider: SoundCloudProvider):
    """验证无关链接不会被误判"""
    invalid_urls = [
        "",
        "not_a_url",
        "https://example.com/soundcloud",
        "https://soundcloud.com/artist",  # 缺少曲目
        "https://youtube.com/watch?v=123",
    ]

    for url in invalid_urls:
        assert not provider.is_supported_url(url), f"URL 不应被识别: {url}"


@pytest.mark.asyncio
async def test_extract_audio_info_impl(provider: SoundCloudProvider, monkeypatch: pytest.MonkeyPatch):
    """验证信息提取逻辑可根据 Track 对象生成 AudioInfo"""
    fake_track = _FakeTrack()
    async def fake_resolve(url: str):
        return fake_track

    monkeypatch.setattr(provider, "_resolve_track", fake_resolve)

    audio_info = await provider._extract_audio_info_impl("https://soundcloud.com/artist-name/track-name")

    assert audio_info is not None
    assert audio_info.title == fake_track.title
    assert audio_info.duration == fake_track.duration // 1000
    assert audio_info.uploader == fake_track.artist
    assert audio_info.thumbnail_url is not None


@pytest.mark.asyncio
async def test_download_audio_impl_success(provider: SoundCloudProvider, monkeypatch: pytest.MonkeyPatch):
    """验证下载流程可写入文件并发送进度"""
    fake_track = _FakeTrack()
    async def fake_resolve(url: str):
        return fake_track

    monkeypatch.setattr(provider, "_resolve_track", fake_resolve)

    progress_events: List[ProgressInfo] = []

    def progress_callback(info: ProgressInfo) -> None:
        progress_events.append(info)

    success, audio_info, error = await provider._download_audio_impl(
        "https://soundcloud.com/artist-name/track-name",
        progress_callback,
    )

    assert success is True
    assert error is None
    assert audio_info is not None
    assert audio_info.file_path is not None and os.path.exists(audio_info.file_path)
    assert audio_info.file_size == os.path.getsize(audio_info.file_path)
    assert audio_info.file_format == "mp3"

    # 验证进度回调包含开始与完成状态
    statuses = [event.status for event in progress_events]
    assert ProgressStatus.STARTING in statuses
    assert ProgressStatus.COMPLETED in statuses


@pytest.mark.asyncio
async def test_download_audio_impl_resolve_failure(provider: SoundCloudProvider, monkeypatch: pytest.MonkeyPatch):
    """当链接解析失败时应返回 False 且不产生文件"""
    async def fake_resolve(url: str):
        return None

    monkeypatch.setattr(provider, "_resolve_track", fake_resolve)

    progress_events: List[ProgressInfo] = []

    def progress_callback(info: ProgressInfo) -> None:
        progress_events.append(info)

    success, audio_info, error = await provider._download_audio_impl(
        "https://soundcloud.com/artist-name/track-name",
        progress_callback,
    )

    assert success is False
    assert audio_info is None
    assert error is not None
    assert any(event.status == ProgressStatus.FAILED for event in progress_events)


@pytest.mark.asyncio
async def test_download_audio_impl_unsupported_format(provider: SoundCloudProvider, monkeypatch: pytest.MonkeyPatch):
    """当音频不支持 Progressive 下载时应返回对应错误"""
    fake_track = _FakeTrack()

    async def raise_unsupported(file_obj):
        raise UnsupportedFormatError("No progressive stream")

    async def fake_resolve(url: str):
        return fake_track

    monkeypatch.setattr(provider, "_resolve_track", fake_resolve)
    monkeypatch.setattr(fake_track, "write_mp3_to", raise_unsupported)

    success, audio_info, error = await provider._download_audio_impl(
        "https://soundcloud.com/artist-name/track-name",
        progress_callback=None,
    )

    assert success is False
    assert audio_info is None
    assert error is not None
    assert "Progressive" in error or "SoundCloud" in error
