

# ---------- README.md ----------
# Metrolist-style Discord Bot (Python)

This project is a starting point for a personal Discord music bot inspired by Metrolist's search/play behavior. It uses `yt-dlp` to search and stream audio from YouTube and `discord.py` to connect to Discord voice channels.

## Quickstart (local)
1. Install system dependencies:
   - Install `ffmpeg` (system package). On Ubuntu: `sudo apt install ffmpeg`.
2. Create a virtualenv and install Python deps:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Set your Discord token in the environment:
   ```bash
   export DISCORD_TOKEN="your_token_here"
   ```
4. Run the bot:
   ```bash
   python bot.py
   ```

## Deploy to Render (free tier)
1. Push the repository to GitHub.
2. Create a new service on Render: choose **Web Service** and connect the GitHub repo.
3. Use the `Free` instance type. Render expects a web process; `bot.py` starts a small Flask keepalive so Render's web service will be happy.
4. Set `DISCORD_TOKEN` in Render's environment variables.

## Notes & safety
- This project is intended for private/personal use on your own servers. Be mindful of YouTube/Google Terms of Service when streaming content.
- If you plan to distribute the bot's code, comply with licenses of any code you reuse.


# End of document
