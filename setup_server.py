import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

intents = discord.Intents.default()
intents.guilds = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    guild = client.guilds[0]
    
    print(f"Setting up server: {guild.name}")
    
    try:
        # 🌟 WELCOME & INFO
        cat_welcome = await guild.create_category('🌟 WELCOME & INFO')
        await guild.create_text_channel('👋・welcome', category=cat_welcome)
        await guild.create_text_channel('📜・rules', category=cat_welcome)
        await guild.create_text_channel('🏷️・self-roles', category=cat_welcome)
        
        # 💬 COMMUNITY
        cat_community = await guild.create_category('💬 COMMUNITY')
        await guild.create_text_channel('💬・general-chat', category=cat_community)
        await guild.create_text_channel('📈・levels', category=cat_community)
        # Note: Not creating livechat here so they don't get a duplicate. They can move their existing one.
        
        # 🎮 VOICE LOUNGES
        cat_voice = await guild.create_category('🎮 VOICE LOUNGES')
        await guild.create_voice_channel('🔊 Duo Call', category=cat_voice, user_limit=2)
        await guild.create_voice_channel('🔊 Trio Call', category=cat_voice, user_limit=3)
        await guild.create_voice_channel('🔊 Squad Call', category=cat_voice, user_limit=4)
        await guild.create_voice_channel('🔊 General VC', category=cat_voice)
        
        print('Server setup complete successfully!')
    except Exception as e:
        print(f"Error during setup: {e}")
        
    await client.close()

client.run(TOKEN)
