import os
from flask import Flask
from threading import Thread

import discord
from discord.ext import commands
from datetime import datetime, date, timedelta
import pytz
from supabase import create_client

def get_today():
    tz = pytz.timezone("Asia/Tokyo")
    return datetime.now(tz).date()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

TOKEN = os.environ["TOKEN"]
GUILD_ID = 1463536665632051213

intents = discord.Intents.default()
intents.voice_states = True
intents.members = True
intents.message_content = True

app = Flask(__name__)

@app.route("/")

def home():
    return "Bot is alive!"

def run_web():
    app.run(host="0.0.0.0", port=10000)

def keep_alive():
    Thread(target=run_web).start()

bot = commands.Bot(command_prefix="!", intents=intents)

def update_vc(user_id):
    today = get_today()
    data = supabase.table("vc_count").select("*").eq("user_id", user_id).execute()

    if not data.data:
        supabase.table("vc_count").insert({
            "user_id": user_id,
            "count": 1,
            "last_date": str(today)
        }).execute()
        return 1

    user = data.data[0]
    last_date = date.fromisoformat(user["last_date"])
    count = user["count"]

    if last_date == today:
        return count

    count = count + 1 if last_date == today - timedelta(days=1) else 1

    supabase.table("vc_count").update({
        "count": count,
        "last_date": str(today)
    }).eq("user_id", user_id).execute()

    return count

@bot.tree.command(
    name="出席簿",
    description="ユーザーの連続出席日数を見る",
    guild=discord.Object(id=GUILD_ID)
)
async def vccount(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()

    if member is None:
        member = interaction.user

    try:
        res = supabase.table("vc_count").select("*").eq("user_id", member.id).execute()
        count = res.data[0]["count"] if res.data else 0

        await interaction.followup.send(
            f"{member.display_name} の連続出席日数は **{count}日** です"
        )

    except Exception as e:
        print("ERROR:", repr(e), flush=True)
        await interaction.followup.send(f"エラー: `{repr(e)}`")
        
@bot.tree.command(name="出席ランキング", description="連続出席日数ランキング（上位10人）", guild=discord.Object(id=GUILD_ID))
async def ranking(interaction: discord.Interaction):
    await interaction.response.defer()
    res = supabase.table("vc_count").select("*").order("count", desc=True).limit(10).execute()

    if not res.data:
        await interaction.followup.send("データがありません")
        return

    text = "🏆 連続出席日数ランキング（TOP10）\n\n"
    for i, row in enumerate(res.data, start=1):
        member = interaction.guild.get_member(row["user_id"])
        name = member.display_name if member else f"ID:{row['user_id']}"
        text += f"{i}位：{name} - {row['count']}日\n"

    await interaction.followup.send(text)

@bot.event
async def on_ready():
    print("Bot ready", flush=True)
    print("SUPABASE_URL:", repr(SUPABASE_URL), flush=True)

    guild = discord.Object(id=GUILD_ID)
    synced = await bot.tree.sync(guild=guild)

    print(f"{bot.user} でログインしました", flush=True)
    print(f"同期したコマンド数: {len(synced)}", flush=True)
    for cmd in synced:
        print(cmd.name, flush=True)

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:
        count = update_vc(member.id)
        print(f"{member.display_name} の連続出席日数: {count}")

@bot.event
async def on_message(message):
    if message.author.bot or message.guild is None:
        return

    update_vc(message.author.id)
    await bot.process_commands(message)

keep_alive()
bot.run(TOKEN)
