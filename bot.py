import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from datetime import datetime
from dotenv import load_dotenv
import os

# Загрузка переменных окружения из .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Проверка наличия токена
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в файле .env")

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot=bot, storage=storage)

# Инициализация базы данных
def init_db():
    with sqlite3.connect('marketplace.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS listings
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      title TEXT,
                      description TEXT,
                      price REAL,
                      category TEXT,
                      status TEXT,
                      created_at TIMESTAMP,
                      rating INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY,
                      username TEXT,
                      reputation INTEGER DEFAULT 0,
                      is_admin BOOLEAN DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS messages
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      listing_id INTEGER,
                      sender_id INTEGER,
                      receiver_id INTEGER,
                      message TEXT,
                      sent_at TIMESTAMP)''')
        conn.commit()

# Состояния для FSM
class ListingForm(StatesGroup):
    title = State()
    description = State()
    price = State()
    category = State()

class SearchForm(StatesGroup):
    query = State()
    category = State()

class MessageForm(StatesGroup):
    message = State()

# Главное меню
def get_main_menu(is_admin=False):
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📝 Создать объявление"))
    builder.add(KeyboardButton(text="🔍 Найти товар"))
    builder.add(KeyboardButton(text="📦 Мои объявления"))
    builder.add(KeyboardButton(text="⭐ Моя репутация"))
    builder.add(KeyboardButton(text="🛠 Админ-панель") if is_admin else KeyboardButton(text="📚 Помощь"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Проверка, является ли пользователь админом
async def is_admin_user(user_id):
    with sqlite3.connect('marketplace.db') as conn:
        c = conn.cursor()
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        return result and result[0]

# Обработчик команды /start
@dp.message(CommandStart())
async def start_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    with sqlite3.connect('marketplace.db') as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
    is_admin = await is_admin_user(user_id)
    await message.answer("Добро пожаловать в Marketplace Bot! 🛒\nВыберите действие:", reply_markup=get_main_menu(is_admin))

# Создание объявления
@dp.message(lambda message: message.text == "📝 Создать объявление")
async def create_listing(message: types.Message, state: FSMContext):
    await state.set_state(ListingForm.title)
    await message.answer("Введите название объявления:", reply_markup=types.ReplyKeyboardRemove())

@dp.message(ListingForm.title)
async def process_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(ListingForm.description)
    await message.answer("Введите описание товара:")

@dp.message(ListingForm.description)
async def process_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(ListingForm.price)
    await message.answer("Введите цену (в рублях):")

@dp.message(ListingForm.price)
async def process_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        if price <= 0:
            raise ValueError
        await state.update_data(price=price)
        await state.set_state(ListingForm.category)
        categories = ["Электроника", "Одежда", "Дом", "Авто", "Другое"]
        builder = ReplyKeyboardBuilder()
        for cat in categories:
            builder.add(KeyboardButton(text=cat))
        builder.adjust(2)
        await message.answer("Выберите категорию:", reply_markup=builder.as_markup(resize_keyboard=True))
    except ValueError:
        await message.answer("Пожалуйста, введите корректную цену (число больше 0):")

@dp.message(ListingForm.category)
async def process_category(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    with sqlite3.connect('marketplace.db') as conn:
        c = conn.cursor()
        c.execute("INSERT INTO listings (user_id, title, description, price, category, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (user_id, data['title'], data['description'], data['price'], message.text, 'active', datetime.now()))
        conn.commit()
    is_admin = await is_admin_user(user_id)
    await state.clear()
    await message.answer("Объявление успешно создано! 🎉", reply_markup=get_main_menu(is_admin))

# Поиск товаров
@dp.message(lambda message: message.text == "🔍 Найти товар")
async def search_listing(message: types.Message, state: FSMContext):
    await state.set_state(SearchForm.query)
    await message.answer("Введите запрос для поиска (или оставьте пустым для всех объявлений):",
                         reply_markup=types.ReplyKeyboardRemove())

@dp.message(SearchForm.query)
async def process_search_query(message: types.Message, state: FSMContext):
    await state.update_data(query=message.text)
    await state.set_state(SearchForm.category)
    categories = ["Все", "Электроника", "Одежда", "Дом", "Авто", "Другое"]
    builder = ReplyKeyboardBuilder()
    for cat in categories:
        builder.add(KeyboardButton(text=cat))
    builder.adjust(2)
    await message.answer("Выберите категорию:", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(SearchForm.category)
async def process_search_category(message: types.Message, state: FSMContext):
    data = await state.get_data()
    query = f"%{data['query']}%"
    category = message.text if message.text != "Все" else "%"
    with sqlite3.connect('marketplace.db') as conn:
        c = conn.cursor()
        c.execute("SELECT id, title, price, category, user_id FROM listings WHERE title LIKE ? AND category LIKE ? AND status = 'active'",
                  (query, category))
        listings = c.fetchall()
    
    if not listings:
        is_admin = await is_admin_user(message.from_user.id)
        await message.answer("Объявления не найдены. 😔 Попробуйте изменить запрос.", reply_markup=get_main_menu(is_admin))
        await state.clear()
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for listing in listings:
        listing_id, title, price, category, user_id = listing
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"{title} ({price}₽)", callback_data=f"view_{listing_id}")
        ])
    await message.answer("Найденные объявления:", reply_markup=keyboard)
    await state.clear()

# Просмотр объявления
@dp.callback_query(lambda c: c.data.startswith('view_'))
async def view_listing(callback: types.CallbackQuery):
    listing_id = int(callback.data.split('_')[1])
    with sqlite3.connect('marketplace.db') as conn:
        c = conn.cursor()
        c.execute("SELECT title, description, price, category, user_id, status FROM listings WHERE id = ?", (listing_id,))
        listing = c.fetchone()
        if not listing:
            await callback.message.answer("Объявление не найдено.")
            return
        title, description, price, category, user_id, status = listing
        c.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
        username = c.fetchone()[0]
    
    text = f"📦 {title}\n💰 Цена: {price}₽\n📋 Категория: {category}\n📝 Описание: {description}\n👤 Продавец: @{username}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    if status == 'active' and callback.from_user.id != user_id:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="📩 Написать продавцу", callback_data=f"msg_{listing_id}")])
    if callback.from_user.id == user_id and status == 'active':
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="❌ Закрыть объявление", callback_data=f"close_{listing_id}")])
    
    await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()

# Закрытие объявления
@dp.callback_query(lambda c: c.data.startswith('close_'))
async def close_listing(callback: types.CallbackQuery):
    listing_id = int(callback.data.split('_')[1])
    with sqlite3.connect('marketplace.db') as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM listings WHERE id = ?", (listing_id,))
        user_id = c.fetchone()[0]
        if callback.from_user.id != user_id:
            await callback.answer("Только владелец может закрыть объявление!", show_alert=True)
            return
        c.execute("UPDATE listings SET status = 'closed' WHERE id = ?", (listing_id,))
        conn.commit()
    is_admin = await is_admin_user(callback.from_user.id)
    await callback.message.answer("Объявление закрыто. ✅", reply_markup=get_main_menu(is_admin))
    await callback.answer()

# Отправка сообщения продавцу
@dp.callback_query(lambda c: c.data.startswith('msg_'))
async def message_seller(callback: types.CallbackQuery, state: FSMContext):
    listing_id = int(callback.data.split('_')[1])
    await state.update_data(listing_id=listing_id)
    await state.set_state(MessageForm.message)
    await callback.message.answer("Введите ваше сообщение продавцу:")
    await callback.answer()

@dp.message(MessageForm.message)
async def process_seller_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    listing_id = data['listing_id']
    sender_id = message.from_user.id
    with sqlite3.connect('marketplace.db') as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM listings WHERE id = ?", (listing_id,))
        receiver_id = c.fetchone()[0]
        c.execute("INSERT INTO messages (listing_id, sender_id, receiver_id, message, sent_at) VALUES (?, ?, ?, ?, ?)",
                  (listing_id, sender_id, receiver_id, message.text, datetime.now()))
        conn.commit()
    is_admin = await is_admin_user(sender_id)
    await message.answer("Сообщение отправлено продавцу! 📩", reply_markup=get_main_menu(is_admin))
    await state.clear()

# Мои объявления
@dp.message(lambda message: message.text == "📦 Мои объявления")
async def my_listings(message: types.Message):
    user_id = message.from_user.id
    with sqlite3.connect('marketplace.db') as conn:
        c = conn.cursor()
        c.execute("SELECT id, title, price, status FROM listings WHERE user_id = ?", (user_id,))
        listings = c.fetchall()
    
    if not listings:
        is_admin = await is_admin_user(user_id)
        await message.answer("У вас нет объявлений. 😔 Создайте новое!", reply_markup=get_main_menu(is_admin))
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for listing in listings:
        listing_id, title, price, status = listing
        status_emoji = "✅" if status == 'active' else "❌"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"{status_emoji} {title} ({price}₽)", callback_data=f"view_{listing_id}")
        ])
    await message.answer("Ваши объявления:", reply_markup=keyboard)

# Репутация пользователя
@dp.message(lambda message: message.text == "⭐ Моя репутация")
async def my_reputation(message: types.Message):
    user_id = message.from_user.id
    with sqlite3.connect('marketplace.db') as conn:
        c = conn.cursor()
        c.execute("SELECT reputation, username FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        reputation, username = user
    is_admin = await is_admin_user(user_id)
    await message.answer(f"👤 @{username}\n⭐ Репутация: {reputation}", reply_markup=get_main_menu(is_admin))

# Админ-панель
@dp.message(lambda message: message.text == "🛠 Админ-панель")
async def admin_panel(message: types.Message):
    user_id = message.from_user.id
    if not await is_admin_user(user_id):
        await message.answer("У вас нет доступа к админ-панели.", reply_markup=get_main_menu())
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🚫 Забанить пользователя", callback_data="admin_ban")]
    ])
    await message.answer("Админ-панель:", reply_markup=keyboard)

# Статистика (для админов)
@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if not await is_admin_user(callback.from_user.id):
        await callback.answer("Доступ запрещен!", show_alert=True)
        return
    with sqlite3.connect('marketplace.db') as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM listings WHERE status = 'active'")
        active_listings = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
    is_admin = await is_admin_user(callback.from_user.id)
    await callback.message.answer(f"📊 Статистика:\nАктивных объявлений: {active_listings}\nВсего пользователей: {total_users}",
                                 reply_markup=get_main_menu(is_admin))
    await callback.answer()

# Запуск бота
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())