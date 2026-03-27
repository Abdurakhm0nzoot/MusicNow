import asyncio
import logging
import os
import shutil
import subprocess
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
)
from aiogram.filters.command import Command
from dotenv import load_dotenv

from music_service import (
    search_music, download_by_id, is_supported_url,
    download_audio_from_url, download_video_from_url
)
import db

logging.basicConfig(level=logging.INFO)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID", "") 

bot: Bot = None
dp = Dispatcher()

# Хранилище результатов поиска {user_id: [results]}
search_cache = {}
# Хранилище ссылок {user_id: url}
download_url_cache = {}

MESSAGES = {
    'ru': {
        'select_lang': "Выберите язык:",
        'welcome': (
            "👋 Привет, <b>{name}</b>!\n\n"
            "Я — <b>🎵 Music & Video Downloader Bot</b>\n\n"
            "Что я умею:\n"
            "🔍 <b>Поиск</b>: Просто напиши название песни.\n"
            "🔗 <b>Ссылки</b>: Пришли ссылку на YouTube, TikTok, Instagram или VK.\n\n"
            "✨ Просто напиши название или отправь ссылку!"
        ),
        'help': "📖 <b>Помощь:</b>\n\n"
                  "Отправь название песни или ссылку на видео.\n\n"
                  "Есть вопросы? Нажми кнопку ниже ✍️",
        'searching': "🔎 Ищу музыку...",
        'not_found': "❌ Ничего не найдено.",
        'full_music_found': "🎵 <b>Полная версия найдена!</b>\nВыберите подходящий вариант ниже:",
        'dl_start': "⏬ Начинаю скачивание...",
        'dl_error': "❌ Ошибка при скачивании.",
        'btn_audio': "🎵 Аудио (MP3)",
        'btn_video': "🎬 Видео (MP4)",
        'btn_cancel': "❌ Отмена",
        'btn_feedback': "✍️ Написать админу",
        'feedback_prompt': "Напишите сообщение администратору. Я перешлю его прямо сейчас!",
        'feedback_sent': "✅ Сообщение отправлено! Админ ответит тебе в ближайшее время.",
    },
    'en': {
        'select_lang': "Select language:",
        'welcome': (
            "👋 Hello, <b>{name}</b>!\n\n"
            "I'm <b>🎵 Music & Video Downloader Bot</b>\n\n"
            "What I can do:\n"
            "🔍 <b>Search</b>: Just type the song name.\n"
            "🔗 <b>Links</b>: Send a link from YouTube, TikTok, Instagram, or VK.\n\n"
            "Just type a name or send a link!"
        ),
        'help': "📖 <b>Help:</b>\n\n"
                  "Send a song title or a video link.\n\n"
                  "Any questions? Tap below ✍️",
        'searching': "🔎 Searching...",
        'not_found': "❌ Nothing found.",
        'full_music_found': "🎵 <b>Full version found!</b>\nSelect the best option below:",
        'dl_start': "⏬ Downloading...",
        'dl_error': "❌ Download error.",
        'btn_audio': "🎵 Audio (MP3)",
        'btn_video': "🎬 Video (MP4)",
        'btn_cancel': "❌ Cancel",
        'btn_feedback': "✍️ Contact Admin",
        'feedback_prompt': "Write your message to the admin. I will forward it right now!",
        'feedback_sent': "✅ Message sent! Admin will reply soon.",
    },
    'uz': {
        'select_lang': "Tilni tanlang:",
        'welcome': (
            "👋 Salom, <b>{name}</b>!\n\n"
            "Men — <b>🎵 Music & Video Downloader Bot</b>\n\n"
            "Nimalar qila olaman:\n"
            "🔍 <b>Izlash</b>: Shunchaki qoʻshiq nomini yozing.\n"
            "🔗 <b>Havolalar</b>: YouTube, TikTok, Instagram yoki VK havolasini yuboring.\n\n"
            "Ismni yozing yoki faylni yuboring!"
        ),
        'help': "📖 <b>Yordam:</b>\n\n"
                  "Qoʻshiq nomini yoki video havolasini yuboring.\n\n"
                  "Savollar bormi? Pastdagi tugmani bosing ✍️",
        'searching': "🔎 Qidirilmoqda...",
        'not_found': "❌ Hech narsa topilmadi.",
        'full_music_found': "🎵 <b>To'liq versiya topildi!</b>\nQuyidagidan birini tanlang:",
        'dl_start': "⏬ Yuklab olinmoqda...",
        'dl_error': "❌ Yuklab olishda xato.",
        'btn_audio': "🎵 Audio (MP3)",
        'btn_video': "🎬 Video (MP4)",
        'btn_cancel': "❌ Bekor qilish",
        'btn_feedback': "✍️ Adminga yozish",
        'feedback_prompt': "Admin uchun xabar matnini yozing. Men uni darhol yuboraman!",
        'feedback_sent': "✅ Xabar yuborildi! Admin tez orada javob beradi.",
    }
}

