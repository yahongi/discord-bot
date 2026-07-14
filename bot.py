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

class MemberSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(
            placeholder="付与するメンバーを選択",
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        member = self.values[0]

        await interaction.response.send_modal(
            AddCoinModal(member)
        )

class RemoveCoinModal(Modal):
    def __init__(self, member):
        super().__init__(title="個人からコイン没収")

        self.member = member

        self.amount = TextInput(
            label="没収金額",
            placeholder="例：1000",
            required=True
        )

        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)

            if amount <= 0:
                await interaction.response.send_message(
                    "没収金額は1以上にしてください。",
                    ephemeral=True
                )
                return

            res = supabase.table("coins").select("*").eq(
                "user_id",
                self.member.id
            ).execute()

            current = res.data[0]["coins"] if res.data else 0
            new = max(0, current - amount)

            supabase.table("coins").upsert({
                "user_id": self.member.id,
                "coins": new,
                "updated_at": str(get_today())
            }).execute()

            await interaction.response.send_message(
                f"{self.member.display_name} から **{amount:,}コイン** 没収しました\n"
                f"現在の所持金：**{new:,}コイン**",
                ephemeral=True
            )

        except Exception as e:
            print("REMOVE COIN ERROR:", repr(e), flush=True)

class MemberSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(MemberSelect())

class RemoveMemberSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(
            placeholder="没収するメンバーを選択",
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        member = self.values[0]
        await interaction.response.send_modal(
            RemoveCoinModal(member)
        )

class SetCoinModal(Modal):
    def __init__(self, member):
        super().__init__(title="個人の所持金設定")

        self.member = member

        self.amount = TextInput(
            label="設定金額",
            placeholder="例：5000",
            required=True
        )

        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "この操作は運営専用です。",
                    ephemeral=True
                )
                return

            try:
                amount = int(self.amount.value)
            except ValueError:
                await interaction.response.send_message(
                    "金額は数字で入力してください。",
                    ephemeral=True
                )
                return

            if amount < 0:
                await interaction.response.send_message(
                    "設定金額は0以上にしてください。",
                    ephemeral=True
                )
                return

            supabase.table("coins").upsert({
                "user_id": self.member.id,
                "coins": amount,
                "updated_at": str(get_today())
            }).execute()

            await interaction.response.send_message(
                f"{self.member.display_name} の所持金を "
                f"**{amount:,}コイン** に設定しました",
                ephemeral=True
            )

        except Exception as e:
            print("SET COIN MODAL ERROR:", repr(e), flush=True)

            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "所持金設定中にエラーが発生しました。",
                    ephemeral=True
                )

class AddAllCoinModal(Modal):
    def __init__(self):
        super().__init__(title="全員にコイン付与")

        self.amount = TextInput(
            label="付与金額",
            placeholder="例：1000",
            required=True
        )

        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "この操作は運営専用です。",
                    ephemeral=True
                )
                return

            try:
                amount = int(self.amount.value)
            except ValueError:
                await interaction.response.send_message(
                    "金額は数字で入力してください。",
                    ephemeral=True
                )
                return

            if amount <= 0:
                await interaction.response.send_message(
                    "付与金額は1以上にしてください。",
                    ephemeral=True
                )
                return

            await interaction.response.send_message(
                f"全員に **{amount:,}コイン** 付与します。\n"
                "本当に実行しますか？",
                view=AddAllConfirmView(amount),
                ephemeral=True
            )

        except Exception as e:
            print("ADD ALL COIN MODAL ERROR:", repr(e), flush=True)


