import os
from flask import Flask
from threading import Thread

import discord
from discord.ext import commands
import sqlite3
from datetime import datetime, timezone, timedelta

TOKEN = os.environ["TOKEN"]

GUILD_ID = 1463536665632051213

JST = timezone(timedelta(hours=9))

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
    t = Thread(target=run_web)
    t.start()

bot = commands.Bot(command_prefix="!", intents=intents)

db = sqlite3.connect("vc_count.db")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS vc_count (
    user_id INTEGER PRIMARY KEY,
    count INTEGER NOT NULL,
    last_date TEXT
)
""")
db.commit()

@bot.tree.command(
    name="出席簿",
    description="ユーザーの連続VC日数を見る",
    guild=discord.Object(id=GUILD_ID)
)
async def vccount(interaction: discord.Interaction, member: discord.Member):
    cur.execute("SELECT count FROM vc_count WHERE user_id = ?", (member.id,))
    row = cur.fetchone()
    count = row[0] if row else 0

    await interaction.response.send_message(
        f"{member.display_name} の連続VC日数は **{count}日** です"
    )

@bot.tree.command(
    name="出席ランキング",
    description="連続VC日数ランキング（上位10人）",
    guild=discord.Object(id=GUILD_ID)
)
async def ranking(interaction: discord.Interaction):
    cur.execute("SELECT user_id, count FROM vc_count ORDER BY count DESC LIMIT 10")
    rows = cur.fetchall()

    if not rows:
        await interaction.response.send_message("データがありません")
        return

    text = "🏆 連続出席日数ランキング（TOP10）\n\n"

    for i, (user_id, count) in enumerate(rows, start=1):
        member = interaction.guild.get_member(user_id)
        name = member.display_name if member else f"ID:{user_id}"
        text += f"{i}位：{name} - {count}日\n"

    await interaction.response.send_message(text)

@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    synced = await bot.tree.sync(guild=guild)

    print(f"{bot.user} でログインしました")
    print(f"同期したコマンド数: {len(synced)}")
    for cmd in synced:
        print(cmd.name)
    
@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:
        today = datetime.now(JST).date()

        cur.execute("SELECT count, last_date FROM vc_count WHERE user_id = ?", (member.id,))
        row = cur.fetchone()

        if row:
            count, last_date = row
            last_date = datetime.strptime(last_date, "%Y-%m-%d").date()
            diff = (today - last_date).days

            if diff == 0:
                return
            elif diff == 1:
                new_count = count + 1
            else:
                new_count = 1

            cur.execute(
                "UPDATE vc_count SET count = ?, last_date = ? WHERE user_id = ?",
                (new_count, today.strftime("%Y-%m-%d"), member.id)
            )
            db.commit()
        else:
            cur.execute(
                "INSERT INTO vc_count (user_id, count, last_date) VALUES (?, 1, ?)",
                (member.id, today.strftime("%Y-%m-%d"))
            )
            db.commit()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # サーバー内だけ対象（DMは除外）
    if message.guild is None:
        return

    today = datetime.now(JST).date()
    member = message.author

    cur.execute("SELECT count, last_date FROM vc_count WHERE user_id = ?", (member.id,))
    row = cur.fetchone()

    if row:
        count, last_date = row
        last_date = datetime.strptime(last_date, "%Y-%m-%d").date()
        diff = (today - last_date).days

        if diff == 0:
            pass
        elif diff == 1:
            cur.execute(
                "UPDATE vc_count SET count = ?, last_date = ? WHERE user_id = ?",
                (count + 1, today.strftime("%Y-%m-%d"), member.id)
            )
            db.commit()
        else:
            cur.execute(
                "UPDATE vc_count SET count = ?, last_date = ? WHERE user_id = ?",
                (1, today.strftime("%Y-%m-%d"), member.id)
            )
            db.commit()
    else:
        cur.execute(
            "INSERT INTO vc_count (user_id, count, last_date) VALUES (?, 1, ?)",
            (member.id, today.strftime("%Y-%m-%d"))
        )
        db.commit()

    await bot.process_commands(message)

keep_alive()
bot.run(TOKEN)