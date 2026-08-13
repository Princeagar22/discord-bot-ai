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
    
    print(f"Upgrading server: {guild.name}")
    
    try:
        # Find existing categories
        cat_welcome = discord.utils.get(guild.categories, name='🌟 WELCOME & INFO')
        cat_community = discord.utils.get(guild.categories, name='💬 COMMUNITY')
        
        if cat_welcome:
            if not discord.utils.get(guild.text_channels, name='📢・announcements'):
                await guild.create_text_channel('📢・announcements', category=cat_welcome)
                
        if cat_community:
            if not discord.utils.get(guild.text_channels, name='🤖・bot-commands'):
                await guild.create_text_channel('🤖・bot-commands', category=cat_community)
            if not discord.utils.get(guild.text_channels, name='📷・media'):
                await guild.create_text_channel('📷・media', category=cat_community)
                
        # 🛡️ STAFF ONLY
        if not discord.utils.get(guild.categories, name='🛡️ STAFF ONLY'):
            # Calculate permissions to hide from @everyone
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            # Note: The owner automatically has access because they own the server.
            cat_staff = await guild.create_category('🛡️ STAFF ONLY', overwrites=overwrites)
            await guild.create_text_channel('💬・staff-chat', category=cat_staff)
        
        print('Server upgrade complete successfully!')
    except Exception as e:
        print(f"Error during upgrade: {e}")
        
    await client.close()

client.run(TOKEN)
