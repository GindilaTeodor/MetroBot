# ---------- player.py ----------
"""
Music player helpers. This module defines a MusicManager and a MusicPlayer
class that handle per-guild queues and playback using yt-dlp and ffmpeg.
"""

# (This file content is included below in the same document for clarity.)


# ---------- player.py (continued) ----------
# The real content is below — included as a single file in this canvas for convenience.

import asyncio
from dataclasses import dataclass
import yt_dlp
import discord
import functools
import os

# YTDLP options
YTDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
}

FFMPEG_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin -vn -hide_banner"


@dataclass
class Track:
    title: str
    url: str
    source_url: str
    duration: int
    requester: discord.Member


class MusicPlayer:
    def __init__(
        self,
        guild_id: int,
        loop: asyncio.AbstractEventLoop,
        voice_client: discord.VoiceClient,
    ):
        self.guild_id = guild_id
        self.loop = loop
        self.voice_client = voice_client
        self.queue = asyncio.Queue()
        self.current: Track | None = None
        self.play_next_event = asyncio.Event()
        self._task = self.loop.create_task(self.player_loop())

    async def queue_entry(self, query: str, requester: discord.Member) -> Track:
        """Search (or take URL) and queue a Track. Returns the Track queued."""
        info = await self.loop.run_in_executor(
            None, functools.partial(extract_info, query)
        )
        track = Track(
            title=info.get("title"),
            url=info.get("url"),
            source_url=info.get("webpage_url"),
            duration=info.get("duration") or 0,
            requester=requester,
        )
        await self.queue.put(track)
        return track

    async def player_loop(self):
        while True:
            self.play_next_event.clear()
            self.current = await self.queue.get()
            # create source
            source = discord.FFmpegPCMAudio(
                self.current.url,
                before_options=FFMPEG_OPTIONS,
                executable=os.getenv("FFMPEG_PATH", "ffmpeg"),
            )

            def after_playing(err):
                if err:
                    print("Player error:", err)
                # signal the loop to continue
                self.loop.call_soon_threadsafe(self.play_next_event.set)

            self.voice_client.play(source, after=after_playing)
            await self.play_next_event.wait()
            self.current = None

    async def skip(self):
        if self.voice_client.is_playing():
            self.voice_client.stop()

    async def stop(self):
        # clear queue
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except asyncio.QueueEmpty:
                break
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()


class MusicManager:
    def __init__(self):
        self.players: dict[int, MusicPlayer] = {}

    def get_player(
        self,
        guild_id: int,
        loop: asyncio.AbstractEventLoop,
        voice_client: discord.VoiceClient,
    ) -> MusicPlayer:
        if guild_id not in self.players:
            self.players[guild_id] = MusicPlayer(guild_id, loop, voice_client)
        return self.players[guild_id]

    def get_player_if_exists(self, guild_id: int):
        return self.players.get(guild_id)

    async def disconnect(self, guild_id: int):
        player = self.players.get(guild_id)
        if player:
            if player.voice_client:
                try:
                    await player.voice_client.disconnect()
                except Exception:
                    pass
            # cancel player loop task
            if player._task:
                player._task.cancel()
            del self.players[guild_id]


# Helper using yt-dlp
YTDL = yt_dlp.YoutubeDL(YTDL_OPTS)


def extract_info(query: str) -> dict:
    """If query looks like a URL, yt-dlp will use it. Otherwise we use ytsearch1: to search YouTube."""
    if query.startswith("http"):
        inq = query
    else:
        inq = f"ytsearch1:{query}"
    info = YTDL.extract_info(inq, download=False)
    # if it's a search, yt-dlp returns a playlist with entries
    if "entries" in info:
        info = info["entries"][0]
    # For streaming we want a URL to feed to ffmpeg. yt-dlp gives us a direct URL in 'url'
    # Note: depending on extractor it may be necessary to pick a format. We used 'format' in opts.
    return info
