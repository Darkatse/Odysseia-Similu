"""Tests for music lyrics integration."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from similubot.music.lyrics_client import NetEaseCloudMusicClient
from similubot.music.lyrics_parser import LyricsParser, LyricLine
from similubot.progress.music_progress import MusicProgressUpdater


class TestLyricsClient:
    """Test cases for NetEaseCloudMusicClient."""

    @pytest.fixture
    def client(self):
        """Create a lyrics client instance."""
        return NetEaseCloudMusicClient()

    @pytest.mark.asyncio
    async def test_get_lyrics_success(self, client):
        """Test successful lyrics fetching."""
        # Mock the aiohttp response
        mock_response_data = {
            "id": "18520488",
            "title": "Never Gonna Give You Up",
            "artist": "Rick Astley",
            "lyric": "[00:18.684]We're no strangers to love\n[00:22.657]You know the rules and so do I",
            "sub_lyric": "[00:18.684]我们都是情场老手\n[00:22.657]你和我都知道爱情的规则",
            "served": True
        }

        import json
        mock_response_text = json.dumps(mock_response_data)

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'content-type': 'text/json;charset=utf-8'}
            mock_response.text.return_value = mock_response_text
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await client.get_lyrics("18520488")

            assert result is not None
            assert result['title'] == "Never Gonna Give You Up"
            assert result['artist'] == "Rick Astley"
            assert 'lyric' in result
            assert 'sub_lyric' in result

    @pytest.mark.asyncio
    async def test_get_lyrics_not_served(self, client):
        """Test lyrics fetching when not served."""
        mock_response_data = {"served": False}

        import json
        mock_response_text = json.dumps(mock_response_data)

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'content-type': 'text/json;charset=utf-8'}
            mock_response.text.return_value = mock_response_text
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await client.get_lyrics("invalid_id")

            assert result is None

    def test_clean_search_query(self, client):
        """Test search query cleaning with regex patterns."""
        test_cases = [
            # Basic official video patterns
            ("Song Title (Official Music Video)", "Song Title"),
            ("Song Title [Official Video]", "Song Title"),
            ("Song Title {Official Audio}", "Song Title"),
            ("Song Title - Official", "Song Title"),

            # Case insensitive patterns
            ("Song Title (OFFICIAL MUSIC VIDEO)", "Song Title"),
            ("Song Title [official audio]", "Song Title"),

            # Lyric video patterns
            ("Song Title (Lyric Video)", "Song Title"),
            ("Song Title [Lyrics]", "Song Title"),
            ("Song Title (With Lyrics)", "Song Title"),

            # Live performance patterns
            ("Song Title (Live Performance)", "Song Title"),
            ("Song Title [Live at Concert]", "Song Title"),
            ("Song Title {Live}", "Song Title"),

            # Featured artist patterns
            ("Song Title (feat. Artist)", "Song Title"),
            ("Song Title [ft. Artist]", "Song Title"),
            ("Song Title (featuring Artist)", "Song Title"),

            # Quality indicators
            ("Song Title (HD)", "Song Title"),
            ("Song Title [4K]", "Song Title"),
            ("Song Title {1080p}", "Song Title"),

            # Year indicators
            ("Song Title (2023)", "Song Title"),
            ("Song Title [1995]", "Song Title"),

            # Unicode brackets
            ("Song Title【Official】", "Song Title"),
            ("Song Title「Official」", "Song Title"),

            # Multiple patterns
            ("Song Title (Official Music Video) [HD] (2023)", "Song Title"),

            # Extra spaces
            ("  Extra   Spaces  ", "Extra Spaces"),

            # Topic channel
            ("Song Title - Topic", "Song Title"),

            # Trailing separators
            ("Song Title ---", "Song Title"),
        ]

        for input_query, expected in test_cases:
            result = client._clean_search_query(input_query)
            assert result == expected, f"Failed for '{input_query}': got '{result}', expected '{expected}'"

    def test_construct_search_query(self, client):
        """Test search query construction with artist deduplication."""
        test_cases = [
            # Artist not in title - should concatenate
            ("Song Title", "Artist Name", "Artist Name - Song Title"),

            # Artist already in title - should use title only
            ("Artist Name - Song Title", "Artist Name", "Artist Name - Song Title"),
            ("Artist Name Song Title", "Artist Name", "Artist Name Song Title"),

            # Multi-word artist partially in title
            ("The Beatles - Hey Jude", "The Beatles", "The Beatles - Hey Jude"),
            ("Beatles Hey Jude", "The Beatles", "Beatles Hey Jude"),  # Partial match, should use title only

            # Case insensitive matching
            ("ARTIST NAME - Song Title", "Artist Name", "ARTIST NAME - Song Title"),

            # Special characters in artist name
            ("AC/DC - Thunderstruck", "AC/DC", "AC/DC - Thunderstruck"),

            # Empty artist
            ("Song Title", "", "Song Title"),

            # Empty title
            ("", "Artist Name", "Artist Name"),

            # Artist with separators already present
            ("Artist: Song Title", "Artist", "Artist: Song Title"),
            ("Artist – Song Title", "Artist", "Artist – Song Title"),
        ]

        for title, artist, expected in test_cases:
            # Clean the title first (as done in the actual method)
            cleaned_title = client._clean_search_query(title)
            result = client._construct_search_query(cleaned_title, artist)
            assert result == expected, f"Failed for title='{title}', artist='{artist}': got '{result}', expected '{expected}'"


class TestLyricsParser:
    """Test cases for LyricsParser."""

    @pytest.fixture
    def parser(self):
        """Create a lyrics parser instance."""
        return LyricsParser()

    def test_parse_lrc_lyrics(self, parser):
        """Test LRC lyrics parsing."""
        lrc_content = """[00:18.684]We're no strangers to love