# ===================== HELPERS =====================

def get_lang(user_id):
    return db.get_user_language(user_id) or 'ru'

async def update_bot_profile_stats():
    """Обновляет публичную статистику в профиле бота, если она превышает порог."""
    stats = db.get_stats()
    total = stats.get('total', 0)
    
    if total > 100:
        desc_text = f"🎵 Fast Music & Video Downloader\n\n👥 We are already {total} users!\n\n🔍 Search music\n🔗 Get video/audio from any link\n\nStart now!"
        short_desc = f"🎵 Music Downloader | 👥 {total} users!"
    else:
        desc_text = "🎵 Fast Music & Video Downloader\n\n🔍 Search music\n🔗 Get video/audio links\n\nStart now!"
        short_desc = "🎵 Music Downloader | Fast & Free!"

    try:
        await bot.set_my_short_description(short_desc)
        await bot.set_my_description(desc_text)
    except: pass

async def handle_ping(request):
    """Мини-сайт для обхода сна на Render Free Tier."""
    return web.Response(text="🎵 Music Bot is running!")

def build_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang:ru")],
        [InlineKeyboardButton(text="🇺🇸 English", callback_data="set_lang:en")],
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="set_lang:uz")]
    ])

def build_results_keyboard(results, lang):
    buttons = []
    row = []
    for i in range(len(results)):
        row.append(InlineKeyboardButton(text=str(i + 1), callback_data=f"pick:{i}"))
        if len(row) == 4:
            buttons.append(row); row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton(text=MESSAGES[lang]['btn_cancel'], callback_data="delete_msg")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_audio_keyboard(video_id, liked=False):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️" if liked else "🤍", callback_data=f"like:{video_id}:{'1' if liked else '0'}"),
            InlineKeyboardButton(text="❌", callback_data="delete_msg")
        ]
    ])

def get_download_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=MESSAGES[lang]['btn_audio'], callback_data="dl_audio"),
            InlineKeyboardButton(text=MESSAGES[lang]['btn_video'], callback_data="dl_video"),
        ],
        [InlineKeyboardButton(text=MESSAGES[lang]['btn_cancel'], callback_data="delete_msg")]
    ])

# ===================== COMMANDS =====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user = message.from_user
    db.add_user(user.id, user.username, user.first_name)
    lang = db.get_user_language(user.id)
    if not lang:
        await message.answer("🇷🇺 Выберите язык / 🇺🇸 Choose language / 🇺🇿 Tilni tanlang:", reply_markup=build_lang_keyboard())
    else:
        text = MESSAGES[lang]['welcome'].format(name=user.first_name or "user")
        await message.answer(text, parse_mode="HTML")
    await update_bot_profile_stats()

@dp.callback_query(F.data.startswith("set_lang:"))
async def set_lang_handler(callback: types.CallbackQuery):
    lang = callback.data.split(":")[1]
    db.set_user_language(callback.from_user.id, lang)
    text = MESSAGES[lang]['welcome'].format(name=callback.from_user.first_name or "user")
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer(); await update_bot_profile_stats()

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    lang = get_lang(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['btn_feedback'], callback_data="admin_contact")]
    ])
    await message.answer(MESSAGES[lang]['help'], parse_mode="HTML", reply_markup=kb)

