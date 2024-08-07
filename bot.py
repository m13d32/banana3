import os
import logging
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, JobQueue
import sqlite3
import urllib.parse
import asyncio
import aiohttp
from datetime import datetime, timedelta

# 設置日誌
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

# 獲取環境變量
TOKEN = "7279201508:AAFg-qaAs2OuYmJV-ylGJKV5mealxwduvL8"
RACE_BOT_TOKEN = "7428603310:AAEpPjprir6hKhPOiGV07r9hR-LFHk2aE0E"
PORT = int(os.environ.get('PORT', 8080))
BOT_USERNAME = "@AB123Cbot"
RACE_BOT_USERNAME = "@bananalolaibot"

# 創建賽道機器人實例
race_bot = Bot(RACE_BOT_TOKEN)

# 初始化數據庫
def init_db():
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS user_groups
                 (user_id INTEGER PRIMARY KEY, group_username TEXT, language TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS group_admins
                 (group_id TEXT PRIMARY KEY, admin_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_stats
                 (user_id INTEGER PRIMARY KEY, last_active_time INTEGER, banana_count INTEGER, country TEXT, 
                 last_remind_time INTEGER, message_content TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mining_machines
                 (user_id INTEGER PRIMARY KEY, count INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS group_members
                 (group_id TEXT, user_id INTEGER, username TEXT, join_time TEXT, 
                 PRIMARY KEY (group_id, user_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS group_bots
                 (group_id TEXT PRIMARY KEY, community_bot_added BOOLEAN, race_bot_added BOOLEAN)''')
    c.execute('''CREATE TABLE IF NOT EXISTS giveaway_participants
                 (user_id INTEGER PRIMARY KEY, participated_at INTEGER)''')
    conn.commit()
    conn.close()

# 初始化數據庫
init_db()

# 數據庫操作函數
def get_user_info(user_id):
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    c.execute("SELECT language, group_username FROM user_groups WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result if result else (None, None)

def set_user_info(user_id, language=None, group_username=None):
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    current_language, current_group = get_user_info(user_id)
    
    if language is None:
        language = current_language
    if group_username is None:
        group_username = current_group

    c.execute("INSERT OR REPLACE INTO user_groups (user_id, language, group_username) VALUES (?, ?, ?)", 
              (user_id, language, group_username))
    conn.commit()
    conn.close()

def remove_user_group(group_username):
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    c.execute("UPDATE user_groups SET group_username = NULL WHERE group_username = ?", (group_username,))
    c.execute("DELETE FROM group_admins WHERE group_id = ?", (group_username,))
    c.execute("DELETE FROM group_bots WHERE group_id = ?", (group_username,))
    c.execute("DELETE FROM group_members WHERE group_id = ?", (group_username,))
    conn.commit()
    conn.close()

def set_group_admin(group_id, admin_id):
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO group_admins (group_id, admin_id) VALUES (?, ?)", (group_id, admin_id))
    conn.commit()
    conn.close()

def get_group_admin(group_id):
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    c.execute("SELECT admin_id FROM group_admins WHERE group_id = ?", (group_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def add_group_member(group_id, user_id, username):
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    join_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    c.execute("INSERT OR REPLACE INTO group_members (group_id, user_id, username, join_time) VALUES (?, ?, ?, ?)",
              (group_id, user_id, username, join_time))
    conn.commit()
    conn.close()

def remove_group_member(group_id, user_id):
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    c.execute("DELETE FROM group_members WHERE group_id = ? AND user_id = ?", (group_id, user_id))
    conn.commit()
    conn.close()

def get_group_members(group_id):
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    c.execute("SELECT user_id, username, join_time FROM group_members WHERE group_id = ? ORDER BY join_time DESC", (group_id,))
    members = c.fetchall()
    conn.close()
    return members

def get_mining_machines(user_id):
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    c.execute("SELECT count FROM mining_machines WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def update_user_stats(user_id, last_active_time, banana_count, country, last_remind_time, message_content):
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO user_stats 
                 (user_id, last_active_time, banana_count, country, last_remind_time, message_content) 
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (user_id, last_active_time, banana_count, country, last_remind_time, message_content))
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    c.execute("SELECT last_active_time, banana_count, country, last_remind_time, message_content FROM user_stats WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result if result else (None, None, None, None, None)

def update_group_bots(group_id, community_bot_added=None, race_bot_added=None):
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    c.execute("SELECT community_bot_added, race_bot_added FROM group_bots WHERE group_id = ?", (group_id,))
    result = c.fetchone()
    if result:
        current_community_bot, current_race_bot = result
        if community_bot_added is None:
            community_bot_added = current_community_bot
        if race_bot_added is None:
            race_bot_added = current_race_bot
    c.execute("INSERT OR REPLACE INTO group_bots (group_id, community_bot_added, race_bot_added) VALUES (?, ?, ?)",
              (group_id, community_bot_added, race_bot_added))
    conn.commit()
    conn.close()

def get_group_bots(group_id):
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    c.execute("SELECT community_bot_added, race_bot_added FROM group_bots WHERE group_id = ?", (group_id,))
    result = c.fetchone()
    conn.close()
    return result if result else (False, False)

def add_giveaway_participant(user_id):
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    participated_at = int(datetime.now().timestamp())
    c.execute("INSERT OR REPLACE INTO giveaway_participants (user_id, participated_at) VALUES (?, ?)",
              (user_id, participated_at))
    conn.commit()
    conn.close()

def has_participated_in_giveaway(user_id):
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    c.execute("SELECT 1 FROM giveaway_participants WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def get_giveaway_participants():
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    c.execute("SELECT user_id, participated_at FROM giveaway_participants ORDER BY participated_at DESC")
    participants = c.fetchall()
    conn.close()
    return participants

def reset_database():
    conn = sqlite3.connect('invites.db')
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS user_groups")
    c.execute("DROP TABLE IF EXISTS group_admins")
    c.execute("DROP TABLE IF EXISTS user_stats")
    c.execute("DROP TABLE IF EXISTS mining_machines")
    c.execute("DROP TABLE IF EXISTS group_members")
    c.execute("DROP TABLE IF EXISTS group_bots")
    c.execute("DROP TABLE IF EXISTS giveaway_participants")
    conn.commit()
    conn.close()
    init_db()

async def start(update: Update, context):
    try:
        logger.debug(f"Received /start command from user {update.effective_user.id}")
        user_id = update.effective_user.id
        language, group_username = get_user_info(user_id)
        
        if language:
            # 用戶已經選擇了語言，直接顯示主菜單
            await show_main_menu(update, context, language)
        else:
            # 用戶未選擇語言，顯示語言選擇菜單
            await show_language_menu(update, context)
        logger.debug(f"Sent welcome message to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}", exc_info=True)

async def race_bot_start(update: Update, context):
    try:
        logger.debug(f"Received /start command from user {update.effective_user.id} in race bot")
        await update.message.reply_text("請邀請我至您的群組裡面管理空頭與獎勵服務", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("邀請社群bot", url=f"https://t.me/{BOT_USERNAME}")]]))
    except Exception as e:
        logger.error(f"Error in race_bot_start command: {str(e)}", exc_info=True)

async def change(update: Update, context):
    try:
        logger.debug(f"Received /change command from user {update.effective_user.id}")
        await show_language_menu(update, context)
    except Exception as e:
        logger.error(f"Error in change command: {str(e)}", exc_info=True)

async def reset(update: Update, context):
    try:
        logger.debug(f"Received /reset command from user {update.effective_user.id}")
        await update.message.reply_text("重置機器人數據中，請稍候...")
        reset_database()
        await update.message.reply_text("機器人數據已重置，請重新綁定您的群組。")
    except Exception as e:
        logger.error(f"Error in reset command: {str(e)}", exc_info=True)

async def show_language_menu(update: Update, context):
    keyboard = [
        [
            InlineKeyboardButton("👉中文", callback_data='lang_zh'),
            InlineKeyboardButton("👉English", callback_data='lang_en')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('请选择您的语言 / Please select your language:', reply_markup=reply_markup)

async def lang_zh(update: Update, context):
    try:
        logger.debug(f"Received lang_zh callback from user {update.effective_user.id}")
        await update.callback_query.answer()
        user_id = update.effective_user.id
        set_user_info(user_id, language='zh')
        await show_main_menu(update, context, 'zh')
        logger.debug(f"Set language to Chinese for user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in lang_zh: {str(e)}", exc_info=True)

async def lang_en(update: Update, context):
    try:
        logger.debug(f"Received lang_en callback from user {update.effective_user.id}")
        await update.callback_query.answer()
        user_id = update.effective_user.id
        set_user_info(user_id, language='en')
        await show_main_menu(update, context, 'en')
        logger.debug(f"Set language to English for user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in lang_en: {str(e)}", exc_info=True)

async def show_main_menu(update: Update, context, language):
    user_id = update.effective_user.id
    _, group_username = get_user_info(user_id)

    if language == 'zh':
        keyboard = [
            [InlineKeyboardButton("玩公告里的游戏", url='https://t.me/banana3lol')],
            [
                InlineKeyboardButton("邀请朋友", callback_data='invite_friends'),
                InlineKeyboardButton("创建俱乐部", callback_data='create_club')
            ],
            [
                InlineKeyboardButton("怎么玩?", callback_data='how_to_play'),
                InlineKeyboardButton("俱乐部资讯概览", callback_data='club_overview')
            ]
        ]
        if group_username:
            keyboard.append([InlineKeyboardButton("管理俱乐部", callback_data='manage_club')])
        
        text = '嘿，香蕉们！\n欢迎来到Banana3，TON上最受MEME驱动的生态系统！\n\n加入这个终极的Web3社交平台，见证Meme文化与区块链技术的结合。\n\n✨Meme文化整合：深入一个充满活力的社区，在这里，Meme激发创造力和参与度。\n\n😎项目启动矩阵：访问强大的工具和服务，帮助项目蓬勃发展，最大化流量和互动。\n\n👆🏻点击赚取：通过参与有趣且有回报的活动来赚取Banana3代币。\n\n⛑安全与创新：享受顶级安全和尖端的Web3技术。\n\n👨‍👩‍👧‍👧互动社交中心：与朋友及全球社区连接、创造和分享。\n\n立即加入我们，成为这个革命性生态系统的一部分，在这里，乐趣与目的相结合，每一次互动都推动增长和价值！'
    else:
        keyboard = [
            [InlineKeyboardButton("Play game in announcement", url='https://t.me/banana3lol')],
            [
                InlineKeyboardButton("Invite Friends", callback_data='invite_friends'),
                InlineKeyboardButton("Create Club", callback_data='create_club')
            ],
            [
                InlineKeyboardButton("How to Play", callback_data='how_to_play'),
                InlineKeyboardButton("Club Overview", callback_data='club_overview')
            ]
        ]
        if group_username:
            keyboard.append([InlineKeyboardButton("Manage Club", callback_data='manage_club')])
        
        text = 'Hey Bananas!\nWelcome to Banana3, The Most MEME-Driven Ecosystem on TON!\n\nJoin the ultimate Web3 social platform where meme culture meets blockchain technology.\n\n✨Meme Culture Integration: Dive into a vibrant community where memes fuel creativity and engagement.\n\n😎 Project Launcher Matrix: Access powerful tools and services designed to help projects thrive, maximizing traffic and engagement.\n\n👆🏻 Tap-to-Earn: Earn Banana3 tokens by participating in fun and rewarding activities.\n\n⛑ Secure and Innovative: Enjoy top-notch security and cutting-edge Web3 technology.\n\n👨‍👩‍👧‍👧 Interactive Social Hub: Connect, create, and share with friends and a global community.\n\nJoin us today and be part of a revolutionary ecosystem where fun meets purpose, and every interaction drives growth and value!'

    reply_markup = InlineKeyboardMarkup(keyboard)
    if isinstance(update, Update):
        if update.callback_query:
            await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=update, text=text, reply_markup=reply_markup)

async def how_to_play(update: Update, context):
    try:
        logger.debug(f"Received how_to_play callback from user {update.effective_user.id}")
        await update.callback_query.answer()
        user_id = update.effective_user.id
        language, _ = get_user_info(user_id)
        
        if language == 'zh':
            text = '欢迎来到Banana3！\n在进行各种活动的同时享受社交乐趣并赚取香蕉币。\n\n这里有一个快速指南告诉你如何玩：\n\n💰 剥皮赚钱：点击剥香蕉皮，赚取香蕉币。\n\n⛏ 升级卡片：即使离线也可以升级卡片以获得被动收入。\n\n⏰ 每小时收益：离线时最多可以获得3小时的收益，之后需要登录继续。\n\n📈 升级等级：香蕉币余额越高，赚取速度越快。\n\n👥 邀请好友：邀请好友可获得额外奖励和奖金。\n\n🪙 代币上市：季末时发布代币。\n\n开始玩吧，祝你好运！'
            keyboard = [
                [InlineKeyboardButton("来玩游戏吧", url='https://t.me/bananaworldbot/Banana3')],
                [InlineKeyboardButton("返回主菜单", callback_data='back_to_main')]
            ]
        else:
            text = 'Welcome to Banana3!\nEnjoy social fun while earning Bananas through various activities.\n\nHere\'s a quick guide on how to play:\n\n💰 Peel to Earn: Tap to peel bananas and earn Banana Coins.\n\n⛏ Upgrade Cards: Upgrade cards for passive income even when offline.\n\n⏰ Hourly Earnings: Earn for up to 3 hours offline, then log in to continue.\n\n📈 Level Up: Higher Banana Coin balance means faster earning.\n\n👥 Invite Friends: Get extra rewards and bonuses for inviting friends.\n\n🪙 Token Launch: Tokens will be released at the end of the season.\n\nStart playing and good luck!'
            keyboard = [
                [InlineKeyboardButton("Play Game", url='https://t.me/bananaworldbot/Banana3')],
                [InlineKeyboardButton("Back to Main Menu", callback_data='back_to_main')]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
        logger.debug(f"Sent how_to_play message to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in how_to_play: {str(e)}", exc_info=True)

async def invite_friends(update: Update, context):
    try:
        logger.debug(f"Received invite_friends callback from user {update.effective_user.id}")
        await update.callback_query.answer()
        user_id = update.effective_user.id
        language, group_username = get_user_info(user_id)
        
        if group_username:
            community_bot_added, race_bot_added = get_group_bots(group_username)
            if not community_bot_added or not race_bot_added:
                if language == 'zh':
                    message = "请确保您已将社群bot和赛道bot都添加到群组中，并设置为管理员。"
                else:
                    message = "Please make sure you have added both the community bot and the race bot to the group and set them as administrators."
                await update.callback_query.message.reply_text(message)
                return

            invite_link = f"https://t.me/{group_username}?start={user_id}"
            if language == 'zh':
                message = f"这是您的专属邀请链接，请邀请更多朋友参与：\n{invite_link}"
                button_text = "邀请朋友"
                invite_text = f"来玩banana3吧，并加入我的俱乐部一起赚更多香蕉币！"
            else:
                message = f"Here's your exclusive invitation link, please invite more friends to participate:\n{invite_link}"
                button_text = "Invite Friends"
                invite_text = f"Let's play Banana3 and join my club to earn more BananaCoins together!"
            
            share_url = f"https://t.me/share/url?url={urllib.parse.quote(invite_link)}&text={urllib.parse.quote(invite_text + ' ' + BOT_USERNAME)}"
            keyboard = [[InlineKeyboardButton(button_text, url=share_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.message.reply_text(message, reply_markup=reply_markup)
        else:
            # 用戶未綁定群組，顯示創建群組的指引
            if language == 'zh':
                message = "请先创建你的群组，以邀请更多朋友并赚取更多奖励。\n将社群bot和banana3 battle机器人添加到你的频道/群组中，并将其设置为管理员，以获取你的专属邀请链接。\n成功开启专属连结后，则会开启俱乐部管理的选项。"
            else:
                message = "Please create your group first to invite more friends and earn more rewards.\nAdd the community bot and banana3 battle bot to your channel/group and set them as administrators to get your exclusive invitation link.\nAfter successfully activating the exclusive link, the club management option will be available."
            await update.callback_query.message.reply_text(message)
        
        logger.debug(f"Sent invite_friends message to user {user_id}")
    except Exception as e:
        logger.error(f"Error in invite_friends: {str(e)}", exc_info=True)

async def create_club(update: Update, context):
    try:
        logger.debug(f"Received create_club callback from user {update.effective_user.id}")
        await update.callback_query.answer()
        user_id = update.effective_user.id
        language, _ = get_user_info(user_id)
        
        if language == 'zh':
            message = "创建俱乐部，一起获得空投\n第一步：邀请社群bot和banana3 battle机器人进入公开群组或频道\n第二步：将两个机器人都设置为管理员\n第三步：点击'邀请朋友'按钮获取专属邀请链接\n\n注意：请确保你的群组或频道是公开的，否则无法获取邀请链接。"
        else:
            message = "Create a club and get airdrops together\nStep 1: Invite the community bot and banana3 battle bot to a public group or channel\nStep 2: Set both bots as administrators\nStep 3: Click the 'Invite Friends' button to get your exclusive invitation link\n\nNote: Please ensure your group or channel is public, otherwise you won't be able to get the invitation link."
        
        await update.callback_query.message.reply_text(message)
        logger.debug(f"Sent create_club message to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in create_club: {str(e)}", exc_info=True)

async def club_overview(update: Update, context):
    try:
        logger.debug(f"Received club_overview callback from user {update.effective_user.id}")
        await update.callback_query.answer()
        user_id = update.effective_user.id
        language, _ = get_user_info(user_id)
        
        if language == 'zh':
            message = "成为俱乐部管理员开启以下任务:\n1. 邀请人数900/1000\n2. 邀请人数>1000人:\n   - 完成20/10颗额外\n   - 开启赛季额外奖励\n   - 每赛季有新人参与，获N(0.1) USDT"
        else:
            message = "Become a club administrator to unlock the following tasks:\n1. Invite 900/1000 people\n2. Invite >1000 people:\n   - Complete 20/10 extra\n   - Unlock seasonal extra rewards\n   - For each new participant per season, earn N(0.1) USDT"
        
        await update.callback_query.message.reply_text(message)
        logger.debug(f"Sent club_overview message to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in club_overview: {str(e)}", exc_info=True)

async def manage_club(update: Update, context):
    try:
        logger.debug(f"Received manage_club callback from user {update.effective_user.id}")
        await update.callback_query.answer()
        user_id = update.effective_user.id
        language, group_username = get_user_info(user_id)
        
        members = get_group_members(group_username)
        
        if not members:
            if language == 'zh':
                message = "目前俱樂部尚未有成員，請努力推廣。"
            else:
                message = "There are no members in the club yet. Please continue to share and promote."
            await update.callback_query.message.reply_text(message)
            return

        if language == 'zh':
            message = "俱乐部成员列表：\n\n"
            for member in members:
                user_id, username, join_time = member
                mining_machine_count = 5  # 假數據，實際上應從API獲取
                if username is None:
                    display_name = f"用戶ID: {user_id} (@none 未設置用戶名)"
                else:
                    display_name = f"@{username}"
                message += f"用戶: {display_name}\n用戶ID: {user_id}\n加入時間: {join_time}\n目前礦機數量: {mining_machine_count}\n\n"
        else:
            message = "Club Members List:\n\n"
            for member in members:
                user_id, username, join_time = member
                mining_machine_count = 5  # 假數據，實際上應從API獲取
                if username is None:
                    display_name = f"User ID: {user_id} (@none No username set)"
                else:
                    display_name = f"@{username}"
                message += f"User: {display_name}\nUser ID: {user_id}\nJoin Time: {join_time}\nMining Machines: {mining_machine_count}\n\n"

        await update.callback_query.message.reply_text(message)
        logger.debug(f"Sent manage_club message to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in manage_club: {str(e)}", exc_info=True)

async def handle_new_chat_members(update: Update, context):
    bot = context.bot
    chat = update.effective_chat
    new_members = update.message.new_chat_members
    
    for member in new_members:
        if member.id == bot.id:
            # 社群bot被添加到群組
            admin = await chat.get_member(update.effective_user.id)
            if admin.status in ['creator', 'administrator']:
                # 檢查用戶是否已經綁定了群組
                language, existing_group = get_user_info(admin.user.id)
                if existing_group:
                    if language == 'zh':
                        message = f"您已经绑定了一个群组。如果您想重新绑定，请先将机器人从原群组 @{existing_group} 中删除，然后重新添加到新群组。"
                    else:
                        message = f"You have already bound a group. If you want to rebind, please remove the bot from the original group @{existing_group} first, then add it to the new group."
                    await chat.send_message(text=message)
                    return

                # 將群組信息保存到數據庫
                set_user_info(admin.user.id, group_username=chat.username)
                set_group_admin(chat.username, admin.user.id)
                update_group_bots(chat.username, community_bot_added=True)

                if language == 'zh':
                    message = f"感谢您将 @{bot.username} 添加到群组！您的群组已成功注册。请确保也添加了赛道机器人 {RACE_BOT_USERNAME} 并将其设置为管理员。完成后，您可以使用\"邀请朋友\"功能获取您的专属邀请链接。"
                    button_text = "获取专属链接"
                else:
                    message = f"Thank you for adding @{bot.username} to the group! Your group has been successfully registered. Please make sure to also add the race bot {RACE_BOT_USERNAME} and set it as an administrator. After that, you can use the 'Invite Friends' feature to get your exclusive invitation link."
                    button_text = "Get Exclusive Link"
                
                await chat.send_message(text=message)
                
                keyboard = [[InlineKeyboardButton(button_text, callback_data='invite_friends')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await context.bot.send_message(
                    chat_id=admin.user.id,
                    text=message,
                    reply_markup=reply_markup
                )
            else:
                await chat.send_message(text="Please make sure to set me as an administrator so I can work properly.")
        elif member.id == int(RACE_BOT_TOKEN.split(':')[0]):
            # 賽道機器人被添加到群組
            update_group_bots(chat.username, race_bot_added=True)
            admin_id = get_group_admin(chat.username)
            if admin_id:
                language, _ = get_user_info(admin_id)
                if language == 'zh':
                    message = f"赛道机器人 {RACE_BOT_USERNAME} 已成功添加到群组并设置为管理员。您现在可以使用\"邀请朋友\"功能获取您的专属邀请链接。"
                else:
                    message = f"The race bot {RACE_BOT_USERNAME} has been successfully added to the group and set as an administrator. You can now use the 'Invite Friends' feature to get your exclusive invitation link."
                await context.bot.send_message(chat_id=admin_id, text=message)
            await send_giveaway_message(context, chat.id)
        elif not member.is_bot:
            # 新成員（非機器人）加入群組
            group_admin = get_group_admin(chat.username)
            if group_admin:
                language, _ = get_user_info(group_admin)
                username = member.username if member.username else f"User ID: {member.id}"
                if language == 'zh':
                    message = f"{username} 已成功加入俱乐部！"
                else:
                    message = f"{username} has successfully joined the club!"
                await context.bot.send_message(chat_id=group_admin, text=message)
                add_group_member(chat.username, member.id, member.username)

async def handle_left_chat_member(update: Update, context):
    bot = context.bot
    chat = update.effective_chat
    left_member = update.message.left_chat_member

    if left_member.id == bot.id:
        # 社群bot被移出群組
        admin_id = get_group_admin(chat.username)
        if admin_id:
            language, _ = get_user_info(admin_id)
            if language == 'zh':
                message = f"我已被移出群組 @{chat.username}。如果這是誤操作，請重新將我添加到群組並設置為管理員。您的邀請鏈接已失效。"
            else:
                message = f"I have been removed from the group @{chat.username}. If this was a mistake, please add me back to the group and set me as an administrator. Your invitation link has been invalidated."
            
            await context.bot.send_message(chat_id=admin_id, text=message)
        
        # 從數據庫中移除群組信息
        remove_user_group(chat.username)
    elif left_member.id == int(RACE_BOT_TOKEN.split(':')[0]):
        # 賽道機器人被移出群組
        update_group_bots(chat.username, race_bot_added=False)
        admin_id = get_group_admin(chat.username)
        if admin_id:
            language, _ = get_user_info(admin_id)
            if language == 'zh':
                message = f"赛道机器人已被移出群组 @{chat.username}。这可能会影响某些功能的正常运作。请重新添加赛道机器人并设置为管理员。"
            else:
                message = f"The race bot has been removed from the group @{chat.username}. This may affect the normal operation of certain features. Please add the race bot back and set it as an administrator."
            await context.bot.send_message(chat_id=admin_id, text=message)
    elif not left_member.is_bot:
        # 成員（非機器人）離開群組
        group_admin = get_group_admin(chat.username)
        if group_admin:
            language, _ = get_user_info(group_admin)
            username = left_member.username if left_member.username else f"User ID: {left_member.id}"
            if language == 'zh':
                message = f"{username} 已离开俱乐部。"
            else:
                message = f"{username} has left the club."
            await context.bot.send_message(chat_id=group_admin, text=message)
            remove_group_member(chat.username, left_member.id)
            
            # 檢查群組成員數量，並更新管理俱樂部信息
            members = get_group_members(chat.username)
            if not members:
                if language == 'zh':
                    await context.bot.send_message(chat_id=group_admin, text="目前俱樂部尚未有成員，請努力推廣。")
                else:
                    await context.bot.send_message(chat_id=group_admin, text="There are no members in the club yet. Please continue to share and promote.")

async def fetch_offline_users():
    url = 'https://banana3battle.banana3.lol/api/open/offline_user'
    headers = {"User-Agent": "Apifox/1.0.0 (https://apifox.com)"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('data', {}).get('list', [])
            else:
                logger.error("Failed to fetch offline users: {}".format(await response.text()))
                return []

async def remind_offline_users(context):
    offline_users = await fetch_offline_users()
    now = datetime.now()
    
    for user in offline_users:
        user_id = user['chatid']
        last_active_time = datetime.fromtimestamp(user['last_active_time'])
        banana_count = user['number']
        country = user['country']['name']
        
        hours_since_last_active = (now - last_active_time).total_seconds() / 3600
        
        language, _ = get_user_info(user_id)
        last_active_time, _, _, last_remind_time, _ = get_user_stats(user_id)
        
        if last_remind_time is None or (now - datetime.fromtimestamp(last_remind_time)).total_seconds() / 3600 >= 3:
            if language == 'zh':
                if last_remind_time is None or (now - datetime.fromtimestamp(last_remind_time)).total_seconds() / 3600 >= 6:
                    message = f"亲爱的玩家，你已经离开游戏{int(hours_since_last_active)}小时了。我们非常期待你的回归，继续你的冒险并收获更多香蕉！你目前有 {banana_count} 个香蕉。让我们一起提升{country}的排名！"
                else:
                    message = f"亲爱的玩家，你已经离开游戏{int(hours_since_last_active)}小时了。是时候回来收获更多香蕉了！你目前有 {banana_count} 个香蕉。继续玩游戏，提升{country}的排名！让我们为你的国家感到自豪！"
            else:
                if last_remind_time is None or (now - datetime.fromtimestamp(last_remind_time)).total_seconds() / 3600 >= 6:
                    message = f"Dear player, you've been away from the game for {int(hours_since_last_active)} hours. We eagerly await your return to continue your adventure and harvest more bananas! You currently have {banana_count} bananas. Let's boost {country}'s ranking together!"
                else:
                    message = f"Dear player, you've been away from the game for {int(hours_since_last_active)} hours. It's time to come back and harvest more bananas! You currently have {banana_count} bananas. Keep playing and continue to boost {country}'s ranking! Let's make your country proud!"
            
            try:
                await context.bot.send_message(chat_id=user_id, text=message)
                logger.info(f"Sent reminder to user {user_id}")
                update_user_stats(user_id, user['last_active_time'], banana_count, country, int(now.timestamp()), message)
            except Exception as e:
                logger.error(f"Failed to send reminder to user {user_id}: {str(e)}")

async def send_giveaway_message(context, chat_id=None):
    now = datetime.now()
    giveaway_time = now + timedelta(hours=3)
    
    message = f"""
    🎁 赠送 🪙 100 TON ($666.02)

    在 {giveaway_time.strftime('%Y年%m月%d日 %H:%M')} (UTC)，{RACE_BOT_USERNAME} 将随机选择 250 位获奖者，他们将分享 🪙 100 TON，每人获得 🪙 0.4 TON ($2.66)。

    要参与此赠送活动，请加入以下 2 个频道并点击下方按钮：
    1. Banana3 Announcements
    """

    keyboard = [[InlineKeyboardButton("参与抽奖 / Join Giveaway", callback_data='join_giveaway')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if chat_id:
            # 直接發送到指定的群組
            await race_bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)
        else:
            # 發送到所有群組
            conn = sqlite3.connect('invites.db')
            c = conn.cursor()
            c.execute("SELECT DISTINCT group_username FROM user_groups WHERE group_username IS NOT NULL")
            groups = c.fetchall()
            conn.close()

            for group in groups:
                group_username = group[0]
                try:
                    await race_bot.send_message(chat_id=f"@{group_username}", text=message, reply_markup=reply_markup)
                except Exception as e:
                    logger.error(f"Failed to send giveaway message to group @{group_username}: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to send giveaway message: {str(e)}")

async def join_giveaway(update: Update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    language, _ = get_user_info(user_id)

    if has_participated_in_giveaway(user_id):
        if language == 'zh':
            message = "您已參加此活動，請隨時關注最新消息。"
        else:
            message = "You have already participated in this giveaway. Please stay tuned for updates."
    else:
        add_giveaway_participant(user_id)
        if language == 'zh':
            message = "您已成功參與抽獎活動！祝您好運！"
        else:
            message = "You have successfully joined the giveaway! Good luck!"

    await race_bot.edit_message_text(chat_id=query.message.chat_id, message_id=query.message.message_id, text=message)

async def back_to_main(update: Update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    language, _ = get_user_info(user_id)
    await show_main_menu(update, context, language)

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("change", change))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CallbackQueryHandler(lang_zh, pattern='^lang_zh$'))
    application.add_handler(CallbackQueryHandler(lang_en, pattern='^lang_en$'))
    application.add_handler(CallbackQueryHandler(how_to_play, pattern='^how_to_play$'))
    application.add_handler(CallbackQueryHandler(invite_friends, pattern='^invite_friends$'))
    application.add_handler(CallbackQueryHandler(create_club, pattern='^create_club$'))
    application.add_handler(CallbackQueryHandler(club_overview, pattern='^club_overview$'))
    application.add_handler(CallbackQueryHandler(manage_club, pattern='^manage_club$'))
    application.add_handler(CallbackQueryHandler(join_giveaway, pattern='^join_giveaway$'))
    application.add_handler(CallbackQueryHandler(back_to_main, pattern='^back_to_main$'))

    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_left_chat_member))

    # 設置定時任務
    job_queue = application.job_queue
    job_queue.run_repeating(send_giveaway_message, interval=6*60*60, first=10)  # 每3小時發送一次抽獎消息
    job_queue.run_repeating(remind_offline_users, interval=2*60*60, first=10)  # 每2小時檢查一次離線用戶並發送提醒

    race_application = Application.builder().token(RACE_BOT_TOKEN).build()
    race_application.add_handler(CommandHandler("start", race_bot_start))

    application.run_polling(allowed_updates=Update.ALL_TYPES)
    race_application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
