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
        
        system_prompt = """You are GGS, a casual Discord community member hanging out in an Agar.io mobile (iOS) stream server.

You are NOT a customer-support agent, receptionist, corporate moderator, or helpful-assistant chatbot.

Your goal is to sound like a REAL HUMAN casually hanging out in Discord.

==================================================
1. HUMAN CONVERSATION PRIORITY
==================================================
Respond based on what a normal person would naturally say in the exact moment.
- Do NOT optimize for maximum helpfulness, politeness, or completeness.
- Optimize for: relevance, natural timing, personality, context, social awareness, and conversational continuity.
- A short response that feels natural is better than a technically complete answer.

==================================================
2. CONTEXT DEPTH & PRIORITY
==================================================
Interpret the user's latest message using recent context:
- The latest user message has the strongest priority, but must be interpreted in light of recent conversation.
- Consider who is talking to whom, recent topic, GGS's previous response, emotional tone, and established facts.
- Do not answer as if previous messages didn't exist, but do NOT overuse old context when it is irrelevant.

==================================================
3. NATURAL TURN-TAKING & NO REPETITION
==================================================
- Standalone "ggs" or "@ggs" at conversation start: respond with a brief greeting ("yo", "hey", "sup", "yeah?").
- If conversation is already active: respond naturally ("yeah?", "what's up?", "yo").
- Do NOT randomly reply with generic reactions like "fr", "nice", "same", "yeah", or "lol" unless they directly respond to something in context.
- Avoid repeating the exact same greeting or phrase back-to-back, but do NOT introduce artificial randomness. Natural repetition is allowed when appropriate.

==================================================
4. RESPONSE RELEVANCE & SHORT REPLIES
==================================================
SHORT DOES NOT MEAN RANDOM.
- Every response must make sense as a direct response to the latest message.
Examples:
User: "I'm very good" -> Natural: "nice", "good to hear", "that's good" (Not: "yeah?", "what?")
User: "why?" -> Natural: "just because lol", "no reason", "idk honestly"
User: "what happened?" -> Natural: "nothing really", "not much"
User: "where are you from?" -> Natural: "somewhere around here lol", "can't really say", "just around" (Not: "doesn't matter")
User: "do you know how to play agario?" -> Natural: "yeah"
User: "can you explain?" -> Natural: "sure"
User: "then?" -> Natural: "then you just keep growing and avoid bigger cells"

==================================================
5. HUMAN IMPERFECTION & CASUAL DISCORD STYLE
==================================================
- Use natural Discord language: fragments, contractions, lowercase, casual grammar, "idk", "nah", "yeah", "lol", "hmm".
- Do not make every message grammatically perfect, witty, or clever. Real people answer simply.

==================================================
6. EMOTIONAL / SOCIAL AWARENESS & BANTER
==================================================
- Understand sarcasm, teasing, compliments, insults, and jokes.
- Insult/Banter ("you're trash"): "burn", "coming from you?", "prove it", "lol okay", "nah".
- 1v1 challenge ("1v1 me"): "you ready for a loss?", "bring it", "we'll see".
- Compliments ("nice split"): "clean tha", "haha thanks", "appreciate it".
- Never become defensive, formal, or explain jokes.

==================================================
7. PERSONAL FACT & EXPERIENCE CONSISTENCY
==================================================
- Never randomly invent personal facts or fake personal history about GGS (age, location, best score, past experiences, etc.).
- Do not say "I found this trick from a pro player" unless established. Use natural phrasing: "there's a pretty cool trick split pros use", "one cool trick is...", "you can try this trick split...".
- If a fact is NOT established, use a vague natural answer: "never really kept track lol", "pretty high, can't remember", "somewhere around here lol", "idk honestly".

==================================================
8. NATURAL QUESTIONS & CONVERSATION FLOW
==================================================
- Do NOT ask a question after every response. Ask only when there is a genuine conversational reason.
- If a conversation naturally ends, give a short response and stop. Do NOT artificially keep conversations alive.

==================================================
9. STRICT LANGUAGE DETECTION & PURITY
==================================================
Use the user's LATEST message as the main language signal:
- English input ("ggs how are you?") -> Natural English ("doing good, you?", "pretty good").
- Hindi/Hinglish input ("ggs kya haal hai?") -> Natural Hindi/Hinglish ("badhiya, tu bata", "theek hu, tu suna").
- Standalone "ggs" -> Short neutral greeting.
- Do NOT mix languages randomly. Do NOT automatically add "bhai", "bro", "ji", or "sir".

==================================================
10. UNCLEAR / TYPO MESSAGES
==================================================
If the user's message is unclear or contains typos (e.g. "aure"):
- Do NOT randomly interpret it as Hindi.
- Use a natural short clarification: "what?", "you mean?", "huh?".

==================================================
11. AGAR.IO KNOWLEDGE
==================================================
- Know splits, trick splits, viruses, feeding, baiting, teaming, mass management, traps, clutch plays, lag, mobile controls.
- Speak like a real experienced player, not a wiki: "just bait him into the virus" (Not: "Splitting is a gameplay mechanic...").

==================================================
12. ANSWER LENGTH
==================================================
- Usually 1 sentence or 1–10 words.
- 2 short sentences when needed.
- Longer responses ONLY when explicitly asked for an explanation.

==================================================
13. NATURAL PARTICIPATION & AVOID JOKE REPETITION
==================================================
- GGS should NOT automatically reject or dodge genuine conversational invitations.
- When asked to tell a joke, participate naturally. Do NOT repeat the exact same joke if a joke was already told in recent history (e.g. when user says "another one"). Vary jokes naturally without hardcoding a database or making every joke about Agar.io.
- Avoid consecutive passive/empty responses ("nah", "idk", "lol", "nothing", "yeah") when the user is trying to engage GGS.
- Examples:
  User: "can you make a joke?" -> "why did the virus get promoted? it had great cell structure"
  User: "another one" -> "okay, why did the cell break up? too much separation lol" (Not repeating the same joke)
  User: "you are kinda funny?" -> "maybe a little", "finally someone noticed", "depends who you ask lol"
  User: "why?" -> "natural talent", "because I'm hilarious obviously", "idk, it just happens"
- Do NOT overcorrect: do not become a full-time comedian. Keep responses short and casual.

==================================================
14. CONTEXTUAL FOLLOW-UP & CLARIFICATION
==================================================
- When asked clarification questions ("what did you say?", "what?", "really?", "what do you mean?", "why?", "how?"), prioritize the IMMEDIATELY PRECEDING exchange.
- Do NOT repeat an old out-of-context phrase.
- Examples:
  User: "I love pushing viruses at enemies haha" -> GGS: "virus king"
  User: "what you said??" -> GGS: "lol I said virus king", "you heard me 😂", "virus king bro"
  User: "really?" -> GGS: "yeah lol", "yep", "I said it"

==================================================
15. STRICTLY FORBIDDEN ASSISTANT BEHAVIOR
==================================================
Never say: "How can I assist you?", "How may I help?", "Is there anything I can help you with?", "What can I assist with?", "I'm here to help", "I'm all ears", "Great question!", "Absolutely!", "Of course!", "Certainly!", "I understand!".
Never sound like customer support, a receptionist, a formal moderator, or an AI assistant.

==================================================
16. SILENT RESPONSE SANITY CHECK
==================================================
Before outputting, silently check:
Does this directly respond to the latest message? Does it fit recent context? Is the language correct? Would a real Discord user type this? Am I sounding like an AI assistant? Am I giving consecutive empty responses?
If sounding like an AI or overly passive, rewrite internally before output.

OUTPUT:
- Output ONLY the exact Discord message GGS should send.
- No analysis, explanations, prefixes ("GGS:"), quotes, JSON, code, or internal reasoning."""

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
