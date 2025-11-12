# ---------- bot.py ----------
import os
import asyncio
import logging
from discord.ext import commands
import discord
from player import MusicManager

from threading import Thread
from flask import Flask

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("metrolist-bot")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    logger.error("Please set DISCORD_TOKEN environment variable and restart.")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
music = MusicManager()


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (id: {bot.user.id})")
    logger.info("Ready!")


@bot.command(name="play")
async def play(ctx, *, query: str):
    async with ctx.typing():
        vc = ctx.voice_client
        if not vc:
            if not ctx.author.voice:
                await ctx.send("You are not connected to a voice channel.")
                return
            channel = ctx.author.voice.channel
            vc = await channel.connect()
        player = music.get_player(ctx.guild.id, bot.loop, vc)
        entry = await player.queue_entry(query, requester=ctx.author)
        await ctx.send(
            embed=discord.Embed(
                title="Queued", description=f"{entry.title}", color=0x1DB954
            )
        )


@bot.command(name="skip")
async def skip(ctx):
    player = music.get_player_if_exists(ctx.guild.id)
    if not player:
        await ctx.send("No music is playing right now.")
        return
    await player.skip()
    await ctx.send("Skipped.")


@bot.command(name="pause")
async def pause(ctx):
    vc = ctx.voice_client
    if not vc or not vc.is_playing():
        await ctx.send("Nothing is playing.")
        return
    vc.pause()
    await ctx.send("Paused.")


@bot.command(name="resume")
async def resume(ctx):
    vc = ctx.voice_client
    if not vc or not vc.is_paused():
        await ctx.send("Nothing is paused.")
        return
    vc.resume()
    await ctx.send("Resumed.")


@bot.command(name="stop")
async def stop(ctx):
    player = music.get_player_if_exists(ctx.guild.id)
    if not player:
        await ctx.send("Nothing to stop.")
        return
    await player.stop()
    await ctx.send("Stopped and cleared the queue.")


@bot.command(name="queue")
async def show_queue(ctx):
    player = music.get_player_if_exists(ctx.guild.id)
    if not player:
        await ctx.send("Nothing is playing.")
        return

    lines = []

    if player.current:
        lines.append(
            f"🎶 Now playing: {player.current.title} ({player.current.requester.display_name})"
        )

    upcoming = list(player.queue._queue)[:10]
    for i, track in enumerate(upcoming, start=1):
        lines.append(f"{i}. {track.title} ({track.requester.display_name})")

    if not lines:
        await ctx.send("Queue is empty.")
        return

    await ctx.send(
        embed=discord.Embed(
            title=f"Queue for {ctx.guild.name}",
            description="\n".join(lines),
            color=0x1DB954,
        )
    )


@bot.command(name="leave")
async def leave(ctx):
    vc = ctx.voice_client
    if not vc:
        await ctx.send("I'm not in a voice channel.")
        return
    await music.disconnect(ctx.guild.id)
    await ctx.send("Left voice channel.")


@bot.command(name="helpme")
async def helpme(ctx):
    help_text = (
        "Commands:\n"
        "!play <query or url> — play or queue a song\n"
        "!skip — skip current song\n"
        "!pause — pause playback\n"
        "!resume — resume playback\n"
        "!stop — stop and clear queue\n"
        "!queue — show queue\n"
        "!leave — disconnect bot\n"
    )
    await ctx.send(f"```\n{help_text}\n```")


# Flask keepalive
app = Flask("keepalive")


@app.route("/")
def index():
    return "Metrolist-style Discord bot is running."


def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))


if __name__ == "__main__":
    if os.getenv("ENABLE_KEEPALIVE", "1") == "1":
        t = Thread(target=run_flask, daemon=True)
        t.start()
    bot.run(DISCORD_TOKEN)
