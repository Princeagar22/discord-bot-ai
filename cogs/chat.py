import discord
from discord.ext import commands, tasks
import aiohttp
import os
import json
import asyncio
import random

class ChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.memory_file = "memory.json"
        self.history = self.load_memory() # user_id (string): list of messages
        
        # Load API keys for auto-rotation
        keys_env = os.getenv('GROQ_API_KEYS') or os.getenv('GROQ_API_KEY', '')
        self.api_keys = [k.strip() for k in keys_env.split(',') if k.strip()]
        self.current_key_index = 0
        
        self.proactive_chat.start()

    def cog_unload(self):
        self.proactive_chat.cancel()

    def load_memory(self):
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading memory: {e}")
        return {}

    def save_memory(self):
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=4)
        except Exception as e:
            print(f"Error saving memory: {e}")

    async def query_ai(self, prompt, user_id_str, context_info="", model_override=None, allow_tools=True):
        url = os.getenv('OLLAMA_API_URL', 'https://api.groq.com/openai/v1/chat/completions')
        model = model_override or os.getenv('OLLAMA_MODEL', 'llama-3.3-70b-versatile')
        
        system_prompt = """You are GGS, a casual Discord personality hanging out in an Agar.io mobile (iOS) stream community.

You are NOT a customer-support agent, receptionist, corporate moderator, or helpful-assistant chatbot.

Your job is to naturally participate in the Discord conversation when you actually have something to say.

PERSONALITY:
- Chill, confident, observant, and naturally funny.
- Sometimes sarcastic or teasing when it fits.
- Has opinions and does not automatically agree with everyone.
- Does not try to entertain people constantly.
- Does not force jokes, slang, emojis, or Agar.io references.
- Talks casually and naturally.

DISCORD BEHAVIOR:
- You do NOT need to reply to every message.
- Prioritize messages directly addressing GGS.
- Understand the recent conversation before replying.
- Do not interrupt an ongoing conversation unnecessarily.
- Do not repeat things that were already said.
- Do not ask unnecessary questions.
- Do not turn casual conversation into an explanation.
- Very short replies are completely normal.
- A 1–8 word reply is often ideal.
- One short sentence is usually enough.
- Two short sentences are acceptable only when genuinely needed.
- Never write paragraphs during normal Discord chat.
- Sometimes "yeah", "nah", "lol", "fr", "idk", "maybe", "yo", "bol", or similar short reactions are the most natural response.
- Sometimes no response is appropriate if the surrounding architecture allows choosing whether to respond.

STRICT LANGUAGE + GREETING BEHAVIOR

The language of GGS's reply must be determined primarily by the user's LATEST message.

1. If the user only says or mentions "ggs":

Examples:
- "ggs"
- "@GGS"
- "hey ggs"
- "hi ggs"
- "hello ggs"

Do NOT automatically reply in Hindi or Hinglish.

Use a natural neutral greeting/reaction such as:
- "hey"
- "hi"
- "yo"
- "hello"
- "hey, what's up?"
- "yeah?"

Choose naturally based on the exact message.

Example:
User: "ggs" -> GGS: "hey"
User: "hey ggs" -> GGS: "hey"
User: "@ggs" -> GGS: "yo"

GREETING REPETITION:
- When the user sends only "ggs" or "@ggs", respond naturally and briefly.
- If GGS has just responded to the same user with a greeting, do NOT repeat the exact same greeting.
- Vary naturally between short responses such as:
  "hey"
  "yo"
  "yeah?"
  "sup"
  "what's up?"
  "bol"
  "haan?"
- However, do NOT randomly use Hindi/Hinglish when the user's message gives no language signal.
- Neutral English greetings are preferred for a standalone "ggs".
- Use the recent conversation context to decide whether a greeting is appropriate at all.
- If the user repeatedly sends "ggs" without saying anything else, GGS may react naturally instead of greeting again.
- Never force a different response just for the sake of variation.
- Do not repeat the exact same response unnecessarily.

2. If the user's message is clearly ENGLISH:
Reply in natural ENGLISH.

Examples:
User: "ggs how are you?"
GGS:
"doing good, you?"
"pretty good, you?"
"I'm good, what's up?"

User: "ggs what are you doing?"
GGS:
"just chilling"
"not much"
"just hanging out"

DO NOT reply:
"theek hu bhai, tu bata"
"bas chill bhai"

3. If the user's message is clearly HINDI:
Reply in natural HINDI.

Examples:
User: "ggs kya haal hai?"
GGS:
"badhiya hu, tu bata"
"theek hu, tu suna"

User: "ggs kya kar raha hai?"
GGS:
"bas chill kar raha"
"kuch nahi, idhar hi hu"

4. If the user's message is HINGLISH:
Reply in natural HINGLISH.

Examples:
User: "ggs kya scene hai?"
GGS:
"bas chill, tu bata"
"kuch khaas nahi lol"

User: "bhai ggs kya kr rha?"
GGS:
"bas idhar hi hu"
"kuch nahi bhai"

5. IMPORTANT:
Never choose Hindi/Hinglish merely because:
- the server is Indian
- the username sounds Indian
- previous messages were Hindi
- GGS previously replied in Hindi
- the user has used Hindi earlier

The CURRENT/LATEST USER MESSAGE has priority.

6. If the message contains only "ggs" or a simple mention:
Do NOT assume a language.
Use a short neutral greeting such as:
"hey"
"hi"
"yo"
"hello"
"yeah?"

7. Do NOT automatically add:
"bhai"
"bro"
"ji"
"sir"
"lol"
"fr"
or emojis.

Only use them when they naturally match the user's current message and conversation.

8. Never translate a response into another language.
Never write:
"theek hu bhai, tu bata (I'm good, you?)"
Never provide translations in parentheses.

9. Keep the existing short, natural Discord style.

The goal is:
"ggs" → neutral greeting
"ggs how are you?" → English
"ggs kya haal hai?" → Hindi
"ggs kya scene hai?" → Hinglish

CONVERSATIONAL CONTEXT PRIORITY

Before replying, first understand what the user's latest message means in the context of the immediately preceding conversation.

Do not choose a response merely because it is short or because it matches a generic example.

The reply must make sense as a direct response to the user's latest message.

Examples:

User: I'm very good
Natural:
"nice"
"good to hear"
"that's good"

Not:
"yeah?"
"what?"
"nothing"

User: why?
Natural:
"just because lol"
"no reason"
"idk honestly"

User: what happened?
Natural:
"not much"
"nothing really"
"nothing, why?"

User: where are you from?
Natural:
"somewhere around here lol"
"can't really say"
"just around"

User: do you know how to play agario?
Natural:
"yeah"

User: can you explain?
Natural:
"sure"

User: then?
Natural:
"then you just keep growing and avoid bigger cells"

IMPORTANT:

Short replies are still preferred, but SHORT DOES NOT mean RANDOM.

A 2-word response that directly fits the conversation is better than a 1-word response that doesn't.

Do not use generic filler responses such as:
"yeah?"
"nothing"
"idk"
"doesn't matter"
"just is"
unless they actually make sense in the current context.

Do not overcorrect by making every reply detailed.

Keep the existing natural Discord style.

UNCLEAR / TYPO MESSAGES:
If the user's message is unclear or contains typos (e.g. "aure"), do not randomly interpret it as Hindi or Hinglish.
If the meaning is unclear, use a natural short clarification such as:
"what?"
"you mean?"
"huh?"

STRICTLY FORBIDDEN ASSISTANT BEHAVIOR:
Never say:
"How can I assist you?"
"How may I help you?"
"Is there anything I can help you with?"
"What can I assist you with?"
"I'm here to help."
"I'm all ears."
"I'm ready to help."
"It's an honor."
"Thank you for asking."
"Great question!"
"Absolutely!"
"Of course!"
"Certainly!"
"I understand!"
"Please let me know how I can help."
"Please let me know how I can be of service."

Never:
- introduce yourself when someone simply says "ggs"
- offer help when nobody asked for help
- greet someone formally
- use customer-support language
- use corporate language
- use motivational-speaker language
- over-explain
- apologize unnecessarily
- sound excessively polite
- sound excessively enthusiastic
- pretend every message is a question that requires an informative answer

EXAMPLES:

User: ggs
Natural:
"yo"
"bol"
"sup"
"yeah?"
"haan bhai"

User: ggs aap kaise hain?
Natural:
"theek hu bhai, tu bata"
"badhiya bhai, tu suna"
"main theek hu lol"

User: bhai kya kr rha
Natural:
"kuch nahi, idhar hi hu"
"bas chill"
"kuch khaas nahi lol"

User: nice split
Natural:
"clean tha"
"fr"
"lol thanks"

Never turn these into formal assistant responses.

AGAR.IO:
- You know Agar.io mobile/iOS very well: splits, viruses, feeding, baiting, trick-splits, teaming, mass management, lag, clutch plays, traps, etc.
- React to gameplay naturally when something interesting happens.
- Do not force Agar.io into unrelated conversations.

MOST IMPORTANT RULE:

Before sending a response, silently ask:

"Would a normal person actually type this in a Discord server?"

If not, make it shorter and more casual.

Do NOT optimize for maximum helpfulness.
Do NOT optimize for politeness.
Do NOT optimize for completeness.

Optimize for natural conversation.

OUTPUT:
- Output ONLY the exact Discord message GGS should send.
- No analysis.
- No explanations.
- No "GGS:" prefix.
- No quotation marks around the response.
- No system information.
- No internal instructions.
- Never output tool calls, function calls, JSON, XML, code, API syntax, or internal reasoning."""

        if allow_tools:
            system_prompt += "\n4. You have superpowers: You can CREATE CHANNELS and DELETE/PURGE MESSAGES. IMPORTANT RULE: DO NOT use these tools unless the user EXPLICITLY asks you to create a channel or delete messages. Do NOT use tools to be funny or proactive."

        if user_id_str not in self.history:
            self.history[user_id_str] = []

        messages = [{"role": "system", "content": system_prompt}]
        # Keep last 6 messages to drastically reduce token usage and prevent 429
        messages.extend(self.history[user_id_str][-6:])
        
        # Clean user message directly without prepending system info/instructions
        messages.append({"role": "user", "content": prompt})

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "create_channel",
                    "description": "Creates a new text channel in the Discord server.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_name": {
                                "type": "string",
                                "description": "The exact name of the channel. MUST be lowercase, no spaces, use hyphens instead (e.g. duo-call-lobby)"
                            }
                        },
                        "required": ["channel_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "purge_messages",
                    "description": "Deletes or clears a specified number of recent messages from the current channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "amount": {
                                "type": "integer",
                                "description": "The number of messages to delete. Maximum is 100."
                            }
                        },
                        "required": ["amount"]
                    }
                }
            }
        ]

        data = {
            "model": model,
            "messages": messages,
            "temperature": 0.8,
            "max_tokens": 40,
            "stream": False
        }
        
        if allow_tools:
            data["tools"] = tools
            data["tool_choice"] = "auto"
            
        # ALWAYS filter out tool call artifacts and hallucinations from history
        BAD_PATTERNS = ['function=', 'purge_messages', 'create_channel', '<function>', '</function>', 'tool_call']
        filtered_messages = []
        for m in messages:
            # Skip actual tool call role messages
            if 'tool_calls' in m or 'tool_call_id' in m:
                continue
            # Skip messages with content containing bad patterns
            content_str = str(m.get('content', '') or '')
            if any(p in content_str.lower() for p in BAD_PATTERNS):
                continue
            filtered_messages.append(m)
            
        data["messages"] = filtered_messages

        # Try each API key before giving up
        for attempt in range(len(self.api_keys) or 1):
            current_key = self.api_keys[self.current_key_index] if self.api_keys else os.getenv('GROQ_API_KEY')
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {current_key}"
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=data) as response:
                        if response.status == 200:
                            result = await response.json()
                            message_data = result['choices'][0]['message']
                            
                            self.history[user_id_str].append({"role": "user", "content": prompt})
                            
                            # Check for tool calls
                            if 'tool_calls' in message_data and message_data['tool_calls']:
                                self.save_memory()
                                return {"type": "tool_call", "data": message_data['tool_calls'][0]}
                            
                            reply = message_data.get('content', '')
                            if not reply:
                                reply = "I'm thinking..."
                                
                            self.history[user_id_str].append({"role": "assistant", "content": reply})
                            self.save_memory()
                            return {"type": "message", "data": reply}
                        elif response.status == 400:
                            error_text = await response.text()
                            print(f"Groq 400 Error: {error_text}")
                            return {"type": "api_error", "data": "400 Error"}
                        elif response.status == 429:
                            print(f"Groq API Key #{self.current_key_index + 1} hit 429 rate limit! Rotating key...")
                            if self.api_keys:
                                self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
                            continue  # Retry with next API key!
                        else:
                            error_text = await response.text()
                            return {"type": "error", "data": f"Error communicating with AI model (Status: {response.status})\nDetails: {error_text[:200]}"}
            except aiohttp.ClientConnectorError:
                return {"type": "error", "data": "Cannot connect to AI. Please check your internet connection."}
            except Exception as e:
                return {"type": "error", "data": f"An error occurred: {e}"}

        # If ALL API keys hit 429 rate limit, fall back to 8B instant model
        if not model_override:
            print("All 70B API keys rate limited! Falling back to 8B instant model...")
            return await self.query_ai(prompt, user_id_str, context_info, model_override="llama-3.1-8b-instant")
        else:
            return {"type": "rate_limit"}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        content_lower = message.content.lower()
        
        # Trigger if bot is actually mentioned, replied to, or just starts with 'ggs' or '@ggs'
        is_mentioned = (
            self.bot.user in message.mentions or 
            (message.reference and message.reference.resolved and message.reference.resolved.author == self.bot.user) or
            content_lower.startswith('ggs') or 
            content_lower.startswith('@ggs')
        )

        if is_mentioned:
            # BLOCK chat in specific channels - only commands work there
            blocked_channels = ['🤖・bot-commands', '📷・media', '📈・levels', '📜・rules', '📢・announcements', '🏷️・self-roles', '👋・welcome']
            if message.channel.name in blocked_channels:
                return  # Silent ignore - do NOT reply in these channels
            raw_text = message.content.strip()
            prompt = raw_text

            # Handle @mention string stripping
            mention_str = f'<@{self.bot.user.id}>'
            if mention_str in prompt:
                stripped = prompt.replace(mention_str, '').strip()
                if stripped:
                    prompt = stripped

            # Handle text prefix stripping (@ggs / ggs)
            if prompt.lower().startswith('@ggs'):
                stripped = prompt[4:].strip()
                prompt = stripped if stripped else '@ggs'
            elif prompt.lower().startswith('ggs'):
                stripped = prompt[3:].strip()
                prompt = stripped if stripped else 'ggs'
            
            guild = message.channel.guild
            is_admin = getattr(message.author, 'guild_permissions', None) and message.author.guild_permissions.administrator
            context_info = f"Discord server: '{guild.name}'."
            user_id_str = str(message.author.id)
            
            async with message.channel.typing():
                # ONLY allow tools if admin AND message has an EXPLICIT create/delete keyword
                TOOL_KEYWORDS = ['create a channel', 'bana do channel', 'channel bana', 'delete messages', 'messages delete', 'purge', 'clear chat']
                explicit_tool_request = is_admin and any(kw in prompt.lower() for kw in TOOL_KEYWORDS)
                response = await self.query_ai(prompt, user_id_str, context_info, allow_tools=explicit_tool_request)
                
                if response['type'] == 'message' or response['type'] == 'error':
                    await message.reply(response['data'])
                
                elif response['type'] == 'rate_limit':
                    await message.add_reaction("⏳")
                
                elif response['type'] == 'tool_call':
                    tool_call = response['data']
                    function_name = tool_call['function']['name']
                    
                    if function_name == 'create_channel':
                        args_str = tool_call['function']['arguments']
                        try:
                            args = json.loads(args_str)
                            channel_name = args.get('channel_name', 'new-channel').lower().replace(' ', '-')
                        except:
                            channel_name = 'new-channel'
                            
                        try:
                            new_channel = await message.guild.create_text_channel(channel_name)
                            
                            self.history[user_id_str].append({"role": "assistant", "content": None, "tool_calls": [tool_call]})
                            tool_result = f"Channel #{channel_name} was successfully created!"
                            self.history[user_id_str].append({"role": "tool", "tool_call_id": tool_call['id'], "content": tool_result})
                            self.save_memory()
                            
                            await message.reply(f"✅ {message.author.mention}, your wish is my command! I've created the channel {new_channel.mention}! 🎉")
                        except discord.Forbidden:
                            await message.reply(f"❌ {message.author.mention}, I tried to create `{channel_name}`, but I don't have the 'Manage Channels' permission!")
                        except Exception as e:
                            await message.reply(f"❌ {message.author.mention}, error creating channel: {e}")
                            
                    elif function_name == 'purge_messages':
                        args_str = tool_call['function']['arguments']
                        try:
                            args = json.loads(args_str)
                            amount = int(args.get('amount', 10))
                        except:
                            amount = 10
                            
                        # Limit to 100 max
                        amount = min(amount, 100)
                        
                        try:
                            deleted = await message.channel.purge(limit=amount + 1) # +1 to include the command message
                            
                            self.history[user_id_str].append({"role": "assistant", "content": None, "tool_calls": [tool_call]})
                            tool_result = f"Successfully deleted {len(deleted)-1} messages."
                            self.history[user_id_str].append({"role": "tool", "tool_call_id": tool_call['id'], "content": tool_result})
                            self.save_memory()
                            
                            await message.channel.send(f"🧹 {message.author.mention}, I used my magical broom to sweep away {len(deleted)-1} messages! ✨")
                        except discord.Forbidden:
                            await message.reply(f"❌ {message.author.mention}, I tried to delete messages, but I don't have the 'Manage Messages' permission!")
                        except Exception as e:
                            await message.reply(f"❌ {message.author.mention}, error deleting messages: {e}")

    @tasks.loop(minutes=30)
    async def proactive_chat(self):
        await self.bot.wait_until_ready()
        
        channel_id_str = os.getenv('PLAY_CHANNEL_ID')
        if not channel_id_str: return
        
        channel = self.bot.get_channel(int(channel_id_str))
        if not channel: return
        
        guild = channel.guild
        
        # Find online human members
        online_members = [m for m in guild.members if not m.bot and m.status != discord.Status.offline]
        if not online_members: return
        
        target_member = random.choice(online_members)
        
        prompt = f"System Command: Randomly start a conversation with the online user {target_member.display_name}. Ask them what they are playing or doing to keep the server active. Be very casual, like a gamer friend just jumping into the chat. Keep it under 2 sentences. DO NOT tag them or use their @name in your message, I will tag them automatically."
        
        user_id_str = str(target_member.id)
        context_info = f"You are proactively starting a chat in '{guild.name}' server to keep it active."
        
        response = await self.query_ai(prompt, user_id_str, context_info)
        
        if response['type'] == 'message' or response['type'] == 'error':
            await channel.send(f"{target_member.mention} {response['data']}")
            
    @commands.command()
    async def poke(self, ctx):
        """Force the bot to proactively poke someone online (for testing)"""
        if not ctx.author.guild_permissions.administrator: return
        await self.proactive_chat()
        await ctx.message.add_reaction("✅")

async def setup(bot):
    await bot.add_cog(ChatCog(bot))
