import discord
from discord.ext import commands

class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # Find the new professional welcome channel
        channel = discord.utils.get(member.guild.text_channels, name='👋・welcome')
        if not channel:
            channel = member.guild.system_channel
        if not channel:
            # Fallback to finding a channel named 'general'
            channel = discord.utils.get(member.guild.text_channels, name='general')
        
        if channel:
            embed = discord.Embed(
                title=f"Welcome to the Server, {member.name}!",
                description=f"Hi {member.mention}, hello, how are you? Welcome to our community!",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))
