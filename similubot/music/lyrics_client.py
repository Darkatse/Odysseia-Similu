"""NetEase Cloud Music API client for lyrics fetching."""

import logging
import asyncio
import aiohttp
import json
from typing import Optional, Dict, Any, Tuple
from urllib.parse import quote


class NetEaseCloudMusicClient:
    """
    Client for interacting with NetEase Cloud Music API.

    Provides functionality to search for songs and fetch lyrics
    using third-party API endpoints.
    """

    def __init__(self):
        """Initialize the NetEase Cloud Music client."""
        self.logger = logging.getLogger("similubot.music.lyrics_client")

        # API endpoints
        self.search_api = "http://music.163.com/api/search/get"
        self.lyrics_api = "https://api.paugram.com/netease/"

        # Request headers for NetEase API
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "http://music.163.com",
            "Host": "music.163.com"
        }

        # Session timeout
        self.timeout = aiohttp.ClientTimeout(total=10)

        self.logger.debug("NetEase Cloud Music client initialized")

    async def search_song_id(self, song_title: str, artist: str = "") -> Optional[str]:
        """
        Search for a song on NetEase Cloud Music and return the song ID.

        Args:
            song_title: Title of the song to search for
            artist: Artist name (optional, helps improve search accuracy)

        Returns:
            Song ID as string, or None if not found
        """
        # Clean up the song title first
        cleaned_title = self._clean_search_query(song_title)

        # Construct search query with smart artist handling
        if artist:
            search_query = self._construct_search_query(cleaned_title, artist)
        else:
            search_query = cleaned_title

        try:
            self.logger.debug(f"Searching NetEase for: {search_query}")

            # Search parameters
            params = {
                's': search_query,
                'type': 1,  # 1 = songs, 2 = albums, 3 = artists, 4 = lyrics
                'limit': 5,  # Get top 5 results for better matching
            }

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    self.search_api,
                    params=params,
                    headers=self.headers
                ) as response:
                    if response.status != 200:
                        self.logger.warning(f"NetEase search API returned status {response.status}")
                        return None

                    # Handle different content types robustly
                    data = None

                    # First, check the content type
                    content_type = response.headers.get('content-type', '').lower()
                    self.logger.debug(f"Response content-type: {content_type}")

                    # Try to get the response text first
                    try:
                        text_response = await response.text()
                        self.logger.debug(f"Response text length: {len(text_response)}")
                    except Exception as e:
                        self.logger.error(f"Failed to read response text: {e}")
                        return None

                    # Try to parse as JSON regardless of content-type
                    if text_response.strip():
                        try:
                            data = json.loads(text_response)
                            self.logger.debug("Successfully parsed response as JSON")
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"Response is not valid JSON: {e}")
                            self.logger.debug(f"Response content (first 300 chars): {text_response[:300]}...")
                            return None
                    else:
                        self.logger.warning("Received empty response")
                        return None

                    # Check if we have results
                    if not data.get('result') or not data['result'].get('songs'):
                        self.logger.debug(f"No search results found for: {search_query}")
                        return None

                    songs = data['result']['songs']

                    # Try to find the best match
                    best_match = self._find_best_match(songs, song_title, artist)

                    if best_match:
                        song_id = str(best_match['id'])
                        self.logger.info(f"Found song ID {song_id} for: {search_query}")
                        return song_id
                    else:
                        self.logger.debug(f"No suitable match found for: {search_query}")
                        return None

        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout searching for song: {search_query}")
            return None
        except Exception as e:
            self.logger.error(f"Error searching for song '{search_query}': {e}", exc_info=True)
            return None

    async def get_lyrics(self, song_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch lyrics for a song using the enhanced API endpoint.

        Args:
            song_id: NetEase Cloud Music song ID

        Returns:
            Dictionary containing lyrics data, or None if failed
        """
        try:
            self.logger.debug(f"Fetching lyrics for song ID: {song_id}")

            url = f"{self.lyrics_api}?id={song_id}"

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        self.logger.warning(f"Lyrics API returned status {response.status}")
                        return None

                    # Handle different content types robustly
                    data = None

                    # First, check the content type
                    content_type = response.headers.get('content-type', '').lower()
                    self.logger.debug(f"Lyrics API content-type: {content_type}")

                    # Try to get the response text first
                    try:
                        text_response = await response.text()
                        self.logger.debug(f"Lyrics response text length: {len(text_response)}")
                    except Exception as e:
                        self.logger.error(f"Failed to read lyrics response text: {e}")
                        return None

                    # Try to parse as JSON regardless of content-type
                    if text_response.strip():
                        try:
                            data = json.loads(text_response)
                            self.logger.debug("Successfully parsed lyrics response as JSON")
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"Lyrics response is not valid JSON: {e}")
                            self.logger.debug(f"Lyrics response content (first 300 chars): {text_response[:300]}...")
                            return None
                    else:
                        self.logger.warning("Received empty lyrics response")
                        return None

                    # Check if the response is valid
                    # if not data.get('served', False):
                    #     self.logger.debug(f"Lyrics not available for song ID: {song_id}")
                    #     return None

                    # Extract lyrics data
                    lyrics_data = {
                        'id': data.get('id'),
                        'title': data.get('title'),
                        'artist': data.get('artist'),
                        'album': data.get('album'),
                        'cover': data.get('cover'),
                        'lyric': data.get('lyric', ''),
                        'sub_lyric': data.get('sub_lyric', ''),  # Translated lyrics
                        'link': data.get('link'),
                        'cached': data.get('cached', False)
                    }

                    self.logger.info(f"Successfully fetched lyrics for song ID: {song_id}")
                    return lyrics_data

        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout fetching lyrics for song ID: {song_id}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching lyrics for song ID '{song_id}': {e}", exc_info=True)
            return None

    def _clean_search_query(self, query: str) -> str:
        """
        Clean up search query to improve search accuracy using robust regex patterns.

        Args:
            query: Raw search query

        Returns:
            Cleaned search query
        """
        import re

        if not query or not query.strip():
            return ""

        cleaned = query.strip()

        # Define comprehensive regex patterns for common YouTube title formats
        # Case-insensitive patterns with flexible punctuation
        cleanup_patterns = [
            # Official video variations (with brackets)
            r'\s*[\(\[\{]\s*official\s+(?:music\s+)?video\s*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*official\s+audio\s*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*official\s*[\)\]\}]\s*',

            # Official variations (without brackets)
            r'\s*-\s*official\s+(?:music\s+)?video\s*',
            r'\s*-\s*official\s+audio\s*',
            r'\s*-\s*official\s*',

            # Lyric video variations (with brackets)
            r'\s*[\(\[\{]\s*lyric\s+video\s*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*lyrics?\s*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*with\s+lyrics?\s*[\)\]\}]\s*',

            # Live performance variations (with brackets)
            r'\s*[\(\[\{]\s*live\s+(?:performance|version|at)[^)]*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*live\s*[\)\]\}]\s*',

            # Remix and version variations (with brackets)
            r'\s*[\(\[\{]\s*(?:remix|extended|radio|clean|explicit)(?:\s+(?:version|edit))?\s*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*remaster(?:ed)?(?:\s*\d{4})?\s*[\)\]\}]\s*',

            # Featured artist patterns (with brackets)
            r'\s*[\(\[\{]\s*feat\.?\s+[^)]*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*ft\.?\s+[^)]*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*featuring\s+[^)]*[\)\]\}]\s*',

            # HD/HQ quality indicators (with brackets)
            r'\s*[\(\[\{]\s*(?:hd|hq|4k|1080p|720p)\s*[\)\]\}]\s*',

            # Year indicators (with brackets)
            r'\s*[\(\[\{]\s*(?:19|20)\d{2}\s*[\)\]\}]\s*',

            # Record label suffixes (with brackets)
            r'\s*[\(\[\{]\s*(?:records?|music|entertainment)\s*[\)\]\}]\s*',

            # Topic channel suffix
            r'\s*-\s*topic\s*$',

            # Special Unicode brackets and their content
            r'【[^】]*】',
            r'「[^」]*」',
            r'『[^』]*』',

            # Multiple consecutive dashes or separators
            r'\s*[-–—]+\s*$',  # Trailing separators
            r'^\s*[-–—]+\s*',  # Leading separators
        ]

        # Apply all cleanup patterns (case-insensitive)
        for pattern in cleanup_patterns:
            cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)

        # Clean up extra whitespace and normalize
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Remove leading/trailing punctuation that might be left over
        cleaned = re.sub(r'^[^\w\u4e00-\u9fff]+|[^\w\u4e00-\u9fff]+$', '', cleaned)

        return cleaned

    def _construct_search_query(self, cleaned_title: str, artist: str) -> str:
        """
        Construct search query with smart artist handling to avoid duplication.

        Args:
            cleaned_title: Already cleaned song title
            artist: Artist name

        Returns:
            Optimized search query
        """
        import re

        if not artist or not artist.strip():
            return cleaned_title

        artist_clean = artist.strip()
        title_clean = cleaned_title.strip()

        if not title_clean:
            return artist_clean

        # Normalize for comparison (lowercase, remove special chars)
        def normalize_for_comparison(text: str) -> str:
            # Convert to lowercase and remove non-alphanumeric chars except spaces
            normalized = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text.lower())
            return re.sub(r'\s+', ' ', normalized).strip()

        artist_normalized = normalize_for_comparison(artist_clean)
        title_normalized = normalize_for_comparison(title_clean)

        # Check if artist name is already present in the title
        artist_words = artist_normalized.split()
        title_words = title_normalized.split()

        # Check for artist presence in different ways
        artist_in_title = False

        # Method 1: Exact artist name match
        if artist_normalized in title_normalized:
            artist_in_title = True

        # Method 2: For multi-word artists, check if all significant words are present
        elif len(artist_words) > 1:
            # Filter out common words like "the", "and", etc.
            significant_words = [word for word in artist_words if len(word) > 2 and word not in ['the', 'and', 'or', 'of']]
            if significant_words and all(word in title_normalized for word in significant_words):
                artist_in_title = True

        # Method 3: For single word artists, check if it's in the title
        else:
            if artist_normalized in title_words:
                artist_in_title = True

        if artist_in_title:
            self.logger.debug(f"Artist '{artist_clean}' already present in title, using title only")
            return title_clean

        # Check for common artist-title separators already in the title
        separator_patterns = [
            r'^\s*' + re.escape(artist_normalized) + r'\s*[-–—:]\s*',
            r'\s*[-–—:]\s*' + re.escape(artist_normalized) + r'\s*$',
            r'^\s*' + re.escape(artist_normalized) + r'\s+',
        ]

        for pattern in separator_patterns:
            if re.search(pattern, title_normalized):
                self.logger.debug(f"Artist-title separator detected, using title only")
                return title_clean

        # Construct the search query with artist
        search_query = f"{title_clean} - {artist_clean}".replace("- Topic", "")

        self.logger.debug(f"Constructed search query: '{search_query}' from artist: '{artist_clean}' and title: '{title_clean}'")
        return search_query

    def _find_best_match(self, songs: list, target_title: str, target_artist: str = "") -> Optional[Dict[str, Any]]:
        """
        Find the best matching song from search results.

        Args:
            songs: List of song results from NetEase API
            target_title: Target song title
            target_artist: Target artist name

        Returns:
            Best matching song data, or None if no good match
        """
        if not songs:
            return None

        # If we only have one result, return it
        if len(songs) == 1:
            return songs[0]

        # Score each song based on title and artist similarity
        best_score = 0
        best_match = None

        target_title_lower = target_title.lower()
        target_artist_lower = target_artist.lower()

        for song in songs:
            score = 0
            song_title = song.get('name', '').lower()
            song_artists = [artist.get('name', '').lower() for artist in song.get('artists', [])]

            # Title similarity (most important)
            if target_title_lower in song_title or song_title in target_title_lower:
                score += 10
            elif any(word in song_title for word in target_title_lower.split()):
                score += 5

            # Artist similarity
            if target_artist_lower:
                for artist in song_artists:
                    if target_artist_lower in artist or artist in target_artist_lower:
                        score += 8
                        break
                    elif any(word in artist for word in target_artist_lower.split()):
                        score += 3
                        break

            # Prefer songs with higher popularity (if available)
            if song.get('popularity', 0) > 50:
                score += 1

            if score > best_score:
                best_score = score
                best_match = song

        # Only return if we have a reasonable match
        if best_score >= 5:
            return best_match

        # Fallback to first result if no good match
        return songs[0]

    async def search_and_get_lyrics(self, song_title: str, artist: str = "") -> Optional[Dict[str, Any]]:
        """
        Search for a song and fetch its lyrics in one operation.

        Args:
            song_title: Title of the song
            artist: Artist name (optional)

        Returns:
            Dictionary containing lyrics data, or None if failed
        """
        try:
            # Try the direct search approach first
            song_id = await self.search_song_id(song_title, artist)
            if song_id:
                lyrics_data = await self.get_lyrics(song_id)
                if lyrics_data:
                    return lyrics_data

            # If direct search fails, try some common song IDs for testing
            # This is a fallback for development/testing purposes
            self.logger.debug(f"Direct search failed for '{song_title}', trying fallback approach")

            # For now, return None to gracefully handle missing lyrics
            # In production, you might want to implement additional search strategies
            return None

        except Exception as e:
            self.logger.error(f"Error in search_and_get_lyrics for '{song_title}' by '{artist}': {e}", exc_info=True)
            return None
