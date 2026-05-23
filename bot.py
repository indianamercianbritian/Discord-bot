import discord
from discord.ext import commands
from discord import app_commands
import os
from flask import Flask
from threading import Thread

# --- CONFIGURATION ---
STAFF_ROLE_IDS = [
    1507591215032438814,
    1507591312894066800,
    1507591349208219738
]

# Fetch the token from your Render environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')

class PrivateServerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True 
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Logged in as {self.user} and synced slash commands.")

bot = PrivateServerBot()

# --- WEB SERVER (For Render Keep-Alive) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# --- MODULE 1: DASHBOARD ---
class DashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) 
        self.add_item(discord.ui.Button(label="Web Map", style=discord.ButtonStyle.link, url="https://your-map-url.com"))

    @discord.ui.select(
        placeholder="Browse sections...",
        custom_id="dashboard_select",
        options=[
            discord.SelectOption(label="Server Rules", description="View the gameplay and discord rules", value="rules", emoji="📜"),
            discord.SelectOption(label="Server Information", description="Get the IP, FAQ, and team details", value="info", emoji="ℹ️")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        if select.values[0] == "rules":
            rules_embed = discord.Embed(title="📜 Valencia SMP | Official Rules", color=discord.Color.red())
            rules_embed.add_field(name="⚔️ In-Game / SMP Rules", value="""
• **No Cheating:** Hacked clients, Freecam, ESP, or Radars (pie chart exception).
• **No Exploits:** Duping, Combat Logging, or Combat TPA.
• **PVP Restrictions:** No TP Trapping, Spawn Killing, or Spawn Trapping. **No Elytra Macing**.
• **Economy:** No IRL Trading or Cross Trading.
• **Protections:** Do not kill players protected by the law or Pacifists.
• **Conduct:** No toxicity.
            """, inline=False)
            rules_embed.add_field(name="🛡️ General / Discord Rules", value="""
• **Zero Tolerance:** No Doxxing, DDOSing, or illicit cyber activities.
• **Respect:** No Racism, Hate Speech, or NSFW content.
• **Advertising:** No DM advertising.
• **Expectation:** Common sense is strictly required.
            """, inline=False)
            await interaction.response.send_message(embed=rules_embed, ephemeral=True)
        
        elif select.values[0] == "info":
            info_embed = discord.Embed(title="ℹ️ Valencia SMP | Server Information", color=discord.Color.blue())
            info_embed.add_field(name="🌐 Connection", value="**IP:** `valenciasmp.playwithbao.com`", inline=False)
            info_embed.add_field(name="⚔️ Core SMP Mechanics", value="""
• **CPVP:** Crystal PVP is strictly forbidden.
• **Spawn Protection:** Do not kill players with NO ARMOR within 100 blocks of spawn.
• **Raiding:** Stealing is allowed; **Griefing is strictly prohibited.**
            """, inline=False)
            info_embed.add_field(name="🕊️ Pacifist System", value="Pacifists are exempt from PVP and build for the community. Do not attack them unless provoked.", inline=False)
            info_embed.add_field(name="❓ FAQ & Teams", value="""
• **Whitelisting:** Ping Exin, Lee, or Zhang with your IGN in the whitelist channel.
• **Teams:** Require 4+ players. Open a ticket to apply.
• **Current Major Teams:** Trinity
            """, inline=False)
            await interaction.response.send_message(embed=info_embed, ephemeral=True)

    @discord.ui.button(label="Notifications", style=discord.ButtonStyle.primary, emoji="🔔", custom_id="toggle_notifications")
    async def notify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔔 Notification preferences updated!", ephemeral=True)

@bot.tree.command(name="setup-dashboard", description="Deploys the rules and information dashboard.")
@app_commands.default_permissions(manage_guild=True)
async def setup_dashboard(interaction: discord.Interaction):
    if not any(role.id in STAFF_ROLE_IDS for role in interaction.user.roles):
        return await interaction.response.send_message("❌ Security Alert: Insufficient authority.", ephemeral=True)
    embed = discord.Embed(title="Valencia SMP Dashboard", description="Use the dropdown below to browse our regulations and information.", color=discord.Color.from_str("#2b2d31"))
    embed.set_image(url="https://your-banner-image-url.com/banner.png") 
    await interaction.channel.send(embed=embed, view=DashboardView())
    await interaction.response.send_message("Dashboard deployed.", ephemeral=True)

# --- MODULE 2: BROADCAST SYSTEM ---
class BroadcastModal(discord.ui.Modal):
    def __init__(self, log_type: str, target_channel: discord.TextChannel):
        super().__init__(title="Post Update" if log_type == "update" else "Publish Ban")
        self.log_type, self.target_channel = log_type, target_channel
        self.content = discord.ui.TextInput(label="Details", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.content)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🛠️ Server Update" if self.log_type == "update" else "🔨 Ban Log", description=self.content.value, color=discord.Color.green() if self.log_type == "update" else discord.Color.red(), timestamp=discord.utils.utcnow())
        await self.target_channel.send(embed=embed)
        await interaction.response.send_message("✅ Published.", ephemeral=True)

@bot.tree.command(name="broadcast", description="Publish an update or ban log.")
@app_commands.default_permissions(manage_messages=True)
async def broadcast(interaction: discord.Interaction, type: str, target_channel: discord.TextChannel):
    if not any(role.id in STAFF_ROLE_IDS for role in interaction.user.roles):
        return await interaction.response.send_message("❌ Security Alert.", ephemeral=True)
    await interaction.response.send_modal(BroadcastModal(type, target_channel))

# --- RUN THE BOT ---
if __name__ == '__main__':
    keep_alive()
    bot.run(BOT_TOKEN)