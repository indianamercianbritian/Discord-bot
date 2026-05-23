import discord
from discord.ext import commands
from discord import app_commands
import os
from flask import Flask
from threading import Thread

# --- CONFIGURATION ---
STAFF_ROLE_IDS = [1507591215032438814, 1507591312894066800, 1507591349208219738]
WHITELIST_CHANNEL_ID = 1507615441282007120
REPORT_CHANNEL_ID = 1507645770923380867

# --- PERSISTENT VIEWS ---
class WhitelistView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Whitelisted", style=discord.ButtonStyle.green, custom_id="whitelist_btn")
    async def whitelist_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id in STAFF_ROLE_IDS for role in interaction.user.roles):
            return await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.set_field_at(0, name=embed.fields[0].name, value=f"{embed.fields[0].value} ✅ (Whitelisted)", inline=True)
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message("✅ User whitelisted.", ephemeral=True)

class ReportView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Handle Report", style=discord.ButtonStyle.red, custom_id="report_btn")
    async def handle_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id in STAFF_ROLE_IDS for role in interaction.user.roles):
            return await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        
        await interaction.message.edit(view=None)
        await interaction.response.send_message("✅ Marked as handled.", ephemeral=True)

class PrivateServerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Register persistent views
        self.add_view(WhitelistView())
        self.add_view(ReportView())
        await self.tree.sync()
        print(f"Logged in as {self.user}")

bot = PrivateServerBot()

# --- WEB SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Bot is alive!"
def keep_alive(): Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

# --- WHITELIST COMMAND ---
@bot.tree.command(name="whitelist", description="Submit whitelist request")
async def whitelist(interaction: discord.Interaction, ign: str):
    channel = bot.get_channel(WHITELIST_CHANNEL_ID)
    embed = discord.Embed(title="📋 Whitelist Request", color=discord.Color.blurple())
    embed.add_field(name="User", value=interaction.user.mention)
    embed.add_field(name="IGN", value=ign)
    await channel.send(content="<@&1507591215032438814> New Request!", embed=embed, view=WhitelistView())
    await interaction.response.send_message("✅ Submitted.", ephemeral=True)

# --- REPORT COMMAND ---
@bot.tree.command(name="report", description="Report a player")
async def report(interaction: discord.Interaction, reported_ign: str, evidence: str):
    channel = bot.get_channel(REPORT_CHANNEL_ID)
    embed = discord.Embed(title="🚨 New Report", color=discord.Color.red())
    embed.add_field(name="Reporter", value=interaction.user.mention)
    embed.add_field(name="Reported", value=reported_ign)
    embed.add_field(name="Evidence", value=evidence)
    await channel.send(embed=embed, view=ReportView())
    await interaction.response.send_message("✅ Reported.", ephemeral=True)

# --- PING/WARN ---
@bot.tree.command(name="ping")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(bot.latency*1000)}ms")

@bot.tree.command(name="warn")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    await interaction.response.send_message(f"⚠️ Warned {member.mention} for {reason}")

if __name__ == '__main__':
    keep_alive()
    bot.run(os.environ.get('BOT_TOKEN'))