[00:22.657]You know the rules and so do I
[00:27.070]A full commitment's what I'm thinking of"""

        result = parser.parse_lrc_lyrics(lrc_content)

        assert len(result) == 3
        assert result[0].timestamp == 18.684
        assert result[0].text == "We're no strangers to love"
        assert result[1].timestamp == 22.657
        assert result[2].timestamp == 27.070

    def test_parse_lrc_with_translation(self, parser):
        """Test LRC parsing with translation."""
        main_lyrics = "[00:18.684]We're no strangers to love"
        translated_lyrics = "[00:18.684]我们都是情场老手"

        result = parser.parse_lrc_lyrics(main_lyrics, translated_lyrics)

        assert len(result) == 1
        assert result[0].text == "We're no strangers to love"
        assert result[0].translated_text == "我们都是情场老手"

    def test_get_current_lyric(self, parser):
        """Test getting current lyric based on position."""
        lyrics = [
            LyricLine(10.0, "First line"),
            LyricLine(20.0, "Second line"),
            LyricLine(30.0, "Third line"),
        ]

        # Test various positions
        assert parser.get_current_lyric(lyrics, 5.0) is None
        assert parser.get_current_lyric(lyrics, 15.0).text == "First line"
        assert parser.get_current_lyric(lyrics, 25.0).text == "Second line"
        assert parser.get_current_lyric(lyrics, 35.0).text == "Third line"

    def test_get_lyric_context(self, parser):
        """Test getting lyric context."""
        lyrics = [
            LyricLine(10.0, "First line"),
            LyricLine(20.0, "Second line"),
            LyricLine(30.0, "Third line"),
            LyricLine(40.0, "Fourth line"),
        ]

        context = parser.get_lyric_context(lyrics, 25.0, context_lines=1)

        assert context['current'].text == "Second line"
        assert len(context['previous']) == 1
        assert context['previous'][0].text == "First line"
        assert len(context['next']) == 1
        assert context['next'][0].text == "Third line"

    def test_is_instrumental_track(self, parser):
        """Test instrumental track detection."""
        # Empty lyrics
        assert parser.is_instrumental_track([])

        # Only metadata
        metadata_lyrics = [
            LyricLine(0.0, "作词 : Someone"),
            LyricLine(1.0, "作曲 : Someone"),
        ]
        assert parser.is_instrumental_track(metadata_lyrics)

        # Real lyrics
        real_lyrics = [
            LyricLine(0.0, "作词 : Someone"),
            LyricLine(10.0, "First line"),
            LyricLine(20.0, "Second line"),
            LyricLine(30.0, "Third line"),
        ]
        assert not parser.is_instrumental_track(real_lyrics)

    def test_format_time(self, parser):
        """Test time formatting."""
        assert parser.format_time(0) == "00:00"
        assert parser.format_time(65) == "01:05"
        assert parser.format_time(125.5) == "02:05"


class TestMusicProgressWithLyrics:
    """Test cases for MusicProgressUpdater with lyrics integration."""

    @pytest.fixture
    def mock_music_player(self):
        """Create a mock music player."""
        player = Mock()
        player.get_current_playback_position.return_value = 25.0
        player.voice_manager.is_playing.return_value = True
        player.voice_manager.is_paused.return_value = False
        player.voice_manager.is_connected.return_value = True
        return player

    @pytest.fixture
    def mock_song(self):
        """Create a mock song object."""
        song = Mock()
        song.title = "Test Song"
        song.uploader = "Test Artist"
        song.duration = 180
        song.requester.display_name = "TestUser"
        song.audio_info.thumbnail_url = "http://example.com/thumb.jpg"
        return song

    @pytest.fixture
    def progress_updater(self, mock_music_player):
        """Create a progress updater instance."""
        return MusicProgressUpdater(mock_music_player)

    @pytest.mark.asyncio
    async def test_get_song_lyrics_cache(self, progress_updater, mock_song):
        """Test lyrics caching functionality."""
        # Mock the lyrics client
        with patch.object(progress_updater.lyrics_client, 'search_and_get_lyrics') as mock_search:
            mock_lyrics_data = {
                'lyric': '[00:10.000]Test lyric\n[00:20.000]Another line\n[00:30.000]Third line\n[00:40.000]Fourth line',
                'sub_lyric': ''
            }
            mock_search.return_value = mock_lyrics_data

            # First call should fetch lyrics
            result1 = await progress_updater.get_song_lyrics(mock_song)
            assert result1 is not None
            assert len(result1) == 4  # Four lyric lines

            # Second call should use cache
            result2 = await progress_updater.get_song_lyrics(mock_song)
            assert result2 == result1

            # Should only call the API once
            assert mock_search.call_count == 1

    def test_get_current_lyric_display(self, progress_updater):
        """Test lyric display formatting."""
        lyrics = [
            LyricLine(10.0, "First line", "第一行"),
            LyricLine(20.0, "Second line", "第二行"),
            LyricLine(30.0, "Third line", "第三行"),
        ]

        # Test current lyric display
        display = progress_updater._get_current_lyric_display(lyrics, 25.0)

        # The display should contain the current line in bold and translation
        assert "**Second line" in display
        assert "第二行" in display
        assert "Third line" in display  # Next line preview

    def test_get_current_lyric_display_no_lyrics(self, progress_updater):
        """Test lyric display with no lyrics."""
        display = progress_updater._get_current_lyric_display([], 25.0)
        assert "No lyrics available" in display

    @pytest.mark.asyncio
    async def test_create_progress_embed_with_lyrics(self, progress_updater, mock_song):
        """Test embed creation with lyrics."""
        lyrics = [LyricLine(20.0, "Test lyric line")]

        embed = progress_updater.create_progress_embed(123, mock_song, lyrics)

        assert embed is not None
        assert embed.title == "🎵 Now Playing"

        # Check if lyrics field is present
        lyrics_field = None
        for field in embed.fields:
            if field.name == "🎤 Lyrics":
                lyrics_field = field
                break

        assert lyrics_field is not None
        assert "Test lyric line" in lyrics_field.value


if __name__ == "__main__":
    pytest.main([__file__])
