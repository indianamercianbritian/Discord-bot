import discord
from discord.ext import commands
from discord import app_commands
import os
from flask import Flask
from threading import Thread

# --- CONFIGURATION ---
STAFF_ROLE_IDS = [1507591215032438814, 1507591312894066800, 1507591349208219738]
WHITELIST_CHANNEL_ID = 1507615441282007120
STAFF_WHITELIST_CHANNEL_ID = 1507645759405817936
REPORT_CHANNEL_ID = 1507645770923380867

# --- 1. PERSISTENT VIEWS (UI Logic) ---

class WhitelistActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Whitelisted", style=discord.ButtonStyle.green, custom_id="btn_whitelist")
    async def whitelist(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id in STAFF_ROLE_IDS for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.add_field(name="Status", value="✅ Whitelisted", inline=False)
        
        # DM User
        try:
            user_id = int(embed.footer.text)
            user = await interaction.guild.fetch_member(user_id)
            await user.send("✅ You have been whitelisted for Valencia SMP! You may now join.")
        except: pass
        
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message("✅ Whitelist complete.", ephemeral=True)

class VerdictView(discord.ui.View):
    def __init__(self, reporter_id: int):
        super().__init__(timeout=None)
        self.reporter_id = reporter_id

    @discord.ui.button(label="Guilty", style=discord.ButtonStyle.danger)
    async def guilty(self, interaction: discord.Interaction, button: discord.ui.Button):
        reporter = interaction.guild.get_member(self.reporter_id)
        if reporter: await reporter.send("🔨 **Verdict:** The reported user was found **GUILTY**.")
        await interaction.response.send_message("✅ Verdict sent. Closing channel...", ephemeral=True)
        await interaction.channel.delete()

    @discord.ui.button(label="Not Guilty", style=discord.ButtonStyle.secondary)
    async def not_guilty(self, interaction: discord.Interaction, button: discord.ui.Button):
        reporter = interaction.guild.get_member(self.reporter_id)
        if reporter: await reporter.send("✅ **Verdict:** The reported user was found **NOT GUILTY**.")
        await interaction.response.send_message("✅ Verdict sent. Closing channel...", ephemeral=True)
        await interaction.channel.delete()

class ReportHandleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Handle Report", style=discord.ButtonStyle.red, custom_id="btn_handle_report")
    async def handle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id in STAFF_ROLE_IDS for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        
        reporter_id = int(interaction.message.embeds[0].footer.text)
        guild = interaction.guild
        category = interaction.channel.category
        channel = await guild.create_text_channel(
            f"report-{interaction.user.name}", 
            category=category,
            overwrites={guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                        guild.get_role(STAFF_ROLE_IDS[0]): discord.PermissionOverwrite(read_messages=True)}
        )
        await channel.send(f"Report claim by {interaction.user.mention}. Please discuss evidence here.", view=VerdictView(reporter_id))
        await interaction.response.send_message(f"✅ Created {channel.mention}", ephemeral=True)

# --- 2. MODALS ---

class WhitelistModal(discord.ui.Modal, title="Whitelist Request"):
    ign = discord.ui.TextInput(label="Minecraft IGN", style=discord.TextStyle.short)
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📋 New Whitelist Request", color=discord.Color.blue())
        embed.add_field(name="User", value=interaction.user.mention)
        embed.add_field(name="IGN", value=self.ign.value)
        embed.set_footer(text=str(interaction.user.id))
        
        # Public Log
        await interaction.guild.get_channel(WHITELIST_CHANNEL_ID).send(embed=embed)
        # Staff Review
        await interaction.guild.get_channel(STAFF_WHITELIST_CHANNEL_ID).send(embed=embed, view=WhitelistActionView())
        await interaction.response.send_message("✅ Request submitted.", ephemeral=True)

class ReportModal(discord.ui.Modal, title="Report Player"):
    ign = discord.ui.TextInput(label="Reported IGN", style=discord.TextStyle.short)
    summary = discord.ui.TextInput(label="Summary", style=discord.TextStyle.paragraph)
    evidence = discord.ui.TextInput(label="Evidence Link", style=discord.TextStyle.short, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🚨 New Report", color=discord.Color.red())
        embed.add_field(name="Reported", value=self.ign.value)
        embed.add_field(name="Summary", value=self.summary.value)
        if self.evidence.value: embed.add_field(name="Evidence", value=self.evidence.value)
        embed.set_footer(text=str(interaction.user.id))
        
        await interaction.guild.get_channel(REPORT_CHANNEL_ID).send(embed=embed, view=ReportHandleView())
        await interaction.response.send_message("✅ Report submitted.", ephemeral=True)

class BroadcastModal(discord.ui.Modal, title="Broadcast"):
    content = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph)
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📢 Announcement", description=self.content.value, color=discord.Color.gold())
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Broadcasted.", ephemeral=True)

# --- 3. BOT & COMMANDS ---

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        self.add_view(WhitelistActionView())
        self.add_view(ReportHandleView())
        await self.tree.sync()

bot = Bot()

@bot.tree.command(name="whitelist", description="Submit whitelist request")
async def whitelist(interaction: discord.Interaction):
    await interaction.response.send_modal(WhitelistModal())

@bot.tree.command(name="report", description="Report a player")
async def report(interaction: discord.Interaction):
    await interaction.response.send_modal(ReportModal())

@bot.tree.command(name="broadcast", description="Send a server broadcast")
async def broadcast(interaction: discord.Interaction):
    await interaction.response.send_modal(BroadcastModal())

@bot.tree.command(name="help", description="Show server info")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="Valencia SMP Help", color=discord.Color.purple())
    embed.add_field(name="⚔️ Rules", value="CPVP forbidden. No griefing. Pacifists protected. No spawn killing.", inline=False)
    embed.add_field(name="❓ FAQ", value="IP: valenciasmp.playwithbao.com\nWhitelist: Use /whitelist\nTeams: 4+ players required.", inline=False)
    embed.add_field(name="🏆 Major Teams", value="Trinity", inline=False)
    await interaction.response.send_message(embed=embed)

# Keep Alive
def keep_alive():
    app = Flask('')
    @app.route('/')
    def home(): return "Alive"
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

if __name__ == "__main__":
    keep_alive()
    bot.run(os.environ.get('BOT_TOKEN'))