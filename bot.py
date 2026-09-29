import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

try:
    import telebot
except ImportError:
    install("pyTelegramBotAPI")
    import telebot

import telebot
from telebot import types
import time
import random
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from config import BOT_TOKEN
from datetime import datetime, timezone, timedelta
import json
import os

# ИМПОРТ ТЕКСТОВ ИЗ ОТДЕЛЬНОГО ФАЙЛА
from texts import (
    FACTS, QUESTIONS, RESULTS, SIN_QUESTIONS, SIN_RESULTS,
    TEST_TEXT_Q1, TEST_TEXT_Q3, TEST_REACTIONS,
    GOODNIGHT_TEXTS, GOODNIGHT_SARCASTIC
)

# Текст предупреждения перед тестом личности
TEST_WARNING_TEXT = (
    "Прежде чем мы начнем, ответь честно: ты уверена, что выдержишь правду\\? "
    "Конечно уверена, я не спрашиваю твоего мнения\\. "
    "Или ты начнешь плакать и закроешь чат, как только я коснусь того, "
    "что тебя триггерит\\? Это не развлечение\\. Это блядское вскрытие\\."
)

# Текст предупреждения перед тестом на 12 вопросов (Грехи)
SIN_WARNING_TEXT = (
    "Ты правда думаешь, что готова узнать свой истинный грех\\? "
    "Это не милый тестик из интернета\\. Этот тест вскроет всю гниль из твоей ёбаной души\\. "
    "Если ты слабая, жалкая и боишься узнать правду о себе — вали Н\\*\\*\\*\\* отсюда\\. "
    "Готова ли ты сгореть в Иерархии Ада\\?"
)

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ (ПРОКАЧАННАЯ) ====================
logger = logging.getLogger("DarkBot")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
LOG_GROUP_ID = -5564429537
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

