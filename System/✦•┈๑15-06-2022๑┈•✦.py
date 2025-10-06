import discord
from discord.ext import commands, tasks
import aiohttp
import json
import asyncio
import os

class SimpleAI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_channel_id = 1378101589520416809
        self.ollama_url = "http://localhost:11434/api/chat"  # Ollama API endpoint
        self.ollama_model = "llama3.2"  # Change to your preferred model (e.g., llama2, mistral, etc.)
        self.last_message_time = None
        self.load_data()
        self.delete_task.start()

    def load_data(self):
        if not os.path.exists("Data/ai_data.json"):
            self.data = {"embed_id": None, "current_personality": "kaffee"}
        else:
            with open("Data/ai_data.json", "r", encoding="utf-8") as file:
                self.data = json.load(file)

        self.current_personality = self.data.get("current_personality")
        if not self.current_personality:
            self.current_personality = "kaffee"
            self.data["current_personality"] = "kaffee"
            self.save_data()

        with open("Data/personalities.json", "r", encoding="utf-8") as file:
            self.personalities = json.load(file)

    def save_data(self):
        with open("Data/ai_data.json", "w", encoding="utf-8") as file:
            json.dump(self.data, file, indent=4)

    async def get_ai_response(self, prompt, user_id):
        try:
            personality_text = self.personalities.get(self.current_personality, self.personalities["kaffee"])
            user_id = str(user_id)
            conversation_history = self.data.get("conversations", {}).get(user_id, [])
            messages = [{"role": "system", "content": personality_text}]

            for msg in conversation_history:
                messages.append(msg)

            messages.append({"role": "user", "content": prompt})

            # Ollama API request
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.ollama_model,
                    "messages": messages,
                    "stream": False
                }
                async with session.post(self.ollama_url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["message"]["content"].strip()
                    else:
                        error_text = await response.text()
                        print(f"Ollama API Fehler {response.status}: {error_text}")
                        return "Es gab einen Fehler bei der Antwortgenerierung."
        except Exception as e:
            print(f"Fehler bei der Ollama-Anfrage: {e}")
            return "Es gab einen Fehler bei der Antwortgenerierung."

    def get_embeds(self):
        embed_de = discord.Embed(
            title="✦•┈๑12-03-2025๑┈•✦",
            description=(
                "🔹 **Erkunde verschiedene KI-Persönlichkeiten!**\n"
                "🔹 Drücke den ⬇️ **Button**, um die verfügbaren Persönlichkeiten anzuzeigen.\n"
                "🔹 Nutze </switch_personality:1348925341904801812> und gib den gewünschten Namen an, "
                "um eine neue Persönlichkeit auszuwählen! ✨\n\n"
                "⚡ **Tipp:** Teste verschiedene Persönlichkeiten und finde deinen Favoriten!"),
            color=0x2596be)
        embed_de.set_footer(text="Powered by gsv2.dev ⚡")

        embed_en = discord.Embed(
            title="✦•┈๑March 12, 2025๑┈•✦",
            description=(
                "🔹 **Explore different AI personalities!**\n"
                "🔹 Press the ⬇️ **button** to view available personalities.\n"
                "🔹 Use </switch_personality:1348925341904801812> and enter the desired name "
                "to select a new personality! ✨\n\n"
                "⚡ **Tip:** Try different personalities and find your favorite!"),
            color=0x2596be)
        embed_en.set_footer(text="Powered by gsv2.dev ⚡")

        return embed_de, embed_en

    @commands.Cog.listener()
    async def on_ready(self):
        channel = self.bot.get_channel(self.target_channel_id)
        async for msg in channel.history(limit=100):
                await msg.delete()

        self.embed_de, self.embed_en = self.get_embeds()
        embed = self.embed_de
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Show personalities", custom_id="show_personalities",
                                        style=discord.ButtonStyle.primary))
        view.add_item(discord.ui.Button(label="Switch to English", custom_id="toggle_language",
                                        style=discord.ButtonStyle.secondary))
        message = await channel.send(embed=embed, view=view)
        self.data["embed_id"] = message.id
        self.data["conversations"] = {}
        self.save_data()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.channel.id == self.target_channel_id:
            self.last_message_time = asyncio.get_event_loop().time()
            loading_message = await message.channel.send("Kiksi_AI generiert deine Antwort...")
            user_id = str(message.author.id)
            if "conversations" not in self.data:
                self.data["conversations"] = {}

            if user_id not in self.data["conversations"]:
                self.data["conversations"][user_id] = []

            ai_response = await self.get_ai_response(message.content, message.author.id)
            self.data["conversations"][user_id].append({"role": "user", "content": message.content})
            self.data["conversations"][user_id].append({"role": "assistant", "content": ai_response})
            self.data["conversations"][user_id] = self.data["conversations"][user_id][-20:]
            self.save_data()
            await loading_message.edit(content=ai_response)

    @commands.slash_command(name="switch_personality", description="Wechselt die Persönlichkeit der KI.")
    async def switch_personality(self, ctx, personality: str):
        if personality in self.personalities:
            self.current_personality = personality
            self.data["current_personality"] = personality
            self.save_data()

            embed = discord.Embed(
                title="🔄 Persönlichkeit gewechselt! / Personality switched!",
                description=(
                    f"**Deutsch:** Die KI-Persönlichkeit wurde auf **{personality}** gesetzt.\n"
                    f"**English:** The AI personality has been set to **{personality}**."),
                color=0x2596be)
            embed.set_footer(text="Powered by gsv2.dev ⚡")
            await ctx.respond(embed=embed)
        else:
            await ctx.respond(
                f"❌ **Deutsch:** Die Persönlichkeit ```{personality}``` existiert nicht. Bitte wähle eine gültige Option.\n"
                f"❌ **English:** The personality ```{personality}``` does not exist. Please choose a valid option.")

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type == discord.InteractionType.component and interaction.data["custom_id"] == "show_personalities":
            if "custom_id" in interaction.data and interaction.data["custom_id"] == "show_personalities":
                personalities_list = "\n".join(f"> **{name}**" for name in self.personalities.keys())
                embed = discord.Embed(
                    title="🧠 Verfügbare KI-Persönlichkeiten / Available AI Personalities",
                    description=(
                    "🔹 **Deutsch:** Wähle eine der Persönlichkeiten für den Bot aus\n"
                    "🔹 Nutze </switch_personality:1348925341904801812>, um eine Persönlichkeit auszuwählen.\n\n"
                    "🔹 **English:** Choose one of the following personalities to change the interaction.\n"
                    "🔹 Use </switch_personality:1348925341904801812> to select a personality.\n\n"
                    f"{personalities_list}"),
                    color=0x2596be)
                embed.set_footer(text="Powered by gsv2.dev ⚡")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            elif interaction.data["custom_id"] == "toggle_language":
                current_embed = interaction.message.embeds[0]
                if current_embed.title == self.embed_de.title:
                    new_embed = self.embed_en
                    button_label = "Wechseln zu Deutsch"
                else:
                    new_embed = self.embed_de
                    button_label = "Switch to English"

                view = discord.ui.View()
                view.add_item(discord.ui.Button(label="Zeige Persönlichkeiten", custom_id="show_personalities",
                                            style=discord.ButtonStyle.primary))
                view.add_item(discord.ui.Button(label=button_label, custom_id="toggle_language",
                                            style=discord.ButtonStyle.secondary))
                await interaction.response.edit_message(embed=new_embed, view=view)

    @tasks.loop(minutes=5)
    async def delete_task(self):
        if self.last_message_time and (asyncio.get_event_loop().time() - self.last_message_time) > 1800:
            channel = self.bot.get_channel(self.target_channel_id)
            async for msg in channel.history(limit=100):
                if msg.id != self.data["embed_id"]:
                    await msg.delete()
            self.data["conversations"] = {}
            self.save_data()


def setup(bot):
    bot.add_cog(SimpleAI(bot))