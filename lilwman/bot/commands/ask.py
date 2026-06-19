import discord
from discord import app_commands
from discord.ext import commands


class AskCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="ask", description="Ask a question answered from the wiki")
    @app_commands.describe(question="Your question")
    async def ask(self, interaction: discord.Interaction, question: str) -> None:
        await interaction.response.defer()
        answer = await self.bot.ask_query.execute(question)
        await interaction.followup.send(f"**Q: {question}**\n\n{answer}")
