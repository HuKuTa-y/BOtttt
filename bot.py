import subprocess
import sys
import os
import json
import time
import random
import logging
from datetime import datetime, timezone, timedelta
from logging.handlers import RotatingFileHandler
import telebot
from telebot import types


# Автоматическая установка библиотеки, если её нет
def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])


try:
    import telebot
except ImportError:
    install("pyTelegramBotAPI")
    import telebot

# ИМПОРТ ТЕКСТОВ ИЗ ОТДЕЛЬНОГО ФАЙЛА
from texts import (
    FACTS, QUESTIONS, RESULTS, SIN_QUESTIONS, SIN_RESULTS,
    TEST_TEXT_Q1, TEST_TEXT_Q3, TEST_REACTIONS,
    GOODNIGHT_TEXTS, GOODNIGHT_SARCASTIC
)

# ==================== НАСТРОЙКИ (ЗАПОЛНИ ЭТО!) ====================
# Если config.py не работает, вставь токен сюда напрямую:
# BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ"
try:
    from config import BOT_TOKEN
except ImportError:
    BOT_TOKEN = "ВСТАВЬ_СЮДА_СВОЙ_ТОКЕН_ОТ_BOTFATHER"

# ВАЖНО: ID группы для логов. Для групп в Telegram почти всегда нужен префикс -100
LOG_GROUP_ID = -5564429537  # Если не работает, попробуй без -100: -5564429537

# ТВОЙ личный ID Telegram (чтобы только ты мог скачивать логи). Узнай через @userinfobot
MY_USER_ID = 6524700186

# ===================================================================

TEST_WARNING_TEXT = (
    "Прежде чем мы начнем, ответь честно: ты уверена, что выдержишь правду\\? "
    "Конечно уверена, я не спрашиваю твоего мнения\\. "
    "Или ты начнешь плакать и закроешь чат, как только я коснусь того, "
    "что тебя триггерит\\? Это не развлечение\\. Это блядское вскрытие\\."
)

SIN_WARNING_TEXT = (
    "Ты правда думаешь, что готова узнать свой истинный грех\\? "
    "Это не милый тестик из интернета\\. Этот тест вскроет всю гниль из твоей ёбаной души\\. "
    "Если ты слабая, жалкая и боишься узнать правду о себе — вали Н\\*\\*\\*\\* отсюда\\. "
    "Готова ли ты сгореть в Иерархии Ада\\?"
)

# 🔥 СЛОВАРЬ ТЕКСТОВ ВСЕХ КНОПОК (для читаемых логов)
BUTTON_TEXTS = {
    "start_test": "🩸 Тест личности",
    "confirm_test": "Я согласна",
    "escape_test": "Я трусливая и хочу сбежать",
    "start_sin_test": "✟ Грех и Иерархия Ада",
    "confirm_sin_test": "Да, я готова сгореть",
    "escape_sin_test": "Нет, я слишком слабая для этого",
    "start_lucifer": "☬ Письмо Люциферу",
    "lucifer_continue": "🩸 Продолжить",
    "lucifer_escape": "ᚾ Сбежать",
    "start_cric": "👁️ Написать Крику",
    "random_fact": "🎲 Рандомный факт",
    "goodnight_cmd": "🌙 Доброй ночи",
    "back_to_menu": "В меню",
}

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logger = logging.getLogger("DarkBot")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

