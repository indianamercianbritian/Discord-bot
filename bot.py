import discord
from discord.ext import commands
from discord import app_commands
import os
import time
import uuid
from flask import Flask
from threading import Thread

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STAFF_ROLE_IDS = [1507591215032438814, 1507591312894066800, 1507591349208219738]
WHITELIST_PUBLIC_ID = 1507615441282007120
WHITELIST_STAFF_ID = 1507645759405817936
REPORT_CHANNEL_ID = 1507645770923380867

THEME_COLOR = discord.Color.from_str("#2B2D31") # Premium dark theme
SUCCESS_COLOR = discord.Color.from_str("#57F287")
DANGER_COLOR = discord.Color.from_str("#ED4245")
WARN_COLOR = discord.Color.from_str("#FEE75C")
SEPARATOR = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

def is_staff(interaction: discord.Interaction) -> bool:
    return any(role.id in STAFF_ROLE_IDS for role in interaction.user.roles)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UI VIEWS (PERSISTENT)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WhitelistStaffView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def process_action(self, interaction: discord.Interaction, action: str):
        await interaction.response.defer(ephemeral=True)
        
        if not is_staff(interaction):
            return await interaction.followup.send("❌ Security Alert: Insufficient authority.", ephemeral=True)

        staff_embed = interaction.message.embeds[0]
        
        # Extract the public message ID hidden in the footer
        footer_text = staff_embed.footer.text
        try:
            public_msg_id = int(footer_text.split("Public Log ID: ")[1].strip())
        except (IndexError, ValueError):
            return await interaction.followup.send("❌ Error: Could not locate original public log ID.", ephemeral=True)

        # Formatting based on action
        if action == "approve":
            color = SUCCESS_COLOR
            status_text = "🟢 **STATUS:** WHITELISTED"
            btn_msg = "✅ User Whitelisted."
        else:
            color = DANGER_COLOR
            status_text = "🔴 **STATUS:** DENIED"
            btn_msg = "❌ User Denied."

        timestamp = f"<t:{int(time.time())}:R>"
        resolution_value = f"{status_text}\n*Moderator:* {interaction.user.mention}\n*Time:* {timestamp}"

        # 1. Update Staff Embed
        staff_embed.color = color
        staff_embed.add_field(name="Staff Resolution", value=resolution_value, inline=False)
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(embed=staff_embed, view=self)

        # 2. Update Public Log Embed
        try:
            pub_channel = interaction.guild.get_channel(WHITELIST_PUBLIC_ID)
            pub_msg = await pub_channel.fetch_message(public_msg_id)
            pub_embed = pub_msg.embeds[0]
            pub_embed.color = color
            pub_embed.add_field(name="Status Update", value=resolution_value, inline=False)
            await pub_msg.edit(embed=pub_embed)
        except Exception as e:
            print(f"Failed to edit public message: {e}")

        await interaction.followup.send(btn_msg, ephemeral=True)

    @discord.ui.button(label="Whitelist User", style=discord.ButtonStyle.success, custom_id="wl_approve", emoji="✅")
    async def approve_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_action(interaction, "approve")

    @discord.ui.button(label="Deny User", style=discord.ButtonStyle.danger, custom_id="wl_deny", emoji="❌")
    async def deny_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_action(interaction, "deny")

