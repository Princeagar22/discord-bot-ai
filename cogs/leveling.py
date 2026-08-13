import discord
from discord.ext import commands
import json
import os
import random
import time

class LevelingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = "levels.json"
        self.users = {}
        self.cooldowns = {}
        self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as f:
                self.users = json.load(f)
        else:
            self.users = {}

    def save_data(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.users, f, indent=4)

    def get_xp_for_level(self, level):
        # 5 * (level ^ 2) + (50 * level) + 100
        return 5 * (level ** 2) + (50 * level) + 100

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Simple 10 second cooldown
        author_id = str(message.author.id)
        current_time = time.time()
        
        if author_id in self.cooldowns:
            if current_time - self.cooldowns[author_id] < 10:
                return
                
        self.cooldowns[author_id] = current_time

        if author_id not in self.users:
            self.users[author_id] = {"xp": 0, "level": 1}

        xp_gained = random.randint(15, 25)
        self.users[author_id]["xp"] += xp_gained
        
        current_level = self.users[author_id]["level"]
        xp_needed = self.get_xp_for_level(current_level)

        if self.users[author_id]["xp"] >= xp_needed:
            self.users[author_id]["level"] += 1
            self.users[author_id]["xp"] -= xp_needed # carry over remainder
            
            new_level = self.users[author_id]["level"]
            self.save_data()
            
            # Announce level up
            level_channel = discord.utils.get(message.guild.text_channels, name='📈・levels')
            if not level_channel:
                level_channel = message.channel
                
            embed = discord.Embed(
                title="Level Up! 🎉",
                description=f"GG {message.author.mention}, you just advanced to **Level {new_level}**!",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=message.author.avatar.url if message.author.avatar else message.author.default_avatar.url)
            await level_channel.send(embed=embed)
        else:
            # Save data every 5 messages to avoid disk spam
            if random.random() < 0.2:
                self.save_data()

    @commands.command(name="rank")
    async def rank(self, ctx, member: discord.Member = None):
        """Shows the rank and XP of a user."""
        # Auto-delete the user's !rank command message to keep channel clean
        try:
            await ctx.message.delete()
        except Exception:
            pass

        # Only allow in bot-commands channel
        bot_commands_channel = discord.utils.get(ctx.guild.text_channels, name='🤖・bot-commands')
        if bot_commands_channel and ctx.channel.id != bot_commands_channel.id:
            await ctx.send(f"❌ {ctx.author.mention} Use commands in {bot_commands_channel.mention} only!", delete_after=5)
            return
        member = member or ctx.author
        member_id = str(member.id)

        if member_id not in self.users:
            embed = discord.Embed(
                description=f"{member.mention} has no XP yet. Start chatting!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        user_data = self.users[member_id]
        level = user_data["level"]
        xp = user_data["xp"]
        next_level_xp = self.get_xp_for_level(level)

        embed = discord.Embed(
            title=f"{member.name}'s Rank Info",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(name="XP", value=f"**{xp} / {next_level_xp}**", inline=True)
        
        # Calculate progress bar
        progress = xp / next_level_xp
        filled_blocks = int(progress * 10)
        empty_blocks = 10 - filled_blocks
        progress_bar = "🟩" * filled_blocks + "⬛" * empty_blocks
        
        embed.add_field(name="Progress", value=progress_bar, inline=False)
        await ctx.send(embed=embed)

        # Move the Commands List embed back to the bottom!
        mod_cog = self.bot.get_cog('ModerationCog')
        if mod_cog and bot_commands_channel:
            await mod_cog.post_help_embed(bot_commands_channel)

async def setup(bot):
    await bot.add_cog(LevelingCog(bot))
