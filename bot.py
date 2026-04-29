import os
from flask import Flask
from threading import Thread

import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta

from supabase import create_client

# ===== Supabase設定 =====
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===== Discord設定 =====
TOKEN = os.environ["TOKEN"]
GUILD_ID = 1463536665632051213

JST = timezone(timedelta(hours=9))

intents = discord.Intents.default()
intents.voice_states = True
intents.members = True
intents.message_content = True

# ===== Flask（keep alive）=====
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive!"

def run_web():
    app.run(host="0.0.0.0", port=10000)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ===== Bot =====
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== コマンド =====
@bot.tree.command(
    name="出席簿",
    description="ユーザーの連続VC日数を見る",
    guild=discord.Object(id=GUILD_ID)
)
async def vccount(interaction: discord.Interaction, member: discord.Member):
    res = supabase.table("vc_count").select("*").eq("user_id", member.id).execute()

    if res.data:
        count = res.data[0]["count"]
    else:
        count = 0

    await interaction.response.send_message(
        f"{member.display_name} の連続VC日数は **{count}日** です"
    )

@bot.tree.command(
    name="出席ランキング",
    description="連続VC日数ランキング（上位10人）",
    guild=discord.Object(id=GUILD_ID)
)
async def ranking(interaction: discord.Interaction):
    res = supabase.table("vc_count").select("*").order("count", desc=True).limit(10).execute()

    if not res.data:
        await interaction.response.send_message("データがありません")
        return

    text = "🏆 連続出席日数ランキング（TOP10）\n\n"

    for i, row in enumerate(res.data, start=1):
        user_id = row["user_id"]
        count = row["count"]

        member = interaction.guild.get_member(user_id)
        name = member.display_name if member else f"ID:{user_id}"

        text += f"{i}位：{name} - {count}日\n"

    await interaction.response.send_message(text)

# ===== Bot起動 =====
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    synced = await bot.tree.sync(guild=guild)

    print(f"{bot.user} でログインしました")
    print(f"同期したコマンド数: {len(synced)}")

# ===== VC入室検知 =====
@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:
        today = datetime.now(JST).date()

        res = supabase.table("vc_count").select("*").eq("user_id", member.id).execute()

        if res.data:
            count = res.data[0]["count"]
            last_date = datetime.strptime(res.data[0]["last_date"], "%Y-%m-%d").date()
            diff = (today - last_date).days

            if diff == 0:
                return
            elif diff == 1:
                new_count = count + 1
            else:
                new_count = 1

            supabase.table("vc_count").update({
                "count": new_count,
                "last_date": str(today)
            }).eq("user_id", member.id).execute()

        else:
            supabase.table("vc_count").insert({
                "user_id": member.id,
                "count": 1,
                "last_date": str(today)
            }).execute()

# ===== メッセージ検知 =====
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.guild is None:
        return

    today = datetime.now(JST).date()
    member = message.author

    res = supabase.table("vc_count").select("*").eq("user_id", member.id).execute()

    if res.data:
        count = res.data[0]["count"]
        last_date = datetime.strptime(res.data[0]["last_date"], "%Y-%m-%d").date()
        diff = (today - last_date).days

        if diff == 1:
            new_count = count + 1
        elif diff > 1:
            new_count = 1
        else:
            return

        supabase.table("vc_count").update({
            "count": new_count,
            "last_date": str(today)
        }).eq("user_id", member.id).execute()

    else:
        supabase.table("vc_count").insert({
            "user_id": member.id,
            "count": 1,
            "last_date": str(today)
        }).execute()

    await bot.process_commands(message)

# ===== 起動 =====
keep_alive()
bot.run(TOKEN)
