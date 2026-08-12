import discord
from discord.ext import commands
import time

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_counts = {} # user_id: [timestamps]
        self.SPAM_LIMIT = 5
        self.SPAM_TIME_FRAME = 5 # seconds

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        user_id = message.author.id
        current_time = time.time()

        if user_id not in self.message_counts:
            self.message_counts[user_id] = []

        # Remove old timestamps
        self.message_counts[user_id] = [ts for ts in self.message_counts[user_id] if current_time - ts <= self.SPAM_TIME_FRAME]
        self.message_counts[user_id].append(current_time)

        if len(self.message_counts[user_id]) > self.SPAM_LIMIT:
            # User is spamming
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            
            warning_embed = discord.Embed(
                title="⚠️ Spam Warning",
                description=f"{message.author.mention}, please slow down! You are sending messages too quickly.\n\n**Server Rules:**\n1. No spamming or flooding the chat.\n2. Be respectful to others.\n3. Listen to the moderators.",
                color=discord.Color.red()
            )
            await message.channel.send(embed=warning_embed, delete_after=10)

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
