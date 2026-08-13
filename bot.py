import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Setup intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True # Required for welcome message
intents.presences = True # Required to see who is online

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')
    await bot.change_presence(activity=discord.Game(name="Chatting & Managing"))

async def load_cogs():
    for cog in ['cogs.chat', 'cogs.moderation', 'cogs.welcome', 'cogs.live_invite', 'cogs.youtube', 'cogs.leveling', 'cogs.roles']:
        try:
            await bot.load_extension(cog)
            print(f'Loaded extension: {cog}')
        except Exception as e:
            print(f'Failed to load extension {cog}: {e}')

async def main():
    async with bot:
        await load_cogs()
        if TOKEN and TOKEN != "your_bot_token_here":
            await bot.start(TOKEN)
        else:
            print("ERROR: Please configure DISCORD_BOT_TOKEN in your .env file.")

if __name__ == '__main__':
    # Ensure cogs directory exists
    os.makedirs('./cogs', exist_ok=True)
    asyncio.run(main())