class AddAllConfirmView(discord.ui.View):
    def __init__(self, amount: int):
        super().__init__(timeout=60)
        self.amount = amount

    @discord.ui.button(
        label="実行",
        style=discord.ButtonStyle.green
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        try:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "この操作は運営専用です。",
                    ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            members = [
                member
                for member in interaction.guild.members
                if not member.bot
            ]

            updated_count = 0

            for member in members:
                res = supabase.table("coins").select("*").eq(
                    "user_id",
                    member.id
                ).execute()

                current_coins = res.data[0]["coins"] if res.data else 0
                new_coins = current_coins + self.amount

                supabase.table("coins").upsert({
                    "user_id": member.id,
                    "coins": new_coins,
                    "updated_at": str(get_today())
                }).execute()

                updated_count += 1

            await interaction.followup.send(
                f"全員に **{self.amount:,}コイン** 付与しました。\n"
                f"対象人数：**{updated_count}人**",
                ephemeral=True
            )

            self.stop()

        except Exception as e:
            print("ADD ALL COINS ERROR:", repr(e), flush=True)

            await interaction.followup.send(
                "全員へのコイン付与中にエラーが発生しました。",
                ephemeral=True
            )

    @discord.ui.button(
        label="キャンセル",
        style=discord.ButtonStyle.gray
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="全員へのコイン付与をキャンセルしました。",
            view=None
        )

        self.stop()

class SetMemberSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(
            placeholder="金額を設定するメンバーを選択",
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        member = self.values[0]

        await interaction.response.send_modal(
            SetCoinModal(member)
        )
        

class SetMemberSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(SetMemberSelect())

class RemoveMemberSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(RemoveMemberSelect())

class AddCoinModal(Modal):
    def __init__(self, member):
        super().__init__(title="個人にコイン付与")

        self.member = member

        self.amount = TextInput(
            label="付与金額",
            placeholder="例：1000",
            required=True
        )

        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "この操作は運営専用です。",
                    ephemeral=True
                )
                return

            try:
                amount = int(self.amount.value)
            except ValueError:
                await interaction.response.send_message(
                    "金額は数字で入力してください。",
                    ephemeral=True
                )
                return

            if amount <= 0:
                await interaction.response.send_message(
                    "付与金額は1以上にしてください。",
                    ephemeral=True
                )
                return

            res = supabase.table("coins").select("*").eq(
                "user_id",
                self.member.id
            ).execute()

            current_coins = res.data[0]["coins"] if res.data else 0
            new_coins = current_coins + amount

            supabase.table("coins").upsert({
                "user_id": self.member.id,
                "coins": new_coins,
                "updated_at": str(get_today())
            }).execute()

            await interaction.response.send_message(
                f"{self.member.display_name} に "
                f"**{amount:,}コイン** 付与しました\n"
                f"現在の所持金：**{new_coins:,}コイン**",
                ephemeral=True
            )

        except Exception as e:
            print("ADD COIN MODAL ERROR:", repr(e), flush=True)

            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "コイン付与中にエラーが発生しました。",
                    ephemeral=True
                )


class CoinManageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "このパネルは運営専用です。",
                ephemeral=True
            )
            return False

        return True

    async def preparing(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "この機能は現在準備中です。",
            ephemeral=True
        )

    @discord.ui.button(
        label="個人に付与",
        style=discord.ButtonStyle.green,
        row=0
    )
    async def add_personal(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "付与するメンバーを選択してください。",
            view=MemberSelectView(),
            ephemeral=True
        )

    @discord.ui.button(
        label="個人から没収",
        style=discord.ButtonStyle.red,
        row=0
    )
    async def remove_personal(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "没収するメンバーを選択してください。",
            view=RemoveMemberSelectView(),
            ephemeral=True
        )

    @discord.ui.button(
        label="個人の金額設定",
        style=discord.ButtonStyle.blurple,
        row=0
    )
    async def set_personal(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "金額を設定するメンバーを選択してください。",
            view=SetMemberSelectView(),
            ephemeral=True
        )

    @discord.ui.button(
        label="全員に付与",
        style=discord.ButtonStyle.green,
        row=1
    )
    async def add_all(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(
            AddAllCoinModal()
        )

    @discord.ui.button(
        label="全員から没収",
        style=discord.ButtonStyle.red,
        row=1
    )
    async def remove_all(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.preparing(interaction)

    @discord.ui.button(
        label="全員の金額設定",
        style=discord.ButtonStyle.blurple,
        row=1
    )
    async def set_all(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.preparing(interaction)

    @discord.ui.button(
        label="閉じる",
        style=discord.ButtonStyle.gray,
        row=2
    )
    async def close_panel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="コイン管理パネルを閉じました。",
            embed=None,
            view=None
        )
        
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

async def create_ranking_text(guild, page: int):
    if page < 1:
        page = 1

    start = (page - 1) * 10
    end = start + 9

    res = supabase.table("vc_count").select("*").order(
        "count",
        desc=True
    ).range(start, end).execute()

    if not res.data:
        return "データがありません"

    text = (
        f"🏆 連続出席日数ランキング\n"
        f"（{start + 1}位 ～ {start + len(res.data)}位）\n\n"
    )

    for i, row in enumerate(res.data, start=start + 1):
        user_id = int(row["user_id"])
        member = guild.get_member(user_id)

        if member:
            name = member.display_name
        else:
            name = f"ID:{user_id}"

        text += f"{i}位：{name} - {row['count']}日\n"

    return text


class RankingView(discord.ui.View):
    def __init__(self, page: int):
        super().__init__(timeout=None)
        self.page = page

    @discord.ui.button(label="前へ", style=discord.ButtonStyle.gray)
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        if self.page <= 1:
            await interaction.response.send_message(
                "これ以上前のページはありません",
                ephemeral=True
            )
            return

        self.page -= 1
        text = await create_ranking_text(interaction.guild, self.page)

        await interaction.response.edit_message(
            content=text,
            view=self
        )

    @discord.ui.button(label="次へ", style=discord.ButtonStyle.gray)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        self.page += 1
        text = await create_ranking_text(interaction.guild, self.page)

        if text == "データがありません":
            self.page -= 1
            await interaction.response.send_message(
                "これ以上次のページはありません",
                ephemeral=True
            )
            return

        await interaction.response.edit_message(
            content=text,
            view=self
        )
        
@bot.tree.command(name="出席ランキング", description="連続出席日数ランキングをページごとに見る", guild=discord.Object(id=GUILD_ID))
async def ranking(
    interaction: discord.Interaction,
    page: int = 1
):
    try:
        text = await create_ranking_text(interaction.guild, page)

        if text == "データがありません":
            await interaction.response.send_message("データがありません")
            return

        await interaction.response.send_message(
            text[:1900],
            view=RankingView(page),
            allowed_mentions=discord.AllowedMentions.none()
        )

    except Exception as e:
        print("RANKING ERROR:", repr(e), flush=True)
        
@bot.tree.command(
    name="自分の順位",
    description="自分の連続出席順位を見る",
    guild=discord.Object(id=GUILD_ID)
)
async def myrank(interaction: discord.Interaction):
    try:
        res = supabase.table("vc_count").select("*").order(
            "count",
            desc=True
        ).execute()

        if not res.data:
            await interaction.response.send_message("データがありません")
            return

        for i, row in enumerate(res.data, start=1):
            if int(row["user_id"]) == interaction.user.id:
                await interaction.response.send_message(
                    f"🏆 あなたの順位\n\n"
                    f"順位：{i}位\n"
                    f"連続出席：{row['count']}日"
                )
                return

        await interaction.response.send_message(
            "まだ出席記録がありません"
        )

    except Exception as e:
        print("MYRANK ERROR:", repr(e), flush=True)

@bot.tree.command(
    name="順位",
    description="指定した人の連続出席順位を見る",
    guild=discord.Object(id=GUILD_ID)
)
async def member_rank(interaction: discord.Interaction, member: discord.Member):
    try:
        res = supabase.table("vc_count").select("*").order(
            "count",
            desc=True
        ).execute()

        if not res.data:
            await interaction.response.send_message("データがありません")
            return

        for i, row in enumerate(res.data, start=1):
            if int(row["user_id"]) == member.id:
                await interaction.response.send_message(
                    f"🏆 順位\n\n"
                    f"対象：{member.display_name}\n"
                    f"順位：{i}位\n"
                    f"連続出席：{row['count']}日"
                )
                return

        await interaction.response.send_message(
            f"{member.display_name} の出席記録がありません"
        )

    except Exception as e:
        print("MEMBER RANK ERROR:", repr(e), flush=True)

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
    name="所持金",
    description="自分の所持コインを確認する",
    guild=discord.Object(id=GUILD_ID)
)
async def balance(interaction: discord.Interaction):
    try:
        res = supabase.table("coins").select("*").eq(
            "user_id",
            interaction.user.id
        ).execute()

        coins = res.data[0]["coins"] if res.data else 0

        await interaction.response.send_message(
            f"所持金：**{coins:,}コイン**"
        )

    except Exception as e:
        print("BALANCE ERROR:", repr(e), flush=True)

@bot.tree.command(
    name="コイン管理",
    description="運営用のコイン管理パネルを開く",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.default_permissions(administrator=True)
async def coin_manage(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "このコマンドは運営専用です。",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="コイン管理",
        description=(
            "**個人操作**\n"
            "個人への付与・没収・金額設定\n\n"
            "**全体操作**\n"
            "全員への付与・没収・金額設定\n\n"
            "下のボタンから操作を選択してください。"
        ),
        color=0xf5b642
    )

    await interaction.response.send_message(
        embed=embed,
        view=CoinManageView(),
        ephemeral=True
    )

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

    try:
        await channel.send(embed=embed)
    except discord.HTTPException as e:
        print("MEMBER REMOVE LOG SEND ERROR:", repr(e), flush=True)
        

keep_alive()
bot.run(TOKEN)
