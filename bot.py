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
import random
import asyncio

def get_today():
    tz = pytz.timezone("Asia/Tokyo")
    return datetime.now(tz).date()

def get_slot_setting_date():
    tz = pytz.timezone("Asia/Tokyo")
    now = datetime.now(tz)

    # 毎朝9時に設定更新
    if now.hour < 9:
        return (now.date() - timedelta(days=1)).isoformat()

    return now.date().isoformat()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

TOKEN = os.environ["TOKEN"]
GUILD_ID = 1463536665632051213
LOG_CHANNEL_ID = 1513382077771546886

MALE_INTRO_CHANNEL_ID = 1463538621293396152
FEMALE_INTRO_CHANNEL_ID = 1463538649915330601
FLOWER_LOG_CHANNEL_ID = 1526955808317898762
TWO_MATCH_MULTIPLIERS = {
    1: 1.1,
    2: 1.2,
    3: 1.3,
    4: 1.4,
    5: 1.5,
    6: 1.6,
    7: 1.7,
    8: 1.8,
    9: 1.9
}

THREE_MATCH_MULTIPLIERS = {
    1: 2.0,
    2: 2.5,
    3: 3.0,
    4: 4.0,
    5: 5.0,
    6: 6.0,
    8: 8.0,
    9: 9.0
}

SLOT_INFO_PRICES = {
    0: 0,
    1: 200,
    2: 500,
    3: 1500
}

SLOT_INFO_NAMES = {
    0: "未購入",
    1: "簡易情報",
    2: "詳細情報",
    3: "設定確定情報"
}


def judge_slot_result(reels: list[int], bet: int):
    first, second, third = reels

    # 3つ揃い
    if first == second == third:
        if first == 7:
            return {
                "type": "jackpot",
                "payout": 0,
                "text": "777 ジャックポット"
            }

        multiplier = THREE_MATCH_MULTIPLIERS[first]
        payout = int(bet * multiplier)

        return {
            "type": "three",
            "payout": payout,
            "text": f"{first}が3つ揃い・{multiplier:g}倍"
        }

    # 2つ揃い
    matched_number = None

    if first == second:
        matched_number = first
    elif first == third:
        matched_number = first
    elif second == third:
        matched_number = second

    if matched_number is not None:
        multiplier = TWO_MATCH_MULTIPLIERS[matched_number]
        payout = int(bet * multiplier)

        return {
            "type": "two",
            "payout": payout,
            "text": f"{matched_number}が2つ揃い・{multiplier:g}倍"
        }

    return {
        "type": "lose",
        "payout": 0,
        "text": "ハズレ"
    }

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

# 使用中のスロット台
# {台番号: ユーザーID}
ACTIVE_MACHINES = {}