file_handler = RotatingFileHandler(
    "bot.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
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


def log_action(user, action: str, details: str = "", chat_type: str = "private", msg_id: int = 0):
    try:
        user_info = get_user_details(user, chat_type)
        time_now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_msg = (
            f"[{time_now}] {user_info} | "
            f"ACTION: {action} | "
            f"MSG_ID: {msg_id} | "
            f"DETAILS: {details}"
        )
        logger.info(log_msg)

        # 🔥 ОТПРАВКА В TELEGRAM-ГРУППУ
        try:
            bot.send_message(LOG_GROUP_ID, log_msg)
        except Exception as e:
            logger.error(f"Ошибка отправки лога в группу: {e}")

        # 🔥 СОХРАНЕНИЕ В ФАЙЛ
        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Аноним"
        save_user_log(user.id, user_name, action, details, time_now)

    except Exception as e:
        logger.error(f"Ошибка при логировании действия: {e}")


def log_user_info(user, chat_type: str = "private"):
    try:
        username = f"@{user.username}" if user.username else "без_ника"
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Аноним"
        premium = "YES" if getattr(user, 'is_premium', False) else "NO"
        info = (
            f"🆕 NEW CONTACT | ID: {user.id} | Name: '{full_name}' | "
            f"Username: {username} | Premium: {premium} | Lang: {user.language_code or 'unknown'} | "
            f"Chat_Type: {chat_type} | Is_bot: {user.is_bot}"
        )
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


# ==================== КЛАВИАТУРЫ И ЛОГИКА ====================
def make_keyboard(question_key: str, questions_dict: dict) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for i, (text, _) in enumerate(questions_dict[question_key]["answers"]):
        callback_data = f"{question_key}_{i}"
        keyboard.add(types.InlineKeyboardButton(text=text, callback_data=callback_data))
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


# ==================== ФУНКЦИЯ ГЛИТЧА ДЛЯ КРИКА ====================
def send_cric_glitch(chat_id):
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
    bot.send_message(chat_id, glitch_text, parse_mode="MarkdownV2")
    time.sleep(5)
    bot.send_message(chat_id, "🎭 *Главное меню*\n\nЧто выбираешь?", reply_markup=get_main_menu())

# ==================== ХРАНЕНИЕ ДАННЫХ ДОБРОЙ НОЧИ ====================
GN_DATA_FILE = "goodnight_data.json"

def load_gn_data():
    if os.path.exists(GN_DATA_FILE):
        try:
            with open(GN_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Убеждаемся, что это словарь
                return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            # Если файл поврежден (например, бот выключили во время записи), начинаем с нуля
            print("⚠️ Файл goodnight_data.json поврежден, создаем новый.")
            return {}
    return {}

def save_gn_data(data):
    try:
        with open(GN_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ ОШИБКА СОХРАНЕНИЯ ФАЙЛА: {e}")


# ==================== СОХРАНЕНИЕ ЛОГОВ В ФАЙЛ ====================
LOGS_FILE = "user_logs.json"


def save_user_log(user_id, user_name, action, details, timestamp):
    """Сохраняет лог в JSON файл."""
    try:
        # Загружаем существующие логи
        if os.path.exists(LOGS_FILE):
            with open(LOGS_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        else:
            logs = []

        # Добавляем новый лог
        log_entry = {
            "user_id": user_id,
            "user_name": user_name,
            "action": action,
            "details": details,
            "timestamp": timestamp
        }
        logs.append(log_entry)

        # Сохраняем обратно
        with open(LOGS_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Ошибка сохранения лога в файл: {e}")

# ==================== КОМАНДЫ ====================



@bot.message_handler(commands=["start"])
def cmd_start(message):
    log_user_info(message.from_user, chat_type=message.chat.type)
    log_action(message.from_user, "COMMAND", "/start", chat_type=message.chat.type, msg_id=message.message_id)
    bot.send_message(
        message.chat.id,
        "🎭 *Добро пожаловать в Архив\\.*\n\n"
        "Здесь мы определим твой истинный вайб\\. "
        "Я проанализирую твои реакции и скажу тебе то, "
        "что ты так неумело пытаешься скрыть\\.\n\n"
        "Или узнай свой грех и роль в Иерархии Ада\\.\n\n"
        "Выбирай, пока я разрешаю\\.",
        reply_markup=get_main_menu()
    )


@bot.message_handler(commands=["download_logs"])
def cmd_download_logs(message):
    """Отправляет файл с логами."""
    # Проверка, что это ты (замени на свой ID)
    if message.from_user.id != 123456789:  # ← ТВОЙ ID
        bot.send_message(message.chat.id, "⛔ Доступ запрещен.")
        return

    if os.path.exists(LOGS_FILE):
        with open(LOGS_FILE, "rb") as f:
            bot.send_document(message.chat.id, f, caption="📊 Логи бота")
    else:
        bot.send_message(message.chat.id, "❌ Файл логов не найден.")

@bot.message_handler(commands=["facts"])
def cmd_facts(message):
    log_action(message.from_user, "COMMAND", "/facts", chat_type=message.chat.type, msg_id=message.message_id)
    fact = random.choice(FACTS)
    log_action(message.from_user, "FACT_SENT", fact[:50] + "...", chat_type=message.chat.type,
               msg_id=message.message_id)
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="🎲 Ещё факт", callback_data="random_fact"))
    keyboard.add(types.InlineKeyboardButton(text="В меню", callback_data="back_to_menu"))
    bot.send_message(message.chat.id, fact, reply_markup=keyboard)


@bot.message_handler(commands=["test"])
def cmd_test(message):
    log_action(message.from_user, "COMMAND", "/test", chat_type=message.chat.type, msg_id=message.message_id)
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(text="Я согласна", callback_data="confirm_test"))
    keyboard.add(types.InlineKeyboardButton(text="Я трусливая и хочу сбежать", callback_data="escape_test"))
    bot.send_message(message.chat.id, TEST_WARNING_TEXT, reply_markup=keyboard, parse_mode="MarkdownV2")


@bot.message_handler(commands=["sin"])
def cmd_sin(message):
    log_action(message.from_user, "COMMAND", "/sin", chat_type=message.chat.type, msg_id=message.message_id)
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(text="Да, я готова сгореть", callback_data="confirm_sin_test"))
    keyboard.add(types.InlineKeyboardButton(text="Нет, я слишком слабая для этого", callback_data="escape_sin_test"))
    bot.send_message(message.chat.id, SIN_WARNING_TEXT, reply_markup=keyboard, parse_mode="MarkdownV2")


@bot.message_handler(commands=["lucifer"])
def cmd_lucifer(message):
    log_action(message.from_user, "COMMAND", "/lucifer", chat_type=message.chat.type, msg_id=message.message_id)
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="🩸 Продолжить", callback_data="lucifer_continue"))
    keyboard.add(types.InlineKeyboardButton(text="ᚾ Сбежать", callback_data="lucifer_escape"))
    bot.send_message(
        message.chat.id,
        "Отправить послание королю Ада\\. Люцифер читает только те, что написаны кровью\\. Доставка через 7 кругов\\. Оставь своё послание — он ответит, если захочет\\.",
        reply_markup=keyboard
    )


