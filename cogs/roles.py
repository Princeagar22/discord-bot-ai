import discord
from discord.ext import commands

class RolesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_message_id = None # You'd normally store this in a DB
        # Mapping emoji to Role Name
        self.emoji_to_role = {
            "🎮": "Gamer",
            "🔔": "Ping Me!",
            "🌟": "VIP"
        }

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return
            
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
            
        channel = guild.get_channel(payload.channel_id)
        if not channel or channel.name != "🏷️・self-roles":
            return
            
        emoji_name = payload.emoji.name
        if emoji_name in self.emoji_to_role:
            role_name = self.emoji_to_role[emoji_name]
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                member = guild.get_member(payload.user_id)
                if member:
                    try:
                        await member.add_roles(role)
                    except discord.Forbidden:
                        pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
            
        channel = guild.get_channel(payload.channel_id)
        if not channel or channel.name != "🏷️・self-roles":
            return
            
        emoji_name = payload.emoji.name
        if emoji_name in self.emoji_to_role:
            role_name = self.emoji_to_role[emoji_name]
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                member = guild.get_member(payload.user_id)
                if member:
                    try:
                        await member.remove_roles(role)
                    except discord.Forbidden:
                        pass

async def setup(bot):
    await bot.add_cog(RolesCog(bot))
