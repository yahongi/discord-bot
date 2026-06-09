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
LOG_CHANNEL_ID = 1513382077771546886

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

class ProfileModal(Modal):

    def __init__(self, profile=None):

        super().__init__(title="自己紹介作成")

        self.name = TextInput(
            label="名前",
            default=profile.get("name", "") if profile else ""
        )

        self.personality = TextInput(
            label="性格と接し方",
            style=discord.TextStyle.paragraph,
            default=profile.get("personality", "") if profile else ""
        )

        self.caution = TextInput(
            label="苦手、絡む時の注意",
            style=discord.TextStyle.paragraph,
            default=profile.get("caution", "") if profile else ""
        )

        self.games = TextInput(
            label="やってるゲーム",
            default=profile.get("games", "") if profile else ""
        )

        self.message = TextInput(
            label="一言",
            style=discord.TextStyle.paragraph,
            default=profile.get("message", "") if profile else ""
        )

        self.add_item(self.name)
        self.add_item(self.personality)
        self.add_item(self.caution)
        self.add_item(self.games)
        self.add_item(self.message)

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
        
        profile_data = supabase.table("profiles").select("*").eq(
            "user_id",
            interaction.user.id
        ).execute()

        profile = profile_data.data[0]
        
        old_profile_message_id = profile.get("profile_message_id")

        if old_profile_message_id:
            try:
                old_message = await interaction.channel.fetch_message(
                    int(old_profile_message_id)
                )
                await old_message.delete()
            except:
                pass

        vc_res = supabase.table("vc_count").select("*").eq(
            "user_id",
            interaction.user.id
        ).execute()

        count = vc_res.data[0]["count"] if vc_res.data else 0

        theme_name = profile.get("theme_color") or "purple"
        theme_color = THEME_COLORS.get(theme_name, 0x8b5cf6)

        embed = discord.Embed(
            title=f"🪪 {interaction.user.display_name} のプロフィール",
            color=theme_color
        )

        embed.description = (
            f"**👤 名前**\n"
            f"{profile.get('name') or '未設定'}\n\n"

            f"**💬 性格と接し方**\n"
            f"{profile.get('personality') or '未設定'}\n\n"

            f"**⚠️ 苦手・絡む時の注意**\n"
            f"{profile.get('caution') or '未設定'}\n\n"

            f"**🎮 やってるゲーム**\n"
            f"{profile.get('games') or '未設定'}\n\n"

            f"**📝 一言**\n"
            f"{profile.get('message') or '未設定'}\n\n"

            f"**🔥 連続出席日数**\n"
            f"{count}日"
        ) 
        
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        profile_message = await interaction.channel.send(
            embed=embed
        )

        supabase.table("profiles").update({
            "profile_message_id": str(profile_message.id)
        }).eq("user_id", interaction.user.id).execute()

        old_panel_message_id = profile.get("panel_message_id")

        if old_panel_message_id:
            try:
                old_panel = await interaction.channel.fetch_message(
                    int(old_panel_message_id)
                )
                await old_panel.delete()
            except:
                pass

        panel_embed = discord.Embed(
            title="自己紹介生成",
            description="自己紹介の作成・修正、テーマカラー変更ができます。",
            color=theme_color
        )

        panel_message = await interaction.channel.send(
            embed=panel_embed,
            view=ProfileView()
        )

        supabase.table("profiles").update({
            "panel_message_id": str(panel_message.id)
        }).eq("user_id", interaction.user.id).execute() 

        await interaction.response.send_message(
            "✅ プロフィールを更新しました！",
            ephemeral=True
        ) 
        
class ProfileView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def save_theme(self, interaction: discord.Interaction, color_name: str):
        await ThemeView().save_theme(interaction, color_name)

    @discord.ui.button(label="自己紹介作成", style=discord.ButtonStyle.green)
    async def create_profile(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ProfileModal())

    @discord.ui.button(label="修正する", style=discord.ButtonStyle.blurple)
    async def edit_profile(self, interaction: discord.Interaction, button: Button):
        res = supabase.table("profiles").select("*").eq("user_id", interaction.user.id).execute()

        profile = res.data[0] if res.data else {}

        await interaction.response.send_modal(ProfileModal(profile))
    @discord.ui.button(label="🟣 紫", style=discord.ButtonStyle.gray, row=1)
    async def purple_theme(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "purple")
        
    @discord.ui.button(label="🩷 ピンク", style=discord.ButtonStyle.gray, row=1)
    async def pink_theme(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "pink")

    @discord.ui.button(label="🔵 水色", style=discord.ButtonStyle.gray, row=1)
    async def blue_theme(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "blue")

    @discord.ui.button(label="🟢 緑", style=discord.ButtonStyle.gray, row=1)
    async def green_theme(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "green")

    @discord.ui.button(label="⚫ 黒", style=discord.ButtonStyle.gray, row=1)
    async def black_theme(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "black")

    @discord.ui.button(label="🔴 赤", style=discord.ButtonStyle.gray, row=2)
    async def red_theme(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "red")

    @discord.ui.button(label="🟠 オレンジ", style=discord.ButtonStyle.gray, row=2)
    async def orange_theme(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "orange")

    @discord.ui.button(label="🟡 黄色", style=discord.ButtonStyle.gray, row=2)
    async def yellow_theme(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "yellow")

    @discord.ui.button(label="⚪ 白", style=discord.ButtonStyle.gray, row=2)
    async def white_theme(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "white")
        