class ReportStaffView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def process_report(self, interaction: discord.Interaction, status: str):
        await interaction.response.defer(ephemeral=True)
        if not is_staff(interaction):
            return await interaction.followup.send("❌ Security Alert: Insufficient authority.", ephemeral=True)

        embed = interaction.message.embeds[0]
        timestamp = f"<t:{int(time.time())}:R>"

        if status == "investigate":
            embed.color = WARN_COLOR
            resolution = f"🟡 **UNDER INVESTIGATION**\n*Handled by:* {interaction.user.mention} ({timestamp})"
            # We don't disable buttons for investigation
        elif status == "ban":
            embed.color = DANGER_COLOR
            resolution = f"🔴 **USER BANNED**\n*Handled by:* {interaction.user.mention} ({timestamp})"
            for child in self.children: child.disabled = True
        elif status == "not_guilty":
            embed.color = SUCCESS_COLOR
            resolution = f"🟢 **NOT GUILTY**\n*Handled by:* {interaction.user.mention} ({timestamp})"
            for child in self.children: child.disabled = True

        # Remove previous resolution field if it exists, then append new one
        if embed.fields and embed.fields[-1].name == "Case Resolution":
            embed.remove_field(-1)
        
        embed.add_field(name="Case Resolution", value=resolution, inline=False)
        await interaction.message.edit(embed=embed, view=self)
        await interaction.followup.send(f"✅ Case updated to: {status.replace('_', ' ').title()}", ephemeral=True)

    @discord.ui.button(label="Ban User", style=discord.ButtonStyle.danger, custom_id="rep_ban", emoji="🔨")
    async def ban_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_report(interaction, "ban")

    @discord.ui.button(label="Not Guilty", style=discord.ButtonStyle.success, custom_id="rep_clear", emoji="⚖️")
    async def clear_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_report(interaction, "not_guilty")

    @discord.ui.button(label="Under Investigation", style=discord.ButtonStyle.secondary, custom_id="rep_inv", emoji="📌")
    async def inv_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_report(interaction, "investigate")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODALS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WhitelistModal(discord.ui.Modal, title="Premium Whitelist Application"):
    ign = discord.ui.TextInput(label="Minecraft IGN", style=discord.TextStyle.short, placeholder="Enter your exact Minecraft name...", required=True, max_length=16)
    referral = discord.ui.TextInput(label="Referral / How did you find us?", style=discord.TextStyle.paragraph, required=False, max_length=300)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Build Public Embed
        pub_embed = discord.Embed(title="✦ Valencia SMP | Whitelist Request ✦", color=THEME_COLOR)
        pub_embed.description = f"{SEPARATOR}\n**Applicant:** {interaction.user.mention}\n**Discord ID:** `{interaction.user.id}`\n**IGN:** `{self.ign.value}`"
        if self.referral.value:
            pub_embed.add_field(name="Referral / Info", value=f"```{self.referral.value}```", inline=False)
        pub_embed.set_footer(text=f"Valencia SMP • Submitted at")
        pub_embed.timestamp = discord.utils.utcnow()

        # Send to public channel
        pub_channel = interaction.guild.get_channel(WHITELIST_PUBLIC_ID)
        pub_msg = await pub_channel.send(embed=pub_embed)

        # Build Staff Embed
        staff_embed = pub_embed.copy()
        staff_embed.title = "🛡️ STAFF REVIEW | Whitelist Request"
        # Hide the public message ID in the footer so the buttons can find it later
        staff_embed.set_footer(text=f"Public Log ID: {pub_msg.id}")

        staff_channel = interaction.guild.get_channel(WHITELIST_STAFF_ID)
        staff_ping = " ".join([f"<@&{role_id}>" for role_id in STAFF_ROLE_IDS])
        await staff_channel.send(content=f"🔔 **New Application** | {staff_ping}", embed=staff_embed, view=WhitelistStaffView())

        await interaction.followup.send("✅ Your whitelist application has been submitted and is pending staff review.", ephemeral=True)