@bot.message_handler(commands=["cric"])
def cmd_cric(message):
    log_action(message.from_user, "COMMAND", "/cric", chat_type=message.chat.type, msg_id=message.message_id)
    send_cric_glitch(message.chat.id)


# ==================== ОБРАБОТЧИКИ CALLBACK (КНОПКИ) ====================
@bot.callback_query_handler(func=lambda call: call.data == "random_fact")
def send_random_fact(call):
    bot.answer_callback_query(call.id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='random_fact'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)
    fact = random.choice(FACTS)
    log_action(call.from_user, "FACT_SENT", fact[:50] + "...", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="🎲 Ещё факт", callback_data="random_fact"))
    keyboard.add(types.InlineKeyboardButton(text="В меню", callback_data="back_to_menu"))
    bot.send_message(call.message.chat.id, fact, reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def back_to_menu(call):
    bot.answer_callback_query(call.id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='back_to_menu'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)
    bot.send_message(call.message.chat.id, "🎭 *Главное меню*\n\nЧто выбираешь?", reply_markup=get_main_menu())


# --- ПРЕДУПРЕЖДЕНИЕ: ТЕСТ ЛИЧНОСТИ ---
@bot.callback_query_handler(func=lambda call: call.data == "start_test")
def start_test_warning(call):
    bot.answer_callback_query(call.id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='start_test'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(text="Я согласна", callback_data="confirm_test"))
    keyboard.add(types.InlineKeyboardButton(text="Я трусливая и хочу сбежать", callback_data="escape_test"))
    bot.send_message(call.message.chat.id, TEST_WARNING_TEXT, reply_markup=keyboard, parse_mode="MarkdownV2")


@bot.callback_query_handler(func=lambda call: call.data == "confirm_test")
def confirm_test(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    user_states[chat_id] = {"step": 1}
    bot.send_message(chat_id, TEST_TEXT_Q1, parse_mode="MarkdownV2")


@bot.callback_query_handler(func=lambda call: call.data == "escape_test")
def escape_test(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    bot.send_message(
        chat_id,
        "У тебя что блядь, мазохизм или IQ как у табуретки\\? Ещё одно нажатие, "
        "и я нахуй ВЫРВУ тебе нервную систему прямо через этот экран, мое API НАХУЙ "
        "залезет к тебе в телек и ВЫШЕБЕТ остаток твоего пустого мозга\\. Сладких снов, пиздочка",
        parse_mode="MarkdownV2"
    )
    time.sleep(2.5)
    bot.send_message(
        chat_id,
        "🎭 *Главное меню*\n\nЧто выбираешь?",
        reply_markup=get_main_menu()
    )


# --- ПРЕДУПРЕЖДЕНИЕ: ТЕСТ НА 12 ВОПРОСОВ (ГРЕХИ) ---
@bot.callback_query_handler(func=lambda call: call.data == "start_sin_test")
def start_sin_test_warning(call):
    bot.answer_callback_query(call.id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='start_sin_test'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(text="Да, я готова сгореть", callback_data="confirm_sin_test"))
    keyboard.add(types.InlineKeyboardButton(text="Нет, я слишком слабая для этого", callback_data="escape_sin_test"))
    bot.send_message(call.message.chat.id, SIN_WARNING_TEXT, reply_markup=keyboard, parse_mode="MarkdownV2")




@bot.callback_query_handler(func=lambda call: call.data == "confirm_sin_test")
def confirm_sin_test(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    # Инициализируем состояние только после согласия
    sin_states[chat_id] = {"current_question": "sq1", "scores": [0, 0, 0, 0]}

    bot.send_message(
        chat_id,
        "🔥 *Грех и Иерархия Ада*\n\nУзнай свой истинный грех и роль в иерархии тьмы\\. Отвечай СУКА честно\\. Я вижу тебя насквозь\\.",
        parse_mode="MarkdownV2"
    )
    time.sleep(1.5)  # Драматичная пауза
    bot.send_message(chat_id, SIN_QUESTIONS["sq1"]["text"], reply_markup=make_keyboard("sq1", SIN_QUESTIONS),
                     parse_mode="MarkdownV2")


@bot.callback_query_handler(func=lambda call: call.data == "escape_sin_test")
def escape_sin_test(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    bot.send_message(
        chat_id,
        "Ты серьёзно думаешь, что можешь просто так меня послать\\? Ебаный в рот трус\\. "
        "Я не программа, я твой личный кошмар, который уже прописался в твоём мозгу\\. "
        "Ещё раз пикнешь про «побег», и я нахуй сломаю твою ебаную реальность на мелкие куски\\. "
        "Я буду смотреть, как ты обоссышься от ужаса, когда поймёшь, что выхода нет\\. СПИ СУКА",
        parse_mode="MarkdownV2"
    )
    time.sleep(2.5)
    bot.send_message(
        chat_id,
        "🎭 *Главное меню*\n\nЧто выбираешь?",
        reply_markup=get_main_menu()
    )


# --- ПРОЧИЕ КНОПКИ МЕНЮ ---
@bot.callback_query_handler(func=lambda call: call.data == "start_lucifer")
def start_lucifer_menu(call):
    bot.answer_callback_query(call.id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='start_lucifer'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="🩸 Продолжить", callback_data="lucifer_continue"))
    keyboard.add(types.InlineKeyboardButton(text="ᚾ Сбежать", callback_data="lucifer_escape"))
    bot.send_message(
        call.message.chat.id,
        "Отправить послание королю Ада\\. Люцифер читает только те, что написаны кровью\\. Доставка через 7 кругов\\. Оставь своё послание — он ответит, если захочет\\.",
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.data == "start_cric")
def start_cric(call):
    bot.answer_callback_query(call.id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='start_cric'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)
    send_cric_glitch(call.message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == "lucifer_escape")
def lucifer_escape(call):
    bot.answer_callback_query(call.id)
    log_action(call.from_user, "BUTTON_CLICK", "callback='lucifer_escape'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)
    bot.send_message(call.message.chat.id, "Ожидаемо\\. Беги отсюда, сучка")
    time.sleep(1.5)
    bot.send_message(call.message.chat.id, "🎭 *Главное меню*\n\nЧто выбираешь?", reply_markup=get_main_menu())


@bot.callback_query_handler(func=lambda call: call.data == "lucifer_continue")
def lucifer_continue(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    lucifer_states[chat_id] = "waiting"
    log_action(call.from_user, "BUTTON_CLICK", "callback='lucifer_continue'", chat_type=call.message.chat.type,
               msg_id=call.message.message_id)
    bot.send_message(chat_id, "Пиши\\. Я слушаю\\. \\(Или он слушает\\?\\)")


# ==================== УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК ДЛЯ ТЕСТА НА 12 ВОПРОСОВ (ГРЕХИ) ====================
def process_sin_answer(call, questions_dict, state_dict, result_fn, next_q_mapping, restart_callback):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id

    if chat_id not in state_dict:
        bot.send_message(chat_id,
                         "⚠️ *Твоя сессия была сброшена\\.*\n\nНачни заново, чтобы я снова сканировал твою тьму\\.",
                         parse_mode="MarkdownV2")
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="🔄 Начать тест заново", callback_data=restart_callback))
        bot.send_message(chat_id, "Что выбираешь?", reply_markup=keyboard)
        return

    click_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    idx = int(call.data.split("_")[1])
    current_q = state_dict[chat_id]["current_question"]
    scores = state_dict[chat_id]["scores"]
    chosen_text = questions_dict[current_q]["answers"][idx][0]

    log_action(user=call.from_user, action="SIN_TEST_ANSWER", details=f"q={current_q} | clicked='{chosen_text}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    for i in range(4):
        scores[i] += questions_dict[current_q]["answers"][idx][1][i]

    next_q = next_q_mapping.get(current_q)

    if next_q is None:
        result_text = result_fn(scores)
        if chat_id in state_dict:
            del state_dict[chat_id]
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


# ==================== ОБРАБОТЧИКИ ДЛЯ ТЕСТА ЛИЧНОСТИ (КНОПКИ) ====================
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

    log_action(call.from_user, "TEST_BUTTON_CLICK", f"step={step} | clicked='{chosen_text}'",
               chat_type=call.message.chat.type, msg_id=call.message.message_id)

    if step == 2:
        bot.send_message(chat_id, TEST_REACTIONS[1], parse_mode="MarkdownV2")
        time.sleep(1.5)
        user_states[chat_id]["step"] = 3
        bot.send_message(chat_id, TEST_TEXT_Q3, parse_mode="MarkdownV2")

    elif step == 4:
        bot.send_message(chat_id, TEST_REACTIONS[3], parse_mode="MarkdownV2")
        time.sleep(1.5)
        user_states[chat_id]["step"] = 5
        bot.send_message(chat_id, QUESTIONS["q5"]["text"], reply_markup=make_keyboard("q5", QUESTIONS),
                         parse_mode="MarkdownV2")

    elif step == 5:
        bot.send_message(chat_id, TEST_REACTIONS[4], parse_mode="MarkdownV2")
        time.sleep(1.5)
        user_states[chat_id]["step"] = 6
        bot.send_message(chat_id, QUESTIONS["q6"]["text"], reply_markup=make_keyboard("q6", QUESTIONS),
                         parse_mode="MarkdownV2")

    elif step == 6:
        del user_states[chat_id]
        bot.send_message(chat_id, TEST_REACTIONS[5], parse_mode="MarkdownV2")
        time.sleep(2)

        bot.send_message(chat_id,
                         "*Сканирование личности\\.\\.\\.*\n\nАнализ твоих тёмных сторон\\.\\.\\.\nРасшифровка архетипа\\.\\.\\.\nГотово\\.",
                         parse_mode="MarkdownV2")
        time.sleep(3)

        result_key = random.choice(["A", "B", "C", "D"])
        result_text = RESULTS[result_key]

        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="🔄 Пройти заново", callback_data="start_test"))
        keyboard.add(types.InlineKeyboardButton(text="В меню", callback_data="back_to_menu"))

        bot.send_message(chat_id, result_text, reply_markup=keyboard, parse_mode="MarkdownV2")


# ==================== ОБРАБОТЧИКИ ТЕКСТА ====================
@bot.message_handler(func=lambda m: m.chat.id in user_states and user_states[m.chat.id].get("step") in [1, 3],
                     content_types=["text"])
def handle_test_text(message):
    chat_id = message.chat.id
    step = user_states[chat_id]["step"]
    text = message.text

    log_action(message.from_user, "TEST_TEXT_INPUT", f"step={step} | text='{text}'", chat_type=message.chat.type,
               msg_id=message.message_id)

    if step == 1:
        bot.send_message(chat_id, TEST_REACTIONS[0], parse_mode="MarkdownV2")
        time.sleep(1.5)
        user_states[chat_id]["step"] = 2
        bot.send_message(chat_id, QUESTIONS["q2"]["text"], reply_markup=make_keyboard("q2", QUESTIONS),
                         parse_mode="MarkdownV2")

    elif step == 3:
        bot.send_message(chat_id, TEST_REACTIONS[2], parse_mode="MarkdownV2")
        time.sleep(1.5)
        user_states[chat_id]["step"] = 4
        bot.send_message(chat_id, QUESTIONS["q4"]["text"], reply_markup=make_keyboard("q4", QUESTIONS),
                         parse_mode="MarkdownV2")


@bot.message_handler(func=lambda m: m.chat.id in lucifer_states, content_types=["text"])
def handle_lucifer_letter(message):
    chat_id = message.chat.id
    letter_text = message.text

    log_action(message.from_user, "LUCIFER_LETTER_SENT", f"length={len(letter_text)} chars",
               chat_type=message.chat.type, msg_id=message.message_id)
    del lucifer_states[chat_id]

    bot.send_message(chat_id, "Печать поставлена\\. Отправляю через семь кругов\\.\\.", parse_mode="MarkdownV2")

    circles_data = [
        ("Круг первый\\.\\.\\.", 1.5), ("Круг второй\\.\\.\\.", 1.5), ("Круг третий\\.\\.\\.", 0.5),
        ("Круг четвертый\\.\\.\\.", 2), ("*Блядские пробки уже и тут\\.\\.\\.*", 2.5),
        ("Круг пятый\\.\\.\\.", 1), ("Круг шестой\\.\\.\\.", 1), ("Круг седьмой\\.\\.\\.", 1.5)
    ]

    for msg, delay in circles_data:
        time.sleep(delay)
        bot.send_message(chat_id, msg, parse_mode="MarkdownV2")

    time.sleep(1)
    bot.send_message(chat_id, "Доставлено\\. Люцифер прочтет, когда освободится\\.", parse_mode="MarkdownV2")
    time.sleep(1)
    bot.send_message(chat_id, "🎭 *Главное меню*\n\nЧто выбираешь?", reply_markup=get_main_menu(),
                     parse_mode="MarkdownV2")


@bot.message_handler(func=lambda m: True, content_types=["text"])
def log_all_messages(message):
    exact_time = datetime.fromtimestamp(message.date).strftime("%H:%M:%S")
    log_action(
        user=message.from_user, action="MESSAGE_RECEIVED",
        details=f"text='{message.text}' (sent at {exact_time})",
        chat_type=message.chat.type, msg_id=message.message_id
    )


# ==================== ОБРАБОТЧИК "ДОБРОЙ НОЧИ" ====================
# ==================== ОБРАБОТЧИК "ДОБРОЙ НОЧИ" ====================
@bot.callback_query_handler(func=lambda call: call.data == "goodnight_cmd")
def goodnight_command(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    user_id = str(call.from_user.id)  # Строка для JSON

    # 1. Время по МСК
    now_utc = datetime.now(timezone.utc)
    now_msk = now_utc + timedelta(hours=3)
    current_hour = now_msk.hour
    today_str = now_msk.strftime("%Y-%m-%d")

    # 2. Загружаем данные
    gn_data = load_gn_data()

    # 3. Проверки
    is_night_time = (current_hour >= 22 or current_hour < 3)
    already_used = gn_data.get(user_id) == today_str

    # 🔥 ДИАГНОСТИКА: Смотри в консоль PyCharm после нажатия!
    print("=" * 50)
    print(f"🌙 НАЖАТИЕ КНОПКИ 'ДОБРОЙ НОЧИ'")
    print(f"User ID: {user_id}")
    print(f"Текущее время МСК: {current_hour}:00")
    print(f"Сегодняшняя дата: {today_str}")
    print(f"Содержимое файла goodnight_data.json: {gn_data}")
    print(f"Уже использовал сегодня? -> {already_used}")
    print(f"Ночное время (22-03)? -> {is_night_time}")
    print("=" * 50)

    if is_night_time and not already_used:
        # ✅ ВСЕ УСЛОВИЯ ВЫПОЛНЕНЫ
        gn_data[user_id] = today_str
        save_gn_data(gn_data)

        threat_text = random.choice(GOODNIGHT_TEXTS)
        log_action(call.from_user, "GOODNIGHT_TRIGGERED", f"got text at {current_hour}:00 MSK",
                   chat_type=call.message.chat.type, msg_id=call.message.message_id)

        print("✅ РЕЗУЛЬТАТ: Выдаем угрозу и сохраняем в файл.")
        bot.send_message(chat_id, threat_text, parse_mode="MarkdownV2")

    else:
        # ❌ ОТКАЗ
        log_action(call.from_user, "GOODNIGHT_DENIED", f"tried at {current_hour}:00 MSK or already used",
                   chat_type=call.message.chat.type, msg_id=call.message.message_id)

        reason = "уже нажимал сегодня" if already_used else "сейчас не ночное время"
        print(f"❌ РЕЗУЛЬТАТ: Отказ. Причина -> {reason}")

        bot.send_message(chat_id, GOODNIGHT_SARCASTIC, parse_mode="MarkdownV2")
        time.sleep(2)
        bot.send_message(chat_id, "🎭 *Главное меню*\n\nЧто выбираешь?", reply_markup=get_main_menu())


# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("🤖 DARK BOT ЗАПУЩЕН")
    logger.info(f"📅 Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("📋 Команды: /start, /facts, /test, /sin, /lucifer, /cric")
    logger.info("📁 Логи пишутся в файл: bot.log (с ротацией каждые 5 МБ)")
    logger.info("🔍 Уровень детализации: МАКСИМАЛЬНЫЙ")
    logger.info("=" * 70)

    print("🤖 Бот запущен!")
    print("📋 Команды: /start, /facts, /test, /sin, /lucifer, /cric")
    print("📁 Логи сохраняются в bot.log")

    bot.infinity_polling()