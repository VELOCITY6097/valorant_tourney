# bot.py

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True
INTENTS.guilds = True
INTENTS.messages = True

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=INTENTS)

# Dynamically get all cogs from cogs/ folder
def get_cog_extensions():
    cogs_dir = "cogs"
    extensions = []
    for filename in os.listdir(cogs_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            extensions.append(f"{cogs_dir}.{filename[:-3]}")
    return extensions

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    synced = await bot.tree.sync()
    print(f"🔁 Synced {len(synced)} slash commands globally.")

async def load_cogs():
    for extension in get_cog_extensions():
        try:
            await bot.load_extension(extension)
            print(f"✅ Loaded extension: {extension}")
        except Exception as e:
            print(f"❌ Failed to load extension {extension}: {e}")

async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