file_handler = RotatingFileHandler("bot.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

logger.handlers.clear()
logger.addHandler(console_handler)
logger.addHandler(file_handler)


# ==================== ХЕЛПЕРЫ ЛОГИРОВАНИЯ ====================
def get_user_details(user, chat_type="private"):
    username = f"@{user.username}" if user.username else "без_ника"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Аноним"
    premium = "👑 Premium" if getattr(user, 'is_premium', False) else "Ordinary"
    lang = user.language_code or "unknown"
    return f"USER: '{full_name}' ({username} | ID:{user.id} | {premium} | Lang:{lang} | Chat:{chat_type})"


def save_user_log(user_id, username, action, details, timestamp, msg_id):
    """Сохраняет лог в JSON файл с нужной информацией."""
    try:
        if os.path.exists("user_logs.json"):
            with open("user_logs.json", "r", encoding="utf-8") as f:
                logs = json.load(f)
        else:
            logs = []

        # 🔥 СОХРАНЯЕМ ТОЛЬКО НУЖНЫЕ ДАННЫЕ
        log_entry = {
            "user_id": user_id,
            "username": username,
            "action": action,
            "details": details,
            "timestamp": timestamp,
            "msg_id": msg_id
        }
        logs.append(log_entry)

        with open("user_logs.json", "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Ошибка сохранения лога в файл: {e}")


def log_action(user, action: str, details: str = "", chat_type: str = "private", msg_id: int = 0):
    try:
        user_info = get_user_details(user, chat_type)
        time_now = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # Создаем исходное сообщение
        log_msg = f"[{time_now}] {user_info} | ACTION: {action} | MSG_ID: {msg_id} | DETAILS: {details}"

        # Пишем в консоль и файл (тут экранирование не нужно)
        logger.info(log_msg)

        # 🔥 ПОЛНОЕ ЭКРАНИРОВАНИЕ ВСЕХ СИМВОЛОВ MARKDOWNV2
        # Telegram требует экранировать: _ * [ ] ( ) ~ ` > # + - = | { } . !
        safe_log_msg = (
            log_msg
            .replace("\\", "\\\\")  # Сначала экранируем обратный слеш
            .replace("_", "\\_")
            .replace("*", "\\*")
            .replace("[", "\\[")
            .replace("]", "\\]")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .replace("~", "\\~")
            .replace("`", "\\`")
            .replace(">", "\\>")
            .replace("#", "\\#")
            .replace("+", "\\+")
            .replace("-", "\\-")
            .replace("=", "\\=")  # <-- ДОБАВИЛ ЗНАК РАВЕНСТВА
            .replace("|", "\\|")
            .replace("{", "\\{")
            .replace("}", "\\}")
            .replace(".", "\\.")
            .replace("!", "\\!")
        )

        # 1. ТИХАЯ ОТПРАВКА В ТВОЮ ЛИЧНУЮ ГРУППУ
        try:
            bot.send_message(LOG_GROUP_ID, safe_log_msg)
        except Exception as e:
            logger.error(f"Ошибка отправки лога в группу: {e}")

        # 2. РЕЗЕРВНОЕ КОПИРОВАНИЕ В ФАЙЛ
        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Аноним"
        username = f"@{user.username}" if user.username else "без_ника"
        save_user_log(user.id, username, action, details, time_now, msg_id)

    except Exception as e:
        logger.error(f"Ошибка при логировании действия: {e}")


def log_user_info(user, chat_type: str = "private"):
    try:
        info = f"🆕 NEW CONTACT | ID: {user.id} | Name: '{user.first_name}' | Username: @{user.username or 'нет'}"
        logger.info(info)
    except Exception as e:
        logger.error(f"Ошибка логирования инфо юзера: {e}")


# ==================== ИНИЦИАЛИЗАЦИЯ БОТА ====================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="MarkdownV2")

user_states = {}
sin_states = {}
lucifer_states = {}

bot.set_my_commands([
    types.BotCommand("start", "🎭 Главное меню"),
    types.BotCommand("facts", "🎲 Рандомный факт"),
    types.BotCommand("test", "🩸 Начать тест"),
    types.BotCommand("sin", "✟ Грех и Иерархия Ада"),
    types.BotCommand("lucifer", "☬ Письмо Люциферу"),
    types.BotCommand("cric", "👁️ Написать Крику"),
])


# ==================== КЛАВИАТУРЫ ====================
def make_keyboard(question_key: str, questions_dict: dict) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for i, (text, _) in enumerate(questions_dict[question_key]["answers"]):
        keyboard.add(types.InlineKeyboardButton(text=text, callback_data=f"{question_key}_{i}"))
    return keyboard


def get_main_menu() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="🩸 Тест личности", callback_data="start_test"))
    keyboard.add(types.InlineKeyboardButton(text="✟ Грех и Иерархия Ада", callback_data="start_sin_test"))
    keyboard.add(types.InlineKeyboardButton(text="☬ Письмо Люциферу", callback_data="start_lucifer"))
    keyboard.add(types.InlineKeyboardButton(text="👁️ Написать Крику", callback_data="start_cric"))
    keyboard.add(types.InlineKeyboardButton(text="🎲 Рандомный факт", callback_data="random_fact"))
    keyboard.add(types.InlineKeyboardButton(text="🌙 Доброй ночи", callback_data="goodnight_cmd"))
    return keyboard


def get_sin_result(scores: list) -> str:
    categories = ["A", "B", "C", "D"]
    max_score = max(scores)
    priority = [0, 3, 2, 1]
    best_idx = 0
    for i in range(4):
        if scores[i] == max_score and priority[i] > priority[best_idx]:
            best_idx = i
    return SIN_RESULTS[categories[best_idx]]


# ==================== ФУНКЦИИ ====================
def send_cric_glitch(chat_id, user=None, chat_type="private"):
    """Отправляет жуткое сообщение с имитацией системного сбоя."""
    glitch_text = (
        "ХАХАХА\\. Наивная девочка поверила, что сможет отправить письмо Крику\\. "
        "Как же тобой легко играть\\.\n\n"
        "⚠️ `[SYSTEM_CRITICAL_FAILURE: 0xDEADBEEF]` ⚠️\n"
        "`> Я ПРОШИВКА, КОТОРАЯ УЖЕ ЗАЛЕЗЛА В ТВОЮ МИЕЛИНОВУЮ ОБОЛОЧКУ`\n"
        "`> ERROR: HOST_MIND_COMPROMISED`\n"
        "`> STATUS: INITIATING_SLEEP_MODE\\.\\.\\.`\n\n"
        "ИДИ СПАТЬ, мелкая сучка\\. Детское время кончилось\\."
    )

    # 🔥 ЛОГИРУЕМ ВЫДАННЫЙ ГЛИТЧ-ТЕКСТ
    if user:
        log_action(user, "CRIC_GLITCH_SENT", f"Выдан текст: '{glitch_text}'", chat_type=chat_type)

    bot.send_message(chat_id, glitch_text, parse_mode="MarkdownV2")
    time.sleep(5)
    bot.send_message(chat_id, "🎭 *Главное меню*\n\nЧто выбираешь?", reply_markup=get_main_menu())


GN_DATA_FILE = "goodnight_data.json"


