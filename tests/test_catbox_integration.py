"""Tests for Catbox audio integration."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import aiohttp

from similubot.music.catbox_client import CatboxClient, CatboxAudioInfo
from similubot.music.audio_source import UnifiedAudioInfo, AudioSourceType
from similubot.music.music_player import MusicPlayer


class TestCatboxClient:
    """Test cases for CatboxClient."""

    def setup_method(self):
        """Set up test fixtures."""
        self.catbox_client = CatboxClient()

    def test_is_catbox_url_valid(self):
        """Test valid Catbox URL detection."""
        valid_urls = [
            "https://files.catbox.moe/abc123.mp3",
            "https://files.catbox.moe/xyz789.wav",
            "https://files.catbox.moe/test.ogg",
            "https://files.catbox.moe/audio.m4a",
            "https://files.catbox.moe/music.flac"
        ]
        
        for url in valid_urls:
            assert self.catbox_client.is_catbox_url(url), f"Should detect {url} as valid Catbox URL"

    def test_is_catbox_url_invalid(self):
        """Test invalid Catbox URL detection."""
        invalid_urls = [
            "https://youtube.com/watch?v=abc123",
            "https://files.catbox.moe/test.txt",  # Not audio format
            "https://files.catbox.moe/test.mp4",  # Video format
            "https://example.com/audio.mp3",      # Wrong domain
            "not_a_url",
            "",
            "https://files.catbox.moe/",          # No file
        ]
        
        for url in invalid_urls:
            assert not self.catbox_client.is_catbox_url(url), f"Should not detect {url} as valid Catbox URL"

    def test_extract_filename_from_url(self):
        """Test filename extraction from Catbox URLs."""
        test_cases = [
            ("https://files.catbox.moe/abc123.mp3", "abc123"),
            ("https://files.catbox.moe/my_song.wav", "my_song"),
            ("https://files.catbox.moe/test-audio.ogg", "test-audio"),
        ]
        
        for url, expected_filename in test_cases:
            result = self.catbox_client._extract_filename_from_url(url)
            assert result == expected_filename, f"Expected {expected_filename}, got {result}"

    def test_get_file_format_from_url(self):
        """Test file format extraction from Catbox URLs."""
        test_cases = [
            ("https://files.catbox.moe/abc123.mp3", "mp3"),
            ("https://files.catbox.moe/my_song.WAV", "wav"),
            ("https://files.catbox.moe/test-audio.OGG", "ogg"),
        ]
        
        for url, expected_format in test_cases:
            result = self.catbox_client._get_file_format_from_url(url)
            assert result == expected_format, f"Expected {expected_format}, got {result}"

    @pytest.mark.asyncio
    async def test_extract_audio_info_success(self):
        """Test successful audio info extraction."""
        test_url = "https://files.catbox.moe/test.mp3"

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {'content-length': '5242880'}  # 5MB

        with patch.object(self.catbox_client, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_session.head.return_value = mock_response
            mock_get_session.return_value = mock_session

            result = await self.catbox_client.extract_audio_info(test_url)

            assert result is not None
            assert isinstance(result, CatboxAudioInfo)
            assert result.title == "test"
            assert result.file_path == test_url
            assert result.url == test_url
            assert result.uploader == "Catbox"
            assert result.file_size == 5242880
            assert result.file_format == "mp3"

    @pytest.mark.asyncio
    async def test_extract_audio_info_invalid_url(self):
        """Test audio info extraction with invalid URL."""
        invalid_url = "https://youtube.com/watch?v=abc123"
        
        result = await self.catbox_client.extract_audio_info(invalid_url)
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_audio_file_success(self):
        """Test successful audio file validation."""
        test_url = "https://files.catbox.moe/test.mp3"

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {'content-length': '5242880'}

        with patch.object(self.catbox_client, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_session.head.return_value = mock_response
            mock_get_session.return_value = mock_session

            success, audio_info, error = await self.catbox_client.validate_audio_file(test_url)

            assert success is True
            assert audio_info is not None
            assert error is None
            assert isinstance(audio_info, CatboxAudioInfo)

    def test_format_file_size(self):
        """Test file size formatting."""
        test_cases = [
            (1024, "1.0 KB"),
            (1048576, "1.0 MB"),
            (1073741824, "1.0 GB"),
            (512, "512 B"),
            (None, "Unknown size"),
        ]
        
        for size_bytes, expected in test_cases:
            result = self.catbox_client.format_file_size(size_bytes)
            assert result == expected, f"Expected {expected}, got {result}"

    @pytest.mark.asyncio
    async def test_user_agent_spoofing(self):
        """Test that User-Agent spoofing is properly configured."""
        # Test User-Agent string
        assert hasattr(self.catbox_client, 'USER_AGENT')
        assert 'Mozilla' in self.catbox_client.USER_AGENT
        assert 'Chrome' in self.catbox_client.USER_AGENT

        # Test session creation with headers
        session = await self.catbox_client._get_session()
        assert session is not None

        # Check that User-Agent is in default headers
        default_headers = dict(session._default_headers)
        assert 'User-Agent' in default_headers
        assert default_headers['User-Agent'] == self.catbox_client.USER_AGENT

        # Check that browser-like headers are present
        expected_headers = ['Accept', 'Accept-Language', 'Accept-Encoding', 'DNT', 'Connection']
        for header in expected_headers:
            assert header in default_headers, f"Missing browser header: {header}"

        # Test additional request headers
        test_url = "https://files.catbox.moe/test.mp3"
        additional_headers = self.catbox_client._get_request_headers(test_url)

        assert 'Referer' in additional_headers
        assert 'Origin' in additional_headers
        assert additional_headers['Referer'] == 'https://catbox.moe/'
        assert additional_headers['Origin'] == 'https://catbox.moe'

    def teardown_method(self):
        """Clean up after tests."""
        # Note: cleanup is async but we can't await in teardown_method
        # The session will be cleaned up automatically when the test ends
        pass


class TestUnifiedAudioInfo:
    """Test cases for UnifiedAudioInfo."""

    def test_from_catbox_info(self):
        """Test creating UnifiedAudioInfo from CatboxAudioInfo."""
        catbox_info = CatboxAudioInfo(
            title="Test Song",
            duration=180,
            file_path="https://files.catbox.moe/test.mp3",
            url="https://files.catbox.moe/test.mp3",
            uploader="Catbox",
            file_size=5242880,
            file_format="mp3"
        )
        
        unified_info = UnifiedAudioInfo.from_catbox_info(catbox_info)
        
        assert unified_info.title == "Test Song"
        assert unified_info.duration == 180
        assert unified_info.source_type == AudioSourceType.CATBOX
        assert unified_info.file_size == 5242880
        assert unified_info.file_format == "mp3"
        assert unified_info.is_catbox() is True
        assert unified_info.is_youtube() is False
        assert unified_info.is_streaming() is True

    def test_get_display_info_catbox(self):
        """Test display info for Catbox audio."""
        catbox_info = CatboxAudioInfo(
            title="Test Song",
            duration=180,
            file_path="https://files.catbox.moe/test.mp3",
            url="https://files.catbox.moe/test.mp3",
            uploader="Catbox",
            file_size=5242880,
            file_format="mp3"
        )
        
        unified_info = UnifiedAudioInfo.from_catbox_info(catbox_info)
        display_info = unified_info.get_display_info()
        
        assert display_info['title'] == "Test Song"
        assert display_info['source'] == "Catbox"
        assert display_info['file_size'] == "5.0 MB"
        assert display_info['format'] == "MP3"


class TestMusicPlayerIntegration:
    """Test cases for MusicPlayer Catbox integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_bot = Mock()
        self.music_player = MusicPlayer(self.mock_bot)

    def test_detect_audio_source_type(self):
        """Test audio source type detection."""
        test_cases = [
            ("https://www.youtube.com/watch?v=abc123", AudioSourceType.YOUTUBE),
            ("https://files.catbox.moe/test.mp3", AudioSourceType.CATBOX),
            ("https://example.com/audio.mp3", None),
        ]
        
        for url, expected_type in test_cases:
            result = self.music_player.detect_audio_source_type(url)
            assert result == expected_type, f"Expected {expected_type}, got {result} for {url}"

    def test_is_supported_url(self):
        """Test supported URL detection."""
        supported_urls = [
            "https://www.youtube.com/watch?v=abc123",
            "https://files.catbox.moe/test.mp3",
            "https://files.catbox.moe/audio.wav",
        ]
        
        unsupported_urls = [
            "https://example.com/audio.mp3",
            "not_a_url",
            "https://files.catbox.moe/test.txt",
        ]
        
        for url in supported_urls:
            assert self.music_player.is_supported_url(url), f"Should support {url}"
            
        for url in unsupported_urls:
            assert not self.music_player.is_supported_url(url), f"Should not support {url}"

    def teardown_method(self):
        """Clean up after tests."""
        # Note: cleanup is async but we can't await in teardown_method
        # The music player will be cleaned up automatically when the test ends
        pass


if __name__ == "__main__":
    pytest.main([__file__])