THEME_COLORS = {
    "purple": 0x8b5cf6,
    "pink": 0xff5fa2,
    "blue": 0x38bdf8,
    "green": 0x22c55e,
    "black": 0x2f3136,
    "red": 0xef4444,
    "orange": 0xf97316,
    "yellow": 0xfacc15,
    "white": 0xffffff,
}

class ThemeView(View):
    def __init__(self):
        super().__init__(timeout=None)
           
    async def save_theme(self, interaction: discord.Interaction, color_name: str):
        supabase.table("profiles").update({
            "theme_color": color_name
        }).eq("user_id", interaction.user.id).execute()

        profile_data = supabase.table("profiles").select("*").eq(
            "user_id",
            interaction.user.id
        ).execute()

        if not profile_data.data:
            await interaction.response.send_message(
                "先に自己紹介を作成してください！",
                ephemeral=True
            )
            return

        profile = profile_data.data[0]

        old_profile_message_id = profile.get("profile_message_id")

        if old_profile_message_id:
            try:
                old_message = await interaction.channel.fetch_message(
                    int(old_profile_message_id)
                )
                await old_message.delete()
            except:
                pass

        vc_res = supabase.table("vc_count").select("*").eq(
            "user_id",
            interaction.user.id
        ).execute()

        count = vc_res.data[0]["count"] if vc_res.data else 0

        theme_color = THEME_COLORS.get(color_name, 0x8b5cf6)

        embed = discord.Embed(
            title=f"🪪 {interaction.user.display_name} のプロフィール",
            color=theme_color
        )

        embed.description = (
            f"**👤 名前**\n"
            f"{profile.get('name') or '未設定'}\n\n"
            f"**💬 性格と接し方**\n"
            f"{profile.get('personality') or '未設定'}\n\n"
            f"**⚠️ 苦手・絡む時の注意**\n"
            f"{profile.get('caution') or '未設定'}\n\n"
            f"**🎮 やってるゲーム**\n"
            f"{profile.get('games') or '未設定'}\n\n"
            f"**📝 一言**\n"
            f"{profile.get('message') or '未設定'}\n\n"
            f"**🔥 連続出席日数**\n"
            f"{count}日"
        )

        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        profile_message = await interaction.channel.send(embed=embed)

        supabase.table("profiles").update({
            "profile_message_id": str(profile_message.id)
        }).eq("user_id", interaction.user.id).execute()

        old_panel_message_id = profile.get("panel_message_id")

        if old_panel_message_id:
            try:
                old_panel = await interaction.channel.fetch_message(
                    int(old_panel_message_id)
                )
                await old_panel.delete()
            except:
                pass

        panel_embed = discord.Embed(
            title="自己紹介生成",
            description="自己紹介の作成・修正、テーマカラー変更ができます。",
            color=theme_color
        )

        panel_message = await interaction.channel.send(
            embed=panel_embed,
            view=ProfileView()
        )

        supabase.table("profiles").update({
            "panel_message_id": str(panel_message.id)
        }).eq("user_id", interaction.user.id).execute()

        await interaction.response.send_message(
            f"✅ テーマを {color_name} に設定しました！",
            ephemeral=True
        )

    @discord.ui.button(label="🟣 紫", style=discord.ButtonStyle.gray, row=0)
    async def purple(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "purple")

    @discord.ui.button(label="🩷 ピンク", style=discord.ButtonStyle.gray, row=0)
    async def pink(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "pink")

    @discord.ui.button(label="🔵 水色", style=discord.ButtonStyle.gray, row=0)
    async def blue(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "blue")

    @discord.ui.button(label="🟢 緑", style=discord.ButtonStyle.gray, row=0)
    async def green(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "green")

    @discord.ui.button(label="⚫ 黒", style=discord.ButtonStyle.gray, row=0)
    async def black(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "black")

    @discord.ui.button(label="🔴 赤", style=discord.ButtonStyle.gray, row=1)
    async def red(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "red")

    @discord.ui.button(label="🟠 オレンジ", style=discord.ButtonStyle.gray, row=1)
    async def orange(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "orange")

    @discord.ui.button(label="🟡 黄色", style=discord.ButtonStyle.gray, row=1)
    async def yellow(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "yellow")

    @discord.ui.button(label="⚪ 白", style=discord.ButtonStyle.gray, row=1)
    async def white(self, interaction: discord.Interaction, button: Button):
        await self.save_theme(interaction, "white")
        
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

    if member is None:
        member = interaction.user

    try:
        res = supabase.table("vc_count").select("*").eq("user_id", member.id).execute()
        count = res.data[0]["count"] if res.data else 0

        await interaction.response.send_message(
            f"{member.display_name} の連続出席日数は **{count}日** です"
        )

    except Exception as e:
        print("ERROR:", repr(e), flush=True)
        