class SlotMachineView(discord.ui.View):
    def __init__(self, owner_id: int, machine_id: int, bet: int):
        super().__init__(timeout=300)

        self.owner_id = owner_id
        self.machine_id = machine_id
        self.bet = bet
        self.running = False

    async def on_timeout(self):
        if ACTIVE_MACHINES.get(self.machine_id) == self.owner_id:
            ACTIVE_MACHINES.pop(self.machine_id, None)

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "このスロット台は他のユーザーが操作中です。",
                ephemeral=True
            )
            return False

        return True

    @discord.ui.button(
        label="スロットSTART",
        style=discord.ButtonStyle.green,
        row=0
    )
    async def start_slot(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if self.running:
            await interaction.response.send_message(
                "すでに回転中です。",
                ephemeral=True
            )
            return

        self.running = True
        await interaction.response.defer()

        try:
            balance_res = supabase.table("coins").select("*").eq(
                "user_id",
                interaction.user.id
            ).execute()

            current_flower = (
                balance_res.data[0]["coins"]
                if balance_res.data
                else 0
            )

            if current_flower < self.bet:
                self.running = False

                await interaction.followup.send(
                    f"フラワーが足りません。\n"
                    f"必要：**{self.bet:,}フラワー**\n"
                    f"現在：**{current_flower:,}フラワー**",
                    ephemeral=True
                )
                return

            after_bet = current_flower - self.bet

            supabase.table("coins").upsert({
                "user_id": interaction.user.id,
                "coins": after_bet,
                "updated_at": str(get_today())
            }).execute()

            reels = [
                random.randint(1, 9),
                random.randint(1, 9),
                random.randint(1, 9)
            ]

            def reel_box(a, b, c):
                return (
                    "```text\n"
                    "┏━━━━━━━━━━━━━━━┓\n"
                    f"┃   {a}   │   {b}   │   {c}   ┃\n"
                    "┗━━━━━━━━━━━━━━━┛\n"
                    "```"
                )

            spin_embed = discord.Embed(
                title=f"スロットマシン #{self.machine_id}",
                description=(
                    f"プレイヤー：{interaction.user.mention}\n"
                    f"BET：**{self.bet:,}フラワー**\n\n"
                    f"{reel_box('?', '?', '?')}\n"
                    "リール回転中..."
                ),
                color=discord.Color.gold()
            )

            spin_embed.set_thumbnail(
                url=interaction.user.display_avatar.url
            )

            await interaction.edit_original_response(
                embed=spin_embed,
                view=None
            )

            for _ in range(7):
                temp = [
                    random.randint(1, 9),
                    random.randint(1, 9),
                    random.randint(1, 9)
                ]

                spin_embed.description = (
                    f"プレイヤー：{interaction.user.mention}\n"
                    f"BET：**{self.bet:,}フラワー**\n\n"
                    f"{reel_box(temp[0], temp[1], temp[2])}\n"
                    "全リール回転中..."
                )

                await interaction.edit_original_response(
                    embed=spin_embed
                )

                await asyncio.sleep(0.18)

            for _ in range(4):
                middle = random.randint(1, 9)
                right = random.randint(1, 9)

                spin_embed.description = (
                    f"プレイヤー：{interaction.user.mention}\n"
                    f"BET：**{self.bet:,}フラワー**\n\n"
                    f"{reel_box(reels[0], middle, right)}\n"
                    "左リール停止"
                )

                await interaction.edit_original_response(
                    embed=spin_embed
                )

                await asyncio.sleep(0.2)

            for _ in range(5):
                right = random.randint(1, 9)

                spin_embed.description = (
                    f"プレイヤー：{interaction.user.mention}\n"
                    f"BET：**{self.bet:,}フラワー**\n\n"
                    f"{reel_box(reels[0], reels[1], right)}\n"
                )

                if reels[0] == reels[1]:
                    spin_embed.title = (
                        f"リーチ！ マシン #{self.machine_id}"
                    )
                    spin_embed.color = discord.Color.orange()
                    spin_embed.description += "最後のリールに注目..."
                else:
                    spin_embed.title = (
                        f"スロットマシン #{self.machine_id}"
                    )
                    spin_embed.color = discord.Color.gold()
                    spin_embed.description += "中央リール停止"

                await interaction.edit_original_response(
                    embed=spin_embed
                )

                await asyncio.sleep(
                    0.3 if reels[0] == reels[1] else 0.2
                )

            await asyncio.sleep(0.5)

            result = judge_slot_result(reels, self.bet)

            payout = result["payout"]
            final_flower = after_bet + payout
            profit = payout - self.bet

            supabase.table("coins").upsert({
                "user_id": interaction.user.id,
                "coins": final_flower,
                "updated_at": str(get_today())
            }).execute()

            if result["type"] == "lose":
                title = f"LOSE - マシン #{self.machine_id}"
                color = discord.Color.red()
            elif result["type"] == "two":
                title = f"WIN - マシン #{self.machine_id}"
                color = discord.Color.blue()
            elif result["type"] == "three":
                title = f"BIG WIN - マシン #{self.machine_id}"
                color = discord.Color.green()
            else:
                title = f"JACKPOT - マシン #{self.machine_id}"
                color = discord.Color.gold()

            result_embed = discord.Embed(
                title=title,
                description=(
                    f"プレイヤー：{interaction.user.mention}\n"
                    f"BET：**{self.bet:,}フラワー**\n\n"
                    f"{reel_box(reels[0], reels[1], reels[2])}\n"
                    f"結果：**{result['text']}**\n\n"
                    f"配当：**{payout:,}フラワー**\n"
                    f"損益：**{profit:+,}フラワー**\n"
                    f"所持フラワー："
                    f"**{final_flower:,}フラワー**"
                ),
                color=color
            )

            result_embed.set_thumbnail(
                url=interaction.user.display_avatar.url
            )

            await interaction.edit_original_response(
                embed=result_embed,
                view=SlotMachineView(
                    owner_id=self.owner_id,
                    machine_id=self.machine_id,
                    bet=self.bet
                )
            )

        except Exception as e:
            print("SLOT BUTTON ERROR:", repr(e), flush=True)

            try:
                await interaction.followup.send(
                    "スロット処理中にエラーが発生しました。",
                    ephemeral=True
                )
            except Exception:
                pass

        finally:
            self.running = False

    @discord.ui.button(
        label="台情報を見る",
        style=discord.ButtonStyle.blurple,
        row=0
    )
    async def machine_info(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        embed = discord.Embed(
            title=f"📄 マシン #{self.machine_id:03} 情報",
            description=(
                "購入する情報を選んでください。\n\n"
                f"🟦 簡易情報：{SLOT_INFO_PRICES[1]}🌸\n"
                f"🟪 詳細情報：{SLOT_INFO_PRICES[2]}🌸\n"
                f"🟨 設定確定：{SLOT_INFO_PRICES[3]}🌸"
            ),
            color=0x5865F2
        )
        await interaction.response.send_message(
            embed=embed,
            view=SlotInfoView(
                machine_id=self.machine_id,
                owner_id=interaction.user.id
            ),
            ephemeral=True
        )
        
    @discord.ui.button(
        label="台を離れる",
        style=discord.ButtonStyle.red,
        row=0
    )
    async def leave_machine(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if self.running:
            await interaction.response.send_message(
                "回転中は台から離れられません。",
                ephemeral=True
            )
            return

        if ACTIVE_MACHINES.get(self.machine_id) == self.owner_id:
            ACTIVE_MACHINES.pop(self.machine_id, None)

        leave_embed = discord.Embed(
            title=f"スロットマシン #{self.machine_id:03}",
            description=(
                f"{interaction.user.mention} が台を離れました。\n\n"
                "台の状態：**空席**"
            ),
            color=discord.Color.gray()
        )

        await interaction.response.edit_message(
            embed=leave_embed,
            view=None
        )

        self.stop()

class SlotInfoView(discord.ui.View):
    def __init__(self, machine_id: int, owner_id: int):
        super().__init__(timeout=180)

        self.machine_id = machine_id
        self.owner_id = owner_id

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "この情報画面は他のユーザー用です。",
                ephemeral=True
            )
            return False

        return True

    async def purchase_info(
        self,
        interaction: discord.Interaction,
        target_level: int
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            setting_date = get_slot_setting_date()

            purchase_res = supabase.table(
                "slot_info_purchases"
            ).select("*").eq(
                "user_id",
                interaction.user.id
            ).eq(
                "machine_id",
                self.machine_id
            ).eq(
                "setting_date",
                setting_date
            ).execute()

            current_level = (
                purchase_res.data[0]["info_level"]
                if purchase_res.data
                else 0
            )

            if current_level >= target_level:
                await interaction.followup.send(
                    f"{SLOT_INFO_NAMES[target_level]}は購入済みです。",
                    ephemeral=True
                )
                return

            current_price = SLOT_INFO_PRICES[current_level]
            target_price = SLOT_INFO_PRICES[target_level]
            price_to_pay = target_price - current_price

            balance_res = supabase.table("coins").select("*").eq(
                "user_id",
                interaction.user.id
            ).execute()

            current_flower = (
                balance_res.data[0]["coins"]
                if balance_res.data
                else 0
            )

            if current_flower < price_to_pay:
                await interaction.followup.send(
                    "フラワーが足りません。\n"
                    f"必要：**{price_to_pay:,}フラワー**\n"
                    f"現在：**{current_flower:,}フラワー**",
                    ephemeral=True
                )
                return

            new_flower = current_flower - price_to_pay

            supabase.table("coins").upsert({
                "user_id": interaction.user.id,
                "coins": new_flower,
                "updated_at": str(get_today())
            }).execute()

            supabase.table("slot_info_purchases").upsert({
                "user_id": interaction.user.id,
                "machine_id": self.machine_id,
                "info_level": target_level,
                "setting_date": setting_date,
                "updated_at": str(
                    datetime.now(
                        pytz.timezone("Asia/Tokyo")
                    )
                )
            }).execute()

            await interaction.followup.send(
                (
                    f"マシン #{self.machine_id:03} の "
                    f"**{SLOT_INFO_NAMES[target_level]}**を購入しました。\n"
                    f"支払い：**{price_to_pay:,}フラワー**\n"
                    f"残高：**{new_flower:,}フラワー**\n\n"
                    "実際の情報表示は次に追加します。"
                ),
                ephemeral=True
            )

        except Exception as e:
            print("SLOT INFO PURCHASE ERROR:", repr(e), flush=True)

            await interaction.followup.send(
                "台情報の購入中にエラーが発生しました。",
                ephemeral=True
            )

    @discord.ui.button(
        label="簡易情報",
        style=discord.ButtonStyle.gray
    )
    async def simple_info(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.purchase_info(interaction, 1)

    @discord.ui.button(
        label="詳細情報",
        style=discord.ButtonStyle.blurple
    )
    async def detail_info(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.purchase_info(interaction, 2)

    @discord.ui.button(
        label="設定確定",
        style=discord.ButtonStyle.green
    )
    async def setting_info(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.purchase_info(interaction, 3)

class SlotMachineButton(discord.ui.Button):
    def __init__(
        self,
        machine_id: int,
        owner_id: int,
        bet: int,
        row: int
    ):
        is_occupied = machine_id in ACTIVE_MACHINES

        super().__init__(
            label=f"{machine_id:03}",
            style=(
                discord.ButtonStyle.red
                if is_occupied
                else discord.ButtonStyle.green
            ),
            disabled=is_occupied,
            row=row
        )

        self.machine_id = machine_id
        self.owner_id = owner_id
        self.bet = bet
        
    async def callback(
        self,
        interaction: discord.Interaction
    ):
        # 押した瞬間にほかの人が確保していないか再確認
        current_owner = ACTIVE_MACHINES.get(self.machine_id)

        if current_owner is not None:
            await interaction.response.send_message(
                "この台は現在ほかのユーザーが遊技中です。",
                ephemeral=True
            )
            return

        # すでに別の台を使っていないか確認
        owned_machine = next(
            (
                machine_id
                for machine_id, user_id in ACTIVE_MACHINES.items()
                if user_id == interaction.user.id
            ),
            None
        )

        if owned_machine is not None:
            await interaction.response.send_message(
                f"すでにマシン #{owned_machine:03} を使用中です。\n"
                "先に現在の台から離れてください。",
                ephemeral=True
            )
            return

        # 台を確保
        ACTIVE_MACHINES[self.machine_id] = interaction.user.id

        embed = discord.Embed(
            title=f"スロットマシン #{self.machine_id:03}",
            description=(
                f"**プレイヤー**\n"
                f"{interaction.user.mention}\n\n"
                f"**BET**\n"
                f"{self.bet:,}フラワー\n\n"
                f"**台情報**\n"
                f"未購入"
            ),
            color=0xD4AF37
        )
        embed.set_thumbnail(
            url=interaction.user.display_avatar.url
        )

        try:
            await interaction.response.send_message(
                embed=embed,
                view=SlotMachineView(
                    owner_id=interaction.user.id,
                    machine_id=self.machine_id,
                    bet=self.bet
                )
            )

        except Exception:
            # メッセージ送信に失敗したら台を開放
            if ACTIVE_MACHINES.get(self.machine_id) == interaction.user.id:
                ACTIVE_MACHINES.pop(self.machine_id, None)

            raise

class SlotMachineSelectView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        bet: int,
        page: int = 1
    ):
        super().__init__(timeout=300)

        self.owner_id = owner_id
        self.bet = bet
        self.page = page

        start = (page - 1) * 16 + 1
        end = min(start + 15, 100)

        for index, machine_id in enumerate(range(start, end + 1)):
            button_row = index // 4
            
            self.add_item(
                SlotMachineButton(
                    machine_id=machine_id,
                    owner_id=owner_id,
                    bet=bet,
                    row=button_row
                )
            )

        self.prev_page.disabled = page <= 1
        self.next_page.disabled = page >= 7

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "この台選択パネルは他のユーザー用です。",
                ephemeral=True
            )
            return False

        return True

    def create_embed(self) -> discord.Embed:
        start = (self.page - 1) * 16 + 1
        end = min(start + 15, 100)

        embed = discord.Embed(
            title="Flower Casino",
            description=(
                f"BET：**{self.bet:,}フラワー**\n"
                f"台番号：**#{start:03} ～ #{end:03}**\n\n"
                "緑：空席　赤：使用中"
            ),
            color=0xD4AF37
        )
        
        embed.set_footer(
            text=f"{self.page} / 7"
        )

        return embed

    @discord.ui.button(
        label="前へ",
        style=discord.ButtonStyle.gray,
        row=4
    )
    async def prev_page(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if self.page <= 1:
            await interaction.response.send_message(
                "これ以上前のページはありません。",
                ephemeral=True
            )
            return

        new_view = SlotMachineSelectView(
            owner_id=self.owner_id,
            bet=self.bet,
            page=self.page - 1
        )

        await interaction.response.edit_message(
            embed=new_view.create_embed(),
            view=new_view
        )

    @discord.ui.button(
        label="次へ",
        style=discord.ButtonStyle.gray,
        row=4
    )
    async def next_page(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if self.page >= 7:
            await interaction.response.send_message(
                "これ以上次のページはありません。",
                ephemeral=True
            )
            return

        new_view = SlotMachineSelectView(
            owner_id=self.owner_id,
            bet=self.bet,
            page=self.page + 1
        )

        await interaction.response.edit_message(
            embed=new_view.create_embed(),
            view=new_view
        )

@bot.tree.command(
    name="スロット",
    description="台を選んでスロットを遊ぶ",
    guild=discord.Object(id=GUILD_ID)
)
async def slot(
    interaction: discord.Interaction,
    bet: int
):
    if bet <= 0:
        await interaction.response.send_message(
            "BET額は1以上にしてください。",
            ephemeral=True
        )
        return

    select_view = SlotMachineSelectView(
        owner_id=interaction.user.id,
        bet=bet,
        page=1
    )

    await interaction.response.send_message(
        embed=select_view.create_embed(),
        view=select_view,
        ephemeral=True
    )

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
        super().__init__(title="個人からフラワー没収")

        self.member = member

        self.amount = TextInput(
            label="没収フラワー",
            placeholder="例：1000",
            required=True
        )

        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)

            if amount <= 0:
                await interaction.response.send_message(
                    "没収フラワーは1以上にしてください。",
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
                f"{self.member.display_name} から **{amount:,}フラワー** 没収しました\n"
                f"現在の所持フラワー：**{new:,}フラワー**",
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
        super().__init__(title="個人の所持フラワー設定")

        self.member = member

        self.amount = TextInput(
            label="設定フラワー",
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
                    "フラワーは数字で入力してください。",
                    ephemeral=True
                )
                return

            if amount < 0:
                await interaction.response.send_message(
                    "設定フラワーは0以上にしてください。",
                    ephemeral=True
                )
                return

            supabase.table("coins").upsert({
                "user_id": self.member.id,
                "coins": amount,
                "updated_at": str(get_today())
            }).execute()

            await interaction.response.send_message(
                f"{self.member.display_name} の所持フラワーを "
                f"**{amount:,}フラワー** に設定しました",
                ephemeral=True
            )

        except Exception as e:
            print("SET COIN MODAL ERROR:", repr(e), flush=True)

            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "所持フラワー設定中にエラーが発生しました。",
                    ephemeral=True
                )

class AddAllCoinModal(Modal):
    def __init__(self):
        super().__init__(title="全員にフラワー付与")

        self.amount = TextInput(
            label="付与フラワー",
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
                    "フラワーは数字で入力してください。",
                    ephemeral=True
                )
                return

            if amount <= 0:
                await interaction.response.send_message(
                    "付与フラワーは1以上にしてください。",
                    ephemeral=True
                )
                return

            await interaction.response.send_message(
                f"全員に **{amount:,}フラワー** 付与します。\n"
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
                f"全員に **{self.amount:,}フラワー** 付与しました。\n"
                f"対象人数：**{updated_count}人**",
                ephemeral=True
            )

            self.stop()

        except Exception as e:
            print("ADD ALL COINS ERROR:", repr(e), flush=True)

            await interaction.followup.send(
                "全員へのフラワー付与中にエラーが発生しました。",
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
            content="全員へのフラワー付与をキャンセルしました。",
            view=None
        )

        self.stop()

class RemoveAllCoinModal(Modal):
    def __init__(self):
        super().__init__(title="全員からフラワー没収")

        self.amount = TextInput(
            label="没収フラワー",
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
                    "フラワーは数字で入力してください。",
                    ephemeral=True
                )
                return

            if amount <= 0:
                await interaction.response.send_message(
                    "没収フラワーは1以上にしてください。",
                    ephemeral=True
                )
                return

            await interaction.response.send_message(
                f"全員から **{amount:,}フラワー** 没収します。\n"
                "所持フラワーは0未満になりません。\n"
                "本当に実行しますか？",
                view=RemoveAllConfirmView(amount),
                ephemeral=True
            )

        except Exception as e:
            print("REMOVE ALL COIN MODAL ERROR:", repr(e), flush=True)

            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "確認画面の表示中にエラーが発生しました。",
                    ephemeral=True
                )


class RemoveAllConfirmView(discord.ui.View):
    def __init__(self, amount: int):
        super().__init__(timeout=60)
        self.amount = amount

    @discord.ui.button(
        label="実行",
        style=discord.ButtonStyle.red
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "この操作は運営専用です。",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
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
                new_coins = max(0, current_coins - self.amount)

                supabase.table("coins").upsert({
                    "user_id": member.id,
                    "coins": new_coins,
                    "updated_at": str(get_today())
                }).execute()

                updated_count += 1

            await interaction.followup.send(
                f"全員から **{self.amount:,}フラワー** 没収しました。\n"
                f"対象人数：**{updated_count}人**",
                ephemeral=True
            )

            self.stop()

        except Exception as e:
            print("REMOVE ALL COINS ERROR:", repr(e), flush=True)

            await interaction.followup.send(
                "全員からのフラワー没収中にエラーが発生しました。",
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
            content="全員からのフラワー没収をキャンセルしました。",
            view=None
        )

        self.stop()



class SetMemberSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(
            placeholder="フラワーを設定するメンバーを選択",
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        member = self.values[0]

        await interaction.response.send_modal(
            SetCoinModal(member)
        )
        
class SetAllCoinModal(Modal):
    def __init__(self):
        super().__init__(title="全員の所持フラワー設定")

        self.amount = TextInput(
            label="設定フラワー",
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
                    "フラワーは数字で入力してください。",
                    ephemeral=True
                )
                return

            if amount < 0:
                await interaction.response.send_message(
                    "0以上を入力してください。",
                    ephemeral=True
                )
                return

            await interaction.response.send_message(
                f"全員の所持フラワーを **{amount:,}フラワー** に設定します。\n"
                "本当に実行しますか？",
                view=SetAllConfirmView(amount),
                ephemeral=True
            )

        except Exception as e:
            print("SET ALL MODAL ERROR:", repr(e), flush=True)

class SetAllConfirmView(discord.ui.View):
    def __init__(self, amount):
        super().__init__(timeout=60)
        self.amount = amount

    @discord.ui.button(
        label="実行",
        style=discord.ButtonStyle.blurple
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        members = [
            m for m in interaction.guild.members
            if not m.bot
        ]

        for member in members:
            supabase.table("coins").upsert({
                "user_id": member.id,
                "coins": self.amount,
                "updated_at": str(get_today())
            }).execute()

        await interaction.followup.send(
            f"全員の所持フラワーを **{self.amount:,}フラワー** に設定しました。",
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
            content="キャンセルしました。",
            view=None
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
        super().__init__(title="個人にフラワー付与")

        self.member = member

        self.amount = TextInput(
            label="付与フラワー",
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
                    "フラワーは数字で入力してください。",
                    ephemeral=True
                )
                return

            if amount <= 0:
                await interaction.response.send_message(
                    "付与フラワーは1以上にしてください。",
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
                f"**{amount:,}フラワー** 付与しました\n"
                f"現在の所持フラワー：**{new_coins:,}フラワー**",
                ephemeral=True
            )

        except Exception as e:
            print("ADD COIN MODAL ERROR:", repr(e), flush=True)

            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "フラワー付与中にエラーが発生しました。",
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
        label="個人のフラワー設定",
        style=discord.ButtonStyle.blurple,
        row=0
    )
    async def set_personal(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "フラワーを設定するメンバーを選択してください。",
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
        await interaction.response.send_modal(
            RemoveAllCoinModal()
        )

    @discord.ui.button(
        label="全員のフラワー設定",
        style=discord.ButtonStyle.blurple,
        row=1
    )
    async def set_all(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(
            SetAllCoinModal()
        )

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
            content="フラワー管理パネルを閉じました。",
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

async def create_flower_ranking_text(guild, page: int):
    if page < 1:
        page = 1

    start = (page - 1) * 10
    end = start + 9

    res = supabase.table("coins").select("*").order(
        "coins",
        desc=True
    ).range(start, end).execute()

    if not res.data:
        return "データがありません"

    text = (
        f"フラワーランキング\n"
        f"（{start + 1}位 ～ {start + len(res.data)}位）\n\n"
    )

    for i, row in enumerate(res.data, start=start + 1):
        user_id = int(row["user_id"])
        member = guild.get_member(user_id)

        if member:
            name = member.display_name
        else:
            name = f"ID:{user_id}"

        text += f"{i}位：{name} - {row['coins']:,}フラワー\n"

    return text

class FlowerRankingView(discord.ui.View):
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

        text = await create_flower_ranking_text(
            interaction.guild,
            self.page
        )

        await interaction.response.edit_message(
            content=text,
            view=self
        )

    @discord.ui.button(label="次へ", style=discord.ButtonStyle.gray)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        self.page += 1

        text = await create_flower_ranking_text(
            interaction.guild,
            self.page
        )

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
    name="フラワーランキング",
    description="所持フラワーランキングをページごとに見る",
    guild=discord.Object(id=GUILD_ID)
)
async def flower_ranking(
    interaction: discord.Interaction,
    page: int = 1
):
    try:
        text = await create_flower_ranking_text(
            interaction.guild,
            page
        )

        if text == "データがありません":
            await interaction.response.send_message(
                "データがありません"
            )
            return

        await interaction.response.send_message(
            text[:1900],
            view=FlowerRankingView(page),
            allowed_mentions=discord.AllowedMentions.none()
        )

    except Exception as e:
        print("FLOWER RANKING ERROR:", repr(e), flush=True)

@bot.tree.command(
    name="花贈り",
    description="指定したメンバーへフラワーを贈る",
    guild=discord.Object(id=GUILD_ID)
)
async def flower_transfer(
    interaction: discord.Interaction,
    member: discord.Member,
    amount: int,
    reason: str = None
):
    await interaction.response.defer(ephemeral=True)

    try:
        if member.bot:
            await interaction.followup.send(
                "Botには花贈りできません。",
                ephemeral=True
            )
            return

        if member.id == interaction.user.id:
            await interaction.followup.send(
                "自分自身には花贈りできません。",
                ephemeral=True
            )
            return

        if amount <= 0:
            await interaction.followup.send(
                "贈るフラワーは1以上にしてください。",
                ephemeral=True
            )
            return

        sender_res = supabase.table("coins").select("*").eq(
            "user_id",
            interaction.user.id
        ).execute()

        sender_coins = sender_res.data[0]["coins"] if sender_res.data else 0

        if sender_coins < amount:
            await interaction.followup.send(
                f"フラワーが足りません。\n"
                f"現在の所持フラワー：**{sender_coins:,}フラワー**",
                ephemeral=True
            )
            return

        receiver_res = supabase.table("coins").select("*").eq(
            "user_id",
            member.id
        ).execute()

        receiver_coins = receiver_res.data[0]["coins"] if receiver_res.data else 0

        new_sender_coins = sender_coins - amount
        new_receiver_coins = receiver_coins + amount

        supabase.table("coins").upsert({
            "user_id": interaction.user.id,
            "coins": new_sender_coins,
            "updated_at": str(get_today())
        }).execute()

        supabase.table("coins").upsert({
            "user_id": member.id,
            "coins": new_receiver_coins,
            "updated_at": str(get_today())
        }).execute()

        reason_text = (
            reason.strip()
            if reason and reason.strip()
            else "理由なし"
        )

        await interaction.followup.send(
            f"{member.display_name} に **{amount:,}フラワー** 贈りました。\n"
            f"理由：**{reason_text}**\n"
            f"現在の所持フラワー：**{new_sender_coins:,}フラワー**",
            ephemeral=True
        )

        log_channel = interaction.guild.get_channel(
            FLOWER_LOG_CHANNEL_ID
        )

        if log_channel:
            embed = discord.Embed(
                title="花贈りログ",
                color=0x2F3136
            )

            embed.set_author(
                name=f"贈り主：{interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )

            embed.set_thumbnail(
                url=member.display_avatar.url
            )

            embed.add_field(
                name="贈り主",
                value=(
                    f"{interaction.user.display_name}\n"
                    f"ID：{interaction.user.id}"
                ),
                inline=False
            )

            embed.add_field(
                name="受取人",
                value=(
                    f"{member.display_name}\n"
                    f"ID：{member.id}"
                ),
                inline=False
            )

            embed.add_field(
                name="贈ったフラワー",
                value=f"{amount:,} フラワー",
                inline=False
            )

            embed.add_field(
                name="理由",
                value=reason_text,
                inline=False
            )

            embed.add_field(
                name="贈与後残高",
                value=(
                    f"贈り主：{new_sender_coins:,} フラワー\n"
                    f"受取人：{new_receiver_coins:,} フラワー"
                ),
                inline=False
            )

            embed.add_field(
                name="日時",
                value=datetime.now(
                    pytz.timezone("Asia/Tokyo")
                ).strftime("%Y/%m/%d %H:%M:%S"),
                inline=False
            )

            await log_channel.send(embed=embed)
            
    except Exception as e:
        print("FLOWER TRANSFER ERROR:", repr(e), flush=True)

        await interaction.followup.send(
            "花贈り中にエラーが発生しました。",
            ephemeral=True
        )
        
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