class ReportModal(discord.ui.Modal, title="Submit Player Report"):
    ign = discord.ui.TextInput(label="Reported Player IGN", style=discord.TextStyle.short, required=True, max_length=16)
    reason = discord.ui.TextInput(label="Reason & Details", style=discord.TextStyle.paragraph, placeholder="What rules were broken?", required=True, max_length=1000)
    evidence = discord.ui.TextInput(label="Evidence Links (Required)", style=discord.TextStyle.short, placeholder="Imgur, YouTube, or Discord attachment links", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        case_id = uuid.uuid4().hex[:8].upper()

        embed = discord.Embed(title=f"🚨 OFFICIAL REPORT | Case #{case_id}", color=THEME_COLOR)
        embed.description = SEPARATOR
        embed.add_field(name="Reporter", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
        embed.add_field(name="Reported IGN", value=f"`{self.ign.value}`", inline=True)
        embed.add_field(name="Incident Details", value=f"```{self.reason.value}```", inline=False)
        embed.add_field(name="Evidence", value=self.evidence.value, inline=False)
        embed.set_footer(text="Valencia SMP Moderation • Awaiting Triage")
        embed.timestamp = discord.utils.utcnow()

        report_channel = interaction.guild.get_channel(REPORT_CHANNEL_ID)
        staff_ping = " ".join([f"<@&{role_id}>" for role_id in STAFF_ROLE_IDS])
        await report_channel.send(content=f"⚠️ **New Case Opened** | {staff_ping}", embed=embed, view=ReportStaffView())
        
        await interaction.followup.send(f"✅ Report submitted successfully. Your Case ID is **#{case_id}**.", ephemeral=True)

class BroadcastModal(discord.ui.Modal, title="Publish Server Broadcast"):
    content = discord.ui.TextInput(label="Broadcast Message", style=discord.TextStyle.paragraph, required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="📢 Server Announcement", description=f"{SEPARATOR}\n\n{self.content.value}\n\n{SEPARATOR}", color=THEME_COLOR)
        embed.set_footer(text=f"Issued by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.channel.send(embed=embed)
        await interaction.followup.send("✅ Broadcast published.", ephemeral=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BOT CLASS & COMMANDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PrivateServerBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def setup_hook(self):
        # Crucial for buttons working after restarts
        self.add_view(WhitelistStaffView())
        self.add_view(ReportStaffView())
        await self.tree.sync()
        print(f"Logged in as {self.user} and synced slash commands.")

bot = PrivateServerBot()

# --- WHITELIST ---
@bot.tree.command(name="whitelist", description="Submit a whitelist application for Valencia SMP.")
async def whitelist(interaction: discord.Interaction):
    await interaction.response.send_modal(WhitelistModal())

# --- REPORT ---
@bot.tree.command(name="report", description="Report a player for breaking server rules.")
async def report(interaction: discord.Interaction):
    await interaction.response.send_modal(ReportModal())

# --- BROADCAST ---
@bot.tree.command(name="broadcast", description="[STAFF] Publish a server announcement.")
@app_commands.default_permissions(manage_messages=True)
async def broadcast(interaction: discord.Interaction):
    if not is_staff(interaction):
        return await interaction.response.send_message("❌ Security Alert: Insufficient authority.", ephemeral=True)
    await interaction.response.send_modal(BroadcastModal())

# --- PURGE ---
@bot.tree.command(name="purge", description="[STAFF] Bulk delete messages.")
@app_commands.describe(amount="Number of messages to delete (1-100)")
@app_commands.default_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
    if not is_staff(interaction):
        return await interaction.response.send_message("❌ Security Alert: Insufficient authority.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🗑️ Deleted **{len(deleted)}** message(s).", ephemeral=True)

# --- WARN ---
@bot.tree.command(name="warn", description="[STAFF] Issue a warning to a player.")
@app_commands.default_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction):
        return await interaction.followup.send("❌ Security Alert: Insufficient authority.", ephemeral=True)
    
    embed = discord.Embed(title="⚠️ Official Warning", description=f"{SEPARATOR}\n**You have received a warning on Valencia SMP.**\n\n**Reason:** `{reason}`\n\n*Please ensure you review the rules to avoid further moderation actions.*", color=WARN_COLOR)
    try:
        await member.send(embed=embed)
        dm_status = "User was notified via DM."
    except discord.Forbidden:
        dm_status = "Could not DM user (DMs closed)."
    
    await interaction.followup.send(f"✅ Warned {member.mention}. {dm_status}", ephemeral=True)

# --- PING ---
@bot.tree.command(name="ping", description="Check the bot's network latency.")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Network Status", description=f"{SEPARATOR}\n**Gateway Latency:** `{latency}ms`\n**Status:** Optimal", color=THEME_COLOR)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- STATUS ---
@bot.tree.command(name="status", description="Display current server connection info.")
async def status(interaction: discord.Interaction):
    embed = discord.Embed(title="🟢 Valencia SMP | Live Status", color=SUCCESS_COLOR)
    embed.description = f"{SEPARATOR}\nThe server is currently **ONLINE** and operating normally."
    embed.add_field(name="🌐 Connection IP", value="`valenciasmp.playwithbao.com`", inline=False)
    embed.add_field(name="📦 Version", value="`1.21.x`", inline=True)
    embed.set_footer(text="Valencia SMP Network")
    await interaction.response.send_message(embed=embed)

# --- HELP / DASHBOARD ---
@bot.tree.command(name="help", description="View server rules, major teams, and FAQ.")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="✦ Valencia SMP | Information Center ✦", color=THEME_COLOR)
    embed.description = f"Welcome to Valencia SMP. Please review our regulations below.\n{SEPARATOR}"
    
    embed.add_field(name="⚔️ SMP RULES", value=(
        "• Crystal PVP (CPVP) is **strictly forbidden**.\n"
        "• Killing players with **NO ARMOR** within 100 blocks of spawn is illegal.\n"
        "• Stealing from bases is allowed, but **griefing is strictly prohibited**.\n"
        "• Do not attack Pacifists.\n"
        "• Do not kill armorless players (unless they are 500+ blocks from spawn)."
    ), inline=False)
    
    embed.add_field(name="❓ FAQ", value=(
        "**Connection IP:** `valenciasmp.playwithbao.com`\n\n"
        "**How to become whitelisted?**\n"
        "Run `/whitelist`. Ping Exin, Lee, or Zhang to get whitelisted ASAP.\n\n"
        "**Why are Pacifists exempt?**\n"
        "They do not engage in combat; they build for the community. They cannot attack, and cannot be attacked unless provoked.\n\n"
        "**How can my team get a role?**\n"
        "Your team must contain 4+ players. Open a ticket if eligible."
    ), inline=False)
    
    embed.add_field(name="🏆 CURRENT MAJOR TEAMS", value="• **Trinity**", inline=False)
    embed.set_footer(text="Valencia SMP Administration")
    
    await interaction.response.send_message(embed=embed)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# KEEP ALIVE & RUN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
app = Flask('')
@app.route('/')
def home():
    return "Valencia SMP Bot is Online!"

def run_web_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

if __name__ == '__main__':
    keep_alive()
    bot.run(os.environ.get('BOT_TOKEN'))