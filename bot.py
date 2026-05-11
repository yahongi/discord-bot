import os
from flask import Flask
from threading import Thread

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
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

MALE_INTRO_CHANNEL_ID = 1463538621293396152
FEMALE_INTRO_CHANNEL_ID = 1463538649915330601

INTRO_TEMPLATE = """【名前】
【年齢】
【好きなタイプ】
【嫌いなタイプ】
【趣味】
【一言】"""

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

class ProfileModal(Modal, title="自己紹介作成"):
    name = TextInput(label="名前")
    personality = TextInput(label="性格と接し方", style=discord.TextStyle.paragraph)
    caution = TextInput(label="苦手、絡む時の注意", style=discord.TextStyle.paragraph)
    games = TextInput(label="やってるゲーム")
    message = TextInput(label="一言", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        supabase.table("profiles").upsert({
            "user_id": interaction.user.id,
            "name": str(self.name),
            "personality": str(self.personality),
            "caution": str(self.caution),
            "games": str(self.games),
            "message": str(self.message),
            "updated_at": str(get_today())
        }).execute()

        await interaction.response.send_message(
            "✅ プロフィールを保存しました！\n`/プロフィール` で確認できます。",
            ephemeral=True
        )

class ProfileView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="自己紹介作成", style=discord.ButtonStyle.green)
    async def create_profile(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ProfileModal())

    @discord.ui.button(label="修正する", style=discord.ButtonStyle.blurple)
    async def edit_profile(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ProfileModal())

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

@bot.tree.command(
    name="プロフィール設定",
    description="プロフィールを設定する",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(
    name="名前",
    personality="性格と接し方",
    caution="苦手、絡む時の注意",
    games="やってるゲーム",
    message="一言"
)
async def profile_set(
    interaction: discord.Interaction,
    name: str,
    personality: str,
    caution: str,
    games: str,
    message: str
):
    supabase.table("profiles").upsert({
        "user_id": interaction.user.id,
        "name": name,
        "personality": personality,
        "caution": caution,
        "games": games,
        "message": message,
        "updated_at": str(get_today())
    }).execute()

    await interaction.response.send_message(
        "✅ プロフィールを保存しました！",
        ephemeral=True
    )

@bot.tree.command(
    name="プロフィール",
    description="プロフィールを見る",
    guild=discord.Object(id=GUILD_ID)
)
async def profile_view(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()

    if member is None:
        member = interaction.user

    res = supabase.table("profiles").select("*").eq("user_id", member.id).execute()
    vc_res = supabase.table("vc_count").select("*").eq("user_id", member.id).execute()

    if not res.data:
        await interaction.followup.send(f"{member.display_name} はまだプロフィール未設定です")
        return

    profile = res.data[0]
    count = vc_res.data[0]["count"] if vc_res.data else 0

 embed = discord.Embed(
    title=f"🪪 {member.display_name} のプロフィール",
    description="━━━━━━━━━━━━━━",
    color=0x8b5cf6
)

embed.add_field(
    name="👤 名前",
    value=f"```{profile.get('name') or '未設定'}```",
    inline=False
)

embed.add_field(
    name="💬 性格と接し方",
    value=f"```{profile.get('personality') or '未設定'}```",
    inline=False
)

embed.add_field(
    name="⚠️ 苦手・絡む時の注意",
    value=f"```{profile.get('caution') or '未設定'}```",
    inline=False
)

embed.add_field(
    name="🎮 やってるゲーム",
    value=f"```{profile.get('games') or '未設定'}```",
    inline=False
)

embed.add_field(
    name="📝 一言",
    value=f"```{profile.get('message') or '未設定'}```",
    inline=False
)

embed.add_field(
    name="🔥 連続出席日数",
    value=f"**{count}日**",
    inline=True
)

embed.set_thumbnail(url=member.display_avatar.url)

embed.set_footer(
    text=f"User ID: {member.id} ｜ /プロフィール設定 で編集できます"
)

await interaction.followup.send(embed=embed)

@bot.tree.command(
    name="プロフィールパネル",
    description="プロフィール作成パネルを表示する",
    guild=discord.Object(id=GUILD_ID)
)
async def profile_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="自己紹介作成",
        description="下のボタンを押して自己紹介を作成・修正してください。",
        color=0x8b5cf6
    )

    await interaction.response.send_message(embed=embed, view=ProfileView())

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

    if message.channel.id in [MALE_INTRO_CHANNEL_ID, FEMALE_INTRO_CHANNEL_ID]:

        try:
            async for msg in message.channel.history(limit=30):
                if msg.author == bot.user and msg.content.strip() == INTRO_TEMPLATE.strip():
                    await msg.delete()
        except Exception as e:
            print("TEMPLATE DELETE ERROR:", repr(e), flush=True)

        try:
            await message.channel.send(INTRO_TEMPLATE)
        except Exception as e:
            print("TEMPLATE SEND ERROR:", repr(e), flush=True)

    await bot.process_commands(message)
        

keep_alive()
bot.run(TOKEN)
