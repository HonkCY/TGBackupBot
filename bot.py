import os
import re
import sqlite3
import json
from telethon import TelegramClient, events
from yt_dlp import YoutubeDL

# read config
with open("config.json", "r") as f:
    config = json.load(f)

# initial bot with client api
bot = TelegramClient('bot', config["API_ID"], config["API_HASH"]).start(bot_token=config["BOT_TOKEN"])

# settings
DOWNLOAD_FOLDER = config["DOWNLOAD_FOLDER"]
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

DB_FILE = config["DB_FILE"]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY,
            platform TEXT,
            title TEXT
        )
        """
    )
    conn.commit()
    conn.close()

def is_video_downloaded(video_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM videos WHERE video_id = ?", (video_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def record_video(video_id, platform, title):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO videos (video_id, platform, title) VALUES (?, ?, ?)",
        (video_id, platform, title),
    )
    conn.commit()
    conn.close()

async def download_video(url, platform):
    try:
        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "outtmpl": f"{DOWNLOAD_FOLDER}/%(title)s.%(ext)s",
            "merge_output_format": "mp4",
            "ratelimit": 500000,  # to avoid throttling
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_id = info.get("id")
            title = info.get("title")

            if is_video_downloaded(video_id):
                return f"Failed to download： {title}"

            ydl.download([url])

            record_video(video_id, platform, title)
            return "Done"

    except Exception as e:
        return f"Error： {e}"

async def download_tg_video(message):
    try:
        platform = "TG"
        video_id = message.media.document.id 
        title = video_id 
        ext = message.media.document.mime_type.split('/')[-1]
        save_path = f"{DOWNLOAD_FOLDER}/{title}.{ext}"
        if is_video_downloaded(video_id):
            return f"Failed to download： {title}"
        await bot.download_media(message,save_path)
        record_video(video_id, platform, title)
        return "Done"
    except Exception as e:
        return f"Error: {e}"


def check_post_link(msg):
    pattern = r"https:\/\/t\.me\/(?P<username_or_chat>[\w\d_]+)\/(?P<message_id>\d+)"
    match = re.match(pattern, msg)
    if not match:
        return False
    return True

def parse_post_link(url):
    pattern = r"https:\/\/t\.me\/(?P<username_or_chat>[\w\d_]+)\/(?P<message_id>\d+)"
    match = re.match(pattern, url)

    username_or_chat = match.group("username_or_chat")
    message_id = int(match.group("message_id"))

    if username_or_chat.isdigit():
        chat_id = int(username_or_chat) * -1
        return chat_id, message_id
    else:
        return username_or_chat, message_id

async def download_media_from_post_link(url):
    chat, message_id = parse_post_link(url)
    try:
        message = await bot.get_messages(chat, ids=message_id)
        if message and message.media:
            file_path = await bot.download_media(message.media, file=DOWNLOAD_FOLDER)
            return "Done"
        else:
            return "Failed to download"
    except Exception as e:
        return f"Error： {e}"


@bot.on(events.NewMessage)
async def handle_message(event):
    message = event.message.message.strip()
    chat_id = event.chat_id

    if message == "/start":
        await bot.send_message(chat_id, "Hello, World!")
        return

    if "youtube.com" in message or "youtu.be" in message:
        print("Request to download YT video.")
        result = await download_video(message, "YouTube")
    elif "instagram.com" in message:
        print("Request to download IG video.")
        result = await download_video(message, "Instagram")
    elif event.message.media is not None:
        print("Request to download TG video by forwarding.")
        result = await download_tg_video(event.message)
    elif check_post_link(message):
        print("Request to download TG video by link.")
        result = await download_media_from_post_link(message)
    else:
        print("Invalid Request.")
    print(f"Status: {result}")
    await event.message.delete()


init_db()

print("Bot started！")
bot.run_until_disconnected()