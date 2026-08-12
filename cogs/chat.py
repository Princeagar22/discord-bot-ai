import discord
from discord.ext import commands
import aiohttp
import os
import json

class ChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.history = {} # user_id: list of messages

    async def query_ollama(self, prompt, user_id, context_info=""):
        url = os.getenv('OLLAMA_API_URL', 'http://localhost:11434/api/chat')
        model = os.getenv('OLLAMA_MODEL', 'llama3')
        
        system_prompt = """You are a highly advanced Discord bot chatting with users in a server.
Your behavior must adapt dynamically to the user's tone.
- If the user is serious, reply seriously and helpfully.
- If the user is funny, joking, or informal, reply with humor, use emojis, laugh, and be fully advanced and fun.
Keep your responses concise enough for Discord (under 2000 characters)."""

        if user_id not in self.history:
            self.history[user_id] = []

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.history[user_id][-5:]) # Keep last 5 messages for context
        
        # Inject context directly into the latest user prompt for smaller models to understand better
        enriched_prompt = f"[System Info: {context_info}]\nUser says: {prompt}" if context_info else prompt
        messages.append({"role": "user", "content": enriched_prompt})

        data = {
            "model": model,
            "messages": messages,
            "stream": False
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        reply = result['message']['content']
                        
                        self.history[user_id].append({"role": "user", "content": prompt})
                        self.history[user_id].append({"role": "assistant", "content": reply})
                        return reply
                    else:
                        return f"Error communicating with local AI model (Status: {response.status})"
        except aiohttp.ClientConnectorError:
            return "Cannot connect to local AI. Is Ollama running on localhost?"
        except Exception as e:
            return f"An error occurred: {e}"

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Check if bot is mentioned or replied to
        if self.bot.user in message.mentions or (message.reference and message.reference.resolved and message.reference.resolved.author == self.bot.user):
            # Remove the mention from the prompt text
            prompt = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
            
            # Generate context info about the server
            guild = message.channel.guild
            context_info = f"You are in the '{guild.name}' Discord server. The server has {guild.member_count} members. The user you are currently talking to is '{message.author.display_name}'. The current channel is '{message.channel.name}'."
            
            async with message.channel.typing():
                reply = await self.query_ollama(prompt, message.author.id, context_info)
                await message.reply(f"{message.author.mention} {reply}")

async def setup(bot):
    await bot.add_cog(ChatCog(bot))
