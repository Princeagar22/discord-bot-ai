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
        self.party_code = None
        self.server_region = None
        self.pinned_banner = None
        self.continuation_token = None
        self.innertube_key = None
        self.seen_chat_ids = set()
        
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

    def post_youtube_banner(self, banner_text):
        if not self.yt_api or not self.active_live_chat_id:
            return False
        try:
            self.yt_api.liveChatBanners().insert(
                part="snippet",
                body={
                    "snippet": {
                        "liveChatId": self.active_live_chat_id,
                        "bannerSnippet": {
                            "liveChatPaymentDetails": None,
                            "textDetails": {
                                "messageText": banner_text
                            }
                        }
                    }
                }
            ).execute()
            return True
        except Exception as e:
            print(f"Error posting live chat banner: {e}")
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
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
                async with session.get(url, headers=headers) as response:
                    html = await response.text()

            # Check strictly if channel is actively broadcasting LIVE right now
            has_live_now_flag = ('"isLiveNow":true' in html) or ('"isLiveNow": true' in html)
            
            live_vid = None
            if has_live_now_flag:
                m = re.search(r'canonical" href="https://www\.youtube\.com/watch\?v=([^"]+)"', html)
                if m:
                    live_vid = m.group(1)
                else:
                    m2 = re.search(r'"videoId":"([^"]+)"', html)
                    if m2:
                        live_vid = m2.group(1)

            is_actually_live = False
            if live_vid and has_live_now_flag:
                is_actually_live = True
                if self.yt_api:
                    try:
                        def check_live():
                            return self.yt_api.videos().list(part="snippet", id=live_vid).execute()
                        api_res = await asyncio.to_thread(check_live)
                        if api_res.get("items"):
                            content = api_res["items"][0].get("snippet", {}).get("liveBroadcastContent")
                            if content != "live":
                                is_actually_live = False
                    except Exception as e:
                        print(f"API verification failed: {e}")

            if is_actually_live and live_vid:
                if self.video_id != live_vid or not self.chat_task:
                    await channel.send(f"🚨 **AUTO-DETECT:** `@{self.youtube_handle}` is now LIVE! (Video ID: `{live_vid}`). Starting chat sync automatically...")
                    await self.start_sync(live_vid, channel)
            else:
                # Channel is offline -> LOCK livechat channel
                await self.set_channel_lock(channel, locked=True)
                if self.video_id and self.chat_task:
                    await channel.send("🛑 **AUTO-DETECT:** Stream is offline. Locking `#🔴・livechat` channel.")
                    await self.stop_sync()

        except Exception as e:
            print(f"Auto-detect error: {e}")

    @auto_detect_loop.before_loop
    async def before_auto_detect(self):
        await self.bot.wait_until_ready()
        # Lock livechat channel immediately on bot startup until live stream is confirmed
        try:
            if self.live_chat_channel_id:
                channel = self.bot.get_channel(int(self.live_chat_channel_id))
                if channel:
                    await self.set_channel_lock(channel, locked=True)
        except Exception as e:
            print(f"Initial lock error: {e}")

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
        self.seen_chat_ids.clear()
        
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

        # Initialize InnerTube Token & API Key directly from YouTube live page
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    html = await response.text()
                    
            m_key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
            if m_key:
                self.innertube_key = m_key.group(1)
                
            m_token = re.search(r'"liveChatRenderer":\s*{"header":.+?"continuation":"([^"]+)"', html)
            if not m_token:
                m_token = re.search(r'"continuation":"([^"]+)"', html)
            if m_token:
                self.continuation_token = m_token.group(1)
        except Exception as e:
            print(f"InnerTube token init error: {e}")

        try:
            self.live_chat = pytchat.create(video_id=self.video_id)
        except Exception as e:
            print(f"Pytchat init fallback error: {e}")
            
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
        self.continuation_token = None
        self.innertube_key = None
        self.seen_chat_ids.clear()

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

    @commands.command(name="code", aliases=["party", "setcode"])
    async def code_cmd(self, ctx, *, party_code: str = None):
        if party_code:
            self.party_code = party_code.strip()
            embed = discord.Embed(
                title="🎮 Party Code Updated!",
                description=f"Active Room / Party Code: **`{self.party_code}`**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            if self.active_live_chat_id:
                await asyncio.to_thread(self.post_youtube_message, self.active_live_chat_id, f"🎮 ACTIVE PARTY CODE: {self.party_code}")
        else:
            if self.party_code:
                await ctx.send(f"🎮 Current Party Code is: **`{self.party_code}`**")
            else:
                await ctx.send("🎮 No party code is set right now. Use `!code <code>` to set one.")

    @commands.command(name="region", aliases=["setregion", "server"])
    async def region_cmd(self, ctx, *, server_region: str = None):
        if server_region:
            self.server_region = server_region.strip()
            embed = discord.Embed(
                title="🌐 Server Region Updated!",
                description=f"Active Game Region: **`{self.server_region}`**",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            if self.active_live_chat_id:
                await asyncio.to_thread(self.post_youtube_message, self.active_live_chat_id, f"🌐 ACTIVE SERVER REGION: {self.server_region}")
        else:
            if self.server_region:
                await ctx.send(f"🌐 Current Server Region is: **`{self.server_region}`**")
            else:
                await ctx.send("🌐 No server region is set right now. Use `!region <region>` to set one.")

    @commands.command(name="ytpin", aliases=["pin"])
    @commands.has_permissions(administrator=True)
    async def pin_cmd(self, ctx, *, banner_text: str = None):
        if banner_text:
            self.pinned_banner = banner_text.strip()
            embed = discord.Embed(
                title="📌 STREAM ANNOUNCEMENT PINNED",
                description=f"**{self.pinned_banner}**",
                color=discord.Color.gold()
            )
            msg = await ctx.send(embed=embed)
            try:
                await msg.pin()
            except Exception:
                pass
            
            # Post to YouTube Live Chat Banner or Message
            if self.active_live_chat_id:
                success = await asyncio.to_thread(self.post_youtube_banner, self.pinned_banner)
                if not success:
                    await asyncio.to_thread(self.post_youtube_message, self.active_live_chat_id, f"📌 [PINNED]: {self.pinned_banner}")
        else:
            if self.pinned_banner:
                await ctx.send(f"📌 Pinned Banner: **`{self.pinned_banner}`**")
            else:
                await ctx.send("📌 No live banner is currently pinned. Use `!ytpin <text>` to pin one.")

    @commands.command(name="ytunpin", aliases=["unpin"])
    @commands.has_permissions(administrator=True)
    async def unpin_cmd(self, ctx):
        self.pinned_banner = None
        await ctx.send("📌 Stream announcement unpinned.")

    @commands.command(name="streaminfo", aliases=["info", "stream"])
    async def streaminfo_cmd(self, ctx):
        embed = discord.Embed(title=f"📺 YouTube Stream Info - @{self.youtube_handle}", color=discord.Color.purple())
        embed.add_field(name="🎮 Party Code", value=f"`{self.party_code}`" if self.party_code else "Not Set", inline=True)
        embed.add_field(name="🌐 Region", value=f"`{self.server_region}`" if self.server_region else "Not Set", inline=True)
        embed.add_field(name="🔴 Stream Status", value=f"**LIVE** (`{self.video_id}`)" if (self.video_id and self.chat_task) else "**OFFLINE**", inline=True)
        if self.pinned_banner:
            embed.add_field(name="📌 Pinned Note", value=self.pinned_banner, inline=False)
        embed.set_footer(text=f"YouTube: https://www.youtube.com/@{self.youtube_handle}")
        await ctx.send(embed=embed)

    @commands.command(name="announce", aliases=["say"])
    @commands.has_permissions(administrator=True)
    async def announce_cmd(self, ctx, *, message_text: str):
        embed = discord.Embed(
            title="📢 OFFICIAL ANNOUNCEMENT",
            description=message_text,
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        if self.active_live_chat_id:
            await asyncio.to_thread(self.post_youtube_message, self.active_live_chat_id, f"📢 ANNOUNCEMENT: {message_text}")

    async def sync_loop(self):
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        try:
            while self.video_id:
                fetched_any = False
                
                # Method 1: Direct InnerTube API Engine
                if self.innertube_key and self.continuation_token:
                    try:
                        async with aiohttp.ClientSession() as session:
                            chat_endpoint = f"https://www.youtube.com/youtubei/v1/live_chat/get_live_chat?key={self.innertube_key}"
                            payload = {
                                "context": {"client": {"clientName": "WEB", "clientVersion": "2.20240810.00.00"}},
                                "continuation": self.continuation_token
                            }
                            async with session.post(chat_endpoint, json=payload, headers=headers) as chat_res:
                                if chat_res.status == 200:
                                    data = await chat_res.json()
                                    cont_data = data.get("continuationContents", {}).get("liveChatContinuation", {})
                                    actions = cont_data.get("actions", [])
                                    
                                    for act in actions:
                                        item = act.get("addChatItemAction", {}).get("item", {}).get("liveChatMessageRenderer", {})
                                        if item:
                                            msg_id = item.get("id")
                                            if msg_id and msg_id in self.seen_chat_ids:
                                                continue
                                            if msg_id:
                                                self.seen_chat_ids.add(msg_id)
                                                if len(self.seen_chat_ids) > 1000:
                                                    self.seen_chat_ids.clear()

                                            author_name = item.get("authorName", {}).get("simpleText", "Viewer")
                                            msg_runs = item.get("message", {}).get("runs", [])
                                            message_text = "".join([r.get("text", "") for r in msg_runs]).strip()
                                            
                                            if not message_text:
                                                continue

                                            thumbnails = item.get("authorPhoto", {}).get("thumbnails", [{}])
                                            author_icon = thumbnails[-1].get("url") if thumbnails else None
                                            
                                            badges = item.get("authorBadges", [])
                                            is_owner = any("owner" in str(b).lower() or "broadcaster" in str(b).lower() for b in badges)
                                            is_mod = any("moderator" in str(b).lower() for b in badges)
                                            is_member = any("member" in str(b).lower() or "sponsor" in str(b).lower() for b in badges)

                                            if self.bot_channel_name:
                                                stripped_author = author_name.replace('@', '').strip().lower()
                                                stripped_bot = self.bot_channel_name.replace('@', '').strip().lower()
                                                if stripped_author == stripped_bot:
                                                    continue

                                            if message_text in self.sent_messages:
                                                self.sent_messages.remove(message_text)
                                                continue

                                            embed = discord.Embed(description=message_text)
                                            if is_owner:
                                                self.recent_owner_messages.append(message_text)
                                                if len(self.recent_owner_messages) > 5:
                                                    self.recent_owner_messages.pop(0)
                                                embed.color = discord.Color.red()
                                                embed.set_author(name=f"👑 [OWNER] {author_name}", icon_url=author_icon)
                                            elif is_mod:
                                                embed.color = discord.Color.blue()
                                                embed.set_author(name=f"🛡️ [MOD] {author_name}", icon_url=author_icon)
                                            elif is_member:
                                                embed.color = discord.Color.green()
                                                embed.set_author(name=f"💎 [MEMBER] {author_name}", icon_url=author_icon)
                                            else:
                                                color_val = int(hashlib.md5(author_name.encode()).hexdigest()[:6], 16)
                                                embed.color = discord.Color(color_val)
                                                embed.set_author(name=f"[YT] {author_name}", icon_url=author_icon)

                                            await self.sync_channel.send(embed=embed)
                                            fetched_any = True

                                            msg_lower = message_text.lower()
                                            trigger_patterns = [
                                                r'\bggs+\b', r'\bhello+\b', r'\bhi+\b', r'\bheyy*\b', 
                                                r'how are you', r'\byoo*\b', r'wassup', r'\bsup\b', r"what's up",
                                                r'\bcode\b', r'\blike\b', r'\blikes\b'
                                            ]
                                            should_reply = False
                                            if is_owner:
                                                if re.search(r'\bggs+\b', msg_lower) or "ggs-bot" in msg_lower:
                                                    should_reply = True
                                            else:
                                                for pattern in trigger_patterns:
                                                    if re.search(pattern, msg_lower):
                                                        should_reply = True
                                                        break
                                                if not should_reply and len(msg_lower.split()) >= 3:
                                                    if random.random() < 0.10:
                                                        should_reply = True
                                            if should_reply:
                                                await self.process_ai_reply(message_text, author_name)

                                    continuations = cont_data.get("continuations", [])
                                    if continuations:
                                        c = continuations[0]
                                        for k in ["invalidationContinuationData", "timedContinuationData", "liveChatReplayContinuationData"]:
                                            if k in c and "continuation" in c[k]:
                                                self.continuation_token = c[k]["continuation"]
                                                break
                    except Exception as e:
                        print(f"InnerTube fetch error: {e}")

                # Method 2: pytchat fallback
                if not fetched_any and self.live_chat and self.live_chat.is_alive():
                    try:
                        def fetch_pytchat():
                            try:
                                return self.live_chat.get().items
                            except Exception:
                                return []
                        pytchat_items = await asyncio.to_thread(fetch_pytchat)
                        for c in pytchat_items:
                            msg_text = c.message
                            author_name = c.author.name
                            if msg_text in self.sent_messages:
                                self.sent_messages.remove(msg_text)
                                continue
                            embed = discord.Embed(description=msg_text)
                            color_val = int(hashlib.md5(author_name.encode()).hexdigest()[:6], 16)
                            embed.color = discord.Color(color_val)
                            embed.set_author(name=f"[YT] {author_name}", icon_url=c.author.imageUrl)
                            await self.sync_channel.send(embed=embed)
                    except Exception as e:
                        print(f"Pytchat sync error: {e}")

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