@dp.message(Command("id"))
async def cmd_id(message: types.Message):
    await message.answer(f"ID: <code>{message.from_user.id}</code>", parse_mode="HTML")

# ===================== ADMIN PRO =====================

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    stats = db.get_stats()
    text = (
        "🛡 <b>Admin Panel</b>\n\n"
        f"Total users: {stats.get('total', 0)}\n"
        f"🇷🇺: {stats.get('ru', 0)} | 🇺🇸: {stats.get('en', 0)} | 🇺🇿: {stats.get('uz', 0)}\n"
        f"❤️ Likes: {stats.get('likes', 0)}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_bc_query")],
        [InlineKeyboardButton(text="🔄 Update yt-dlp", callback_data="admin_update_ytdlp")],
        [InlineKeyboardButton(text="🧹 Clean Cache", callback_data="admin_clean")]
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "admin_update_ytdlp")
async def update_yt(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID): return
    await callback.message.answer("⏳ Updating yt-dlp...")
    try:
        proc = subprocess.run(["pip", "install", "-U", "yt-dlp"], capture_output=True, text=True)
        await callback.message.answer(f"✅ Result:\n<code>{proc.stdout[-500:]}</code>", parse_mode="HTML")
    except Exception as e:
        await callback.message.answer(f"❌ Error: {e}")
    await callback.answer()

@dp.callback_query(F.data == "admin_clean")
async def clean_dl(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID): return
    if os.path.exists("downloads"):
        shutil.rmtree("downloads"); os.makedirs("downloads")
        await callback.message.answer("✅ Downloads folder cleared!")
    await callback.answer()

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("Usage: <code>/broadcast text</code>"); return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="All", callback_data="bc_all")], [InlineKeyboardButton(text="RU", callback_data="bc_ru")], [InlineKeyboardButton(text="EN", callback_data="bc_en")], [InlineKeyboardButton(text="UZ", callback_data="bc_uz")]])
    download_url_cache[message.from_user.id] = text
    await message.answer("Select Target:", reply_markup=kb)

@dp.callback_query(F.data.startswith("bc_"))
async def do_bc(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID): return
    target = callback.data.split("_")[1]
    if target == "all": target = None
    text = download_url_cache.get(callback.from_user.id)
    if not text: await callback.answer("Text lost"); return
    users = db.get_users_by_language(target)
    await callback.message.edit_text(f"🚀 Sending to {len(users)}...")
    ok, err = 0, 0
    for u in users:
        try:
            await bot.send_message(u, text); ok += 1
            if ok % 20 == 0: await asyncio.sleep(0.5)
        except: err += 1
    await callback.message.answer(f"✅ OK: {ok}, ERR: {err}"); await callback.answer()

# ===================== FEEDBACK =====================

@dp.callback_query(F.data == "admin_contact")
async def contact_admin_start(callback: types.CallbackQuery):
    lang = get_lang(callback.from_user.id)
    download_url_cache[callback.from_user.id] = "waiting_feedback"
    await callback.message.answer(MESSAGES[lang]['feedback_prompt'])
    await callback.answer()

