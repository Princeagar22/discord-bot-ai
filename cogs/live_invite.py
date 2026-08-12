import discord
from discord.ext import commands
import os

class LiveInviteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="live")
    async def live_command(self, ctx, code: str = None, region: str = None):
        # Allow only 'prince' (or Server Owner for generality if prince's ID is unknown)
        # You can hardcode your user ID here: if ctx.author.id != YOUR_ID: return
        if not ctx.author.guild_permissions.administrator and ctx.author.name.lower() != "prince":
            await ctx.send("Only Prince or server administrators can use this command.")
            return

        if not code or not region:
            await ctx.send("Usage: `!live <code> <region>`")
            return

        play_channel_id_str = os.getenv('PLAY_CHANNEL_ID')
        if play_channel_id_str:
            try:
                play_channel_id = int(play_channel_id_str)
                play_channel = self.bot.get_channel(play_channel_id)
            except ValueError:
                play_channel = None
        else:
            # Fallback to finding a channel named 'play'
            play_channel = discord.utils.get(ctx.guild.text_channels, name='play')

        if not play_channel:
            await ctx.send("Could not find the 'play' channel. Please configure PLAY_CHANNEL_ID in .env or create a channel named 'play'.")
            return

        # Prepare invite embed
        embed = discord.Embed(
            title="🎮 Prince is playing!",
            description=f"Hey everyone! Prince is live and playing right now. Do you want to play?\n\n**Game Code:** `{code}`\n**Region:** `{region}`",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Join up fast!")
        
        # Ping @here or @everyone depending on preference, we use @here for active users
        await play_channel.send(content="@here kya aap khelenge prince khel raha hai!", embed=embed)
        await ctx.send(f"Live notification sent in {play_channel.mention}!")

async def setup(bot):
    await bot.add_cog(LiveInviteCog(bot))
