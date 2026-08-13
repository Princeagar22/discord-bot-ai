import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    guild = client.guilds[0]
    print(f"Setting up content for server: {guild.name}")
    
    try:
        # 1. Create Roles
        role_data = [
            {"name": "VIP", "color": discord.Color.gold(), "hoist": True},
            {"name": "Gamer", "color": discord.Color.blue(), "hoist": False},
            {"name": "Ping Me!", "color": discord.Color.green(), "hoist": False}
        ]
        
        for data in role_data:
            role = discord.utils.get(guild.roles, name=data["name"])
            if not role:
                await guild.create_role(name=data["name"], color=data["color"], hoist=data["hoist"])
                print(f"Created role: {data['name']}")
                
        # 2. Populate #📜・rules
        channel_rules = discord.utils.get(guild.text_channels, name='📜・rules')
        if channel_rules:
            await channel_rules.purge(limit=10)
            embed = discord.Embed(
                title="📜 SERVER RULES", 
                description="Welcome to the server! Please follow these rules to keep the community safe and fun.",
                color=discord.Color.red()
            )
            embed.add_field(name="1. Be Respectful", value="No toxicity, hate speech, or harassment.", inline=False)
            embed.add_field(name="2. No Spamming", value="Do not spam messages, links, or mentions.", inline=False)
            embed.add_field(name="3. Keep it PG-13", value="No NSFW content allowed anywhere.", inline=False)
            embed.add_field(name="4. Listen to Staff", value="Moderators have the final say.", inline=False)
            embed.set_footer(text="Breaking rules may result in a ban.")
            await channel_rules.send(embed=embed)
            print("Populated #rules")
            
        # 3. Populate #📢・announcements
        channel_ann = discord.utils.get(guild.text_channels, name='📢・announcements')
        if channel_ann:
            await channel_ann.purge(limit=10)
            embed = discord.Embed(
                title="📢 Welcome to the Announcements!", 
                description="This is where all official updates, new videos, and live stream links will be posted.\n\nMake sure you have the **Ping Me!** role to get notified!",
                color=discord.Color.blue()
            )
            await channel_ann.send(embed=embed)
            print("Populated #announcements")
            
        # 4. Populate #🏷️・self-roles
        channel_roles = discord.utils.get(guild.text_channels, name='🏷️・self-roles')
        if channel_roles:
            await channel_roles.purge(limit=10)
            embed = discord.Embed(
                title="🏷️ CLAIM YOUR ROLES", 
                description="React to this message with the emojis below to get your roles!\n\n"
                            "🎮 : **Gamer** (Show that you're a gamer)\n"
                            "🔔 : **Ping Me!** (Get notified for streams & giveaways)\n"
                            "🌟 : **VIP** (For special supporters)",
                color=discord.Color.purple()
            )
            msg = await channel_roles.send(embed=embed)
            await msg.add_reaction("🎮")
            await msg.add_reaction("🔔")
            await msg.add_reaction("🌟")
            print("Populated #self-roles")
            
        print('Content setup complete successfully!')
    except Exception as e:
        print(f"Error during setup: {e}")
        
    await client.close()

client.run(TOKEN)
