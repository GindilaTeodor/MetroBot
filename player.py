# ---------- player.py ----------
"""
Music player helpers. This module defines a MusicManager and a MusicPlayer
class that handle per-guild queues and playback using yt-dlp and ffmpeg.

Features:
- Auto-disconnect after inactivity (default 5 min)
- Auto-disconnect if alone in VC
- Fully downloads tracks before playing to avoid streaming HLS issues
"""

import asyncio
from dataclasses import dataclass
import yt_dlp
import discord
import functools
import os
import tempfile

# ---------- yt-dlp options ----------
YTDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "cookiefile": "cookies.txt"  # change to your cookies file if needed
}

FFMPEG_OPTIONS = "-nostdin -hide_banner"

YTDL = yt_dlp.YoutubeDL(YTDL_OPTS)

# ---------- Track dataclass ----------
@dataclass
class Track:
    title: str
    url: str
    source_url: str
    duration: int
    requester: discord.Member
    file_path: str | None = None  # temp file path after download

# ---------- MusicPlayer ----------
class MusicPlayer:
    def __init__(self, guild_id: int, loop: asyncio.AbstractEventLoop, voice_client: discord.VoiceClient):
        self.guild_id = guild_id
        self.loop = loop
        self.voice_client = voice_client
        self.queue = asyncio.Queue()
        self.current: Track | None = None
        self.play_next_event = asyncio.Event()
        self.auto_disconnect_task: asyncio.Task | None = None
        self._task = self.loop.create_task(self.player_loop())

    async def queue_entry(self, query: str, requester: discord.Member) -> Track:
        info = await self.loop.run_in_executor(None, functools.partial(extract_info, query))
        track = Track(
            title=info.get("title"),
            url=info.get("url"),
            source_url=info.get("webpage_url"),
            duration=info.get("duration") or 0,
            requester=requester,
        )
        await self.queue.put(track)
        # Reset auto-disconnect timer
        await self.start_auto_disconnect()
        return track

    async def player_loop(self):
        while True:
            self.play_next_event.clear()
            self.current = await self.queue.get()

            # Download track fully before playing
            self.current.file_path = await self.loop.run_in_executor(None, download_track, self.current.url)

            source = discord.FFmpegPCMAudio(
                self.current.file_path,
                before_options=FFMPEG_OPTIONS,
                executable=os.getenv("FFMPEG_PATH", "ffmpeg")
            )

            def after_playing(err):
                if err:
                    print("Player error:", err)
                # cleanup temp file
                if self.current and self.current.file_path:
                    try:
                        os.remove(self.current.file_path)
                    except Exception:
                        pass
                self.loop.call_soon_threadsafe(self.play_next_event.set)

            self.voice_client.play(source, after=after_playing)
            await self.play_next_event.wait()
            self.current = None
            # Start auto-disconnect after finishing song
            await self.start_auto_disconnect()

    async def skip(self):
        if self.voice_client.is_playing():
            self.voice_client.stop()

    async def stop(self):
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except asyncio.QueueEmpty:
                break
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
        await self.start_auto_disconnect()

    async def start_auto_disconnect(self, timeout: int = 300):
        if self.auto_disconnect_task and not self.auto_disconnect_task.done():
            self.auto_disconnect_task.cancel()
        self.auto_disconnect_task = self.loop.create_task(self._auto_disconnect(timeout))

    async def _auto_disconnect(self, timeout: int):
        await asyncio.sleep(timeout)
        if not self.voice_client or not self.voice_client.is_connected():
            return
        # Leave immediately if alone
        if len(self.voice_client.channel.members) == 1:
            await self.voice_client.disconnect()
            return
        # Wait a short time for FFmpeg to finalize
        await asyncio.sleep(1)
        # Disconnect if nothing is playing and queue is empty
        if not self.voice_client.is_playing() and self.queue.empty() and self.current is None:
            await self.voice_client.disconnect()

# ---------- MusicManager ----------
class MusicManager:
    def __init__(self):
        self.players: dict[int, MusicPlayer] = {}

    def get_player(self, guild_id: int, loop: asyncio.AbstractEventLoop, voice_client: discord.VoiceClient) -> MusicPlayer:
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
            if player._task:
                player._task.cancel()
            if player.auto_disconnect_task:
                player.auto_disconnect_task.cancel()
            del self.players[guild_id]

# ---------- yt-dlp helper functions ----------
def extract_info(query: str) -> dict:
    if query.startswith("http"):
        inq = query
    else:
        inq = f"ytsearch1:{query}"
    info = YTDL.extract_info(inq, download=False)
    if "entries" in info:
        info = info["entries"][0]
    return info

def download_track(track_url: str) -> str:
    """
    Fully downloads the track to a temp file and returns the file path.
    """
    ytdl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(tempfile.gettempdir(), "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "cookiefile": "cookies.txt",
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
        info = ydl.extract_info(track_url, download=True)
        filename = ydl.prepare_filename(info)
        return filename