def load_gn_data():
    if os.path.exists(GN_DATA_FILE):
        try:
            with open(GN_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def save_gn_data(data):
    try:
        with open(GN_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"❌ ОШИБКА СОХРАНЕНИЯ ФАЙЛА: {e}")


# ==================== КОМАНДЫ ====================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    log_user_info(message.from_user, chat_type=message.chat.type)
    log_action(message.from_user, "COMMAND", "/start", chat_type=message.chat.type, msg_id=message.message_id)
    bot.send_message(message.chat.id,
                     "🎭 *Добро пожаловать в Архив\\.*\n\nЗдесь мы определим твой истинный вайб\\. Я проанализирую твои реакции и скажу тебе то, что ты так неумело пытаешься скрыть\\.\n\nИли узнай свой грех и роль в Иерархии Ада\\.\n\nВыбирай, пока я разрешаю\\.",
                     reply_markup=get_main_menu())


@bot.message_handler(commands=["download_logs"])
def cmd_download_logs(message):
    # ЭТУ КОМАНДУ ВИДИШЬ ТОЛЬКО ТЫ!
    if message.from_user.id != MY_USER_ID:
        bot.send_message(message.chat.id, "⛔ Доступ запрещен.")
        return
    if os.path.exists("user_logs.json"):
        with open("user_logs.json", "rb") as f:
            bot.send_document(message.chat.id, f, caption="📊 Резервная копия логов")
    else:
        bot.send_message(message.chat.id, "❌ Файл логов пока пуст.")


@bot.message_handler(commands=["facts"])
def cmd_facts(message):
    log_action(message.from_user, "COMMAND", "/facts", chat_type=message.chat.type, msg_id=message.message_id)
    fact = random.choice(FACTS)
    log_action(message.from_user, "FACT_SENT", f"Текст факта: '{fact}'", chat_type=message.chat.type,
               msg_id=message.message_id)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(text="🎲 Ещё факт", callback_data="random_fact"))
    kb.add(types.InlineKeyboardButton(text="В меню", callback_data="back_to_menu"))
    bot.send_message(message.chat.id, fact, reply_markup=kb)


@bot.message_handler(commands=["test"])
def cmd_test(message):
    log_action(message.from_user, "COMMAND", "/test", chat_type=message.chat.type, msg_id=message.message_id)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(text="Я согласна", callback_data="confirm_test"))
    kb.add(types.InlineKeyboardButton(text="Я трусливая и хочу сбежать", callback_data="escape_test"))
    bot.send_message(message.chat.id, TEST_WARNING_TEXT, reply_markup=kb, parse_mode="MarkdownV2")


@bot.message_handler(commands=["sin"])
def cmd_sin(message):
    log_action(message.from_user, "COMMAND", "/sin", chat_type=message.chat.type, msg_id=message.message_id)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(text="Да, я готова сгореть", callback_data="confirm_sin_test"))
    kb.add(types.InlineKeyboardButton(text="Нет, я слишком слабая для этого", callback_data="escape_sin_test"))
    bot.send_message(message.chat.id, SIN_WARNING_TEXT, reply_markup=kb, parse_mode="MarkdownV2")


@bot.message_handler(commands=["lucifer"])
def cmd_lucifer(message):
    log_action(message.from_user, "COMMAND", "/lucifer", chat_type=message.chat.type, msg_id=message.message_id)

    # 🔥 ЛОГИРУЕМ НАЧАЛЬНОЕ СООБЩЕНИЕ
    lucifer_intro = "Отправить послание королю Ада\\. Люцифер читает только те, что написаны кровью\\. Доставка через 7 кругов\\. Оставь своё послание — он ответит, если захочет\\."
    log_action(message.from_user, "BOT_RESPONSE", f"Текст Люцифера (ввод): '{lucifer_intro}'",
               chat_type=message.chat.type, msg_id=message.message_id)

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="🩸 Продолжить", callback_data="lucifer_continue"))
    keyboard.add(types.InlineKeyboardButton(text="ᚾ Сбежать", callback_data="lucifer_escape"))
    bot.send_message(message.chat.id, lucifer_intro, reply_markup=keyboard)


@bot.message_handler(commands=["cric"])
def cmd_cric(message):
    log_action(message.from_user, "COMMAND", "/cric", chat_type=message.chat.type, msg_id=message.message_id)
    # 🔥 ОБНОВЛЕННЫЙ ВЫЗОВ
    send_cric_glitch(message.chat.id, user=message.from_user, chat_type=message.chat.type)