@dp.message(Command("reply"))
async def admin_reply(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    parts = message.text.split(" ", 2)
    if len(parts) < 3: return
    try:
        await bot.send_message(parts[1], f"✉️ <b>Message from Admin:</b>\n\n{parts[2]}", parse_mode="HTML")
        await message.answer("✅ Reply sent!")
    except Exception as e: await message.answer(f"❌ Error: {e}")

# ===================== TEXT & LINKS =====================

@dp.message(F.text)
async def handle_text(message: types.Message):
    if message.text.startswith('/'): return
    u_id = message.from_user.id
    lang = get_lang(u_id)
    if download_url_cache.get(u_id) == "waiting_feedback":
        await bot.send_message(ADMIN_ID, f"👤 <b>Feedback from</b> {message.from_user.mention_html()} (ID: <code>{u_id}</code>):\n\n{message.text}", parse_mode="HTML")
        download_url_cache[u_id] = None
        await message.answer(MESSAGES[lang]['feedback_sent'])
        return
    url = is_supported_url(message.text)
    if url:
        download_url_cache[u_id] = url
        await message.reply(MESSAGES[lang]['btn_audio'] + "/" + MESSAGES[lang]['btn_video'], reply_markup=get_download_keyboard(lang))
        return

    status = await message.reply(MESSAGES[lang]['searching'])
    res = await search_music(message.text)
    if res:
        search_cache[u_id] = res
        prompt = MESSAGES[lang]['full_music_found']
        await status.edit_text(f"🔍 {message.text}\n\n{prompt}", reply_markup=build_results_keyboard(res, lang), parse_mode="HTML")
    else: await status.edit_text(MESSAGES[lang]['not_found'])

# ===================== CALLBACKS =====================

@dp.callback_query(F.data == "dl_audio")
async def dl_audio(callback: types.CallbackQuery):
    lang = get_lang(callback.from_user.id); url = download_url_cache.get(callback.from_user.id)
    if not url: return
    await callback.message.edit_text(MESSAGES[lang]['dl_start'])
    res = await download_audio_from_url(url)
    if res:
        try: await callback.message.reply_audio(audio=FSInputFile(res['filename']), title=res['title'], performer=res['uploader'], duration=int(res['duration']), reply_markup=get_audio_keyboard(res['video_id'], db.has_like(callback.from_user.id, res['video_id'])))
        finally: 
            if os.path.exists(res['filename']): os.remove(res['filename'])
    else: await callback.message.edit_text(MESSAGES[lang]['dl_error'])

@dp.callback_query(F.data == "dl_video")
async def dl_video(callback: types.CallbackQuery):
    lang = get_lang(callback.from_user.id); url = download_url_cache.get(callback.from_user.id)
    if not url: return
    await callback.message.edit_text(MESSAGES[lang]['dl_start'])
    res = await download_video_from_url(url)
    if res:
        try: await callback.message.reply_video(video=FSInputFile(res['filename']), caption=res['title'], duration=int(res['duration']), supports_streaming=True)
        finally:
            if os.path.exists(res['filename']): os.remove(res['filename'])
    else: await callback.message.edit_text(MESSAGES[lang]['dl_error'])

@dp.callback_query(F.data.startswith("pick:"))
async def dl_picked(callback: types.CallbackQuery):
    lang = get_lang(callback.from_user.id); idx = int(callback.data.split(":")[1])
    res_list = search_cache.get(callback.from_user.id)
    if not res_list: return
    track = res_list[idx]
    await callback.message.edit_text(MESSAGES[lang]['dl_start'] + f"\n{track['title']}")
    res = await download_by_id(track['video_id'])
    if res:
        fname, title, uploader, dur = res
        try: await callback.message.reply_audio(audio=FSInputFile(fname), title=title, performer=uploader, duration=int(dur), reply_markup=get_audio_keyboard(track['video_id'], db.has_like(callback.from_user.id, track['video_id'])))
        finally:
            if os.path.exists(fname): os.remove(fname)
    else: await callback.message.answer(MESSAGES[lang]['dl_error'])

@dp.callback_query(F.data.startswith("like:"))
async def like_handler(callback: types.CallbackQuery):
    _, vid, liked = callback.data.split(":"); is_liked = liked == "1"; u_id = callback.from_user.id
    if is_liked: db.remove_like(u_id, vid)
    else: db.add_like(u_id, vid, callback.message.audio.title if callback.message.audio else "Track")
    try: await callback.message.edit_reply_markup(reply_markup=get_audio_keyboard(vid, not is_liked))
    except: pass
    await callback.answer()

@dp.callback_query(F.data == "delete_msg")
async def delete_msg(callback: types.CallbackQuery):
    await callback.message.delete()
    try: 
        if callback.message.reply_to_message: await callback.message.reply_to_message.delete()
    except: pass

async def main():
    global bot
    if not BOT_TOKEN: return
    bot = Bot(token=BOT_TOKEN)
    if os.path.exists("downloads"): shutil.rmtree("downloads")
    os.makedirs("downloads")
    
    # Мини-сайт для Render (чтобы не засыпал)
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    await update_bot_profile_stats()
    
    # Запускаем и бота, и сервер одновременно
    await asyncio.gather(
        site.start(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