@bot.tree.command(name="出席ランキング", description="連続出席日数ランキング（上位10人）", guild=discord.Object(id=GUILD_ID))
async def ranking(interaction: discord.Interaction):
    try:
        res = supabase.table("vc_count").select("*").order(
            "count",
            desc=True
        ).limit(10).execute()

        if not res.data:
            await interaction.response.send_message("データがありません")
            return

        text = "🏆 連続出席日数ランキング（TOP10）\n\n"

        for i, row in enumerate(res.data, start=1):
            user_id = int(row["user_id"])
            member = interaction.guild.get_member(user_id)

            if member:
                name = member.display_name
            else:
                name = f"ID:{user_id}"

            text += f"{i}位：{name} - {row['count']}日\n"

        await interaction.response.send_message(
            text[:1900],
            allowed_mentions=discord.AllowedMentions.none()
        )

    except Exception as e:
        print("RANKING ERROR:", repr(e), flush=True)

@bot.tree.command(
    name="プロフィール",
    description="プロフィールを見る",
    guild=discord.Object(id=GUILD_ID)
)

async def profile_view(interaction: discord.Interaction, member: discord.Member = None):

    if member is None:
        member = interaction.user

    res = supabase.table("profiles").select("*").eq("user_id", member.id).execute()
    vc_res = supabase.table("vc_count").select("*").eq("user_id", member.id).execute()

    if not res.data:
        await interaction.response.send_message(
            f"{member.display_name} はまだプロフィール未設定です"
        )
        return

    profile = res.data[0]
    count = vc_res.data[0]["count"] if vc_res.data else 0

    theme_name = profile.get("theme_color") or "purple"
    theme_color = THEME_COLORS.get(theme_name, 0x8b5cf6)

    embed = discord.Embed(
        title=f"🪪 {member.display_name} のプロフィール",
        color=theme_color
    )

    embed.description = (
        f"**👤 名前**\n"
        f"{profile.get('name') or '未設定'}\n\n"

        f"**💬 性格と接し方**\n"
        f"{profile.get('personality') or '未設定'}\n\n"

        f"**⚠️ 苦手・絡む時の注意**\n"
        f"{profile.get('caution') or '未設定'}\n\n"

        f"**🎮 やってるゲーム**\n"
        f"{profile.get('games') or '未設定'}\n\n"

        f"**📝 一言**\n"
        f"{profile.get('message') or '未設定'}\n\n"

        f"**🔥 連続出席日数**\n"
        f"{count}日"
    )

    embed.set_thumbnail(url=member.display_avatar.url)

    embed.set_footer(
        text=f"User ID: {member.id}"
    )

    await interaction.response.send_message(embed=embed)

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
    if member.bot:
        return

    if after.channel is not None and before.channel != after.channel:
        count = update_vc(member.id)
        print(f"{member.display_name} の連続出席日数: {count}", flush=True)

        res = supabase.table("profiles").select("*").eq("user_id", member.id).execute()

        if not res.data:
            return

        profile = res.data[0] 

        theme_name = profile.get("theme_color") or "purple"
        theme_color = THEME_COLORS.get(theme_name, 0x8b5cf6)

        embed = discord.Embed(
            title=f"🎧 {member.display_name} さんがVCに参加しました",
            color=theme_color
        )

        embed.description = (
            f"**👤 名前**\n"
            f"{profile.get('name') or '未設定'}\n\n"

            f"**💬 性格と接し方**\n"
            f"{profile.get('personality') or '未設定'}\n\n"

            f"**⚠️ 苦手・絡む時の注意**\n"
            f"{profile.get('caution') or '未設定'}\n\n"

            f"**🎮 やってるゲーム**\n"
            f"{profile.get('games') or '未設定'}\n\n"

            f"**📝 一言**\n"
            f"{profile.get('message') or '未設定'}\n\n"

            f"**🔥 連続出席日数**\n"
            f"{count}日"
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        channel = after.channel

        await channel.send(embed=embed)

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

@bot.event
async def on_member_remove(member):
    channel = bot.get_channel(LOG_CHANNEL_ID)

    if channel is None:
        return

    join_date = member.joined_at

    if join_date:
        days = (discord.utils.utcnow() - join_date).days
        join_text = join_date.strftime("%Y/%m/%d")
    else:
        days = 0
        join_text = "不明"

    roles = [
        role.name
        for role in member.roles
        if role.name != "@everyone"
    ]

    role_text = " / ".join(roles) if roles else "なし"

    embed = discord.Embed(
        title="【生徒退出】",
        color=discord.Color.red()
    )

    embed.description = (
        f"{member.display_name}\n"
        f"ID：{member.id}\n\n"

        f"参加日\n"
        f"{join_text}\n\n"

        f"在籍日数\n"
        f"{days}日\n\n"

        f"ロール\n"
        f"{role_text}\n\n"

        f"退出日時\n"
        f"{datetime.now(pytz.timezone('Asia/Tokyo')).strftime('%Y/%m/%d %H:%M')}"
)
    
    embed.set_thumbnail(url=member.display_avatar.url)

    await channel.send(embed=embed)
        

keep_alive()
bot.run(TOKEN)
