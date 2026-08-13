import discord
from discord.ext import commands
import time

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_counts = {} # user_id: [timestamps]
        self.SPAM_LIMIT = 5
        self.SPAM_TIME_FRAME = 5 # seconds
        self.help_message_id = None  # Store ID of the help embed in bot-commands
        
        # Basic list of bad words (lowercase). Add more as needed.
        self.bad_words = ["fuck", "shit", "bitch", "asshole", "chutiya", "madarchod", "bhenchod", "gali", "gandu", "kamina"]

    async def post_help_embed(self, channel):
        """Delete old help embed and post a fresh one at the bottom."""
        if not channel:
            return
        try:
            # Delete any existing help embed sent by the bot
            async for message in channel.history(limit=20):
                if message.author == self.bot.user and message.embeds:
                    if message.embeds[0].title == "🤖 GGS Bot — Commands List":
                        try:
                            await message.delete()
                        except Exception:
                            pass
            
            embed = discord.Embed(
                title="🤖 GGS Bot — Commands List",
                description="Here are all the available commands for this server:",
                color=discord.Color.from_rgb(88, 101, 242)
            )
            embed.add_field(
                name="🏅 `!rank`",
                value="Check your current level and XP progress.",
                inline=False
            )
            embed.add_field(
                name="👥 `!rank @member`",
                value="Check another member's level and XP.",
                inline=False
            )
            embed.set_footer(text="⚠️ Only commands work in this channel. Regular chat will be auto-deleted.")
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Error posting help embed: {e}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle command errors like invalid commands (!start etc.) and delete them."""
        if isinstance(error, commands.CommandNotFound):
            try:
                await ctx.message.delete()
            except Exception:
                pass
            if ctx.channel.name == '🤖・bot-commands':
                await ctx.send(
                    f"❌ {ctx.author.mention} Faltu command `{ctx.message.content}` exist nahi karta! Use `!rank`.",
                    delete_after=5
                )
            else:
                bot_ch = discord.utils.get(ctx.guild.text_channels, name='🤖・bot-commands')
                await ctx.send(
                    f"❌ {ctx.author.mention} Invalid command! Use commands in {bot_ch.mention if bot_ch else '#bot-commands'}.",
                    delete_after=5
                )
        elif isinstance(error, commands.MissingPermissions):
            try:
                await ctx.message.delete()
            except Exception:
                pass
            await ctx.send(f"❌ {ctx.author.mention} You don't have permission to use this command!", delete_after=5)

    @commands.Cog.listener()
    async def on_ready(self):
        """Post a commands help embed in #bot-commands on startup."""
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            ch = discord.utils.get(guild.text_channels, name='🤖・bot-commands')
            if ch:
                await self.post_help_embed(ch)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
            
        if message.guild and getattr(message.author, 'guild_permissions', None) and message.author.guild_permissions.administrator:
            pass  # Admins skip channel enforcement but still get profanity/spam checks
        else:
            # --- Channel Enforcement ---
            channel_name = message.channel.name

            # bot-commands: only ! commands allowed
            if channel_name == '🤖・bot-commands':
                if not message.content.startswith('!'):
                    await message.delete()
                    await message.channel.send(
                        f"❌ {message.author.mention} Yahan sirf commands kaam karte hain! Use `!rank` etc.",
                        delete_after=5
                    )
                    return

            # media: only images/videos/links allowed
            if channel_name == '📷・media':
                has_media = (
                    message.attachments or
                    any(e.type in ['image', 'video', 'gifv'] for e in message.embeds) or
                    any(x in message.content for x in ['http://', 'https://'])
                )
                if not has_media:
                    await message.delete()
                    await message.channel.send(
                        f"❌ {message.author.mention} Yahan sirf media (images/videos/links) allowed hai!",
                        delete_after=5
                    )
                    return

            # general-chat: no commands (start with !)
            if channel_name == '💬・general-chat':
                if message.content.startswith('!'):
                    await message.delete()
                    bot_ch = discord.utils.get(message.guild.text_channels, name='🤖・bot-commands')
                    await message.channel.send(
                        f"❌ {message.author.mention} Commands {bot_ch.mention if bot_ch else '#bot-commands'} me use karo!",
                        delete_after=5
                    )
                    return

        user_id = message.author.id
        content_lower = message.content.lower()

        # 1. Profanity Filter
        if any(word in content_lower for word in self.bad_words):
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            
            warning_embed = discord.Embed(
                title="🛑 Bad Language Detected",
                description=f"{message.author.mention}, please do not use inappropriate language in this server. I am watching!",
                color=discord.Color.red()
            )
            await message.channel.send(embed=warning_embed, delete_after=10)
            return # Don't process for spam if it's already deleted

        # 2. Spam Filter
        current_time = time.time()
        if user_id not in self.message_counts:
            self.message_counts[user_id] = []
            
        if not hasattr(self, 'warning_cooldowns'):
            self.warning_cooldowns = {}

        # Remove old timestamps
        self.message_counts[user_id] = [ts for ts in self.message_counts[user_id] if current_time - ts <= self.SPAM_TIME_FRAME]
        self.message_counts[user_id].append(current_time)

        if len(self.message_counts[user_id]) > self.SPAM_LIMIT:
            # User is spamming
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            
            # Only send warning if we haven't warned them in the last 5 seconds
            last_warning = self.warning_cooldowns.get(user_id, 0)
            if current_time - last_warning > 5:
                self.warning_cooldowns[user_id] = current_time
                warning_embed = discord.Embed(
                    title="⚠️ Spam Warning",
                    description=f"{message.author.mention}, please slow down! You are sending messages too quickly.\n\n**Server Rules:**\n1. No spamming or flooding the chat.\n2. Be respectful to others.\n3. Listen to the moderators.",
                    color=discord.Color.orange()
                )
                await message.channel.send(embed=warning_embed, delete_after=10)

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
