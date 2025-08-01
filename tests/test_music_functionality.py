"""Comprehensive tests for music functionality."""

import unittest
import asyncio
import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch, Mock
import tempfile
import shutil

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from similubot.music.youtube_client import YouTubeClient, AudioInfo
from similubot.music.queue_manager import QueueManager, Song
from similubot.music.voice_manager import VoiceManager
from similubot.music.music_player import MusicPlayer
from similubot.commands.music_commands import MusicCommands
from similubot.utils.config_manager import ConfigManager


class TestYouTubeClient(unittest.TestCase):
    """Test YouTube client functionality."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_config = MagicMock(spec=ConfigManager)
        # Configure mock config for basic functionality
        self.mock_config.is_potoken_enabled.return_value = False
        self.mock_config.is_youtube_auto_fallback_enabled.return_value = True
        self.client = YouTubeClient(self.temp_dir, self.mock_config)

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_is_youtube_url_valid(self):
        """Test YouTube URL validation with valid URLs."""
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "http://youtube.com/watch?v=dQw4w9WgXcQ",
            "www.youtube.com/watch?v=dQw4w9WgXcQ",
            "youtube.com/watch?v=dQw4w9WgXcQ"
        ]
        
        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(self.client.is_youtube_url(url))

    def test_is_youtube_url_invalid(self):
        """Test YouTube URL validation with invalid URLs."""
        invalid_urls = [
            "https://www.google.com",
            "https://www.spotify.com/track/123",
            "not_a_url",
            "",
            "https://www.youtube.com/playlist?list=123"  # Playlists not supported yet
        ]
        
        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(self.client.is_youtube_url(url))

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        test_cases = [
            ("Normal Title", "Normal Title"),
            ("Title with <invalid> chars", "Title with _invalid_ chars"),
            ("Title/with\\slashes", "Title_with_slashes"),
            ("", "audio"),
            ("A" * 150, "A" * 100),  # Length limit
            ("   Whitespace   ", "Whitespace")
        ]
        
        for input_name, expected in test_cases:
            with self.subTest(input_name=input_name):
                result = self.client._sanitize_filename(input_name)
                self.assertEqual(result, expected)

    def test_format_duration(self):
        """Test duration formatting."""
        test_cases = [
            (30, "00:30"),
            (90, "01:30"),
            (3600, "01:00:00"),
            (3661, "01:01:01"),
            (0, "00:00")
        ]
        
        for seconds, expected in test_cases:
            with self.subTest(seconds=seconds):
                result = self.client.format_duration(seconds)
                self.assertEqual(result, expected)

    @patch('similubot.music.youtube_client.YouTube')
    async def test_extract_audio_info_success(self, mock_youtube):
        """Test successful audio info extraction."""
        # Mock YouTube object
        mock_yt = MagicMock()
        mock_yt.title = "Test Video"
        mock_yt.length = 180
        mock_yt.author = "Test Channel"
        mock_yt.thumbnail_url = "https://example.com/thumb.jpg"
        
        # Mock audio stream
        mock_stream = MagicMock()
        mock_yt.streams.get_audio_only.return_value = mock_stream
        
        mock_youtube.return_value = mock_yt
        
        url = "https://www.youtube.com/watch?v=test"
        result = await self.client.extract_audio_info(url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.title, "Test Video")
        self.assertEqual(result.duration, 180)
        self.assertEqual(result.uploader, "Test Channel")
        self.assertEqual(result.url, url)

    async def test_extract_audio_info_invalid_url(self):
        """Test audio info extraction with invalid URL."""
        result = await self.client.extract_audio_info("https://www.google.com")
        self.assertIsNone(result)


class TestQueueManager(unittest.TestCase):
    """Test queue manager functionality."""

    def setUp(self):
        """Set up test environment."""
        self.queue_manager = QueueManager(guild_id=12345)
        
        # Create mock audio info and member
        self.mock_audio_info = AudioInfo(
            title="Test Song",
            duration=180,
            file_path="/tmp/test.mp3",
            url="https://youtube.com/watch?v=test",
            uploader="Test Channel"
        )
        
        self.mock_member = MagicMock()
        self.mock_member.display_name = "TestUser"

    async def test_add_song(self):
        """Test adding songs to queue."""
        position = await self.queue_manager.add_song(self.mock_audio_info, self.mock_member)
        self.assertEqual(position, 1)
        
        # Add another song
        position2 = await self.queue_manager.add_song(self.mock_audio_info, self.mock_member)
        self.assertEqual(position2, 2)

    async def test_get_next_song(self):
        """Test getting next song from queue."""
        # Empty queue
        song = await self.queue_manager.get_next_song()
        self.assertIsNone(song)
        
        # Add song and get it
        await self.queue_manager.add_song(self.mock_audio_info, self.mock_member)
        song = await self.queue_manager.get_next_song()
        
        self.assertIsNotNone(song)
        self.assertEqual(song.title, "Test Song")
        self.assertEqual(song.requester, self.mock_member)

    async def test_clear_queue(self):
        """Test clearing the queue."""
        # Add multiple songs
        await self.queue_manager.add_song(self.mock_audio_info, self.mock_member)
        await self.queue_manager.add_song(self.mock_audio_info, self.mock_member)
        
        count = await self.queue_manager.clear_queue()
        self.assertEqual(count, 2)
        
        # Queue should be empty
        queue_info = await self.queue_manager.get_queue_info()
        self.assertTrue(queue_info["is_empty"])

    async def test_jump_to_position(self):
        """Test jumping to specific position in queue."""
        # Add multiple songs
        for i in range(5):
            await self.queue_manager.add_song(self.mock_audio_info, self.mock_member)
        
        # Jump to position 3
        song = await self.queue_manager.jump_to_position(3)
        self.assertIsNotNone(song)
        
        # Queue should now have 2 songs left (positions 4 and 5)
        queue_info = await self.queue_manager.get_queue_info()
        self.assertEqual(queue_info["queue_length"], 2)

    async def test_jump_to_invalid_position(self):
        """Test jumping to invalid position."""
        await self.queue_manager.add_song(self.mock_audio_info, self.mock_member)
        
        # Invalid positions
        song1 = await self.queue_manager.jump_to_position(0)
        song2 = await self.queue_manager.jump_to_position(5)
        
        self.assertIsNone(song1)
        self.assertIsNone(song2)


class TestVoiceManager(unittest.TestCase):
    """Test voice manager functionality."""

    def setUp(self):
        """Set up test environment."""
        self.mock_bot = MagicMock()
        self.voice_manager = VoiceManager(self.mock_bot)
        
        # Create mock voice channel and client
        self.mock_channel = MagicMock()
        self.mock_channel.guild.id = 12345
        self.mock_channel.name = "Test Channel"
        
        self.mock_voice_client = MagicMock()
        self.mock_voice_client.is_connected.return_value = True
        self.mock_voice_client.is_playing.return_value = False
        self.mock_voice_client.is_paused.return_value = False
        self.mock_voice_client.channel = self.mock_channel

    async def test_connect_to_voice_channel_success(self):
        """Test successful voice channel connection."""
        self.mock_channel.connect = AsyncMock(return_value=self.mock_voice_client)
        
        result = await self.voice_manager.connect_to_voice_channel(self.mock_channel)
        
        self.assertEqual(result, self.mock_voice_client)
        self.mock_channel.connect.assert_called_once()

    async def test_connect_to_voice_channel_timeout(self):
        """Test voice channel connection timeout."""
        self.mock_channel.connect = AsyncMock(side_effect=asyncio.TimeoutError())
        
        result = await self.voice_manager.connect_to_voice_channel(self.mock_channel)
        
        self.assertIsNone(result)

    def test_is_connected(self):
        """Test connection status checking."""
        guild_id = 12345
        
        # Not connected
        self.assertFalse(self.voice_manager.is_connected(guild_id))
        
        # Add voice client
        self.voice_manager._voice_clients[guild_id] = self.mock_voice_client
        self.assertTrue(self.voice_manager.is_connected(guild_id))

    def test_is_playing(self):
        """Test playback status checking."""
        guild_id = 12345
        
        # Not connected
        self.assertFalse(self.voice_manager.is_playing(guild_id))
        
        # Connected but not playing
        self.voice_manager._voice_clients[guild_id] = self.mock_voice_client
        self.assertFalse(self.voice_manager.is_playing(guild_id))
        
        # Playing
        self.mock_voice_client.is_playing.return_value = True
        self.assertTrue(self.voice_manager.is_playing(guild_id))

    async def test_disconnect_from_guild(self):
        """Test disconnecting from guild."""
        guild_id = 12345
        self.voice_manager._voice_clients[guild_id] = self.mock_voice_client
        self.mock_voice_client.disconnect = AsyncMock()
        
        result = await self.voice_manager.disconnect_from_guild(guild_id)
        
        self.assertTrue(result)
        self.mock_voice_client.disconnect.assert_called_once()
        self.assertNotIn(guild_id, self.voice_manager._voice_clients)


class TestMusicCommands(unittest.TestCase):
    """Test music commands functionality."""

    def setUp(self):
        """Set up test environment."""
        self.mock_config = MagicMock(spec=ConfigManager)
        self.mock_config.get.return_value = True  # Music enabled
        
        self.mock_music_player = MagicMock(spec=MusicPlayer)
        self.music_commands = MusicCommands(self.mock_config, self.mock_music_player)
        
        # Create mock context
        self.mock_ctx = MagicMock()
        self.mock_ctx.guild.id = 12345
        self.mock_ctx.author.display_name = "TestUser"
        self.mock_ctx.reply = AsyncMock()

    def test_is_available(self):
        """Test availability checking."""
        self.assertTrue(self.music_commands.is_available())
        
        # Disabled
        self.mock_config.get.return_value = False
        commands_disabled = MusicCommands(self.mock_config, self.mock_music_player)
        self.assertFalse(commands_disabled.is_available())

    async def test_music_command_no_args(self):
        """Test music command with no arguments."""
        await self.music_commands.music_command(self.mock_ctx)
        
        # Should show help
        self.mock_ctx.reply.assert_called_once()
        call_args = self.mock_ctx.reply.call_args
        self.assertIn("embed", call_args.kwargs)

    async def test_music_command_queue(self):
        """Test queue subcommand."""
        self.mock_music_player.get_queue_info.return_value = {
            "is_empty": True,
            "current_song": None,
            "queue_length": 0,
            "total_duration": 0,
            "connected": False
        }
        
        await self.music_commands.music_command(self.mock_ctx, "queue")
        
        self.mock_music_player.get_queue_info.assert_called_once_with(12345)
        self.mock_ctx.reply.assert_called_once()

    async def test_music_command_youtube_url(self):
        """Test music command with YouTube URL."""
        # Mock user in voice channel
        self.mock_ctx.author.voice = MagicMock()
        self.mock_ctx.author.voice.channel = MagicMock()
        
        # Mock successful operations
        self.mock_music_player.connect_to_user_channel.return_value = (True, None)
        self.mock_music_player.add_song_to_queue.return_value = (True, 1, None)
        self.mock_music_player.youtube_client.extract_audio_info.return_value = AudioInfo(
            title="Test Song",
            duration=180,
            file_path="",
            url="https://youtube.com/watch?v=test",
            uploader="Test Channel"
        )
        
        url = "https://www.youtube.com/watch?v=test"
        await self.music_commands._handle_play_command(self.mock_ctx, url)
        
        self.mock_music_player.connect_to_user_channel.assert_called_once()
        self.mock_music_player.add_song_to_queue.assert_called_once()

    async def test_music_command_user_not_in_voice(self):
        """Test music command when user is not in voice channel."""
        self.mock_ctx.author.voice = None
        
        url = "https://www.youtube.com/watch?v=test"
        await self.music_commands._handle_play_command(self.mock_ctx, url)
        
        self.mock_ctx.reply.assert_called_once_with(
            "❌ You must be in a voice channel to play music!"
        )


class TestMusicPlayerAutoDisconnect(unittest.TestCase):
    """Test music player auto-disconnect functionality."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_bot = MagicMock()

        # Create mock config with auto-disconnect timeout
        self.mock_config = MagicMock(spec=ConfigManager)
        self.mock_config.get_music_auto_disconnect_timeout.return_value = 2  # 2 seconds for testing

        self.music_player = MusicPlayer(
            bot=self.mock_bot,
            temp_dir=self.temp_dir,
            config=self.mock_config
        )

        self.guild_id = 12345

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_auto_disconnect_timeout_with_config(self):
        """Test getting auto-disconnect timeout from config."""
        timeout = self.music_player._get_auto_disconnect_timeout()
        self.assertEqual(timeout, 2)

    def test_get_auto_disconnect_timeout_without_config(self):
        """Test getting auto-disconnect timeout without config (default)."""
        music_player_no_config = MusicPlayer(bot=self.mock_bot, temp_dir=self.temp_dir)
        timeout = music_player_no_config._get_auto_disconnect_timeout()
        self.assertEqual(timeout, 300)  # Default 5 minutes

    async def test_reset_inactivity_timer(self):
        """Test resetting inactivity timer."""
        # Start a timer first
        self.music_player._start_inactivity_timer(self.guild_id)
        self.assertIn(self.guild_id, self.music_player._inactivity_timers)

        # Reset it
        self.music_player._reset_inactivity_timer(self.guild_id)

        # Timer should be cancelled and removed
        self.assertNotIn(self.guild_id, self.music_player._inactivity_timers)
        self.assertIn(self.guild_id, self.music_player._last_activity_times)

    async def test_start_inactivity_timer(self):
        """Test starting inactivity timer."""
        self.music_player._start_inactivity_timer(self.guild_id)

        # Timer should be created
        self.assertIn(self.guild_id, self.music_player._inactivity_timers)
        self.assertTrue(self.music_player._inactivity_timers[self.guild_id])

    async def test_stop_inactivity_timer(self):
        """Test stopping inactivity timer."""
        # Start a timer first
        self.music_player._start_inactivity_timer(self.guild_id)
        self.assertIn(self.guild_id, self.music_player._inactivity_timers)

        # Stop it
        self.music_player._stop_inactivity_timer(self.guild_id)

        # Timer should be removed
        self.assertNotIn(self.guild_id, self.music_player._inactivity_timers)

    async def test_cleanup_guild_state(self):
        """Test cleaning up all guild state."""
        # Set up some state
        self.music_player._last_activity_times[self.guild_id] = 123456789
        self.music_player._start_inactivity_timer(self.guild_id)

        # Clean up
        await self.music_player._cleanup_guild_state(self.guild_id)

        # All state should be cleaned
        self.assertNotIn(self.guild_id, self.music_player._last_activity_times)
        self.assertNotIn(self.guild_id, self.music_player._inactivity_timers)

    async def test_inactivity_timer_task_disconnects(self):
        """Test that inactivity timer task disconnects after timeout."""
        # Mock voice manager methods
        self.music_player.voice_manager.is_connected = MagicMock(return_value=True)
        self.music_player.voice_manager.is_playing = MagicMock(return_value=False)
        self.music_player.voice_manager.disconnect_from_guild = AsyncMock(return_value=True)

        # Start inactivity timer with very short timeout
        timeout_seconds = 0.1  # 100ms for testing

        # Run the timer task
        await self.music_player._inactivity_timer_task(self.guild_id, timeout_seconds)

        # Should have attempted to disconnect
        self.music_player.voice_manager.disconnect_from_guild.assert_called_once_with(self.guild_id)

    async def test_inactivity_timer_task_cancelled(self):
        """Test that inactivity timer task handles cancellation."""
        # Mock voice manager methods
        self.music_player.voice_manager.is_connected = MagicMock(return_value=True)
        self.music_player.voice_manager.is_playing = MagicMock(return_value=False)
        self.music_player.voice_manager.disconnect_from_guild = AsyncMock(return_value=True)

        # Create and immediately cancel the task
        task = asyncio.create_task(
            self.music_player._inactivity_timer_task(self.guild_id, 10)
        )
        task.cancel()

        # Should handle cancellation gracefully
        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected

        # Should not have attempted to disconnect
        self.music_player.voice_manager.disconnect_from_guild.assert_not_called()


if __name__ == '__main__':
    # Run async tests
    async def run_async_tests():
        """Run all async tests."""
        test_classes = [
            TestYouTubeClient,
            TestQueueManager,
            TestVoiceManager,
            TestMusicCommands,
            TestMusicPlayerAutoDisconnect
        ]
        
        for test_class in test_classes:
            suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
            
            for test in suite:
                if asyncio.iscoroutinefunction(getattr(test, test._testMethodName)):
                    try:
                        await getattr(test, test._testMethodName)()
                        print(f"✅ {test_class.__name__}.{test._testMethodName}")
                    except Exception as e:
                        print(f"❌ {test_class.__name__}.{test._testMethodName}: {e}")
                else:
                    try:
                        getattr(test, test._testMethodName)()
                        print(f"✅ {test_class.__name__}.{test._testMethodName}")
                    except Exception as e:
                        print(f"❌ {test_class.__name__}.{test._testMethodName}: {e}")
    
    # Run tests
    asyncio.run(run_async_tests())
