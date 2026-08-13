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
    
    print(f"Locking down server: {guild.name}")
    
    try:
        # 1. Cleanup old channels
        old_general = discord.utils.get(guild.text_channels, name='general')
        old_play = discord.utils.get(guild.text_channels, name='play')
        old_livechat = discord.utils.get(guild.text_channels, name='livechat')
        old_vc = discord.utils.get(guild.voice_channels, name='General')
        
        # We also want to delete any livechat-2 if it exists
        livechat_2 = discord.utils.get(guild.text_channels, name='🔴・livechat-2')
        if livechat_2:
            await livechat_2.delete()
            
        if old_general:
            await old_general.delete()
            print("Deleted old #general")
        if old_play:
            await old_play.delete()
            print("Deleted old #play")
        if old_vc:
            await old_vc.delete()
            print("Deleted old General VC")
            
        # Move livechat
        cat_community = discord.utils.get(guild.categories, name='💬 COMMUNITY')
        if old_livechat and cat_community:
            await old_livechat.edit(category=cat_community, name='🔴・livechat')
            print("Moved and renamed #livechat")

        # 2. Lockdown Permissions
        cat_welcome = discord.utils.get(guild.categories, name='🌟 WELCOME & INFO')
        if cat_welcome:
            # Everyone can read, no one can send
            await cat_welcome.set_permissions(guild.default_role, send_messages=False, read_messages=True)
            print("Locked down WELCOME & INFO")
            
            # Re-sync channels in the category to inherit permissions
            for channel in cat_welcome.channels:
                await channel.edit(sync_permissions=True)

        cat_staff = discord.utils.get(guild.categories, name='🛡️ STAFF ONLY')
        if cat_staff:
            # Everyone cannot even read (hidden)
            await cat_staff.set_permissions(guild.default_role, read_messages=False)
            print("Secured STAFF ONLY")
            
            for channel in cat_staff.channels:
                await channel.edit(sync_permissions=True)
                
        print('Server lockdown complete successfully!')
    except Exception as e:
        print(f"Error during lockdown: {e}")
        
    await client.close()

client.run(TOKEN)
