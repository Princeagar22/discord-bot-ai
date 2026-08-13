import discord
from discord.ext import commands, tasks
import pytchat
import asyncio
import aiohttp
import re
import os
import json
import hashlib
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

class YouTubeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.live_chat = None
        self.sync_channel = None
        self.video_id = None
        self.chat_task = None
        self.youtube_handle = os.getenv('YOUTUBE_HANDLE')
        self.live_chat_channel_id = os.getenv('LIVE_CHAT_CHANNEL_ID')
        self.active_live_chat_id = None
        self.yt_api = None
        self.sent_messages = set()
        self.bot_channel_name = None
        self.bot_channel_id = None
        
        self.stream_stats = {"viewers": "Unknown", "likes": "Unknown"}
        self.recent_owner_messages = []
        
        self.setup_youtube_api()
        
        self.fetch_stream_stats_loop.start()
        
        if self.youtube_handle and self.live_chat_channel_id:
            self.auto_detect_loop.start()

    def setup_youtube_api(self):
        try:
            creds = None
            if os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/youtube.force-ssl'])
            elif os.getenv('YOUTUBE_TOKEN_JSON'):
                token_data = json.loads(os.getenv('YOUTUBE_TOKEN_JSON'))
                creds = Credentials.from_authorized_user_info(token_data, ['https://www.googleapis.com/auth/youtube.force-ssl'])
            
            if creds:
                if creds.expired and creds.refresh_token:
                    from google.auth.transport.requests import Request
                    creds.refresh(Request())
                    with open('token.json', 'w') as token:
                        token.write(creds.to_json())
                        
                self.yt_api = build('youtube', 'v3', credentials=creds)
                print("YouTube API successfully authorized!")
                
                # Fetch bot's own channel ID and name to prevent echo loops
                channel_response = self.yt_api.channels().list(mine=True, part="id,snippet").execute()
                if channel_response.get("items"):
                    self.bot_channel_id = channel_response["items"][0]["id"]
                    self.bot_channel_name = channel_response["items"][0]["snippet"]["title"]
                    print(f"Bot authenticated as: {self.bot_channel_name} (ID: {self.bot_channel_id})")
            else:
                print("Warning: No YouTube token found. The bot will not be able to reply on YouTube.")
        except Exception as e:
            print(f"Error setting up YouTube API: {e}")

    @tasks.loop(seconds=60)
    async def fetch_stream_stats_loop(self):
        if not self.video_id or not self.yt_api:
            return
        try:
            def fetch():
                return self.yt_api.videos().list(
                    part="statistics,liveStreamingDetails",
                    id=self.video_id
                ).execute()
            
            response = await asyncio.to_thread(fetch)
            items = response.get("items", [])
            if items:
                stats = items[0].get("statistics", {})
                live_details = items[0].get("liveStreamingDetails", {})
                self.stream_stats["likes"] = stats.get("likeCount", "Unknown")
                self.stream_stats["viewers"] = live_details.get("concurrentViewers", "Unknown")
        except Exception as e:
            print(f"Error fetching stream stats: {e}")

    def get_live_chat_id(self, video_id):
        if not self.yt_api:
            return None
        try:
            response = self.yt_api.videos().list(
                part="liveStreamingDetails",
                id=video_id
            ).execute()
            
            items = response.get("items", [])
            if items:
                details = items[0].get("liveStreamingDetails", {})
                return details.get("activeLiveChatId")
        except Exception as e:
            print(f"Error getting live chat ID: {e}")
        return None

    def post_youtube_message(self, chat_id, message_text):
        if not self.yt_api:
            return False
        try:
            self.yt_api.liveChatMessages().insert(
                part="snippet",
                body={
                    "snippet": {
                        "liveChatId": chat_id,
                        "type": "textMessageEvent",
                        "textMessageDetails": {
                            "messageText": message_text
                        }
                    }
                }
            ).execute()
            return True
        except Exception as e:
            print(f"Error posting to YouTube chat: {e}")
            return False

    def cog_unload(self):
        if self.auto_detect_loop.is_running():
            self.auto_detect_loop.cancel()
        if self.chat_task:
            self.chat_task.cancel()
        if self.live_chat:
            self.live_chat.terminate()

    @tasks.loop(minutes=2)
    async def auto_detect_loop(self):
        try:
            channel = self.bot.get_channel(int(self.live_chat_channel_id))
            if not channel:
                return

            async with aiohttp.ClientSession() as session:
                url = f"https://www.youtube.com/@{self.youtube_handle}/live"
                headers = {"User-Agent": "Mozilla/5.0"}
                async with session.get(url, headers=headers) as response:
                    html = await response.text()
                    
            m = re.search(r'canonical" href="https://www\.youtube\.com/watch\?v=([^"]+)"', html)
            live_vid = None
            if m:
                live_vid = m.group(1)
            else:
                if '"isLiveBroadcast":true' in html or 'isLiveNow' in html:
                    m2 = re.search(r'"videoId":"([^"]+)"', html)
                    if m2:
                        live_vid = m2.group(1)

            if live_vid:
                # Verify via API if it is TRULY live
                is_actually_live = False
                if self.yt_api:
                    try:
                        def check_live():
                            return self.yt_api.videos().list(part="snippet", id=live_vid).execute()
                        api_res = await asyncio.to_thread(check_live)
                        if api_res.get("items"):
                            content = api_res["items"][0].get("snippet", {}).get("liveBroadcastContent")
                            if content == "live":
                                is_actually_live = True
                    except Exception as e:
                        print(f"API verification failed: {e}")
                        is_actually_live = True # fallback
                else:
                    is_actually_live = True

                if is_actually_live:
                    if self.video_id != live_vid or not self.chat_task:
                        await channel.send(f"🚨 **AUTO-DETECT:** `@{self.youtube_handle}` is now LIVE! (Video ID: `{live_vid}`). Starting chat sync automatically...")
                        await self.start_sync(live_vid, channel)
                else:
                    # Not actually live, so stop if we were syncing this
                    if self.video_id and self.chat_task:
                        await channel.send("🛑 **AUTO-DETECT:** Stream has ended. Stopping chat sync automatically.")
                        await self.stop_sync()
            else:
                if self.video_id and self.chat_task:
                    await channel.send("🛑 **AUTO-DETECT:** Stream has ended. Stopping chat sync automatically.")
                    await self.stop_sync()

        except Exception as e:
            print(f"Auto-detect error: {e}")

    @auto_detect_loop.before_loop
    async def before_auto_detect(self):
        await self.bot.wait_until_ready()

    async def set_channel_lock(self, channel, locked: bool):
        if not channel:
            return
        try:
            # Deny SEND_MESSAGES for everyone if locked, otherwise reset to default (unlocked)
            await channel.set_permissions(channel.guild.default_role, send_messages=False if locked else None)
        except Exception as e:
            print(f"Failed to lock/unlock channel: {e}")

    async def start_sync(self, video_id, channel):
        await self.stop_sync()
        self.video_id = video_id
        self.sync_channel = channel
        
        # Clear the old chat before starting the new one
        try:
            await channel.purge(limit=1000)
        except Exception as e:
            print(f"Failed to clear chat: {e}")
            
        # Unlock the channel when we start syncing
        await self.set_channel_lock(channel, locked=False)
        
        # Get liveChatId using YouTube API
        self.active_live_chat_id = await asyncio.to_thread(self.get_live_chat_id, video_id)
        if self.active_live_chat_id:
            await channel.send("✅ Successfully connected to YouTube API! The AI can now reply directly on YouTube.")
        else:
            await channel.send("⚠️ Connected, but could not get YouTube API Chat ID. AI replies will only show on Discord.")

        try:
            self.live_chat = pytchat.create(video_id=self.video_id)
            if not self.live_chat.is_alive():
                await channel.send(f"⚠️ Could not connect to chat for video `{video_id}`.")
                return
        except Exception as e:
            await channel.send(f"⚠️ Error connecting to YouTube: {e}")
            return
            
        self.chat_task = self.bot.loop.create_task(self.sync_loop())
        await channel.send(f"🟢 YouTube live chat connected! Messages will appear here.")

    async def stop_sync(self):
        channel = self.sync_channel
        if not channel and self.live_chat_channel_id:
            channel = self.bot.get_channel(int(self.live_chat_channel_id))
            
        if channel:
            # Lock the channel when stream ends
            await self.set_channel_lock(channel, locked=True)
            # Clear chat so it's empty while offline
            try:
                await channel.purge(limit=1000)
                await channel.send("🛑 **Live stream has ended. The chat has been cleared and locked.**")
            except Exception as e:
                print(f"Failed to clear chat on stop: {e}")
            
        if self.chat_task:
            self.chat_task.cancel()
            self.chat_task = None
        if self.live_chat:
            self.live_chat.terminate()
            self.live_chat = None
        self.video_id = None
        self.active_live_chat_id = None

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def ytstart(self, ctx, video_id: str):
        if self.chat_task and not self.chat_task.done():
            await ctx.send("YouTube sync is already running! Stop it first with `!ytstop`.")
            return
        await ctx.send(f"🔴 Manual start: Syncing YouTube live chat for video `{video_id}` to this channel!")
        await self.start_sync(video_id, ctx.channel)
        
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def ytstop(self, ctx):
        await self.stop_sync()
        await ctx.send("🛑 YouTube live chat sync manually stopped.")

    async def sync_loop(self):
        try:
            while self.live_chat and self.live_chat.is_alive():
                chat_data = await asyncio.to_thread(self.live_chat.get)
                
                for c in chat_data.sync_items():
                    message_text = c.message
                    author_name = c.author.name
                    
                    # PERFECT FIX: Ignore ANY message sent by our own bot account using Channel ID!
                    if self.bot_channel_id and getattr(c.author, 'channelId', None) == self.bot_channel_id:
                        continue
                        
                    # Fallback name check (ignoring @ symbols)
                    if self.bot_channel_name:
                        stripped_author = author_name.replace('@', '').strip().lower()
                        stripped_bot = self.bot_channel_name.replace('@', '').strip().lower()
                        if stripped_author == stripped_bot:
                            continue
                    
                    # Prevent echoing messages that we just sent from Discord (fallback)
                    if message_text in self.sent_messages:
                        self.sent_messages.remove(message_text)
                        continue
                    
                    # Create a beautiful embed for the message
                    embed = discord.Embed(description=message_text)
                    
                    # Determine color and badge based on role
                    if c.author.isChatOwner:
                        self.recent_owner_messages.append(message_text)
                        if len(self.recent_owner_messages) > 5:
                            self.recent_owner_messages.pop(0)
                        embed.color = discord.Color.red()
                        embed.set_author(name=f"👑 [OWNER] {author_name}", icon_url=c.author.imageUrl)
                    elif c.author.isChatModerator:
                        embed.color = discord.Color.blue()
                        embed.set_author(name=f"🛡️ [MOD] {author_name}", icon_url=c.author.imageUrl)
                    elif c.author.isChatSponsor:
                        embed.color = discord.Color.green()
                        embed.set_author(name=f"💎 [MEMBER] {author_name}", icon_url=c.author.imageUrl)
                    else:
                        color_val = int(hashlib.md5(author_name.encode()).hexdigest()[:6], 16)
                        embed.color = discord.Color(color_val)
                        embed.set_author(name=f"[YT] {author_name}", icon_url=c.author.imageUrl)
                        
                    await self.sync_channel.send(embed=embed)
                    
                    msg_lower = message_text.lower()
                    
                    # Flexible trigger words (matches hello, hellooo, hey, heyyy, yo, yoo etc)
                    trigger_patterns = [
                        r'\bggs+\b', r'\bhello+\b', r'\bhi+\b', r'\bheyy*\b', 
                        r'how are you', r'\byoo*\b', r'wassup', r'\bsup\b', r"what's up",
                        r'\bcode\b', r'\blike\b', r'\blikes\b'
                    ]
                    
                    should_reply = False
                    
                    if c.author.isChatOwner:
                        # Owner only triggers if they explicitly say 'ggs' or tag the bot
                        if re.search(r'\bggs+\b', msg_lower) or "ggs-bot" in msg_lower:
                            should_reply = True
                    else:
                        for pattern in trigger_patterns:
                            if re.search(pattern, msg_lower):
                                should_reply = True
                                break
                                
                        # Random 10% chance to reply to ANY normal message (3+ words) from viewers to make it feel alive
                        import random
                        if not should_reply and len(msg_lower.split()) >= 3:
                            if random.random() < 0.10:
                                should_reply = True
                            
                    if should_reply:
                        await self.process_ai_reply(message_text, author_name)
                        
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"YouTube sync error: {e}")
            if self.sync_channel:
                await self.sync_channel.send("⚠️ YouTube sync crashed or stream ended unexpectedly.")
                self.video_id = None 

    async def process_ai_reply(self, message_text, author_name):
        chat_cog = self.bot.get_cog("ChatCog")
        if chat_cog:
            clean_author = author_name.replace('@', '').strip()
            prompt = message_text
            
            owner_context = "\n".join(self.recent_owner_messages[-3:]) if self.recent_owner_messages else "None"
            context_info = (
                f"Stream chat context: You're watching an Agar.io mobile stream. "
                f"The streamer is @ZipAgar. "
                f"Current viewers: {self.stream_stats.get('viewers', '?')}, likes: {self.stream_stats.get('likes', '?')}. "
                f"Recent things @ZipAgar said: {owner_context}. "
                f"You are a human mod/viewer. Keep your reply to 1-2 short sentences. "
                f"If they ask about codes or likes, only say what @ZipAgar actually mentioned - don't make up numbers or goals. "
                f"If he said nothing about codes, say something like 'haven't heard anything about a code yet'. "
                f"Sound like a real person. No bot vibes."
            )
            
            user_id_str = f"YT_{clean_author}"
            
            async with self.sync_channel.typing():
                response = await chat_cog.query_ai(prompt, user_id_str, context_info=context_info, allow_tools=False)
                
                if response['type'] == 'message':
                    # Add mention back so it's clear who the bot is talking to on YouTube
                    reply_text = f"@{clean_author} {response['data']}"
                    
                    # YouTube Live Chat completely rejects messages containing < or > (HTML/XML tags)
                    reply_text = reply_text.replace('<', '').replace('>', '')
                    
                    if len(reply_text) > 200:
                        reply_text = reply_text[:197] + "..."
                        
                    bot_embed = discord.Embed(description=reply_text, color=discord.Color.gold())
                    bot_embed.set_author(name=f"🤖 GGS Bot Replied to @{clean_author}", icon_url=self.bot.user.display_avatar.url if self.bot.user.display_avatar else None)
                    await self.sync_channel.send(embed=bot_embed)
                    
                    self.sent_messages.add(reply_text)
                    if self.active_live_chat_id:
                        success = await asyncio.to_thread(self.post_youtube_message, self.active_live_chat_id, reply_text)
                        if not success:
                            self.sent_messages.discard(reply_text)
                            await self.sync_channel.send(f"⚠️ Failed to send message to YouTube.")

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bots (including ourselves)
        if message.author.bot:
            return
            
        # Only process messages in the designated live chat channel
        if str(message.channel.id) != str(self.live_chat_channel_id):
            return
            
        # Only forward if we are actively syncing a live stream
        if not self.active_live_chat_id or not self.chat_task:
            return
            
        # Forward message to YouTube with an @ mention style
        reply_text = f"@{message.author.display_name}: {message.content}"
        
        if len(reply_text) > 200:
            reply_text = reply_text[:197] + "..."
            
        self.sent_messages.add(reply_text)
        success = await asyncio.to_thread(self.post_youtube_message, self.active_live_chat_id, reply_text)
        if success:
            await message.add_reaction("✅")
        else:
            self.sent_messages.discard(reply_text)
            await message.add_reaction("❌")

async def setup(bot):
    await bot.add_cog(YouTubeCog(bot))