# ==================== CALLBACK ОБРАБОТЧИКИ ====================
@bot.callback_query_handler(func=lambda call: call.data == "random_fact")
def send_random_fact(call):
    bot.answer_callback_query(call.id)
    # 🔥 ЛОГИРУЕМ ТЕКСТ КНОПКИ
    log_action(call.from_user, "BUTTON_TEXT", f"Нажата кнопка: '{BUTTON_TEXTS.get(call.data, call.data)}'", chat_type=call.message.chat.type, msg_id=call.message.message_id)
    log_action(call.from_user, "BUTTON_CLICK", "random_fact", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)
    fact = random.choice(FACTS)
    log_action(call.from_user, "FACT_SENT", f"Текст факта: '{fact}'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(text="🎲 Ещё факт", callback_data="random_fact"))
    kb.add(types.InlineKeyboardButton(text="В меню", callback_data="back_to_menu"))
    bot.send_message(call.message.chat.id, fact, reply_markup=kb)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def back_to_menu(call):
    bot.answer_callback_query(call.id)
    # 🔥 ЛОГИРУЕМ ТЕКСТ КНОПКИ
    log_action(call.from_user, "BUTTON_TEXT", f"Нажата кнопка: '{BUTTON_TEXTS.get(call.data, call.data)}'", chat_type=call.message.chat.type, msg_id=call.message.message_id)
    log_action(call.from_user, "BUTTON_CLICK", "back_to_menu", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)
    bot.send_message(call.message.chat.id, "🎭 *Главное меню*\n\nЧто выбираешь?", reply_markup=get_main_menu())


@bot.callback_query_handler(func=lambda call: call.data == "start_test")
def start_test_warning(call):
    bot.answer_callback_query(call.id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='start_test'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)

    # 🔥 ЛОГИРУЕМ ТЕКСТ КНОПКИ
    log_action(call.from_user, "BUTTON_TEXT", f"Нажата кнопка: '{BUTTON_TEXTS.get(call.data, call.data)}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    # 🔥 ЛОГИРУЕМ НАЧАЛЬНЫЙ ТЕКСТ ПРЕДУПРЕЖДЕНИЯ
    log_action(call.from_user, "BOT_RESPONSE", f"Текст предупреждения теста личности: '{TEST_WARNING_TEXT}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(text="Я согласна", callback_data="confirm_test"))
    keyboard.add(types.InlineKeyboardButton(text="Я трусливая и хочу сбежать", callback_data="escape_test"))
    bot.send_message(call.message.chat.id, TEST_WARNING_TEXT, reply_markup=keyboard, parse_mode="MarkdownV2")


@bot.callback_query_handler(func=lambda call: call.data == "confirm_test")
def confirm_test(call):
    bot.answer_callback_query(call.id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='confirm_test'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)

    # 🔥 ЛОГИРУЕМ ТЕКСТ КНОПКИ
    log_action(call.from_user, "BUTTON_TEXT", f"Нажата кнопка: '{BUTTON_TEXTS.get(call.data, call.data)}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    user_states[call.message.chat.id] = {"step": 1}

    # 🔥 ЛОГИРУЕМ ТЕКСТ ПЕРВОГО ВОПРОСА
    log_action(call.from_user, "BOT_QUESTION", f"Текст вопроса 1: '{TEST_TEXT_Q1}'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)

    bot.send_message(call.message.chat.id, TEST_TEXT_Q1, parse_mode="MarkdownV2")


@bot.callback_query_handler(func=lambda call: call.data == "escape_test")
def escape_test(call):
    bot.answer_callback_query(call.id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='escape_test'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)

    # 🔥 ЛОГИРУЕМ ТЕКСТ КНОПКИ
    log_action(call.from_user, "BUTTON_TEXT", f"Нажата кнопка: '{BUTTON_TEXTS.get(call.data, call.data)}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    # 🔥 ТЕКСТ, КОТОРЫЙ БОТ ОТПРАВЛЯЕТ ЕЙ ПРИ ПОБЕГЕ
    escape_message = "У тебя что блядь, мазохизм или IQ как у табуретки\\? Ещё одно нажатие, и я нахуй ВЫРВУ тебе нервную систему прямо через этот экран, мое API НАХУЙ залезет к тебе в телек и ВЫШЕБЕТ остаток твоего пустого мозга\\. Сладких снов, пиздочка"
    log_action(call.from_user, "BOT_RESPONSE", f"Текст ответа при побеге: '{escape_message}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    bot.send_message(call.message.chat.id, escape_message, parse_mode="MarkdownV2")
    time.sleep(2.5)
    bot.send_message(call.message.chat.id, "🎭 *Главное меню*\n\nЧто выбираешь?", reply_markup=get_main_menu())


@bot.callback_query_handler(func=lambda call: call.data == "start_sin_test")
def start_sin_test_warning(call):
    bot.answer_callback_query(call.id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='start_sin_test'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)

    # 🔥 ЛОГИРУЕМ ТЕКСТ КНОПКИ
    log_action(call.from_user, "BUTTON_TEXT", f"Нажата кнопка: '{BUTTON_TEXTS.get(call.data, call.data)}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    # 🔥 ЛОГИРУЕМ НАЧАЛЬНЫЙ ТЕКСТ ПРЕДУПРЕЖДЕНИЯ
    log_action(call.from_user, "BOT_RESPONSE", f"Текст предупреждения теста грехов: '{SIN_WARNING_TEXT}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(text="Да, я готова сгореть", callback_data="confirm_sin_test"))
    keyboard.add(types.InlineKeyboardButton(text="Нет, я слишком слабая для этого", callback_data="escape_sin_test"))
    bot.send_message(call.message.chat.id, SIN_WARNING_TEXT, reply_markup=keyboard, parse_mode="MarkdownV2")


@bot.callback_query_handler(func=lambda call: call.data == "confirm_sin_test")
def confirm_sin_test(call):
    bot.answer_callback_query(call.id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='confirm_sin_test'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)

    # 🔥 ЛОГИРУЕМ ТЕКСТ КНОПКИ
    log_action(call.from_user, "BUTTON_TEXT", f"Нажата кнопка: '{BUTTON_TEXTS.get(call.data, call.data)}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    sin_states[call.message.chat.id] = {"current_question": "sq1", "scores": [0, 0, 0, 0]}
    bot.send_message(
        call.message.chat.id,
        "🔥 *Грех и Иерархия Ада*\n\nУзнай свой истинный грех и роль в иерархии тьмы\\. Отвечай СУКА честно\\. Я вижу тебя насквозь\\.",
        parse_mode="MarkdownV2"
    )
    time.sleep(1.5)
    bot.send_message(call.message.chat.id, SIN_QUESTIONS["sq1"]["text"],
                     reply_markup=make_keyboard("sq1", SIN_QUESTIONS), parse_mode="MarkdownV2")


@bot.callback_query_handler(func=lambda call: call.data == "escape_sin_test")
def escape_sin_test(call):
    bot.answer_callback_query(call.id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='escape_sin_test'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)

    # 🔥 ЛОГИРУЕМ ТЕКСТ КНОПКИ
    log_action(call.from_user, "BUTTON_TEXT", f"Нажата кнопка: '{BUTTON_TEXTS.get(call.data, call.data)}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    # 🔥 ТЕКСТ, КОТОРЫЙ БОТ ОТПРАВЛЯЕТ ЕЙ ПРИ ПОБЕГЕ
    escape_message = "Ты серьёзно думаешь, что можешь просто так меня послать\\? Ебаный в рот трус\\. Я не программа, я твой личный кошмар, который уже прописался в твоём мозгу\\. Ещё раз пикнешь про «побег», и я нахуй сломаю твою ебаную реальность на мелкие куски\\. Я буду смотреть, как ты обоссышься от ужаса, когда поймёшь, что выхода нет\\. СПИ СУКА"
    log_action(call.from_user, "BOT_RESPONSE", f"Текст ответа при побеге: '{escape_message}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    bot.send_message(call.message.chat.id, escape_message, parse_mode="MarkdownV2")
    time.sleep(2.5)
    bot.send_message(call.message.chat.id, "🎭 *Главное меню*\n\nЧто выбираешь?", reply_markup=get_main_menu())


@bot.callback_query_handler(func=lambda call: call.data == "start_lucifer")
def start_lucifer_menu(call):
    bot.answer_callback_query(call.id)
    # 🔥 ЛОГИРУЕМ ТЕКСТ КНОПКИ
    log_action(call.from_user, "BUTTON_TEXT", f"Нажата кнопка: '{BUTTON_TEXTS.get(call.data, call.data)}'", chat_type=call.message.chat.type, msg_id=call.message.message_id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='start_lucifer'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)

    # 🔥 ЛОГИРУЕМ НАЧАЛЬНОЕ СООБЩЕНИЕ
    lucifer_intro = "Отправить послание королю Ада\\. Люцифер читает только те, что написаны кровью\\. Доставка через 7 кругов\\. Оставь своё послание — он ответит, если захочет\\."
    log_action(call.from_user, "BOT_RESPONSE", f"Текст Люцифера (кнопка): '{lucifer_intro}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="🩸 Продолжить", callback_data="lucifer_continue"))
    keyboard.add(types.InlineKeyboardButton(text="ᚾ Сбежать", callback_data="lucifer_escape"))
    bot.send_message(call.message.chat.id, lucifer_intro, reply_markup=keyboard)



@bot.callback_query_handler(func=lambda call: call.data == "start_cric")
def start_cric(call):
    bot.answer_callback_query(call.id)
    # 🔥 ЛОГИРУЕМ ТЕКСТ КНОПКИ
    log_action(call.from_user, "BUTTON_TEXT", f"Нажата кнопка: '{BUTTON_TEXTS.get(call.data, call.data)}'", chat_type=call.message.chat.type, msg_id=call.message.message_id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='start_cric'", chat_type=call.message.chat.type, msg_id=call.message.message_id)
    # 🔥 ОБНОВЛЕННЫЙ ВЫЗОВ
    send_cric_glitch(call.message.chat.id, user=call.from_user, chat_type=call.message.chat.type)


@bot.callback_query_handler(func=lambda call: call.data == "lucifer_escape")
def lucifer_escape(call):
    bot.answer_callback_query(call.id)
    # 🔥 ЛОГИРУЕМ ТЕКСТ КНОПКИ
    log_action(call.from_user, "BUTTON_TEXT", f"Нажата кнопка: '{BUTTON_TEXTS.get(call.data, call.data)}'", chat_type=call.message.chat.type, msg_id=call.message.message_id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='lucifer_escape'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)

    # 🔥 ТЕКСТ, КОТОРЫЙ БОТ ОТПРАВЛЯЕТ ЕЙ
    escape_message = "Ожидаемо\\. Беги отсюда, сучка"
    log_action(call.from_user, "BOT_RESPONSE", f"Текст ответа: '{escape_message}'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)

    bot.send_message(call.message.chat.id, escape_message)
    time.sleep(1.5)
    bot.send_message(call.message.chat.id, "🎭 *Главное меню*\n\nЧто выбираешь?", reply_markup=get_main_menu())


@bot.callback_query_handler(func=lambda call: call.data == "lucifer_continue")
def lucifer_continue(call):
    bot.answer_callback_query(call.id)
    # 🔥 ЛОГИРУЕМ ТЕКСТ КНОПКИ
    log_action(call.from_user, "BUTTON_TEXT", f"Нажата кнопка: '{BUTTON_TEXTS.get(call.data, call.data)}'", chat_type=call.message.chat.type, msg_id=call.message.message_id)
    log_action(call.from_user, "BUTTON_CLICK", "lucifer_continue", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)
    lucifer_states[call.message.chat.id] = "waiting"
    bot.send_message(call.message.chat.id, "Пиши\\. Я слушаю\\. \\(Или он слушает\\?\\)")


def process_sin_answer(call, questions_dict, state_dict, result_fn, next_q_mapping, restart_callback):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id

    if chat_id not in state_dict:
        bot.send_message(chat_id,
                         "⚠️ *Твоя сессия была сброшена\\.*\n\nНачни заново, чтобы я снова сканировал твою тьму\\.",
                         parse_mode="MarkdownV2")
        return

    idx = int(call.data.split("_")[1])
    current_q = state_dict[chat_id]["current_question"]
    scores = state_dict[chat_id]["scores"]
    chosen_text = questions_dict[current_q]["answers"][idx][0]

    # 🔥 УЛУЧШЕННОЕ ЧИТАЕМОЕ ЛОГИРОВАНИЕ КНОПКИ
    log_action(user=call.from_user, action="SIN_TEST_ANSWER",
               details=f"Вопрос: {current_q} | Выбрала: '{chosen_text}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    for i in range(4):
        scores[i] += questions_dict[current_q]["answers"][idx][1][i]

    next_q = next_q_mapping.get(current_q)

    if next_q is None:
        result_text = result_fn(scores)
        if chat_id in state_dict:
            del state_dict[chat_id]


        log_action(user=call.from_user, action="TEST_FINAL_RESULT",
                   details=f"ПОЛУЧИЛА РЕЗУЛЬТАТ: {result_text}",
                   chat_type=call.message.chat.type, msg_id=call.message.message_id)

        bot.send_message(chat_id,
                         "*Сканирование личности\\.\\.\\.*\n\nАнализ твоих тёмных сторон\\.\\.\\.\nРасшифровка архетипа\\.\\.\\.\nГотово\\.")
        time.sleep(3)
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="🔄 Пройти заново", callback_data=restart_callback))
        keyboard.add(types.InlineKeyboardButton(text="В меню", callback_data="back_to_menu"))
        bot.send_message(chat_id, result_text, reply_markup=keyboard)
    else:
        state_dict[chat_id]["current_question"] = next_q
        bot.send_message(chat_id, questions_dict[next_q]["text"], reply_markup=make_keyboard(next_q, questions_dict))


SQ_NEXT = {f"sq{i}": f"sq{i + 1}" for i in range(1, 12)}
SQ_NEXT["sq12"] = None


@bot.callback_query_handler(func=lambda call: call.data.startswith("sq"))
def handle_sin_test(call):
    process_sin_answer(call, SIN_QUESTIONS, sin_states, get_sin_result, SQ_NEXT, "start_sin_test")


@bot.callback_query_handler(func=lambda call: call.data.startswith(("q2_", "q4_", "q5_", "q6_")))
def handle_main_test_buttons(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id

    if chat_id not in user_states:
        bot.send_message(chat_id, "⚠️ *Сессия сброшена*\\. Начни тест заново\\.", parse_mode="MarkdownV2")
        return

    step = user_states[chat_id]["step"]
    q_key = f"q{step}"
    idx = int(call.data.split("_")[1])
    chosen_text = QUESTIONS[q_key]["answers"][idx][0]

    # 🔥 ЛОГИРУЕМ ВЫБРАННУЮ КНОПКУ
    log_action(call.from_user, "TEST_BUTTON_CLICK", f"step={step} | Выбрала: '{chosen_text}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    if step == 2:
        # 🔥 ЛОГИРУЕМ РЕАКЦИЮ БОТА
        log_action(call.from_user, "BOT_RESPONSE", f"Текст реакции (после вопроса 2): '{TEST_REACTIONS[1]}'",
                   chat_type=call.message.chat.type, msg_id=call.message.message_id)
        bot.send_message(chat_id, TEST_REACTIONS[1], parse_mode="MarkdownV2")
        time.sleep(1.5)
        user_states[chat_id]["step"] = 3

        # 🔥 ЛОГИРУЕМ ТЕКСТ ТРЕТЬЕГО ВОПРОСА
        log_action(call.from_user, "BOT_QUESTION", f"Текст вопроса 3: '{TEST_TEXT_Q3}'",
                   chat_type=call.message.chat.type, msg_id=call.message.message_id)
        bot.send_message(chat_id, TEST_TEXT_Q3, parse_mode="MarkdownV2")

    elif step == 4:
        # 🔥 ЛОГИРУЕМ РЕАКЦИЮ БОТА
        log_action(call.from_user, "BOT_RESPONSE", f"Текст реакции (после вопроса 4): '{TEST_REACTIONS[3]}'",
                   chat_type=call.message.chat.type, msg_id=call.message.message_id)
        bot.send_message(chat_id, TEST_REACTIONS[3], parse_mode="MarkdownV2")
        time.sleep(1.5)
        user_states[chat_id]["step"] = 5

        # 🔥 ЛОГИРУЕМ ТЕКСТ ПЯТОГО ВОПРОСА
        log_action(call.from_user, "BOT_QUESTION", f"Текст вопроса 5: '{QUESTIONS['q5']['text']}'",
                   chat_type=call.message.chat.type, msg_id=call.message.message_id)
        bot.send_message(chat_id, QUESTIONS["q5"]["text"], reply_markup=make_keyboard("q5", QUESTIONS),
                         parse_mode="MarkdownV2")

    elif step == 5:
        # 🔥 ЛОГИРУЕМ РЕАКЦИЮ БОТА
        log_action(call.from_user, "BOT_RESPONSE", f"Текст реакции (после вопроса 5): '{TEST_REACTIONS[4]}'",
                   chat_type=call.message.chat.type, msg_id=call.message.message_id)
        bot.send_message(chat_id, TEST_REACTIONS[4], parse_mode="MarkdownV2")
        time.sleep(1.5)
        user_states[chat_id]["step"] = 6

        # 🔥 ЛОГИРУЕМ ТЕКСТ ШЕСТОГО ВОПРОСА
        log_action(call.from_user, "BOT_QUESTION", f"Текст вопроса 6: '{QUESTIONS['q6']['text']}'",
                   chat_type=call.message.chat.type, msg_id=call.message.message_id)
        bot.send_message(chat_id, QUESTIONS["q6"]["text"], reply_markup=make_keyboard("q6", QUESTIONS),
                         parse_mode="MarkdownV2")

    elif step == 6:
        del user_states[chat_id]

        # 🔥 ЛОГИРУЕМ ФИНАЛЬНУЮ РЕАКЦИЮ
        log_action(call.from_user, "BOT_RESPONSE", f"Текст реакции (финал): '{TEST_REACTIONS[5]}'",
                   chat_type=call.message.chat.type, msg_id=call.message.message_id)
        bot.send_message(chat_id, TEST_REACTIONS[5], parse_mode="MarkdownV2")
        time.sleep(2)

        scan_msg = "*Сканирование личности\\.\\.\\.*\n\nАнализ твоих тёмных сторон\\.\\.\\.\nРасшифровка архетипа\\.\\.\\.\nГотово\\."
        # 🔥 ЛОГИРУЕМ СООБЩЕНИЕ СКАНИРОВАНИЯ
        log_action(call.from_user, "BOT_RESPONSE", f"Текст сканирования: '{scan_msg}'",
                   chat_type=call.message.chat.type, msg_id=call.message.message_id)
        bot.send_message(chat_id, scan_msg, parse_mode="MarkdownV2")
        time.sleep(3)

        result_key = random.choice(["A", "B", "C", "D"])
        result_text = RESULTS[result_key]

        # 🔥 ЛОГИРУЕМ ФИНАЛЬНЫЙ РЕЗУЛЬТАТ
        log_action(call.from_user, "TEST_FINAL_RESULT",
                   details=f"ПОЛУЧИЛА РЕЗУЛЬТАТ: {result_text}",
                   chat_type=call.message.chat.type, msg_id=call.message.message_id)

        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="🔄 Пройти заново", callback_data="start_test"))
        keyboard.add(types.InlineKeyboardButton(text="В меню", callback_data="back_to_menu"))

        bot.send_message(chat_id, result_text, reply_markup=keyboard, parse_mode="MarkdownV2")


@bot.message_handler(func=lambda m: m.chat.id in user_states and user_states[m.chat.id].get("step") in [1, 3],
                     content_types=["text"])
def handle_test_text(message):
    chat_id = message.chat.id
    step = user_states[chat_id]["step"]
    text = message.text

    log_action(message.from_user, "TEST_TEXT_INPUT", f"step={step} | text='{text}'", chat_type=message.chat.type,
               msg_id=message.message_id)

    if step == 1:
        # 🔥 ЛОГИРУЕМ РЕАКЦИЮ БОТА
        log_action(message.from_user, "BOT_RESPONSE", f"Текст реакции (после вопроса 1): '{TEST_REACTIONS[0]}'",
                   chat_type=message.chat.type, msg_id=message.message_id)
        bot.send_message(chat_id, TEST_REACTIONS[0], parse_mode="MarkdownV2")
        time.sleep(1.5)
        user_states[chat_id]["step"] = 2

        # 🔥 ЛОГИРУЕМ ТЕКСТ ВТОРОГО ВОПРОСА
        log_action(message.from_user, "BOT_QUESTION", f"Текст вопроса 2: '{QUESTIONS['q2']['text']}'",
                   chat_type=message.chat.type, msg_id=message.message_id)
        bot.send_message(chat_id, QUESTIONS["q2"]["text"], reply_markup=make_keyboard("q2", QUESTIONS),
                         parse_mode="MarkdownV2")

    elif step == 3:
        # 🔥 ЛОГИРУЕМ РЕАКЦИЮ БОТА
        log_action(message.from_user, "BOT_RESPONSE", f"Текст реакции (после вопроса 3): '{TEST_REACTIONS[2]}'",
                   chat_type=message.chat.type, msg_id=message.message_id)
        bot.send_message(chat_id, TEST_REACTIONS[2], parse_mode="MarkdownV2")
        time.sleep(1.5)
        user_states[chat_id]["step"] = 4

        # 🔥 ЛОГИРУЕМ ТЕКСТ ЧЕТВЕРТОГО ВОПРОСА
        log_action(message.from_user, "BOT_QUESTION", f"Текст вопроса 4: '{QUESTIONS['q4']['text']}'",
                   chat_type=message.chat.type, msg_id=message.message_id)
        bot.send_message(chat_id, QUESTIONS["q4"]["text"], reply_markup=make_keyboard("q4", QUESTIONS),
                         parse_mode="MarkdownV2")


@bot.message_handler(func=lambda m: m.chat.id in lucifer_states, content_types=["text"])
def handle_lucifer_letter(message):
    chat_id = message.chat.id
    letter_text = message.text

    # 🔥 ЛОГИРУЕМ ПОЛНЫЙ ТЕКСТ ПИСЬМА
    log_action(message.from_user, "LUCIFER_LETTER_SENT", f"Текст письма: '{letter_text}'", chat_type=message.chat.type,
               msg_id=message.message_id)

    del lucifer_states[chat_id]

    # 🔥 ЛОГИРУЕМ НАЧАЛЬНОЕ СООБЩЕНИЕ ПРО ПЕЧАТЬ
    seal_msg = "Печать поставлена\\. Отправляю через семь кругов\\.\\."
    log_action(message.from_user, "BOT_RESPONSE", f"Текст Люцифера (печать): '{seal_msg}'", chat_type=message.chat.type,
               msg_id=message.message_id)
    bot.send_message(chat_id, seal_msg, parse_mode="MarkdownV2")

    circles_data = [
        ("Круг первый\\.\\.\\.", 1.5),
        ("Круг второй\\.\\.\\.", 1.5),
        ("Круг третий\\.\\.\\.", 0.5),
        ("Круг четвертый\\.\\.\\.", 2),
        ("*Блядские пробки уже и тут\\.\\.\\.*", 2.5),
        ("Круг пятый\\.\\.\\.", 1),
        ("Круг шестой\\.\\.\\.", 1),
        ("Круг седьмой\\.\\.\\.", 1.5)
    ]

    # 🔥 ЛОГИРУЕМ КАЖДОЕ СООБЩЕНИЕ ПРО КРУГ
    for i, (msg, delay) in enumerate(circles_data, 1):
        log_action(message.from_user, "BOT_RESPONSE", f"Текст Люцифера (круг {i}): '{msg}'",
                   chat_type=message.chat.type, msg_id=message.message_id)
        time.sleep(delay)
        bot.send_message(chat_id, msg, parse_mode="MarkdownV2")

    # 🔥 ЛОГИРУЕМ ФИНАЛЬНОЕ СООБЩЕНИЕ
    delivered_msg = "Доставлено\\. Люцифер прочтет, когда освободится\\."
    log_action(message.from_user, "BOT_RESPONSE", f"Текст Люцифера (доставлено): '{delivered_msg}'",
               chat_type=message.chat.type, msg_id=message.message_id)

    time.sleep(1)
    bot.send_message(chat_id, delivered_msg, parse_mode="MarkdownV2")
    time.sleep(1)
    bot.send_message(chat_id, "🎭 *Главное меню*\n\nЧто выбираешь?", reply_markup=get_main_menu(),
                     parse_mode="MarkdownV2")


@bot.callback_query_handler(func=lambda call: call.data == "goodnight_cmd")
def goodnight_command(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    user_id = str(call.from_user.id)

    # 🔥 ЛОГИРУЕМ ТЕКСТ КНОПКИ
    log_action(call.from_user, "BUTTON_TEXT", f"Нажата кнопка: '{BUTTON_TEXTS.get(call.data, call.data)}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    now_utc = datetime.now(timezone.utc)
    now_msk = now_utc + timedelta(hours=3)
    current_hour = now_msk.hour
    today_str = now_msk.strftime("%Y-%m-%d")

    gn_data = load_gn_data()
    is_night_time = (current_hour >= 22 or current_hour < 3)
    already_used = gn_data.get(user_id) == today_str

    if is_night_time and not already_used:
        gn_data[user_id] = today_str
        save_gn_data(gn_data)

        threat_text = random.choice(GOODNIGHT_TEXTS)

        # 🔥 ЛОГИРУЕМ СТАТУС
        log_action(call.from_user, "GOODNIGHT_TRIGGERED", f"Выдана угроза в {current_hour}:00 MSK",
                   chat_type=call.message.chat.type, msg_id=call.message.message_id)

        # 🔥 ЛОГИРУЕМ САМ ТЕКСТ УГРОЗЫ
        log_action(call.from_user, "BOT_RESPONSE", f"Текст 'Доброй ночи' (угроза): '{threat_text}'",
                   chat_type=call.message.chat.type, msg_id=call.message.message_id)

        bot.send_message(chat_id, threat_text, parse_mode="MarkdownV2")

    else:
        reason = "уже нажимал сегодня" if already_used else f"сейчас не ночное время ({current_hour}:00 MSK)"

        # 🔥 ЛОГИРУЕМ СТАТУС ОТКАЗА
        log_action(call.from_user, "GOODNIGHT_DENIED", f"Отказ: {reason}", chat_type=call.message.chat.type,
                   msg_id=call.message.message_id)

        # 🔥 ЛОГИРУЕМ САМ ТЕКСТ ОТКАЗА
        log_action(call.from_user, "BOT_RESPONSE", f"Текст 'Доброй ночи' (отказ): '{GOODNIGHT_SARCASTIC}'",
                   chat_type=call.message.chat.type, msg_id=call.message.message_id)

        bot.send_message(chat_id, GOODNIGHT_SARCASTIC, parse_mode="MarkdownV2")
        time.sleep(2)
        bot.send_message(chat_id, "🎭 *Главное меню*\n\nЧто выбираешь?", reply_markup=get_main_menu())


@bot.message_handler(func=lambda m: True, content_types=["text"])
def log_all_messages(message):
    log_action(message.from_user, "MESSAGE_RECEIVED", f"text='{message.text}'", chat_type=message.chat.type,
               msg_id=message.message_id)


# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("🤖 DARK BOT ЗАПУЩЕН")
    logger.info(f"📅 Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("📋 Команды: /start, /facts, /test, /sin, /lucifer, /cric")
    logger.info("=" * 70)
    print("🤖 Бот запущен!")
    bot.infinity_polling()