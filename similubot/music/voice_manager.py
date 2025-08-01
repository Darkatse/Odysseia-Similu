"""Discord voice connection management for SimiluBot."""

import logging
import asyncio
from typing import Optional, Dict, Callable, Any
import discord
from discord.ext import commands


class VoiceManager:
    """
    Manages Discord voice connections for music playback.
    
    Handles connecting to voice channels, managing voice clients,
    and providing voice connection state management.
    """

    def __init__(self, bot: commands.Bot):
        """
        Initialize the voice manager.
        
        Args:
            bot: Discord bot instance
        """
        self.logger = logging.getLogger("similubot.music.voice_manager")
        self.bot = bot
        self._voice_clients: Dict[int, discord.VoiceClient] = {}
        self._connection_locks: Dict[int, asyncio.Lock] = {}

    async def connect_to_voice_channel(
        self, 
        channel: discord.VoiceChannel,
        timeout: float = 10.0
    ) -> Optional[discord.VoiceClient]:
        """
        Connect to a voice channel.
        
        Args:
            channel: Voice channel to connect to
            timeout: Connection timeout in seconds
            
        Returns:
            VoiceClient if successful, None otherwise
        """
        guild_id = channel.guild.id
        
        # Get or create lock for this guild
        if guild_id not in self._connection_locks:
            self._connection_locks[guild_id] = asyncio.Lock()
        
        async with self._connection_locks[guild_id]:
            try:
                # Check if already connected to this channel
                if guild_id in self._voice_clients:
                    voice_client = self._voice_clients[guild_id]
                    if voice_client.channel == channel and voice_client.is_connected():
                        self.logger.debug(f"Already connected to {channel.name}")
                        return voice_client
                    else:
                        # Disconnect from current channel
                        await self._disconnect_guild(guild_id)
                
                self.logger.info(f"Connecting to voice channel: {channel.name} in {channel.guild.name}")
                
                # Connect to the new channel
                voice_client = await channel.connect(timeout=timeout)
                self._voice_clients[guild_id] = voice_client
                
                self.logger.info(f"Successfully connected to {channel.name}")
                return voice_client
                
            except asyncio.TimeoutError:
                self.logger.error(f"Timeout connecting to {channel.name}")
                return None
            except discord.ClientException as e:
                self.logger.error(f"Discord error connecting to {channel.name}: {e}")
                return None
            except Exception as e:
                self.logger.error(f"Unexpected error connecting to {channel.name}: {e}", exc_info=True)
                return None

    async def disconnect_from_guild(self, guild_id: int) -> bool:
        """
        Disconnect from voice channel in a specific guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if disconnected successfully, False otherwise
        """
        if guild_id not in self._connection_locks:
            self._connection_locks[guild_id] = asyncio.Lock()
        
        async with self._connection_locks[guild_id]:
            return await self._disconnect_guild(guild_id)

    async def _disconnect_guild(self, guild_id: int) -> bool:
        """
        Internal method to disconnect from a guild (must be called with lock).
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if disconnected successfully, False otherwise
        """
        try:
            if guild_id in self._voice_clients:
                voice_client = self._voice_clients[guild_id]
                
                if voice_client.is_connected():
                    await voice_client.disconnect()
                    self.logger.info(f"Disconnected from voice channel in guild {guild_id}")
                
                del self._voice_clients[guild_id]
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error disconnecting from guild {guild_id}: {e}", exc_info=True)
            return False

    def get_voice_client(self, guild_id: int) -> Optional[discord.VoiceClient]:
        """
        Get the voice client for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            VoiceClient if connected, None otherwise
        """
        voice_client = self._voice_clients.get(guild_id)
        
        # Check if the connection is still valid
        if voice_client and not voice_client.is_connected():
            # Clean up invalid connection
            del self._voice_clients[guild_id]
            return None
        
        return voice_client

    def is_connected(self, guild_id: int) -> bool:
        """
        Check if bot is connected to a voice channel in a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if connected, False otherwise
        """
        voice_client = self.get_voice_client(guild_id)
        return voice_client is not None and voice_client.is_connected()

    def is_playing(self, guild_id: int) -> bool:
        """
        Check if bot is currently playing audio in a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if playing, False otherwise
        """
        voice_client = self.get_voice_client(guild_id)
        return voice_client is not None and voice_client.is_playing()

    def is_paused(self, guild_id: int) -> bool:
        """
        Check if bot is currently paused in a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            True if paused, False otherwise
        """
        voice_client = self.get_voice_client(guild_id)
        return voice_client is not None and voice_client.is_paused()

    def is_idle(self, guild_id: int) -> bool:
        """
        Check if bot is connected but not playing or paused (idle).

        Args:
            guild_id: Discord guild ID

        Returns:
            True if connected but idle, False otherwise
        """
        voice_client = self.get_voice_client(guild_id)
        if not voice_client or not voice_client.is_connected():
            return False

        return not voice_client.is_playing() and not voice_client.is_paused()

    async def play_audio(
        self, 
        guild_id: int, 
        source: discord.AudioSource,
        after_callback: Optional[Callable[[Optional[Exception]], None]] = None
    ) -> bool:
        """
        Play audio in a guild's voice channel.
        
        Args:
            guild_id: Discord guild ID
            source: Audio source to play
            after_callback: Optional callback when playback finishes
            
        Returns:
            True if playback started successfully, False otherwise
        """
        voice_client = self.get_voice_client(guild_id)
        
        if not voice_client:
            self.logger.error(f"No voice client for guild {guild_id}")
            return False
        
        try:
            if voice_client.is_playing():
                voice_client.stop()
            
            voice_client.play(source, after=after_callback)
            self.logger.info(f"Started audio playback in guild {guild_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting playback in guild {guild_id}: {e}", exc_info=True)
            return False

    def stop_audio(self, guild_id: int) -> bool:
        """
        Stop audio playback in a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if stopped successfully, False otherwise
        """
        voice_client = self.get_voice_client(guild_id)
        
        if not voice_client:
            return False
        
        try:
            if voice_client.is_playing() or voice_client.is_paused():
                voice_client.stop()
                self.logger.info(f"Stopped audio playback in guild {guild_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error stopping playback in guild {guild_id}: {e}", exc_info=True)
            return False

    def pause_audio(self, guild_id: int) -> bool:
        """
        Pause audio playback in a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if paused successfully, False otherwise
        """
        voice_client = self.get_voice_client(guild_id)
        
        if not voice_client or not voice_client.is_playing():
            return False
        
        try:
            voice_client.pause()
            self.logger.info(f"Paused audio playback in guild {guild_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error pausing playback in guild {guild_id}: {e}", exc_info=True)
            return False

    def resume_audio(self, guild_id: int) -> bool:
        """
        Resume audio playback in a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if resumed successfully, False otherwise
        """
        voice_client = self.get_voice_client(guild_id)
        
        if not voice_client or not voice_client.is_paused():
            return False
        
        try:
            voice_client.resume()
            self.logger.info(f"Resumed audio playback in guild {guild_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error resuming playback in guild {guild_id}: {e}", exc_info=True)
            return False

    async def cleanup_all_connections(self) -> None:
        """Clean up all voice connections."""
        self.logger.info("Cleaning up all voice connections")
        
        for guild_id in list(self._voice_clients.keys()):
            await self.disconnect_from_guild(guild_id)
        
        self._voice_clients.clear()
        self._connection_locks.clear()

    def get_connection_info(self, guild_id: int) -> Dict[str, Any]:
        """
        Get voice connection information for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Dictionary with connection details
        """
        voice_client = self.get_voice_client(guild_id)
        
        if not voice_client:
            return {
                "connected": False,
                "channel": None,
                "playing": False,
                "paused": False,
                "idle": False
            }
        
        return {
            "connected": voice_client.is_connected(),
            "channel": voice_client.channel.name if voice_client.channel else None,
            "playing": voice_client.is_playing(),
            "paused": voice_client.is_paused(),
            "idle": self.is_idle(guild_id)
        }
