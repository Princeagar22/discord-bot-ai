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

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')
    await bot.change_presence(activity=discord.Game(name="Chatting & Managing"))

async def load_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Loaded extension: {filename}')
            except Exception as e:
                print(f'Failed to load extension {filename}: {e}')

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
