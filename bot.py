import os
import asyncio
import re
import json
from datetime import datetime
import random
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Инициализация бота
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ================== МОДЕЛИ ДАННЫХ И ХРАНИЛИЩЕ ==================

@dataclass
class Listing:
    id: str
    user_id: int
    title: str
    description: str
    photos: List[str]
    price: int
    created_at: str
    is_active: bool = True

@dataclass
class UserViewHistory:
    user_id: int
    viewed_ids: List[str]
    favorites: List[str]

class JSONStorage:
    def __init__(self, file_path: str = "flea_market_data.json"):
        self.file_path = file_path
        self.listings: Dict[str, Listing] = {}
        self.user_histories: Dict[int, UserViewHistory] = {}
        self.load_data()

    def load_data(self):
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.listings = {k: Listing(**v) for k, v in data.get("listings", {}).items()}
                self.user_histories = {
                    int(k): UserViewHistory(
                        user_id=int(k),
                        viewed_ids=v.get("viewed_ids", []),
                        favorites=v.get("favorites", [])
                    )
                    for k, v in data.get("user_histories", {}).items()
                }
        except (FileNotFoundError, json.JSONDecodeError):
            self.listings = {}
            self.user_histories = {}

    def save_data(self):
        data = {
            "listings": {k: asdict(v) for k, v in self.listings.items()},
            "user_histories": {
                str(k): {
                    "viewed_ids": v.viewed_ids,
                    "favorites": v.favorites
                }
                for k, v in self.user_histories.items()
            }
        }
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_user_history(self, user_id: int) -> UserViewHistory:
        if user_id not in self.user_histories:
            self.user_histories[user_id] = UserViewHistory(
                user_id=user_id,
                viewed_ids=[],
                favorites=[]
            )
        return self.user_histories[user_id]

    def add_listing(self, listing: Listing):
        self.listings[listing.id] = listing
        self.save_data()

    def get_listing(self, listing_id: str) -> Optional[Listing]:
        return self.listings.get(listing_id)

    def get_user_listings(self, user_id: int) -> List[Listing]:
        return [
            listing for listing in self.listings.values() 
            if listing.user_id == user_id and listing.is_active
        ]

    def get_active_listings(self, exclude_user_id: int) -> List[Listing]:
        return [
            listing for listing in self.listings.values()
            if listing.is_active and listing.user_id != exclude_user_id
        ]

    def mark_as_viewed(self, user_id: int, listing_id: str):
        history = self.get_user_history(user_id)
        if listing_id not in history.viewed_ids:
            history.viewed_ids.append(listing_id)
        self.save_data()

    def reset_viewed(self, user_id: int):
        history = self.get_user_history(user_id)
        history.viewed_ids = []
        self.save_data()

    def add_to_favorites(self, user_id: int, listing_id: str):
        history = self.get_user_history(user_id)
        if listing_id not in history.favorites:
            history.favorites.append(listing_id)
        self.save_data()

    def remove_from_favorites(self, user_id: int, listing_id: str):
        history = self.get_user_history(user_id)
        if listing_id in history.favorites:
            history.favorites.remove(listing_id)
        self.save_data()

    def get_favorites(self, user_id: int) -> List[Listing]:
        history = self.get_user_history(user_id)
        return [
            listing for listing_id in history.favorites
            if (listing := self.get_listing(listing_id)) is not None and listing.is_active
        ]

    def deactivate_listing(self, listing_id: str, user_id: int):
        listing = self.get_listing(listing_id)
        if listing and listing.user_id == user_id:
            listing.is_active = False
            self.save_data()
            return True
        return False

# Инициализация хранилища
storage = JSONStorage()

# Генерация ID для объявлений
def generate_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))

# ================== СОСТОЯНИЯ FSM ==================

class CreateForm(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_photos = State()
    waiting_for_price = State()
    confirmation = State()

preview_message_id = None

def is_next_command(text: str) -> bool:
    return re.fullmatch(r'дальше|дпльше|далше|далее|следующий шаг|продолжить|пропустить', text.lower()) is not None

# ================== ОСНОВНЫЕ КОМАНДЫ ==================

@dp.message(Command("start"))
async def start(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.row(
        types.KeyboardButton(text="🔍 Поиск объявлений"),
        types.KeyboardButton(text="📝 Создать анкету"),
    )
    builder.row(
        types.KeyboardButton(text="💼 Мои анкеты"),
        types.KeyboardButton(text="🕑 История покупок"),
    )
    builder.row(
        types.KeyboardButton(text="♥️ Избранные анкеты")
    )

    welcome_message = """
<b>🌟 Добро пожаловать в FleaMarketBot!</b> 🛍️💰

Это твой личный помощник для <b>быстрых</b> и <b>безопасных</b> покупок и продаж прямо в Telegram!

✨ <b>Что умеет этот бот?</b> ✨
• <b>Продавать вещи</b> — легко и без комиссии!
• <b>Находить выгодные предложения</b> — всё в одном месте!
• <b>Сохранять избранное</b> — чтобы не потерять понравившееся!

🚀 <b>Как начать?</b>
Просто нажми на одну из кнопок ниже и следуй подсказкам!

<b>Удачных сделок!</b> 💫
"""
    await message.answer(welcome_message, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(Command("help"))
async def help_command(message: types.Message):
    help_text = """
🆘 <b>Помощь по использованию бота</b> 🆘

<b>Основные команды:</b>
/start - Начать работу с ботом
/help - Получить справку

<b>Как создать анкету?</b>
1. Нажмите "📝 Создать анкету"
2. Следуйте пошаговым инструкциям
3. Проверьте информацию и подтвердите создание

<b>Как купить товар?</b>
1. Найдите нужный товар через "🔍 Поиск объявлений"
2. Свяжитесь с продавцом
3. Договоритесь об условиях сделки

<b>Вопросы и поддержка:</b>
Если у вас возникли проблемы, напишите нам: @Ukinnne
"""
    await message.answer(help_text)

# ================== СОЗДАНИЕ АНКЕТЫ ==================

@dp.message(F.text == "📝 Создать анкету")
async def handle_create(message: types.Message, state: FSMContext):
    await state.set_state(CreateForm.waiting_for_title)
    await message.answer("🛍️ <b>Создание новой анкеты</b>\n\n📛 <b>Шаг 1 из 4</b>\n\nПридумайте <b>яркое название</b> для вашего товара:\n\n<code>Пример: \"Крутой велосипед GT Aggressor\"</code>")

@dp.message(CreateForm.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(CreateForm.waiting_for_description)
    await message.answer("📝 <b>Шаг 2 из 4</b>\n\nНапишите <b>подробное описание</b> вашего товара:\n\n<code>Пример: \"Велосипед в отличном состоянии, 2021 год выпуска. Все компоненты работают идеально, пробег менее 500 км.\"</code>")

@dp.message(CreateForm.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(CreateForm.waiting_for_photos)
    await message.answer("📸 <b>Шаг 3 из 4</b>\n\nПришлите <b>до 3 фотографий</b> вашего товара (чем больше, тем лучше!):\n\nИли напишите <b>\"Дальше\"</b> (можно в любом написании), если фотографий нет")

@dp.message(CreateForm.waiting_for_photos, F.text)
async def handle_text_during_photos(message: types.Message, state: FSMContext):
    if is_next_command(message.text):
        await state.set_state(CreateForm.waiting_for_price)
        await message.answer("💰 <b>Финальный шаг!</b>\n\nУкажите <b>цену</b> вашего товара в рублях (только цифры):\n\n<code>Пример: 15000</code>")
    else:
        await message.answer("📸 Вы находитесь на этапе загрузки фотографий.\n\nОтправьте до 3 фото или напишите <b>\"Дальше\"</b> (можно в любом написании), чтобы пропустить этот шаг.")

@dp.message(CreateForm.waiting_for_photos, F.photo)
async def process_photos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    
    if len(photos) < 3:
        photos.append(message.photo[-1].file_id)
        await state.update_data(photos=photos)
        
        if len(photos) < 3:
            await message.answer(f"📸 Фото {len(photos)}/3 получено!\n\nМожете отправить еще фото или написать <b>\"Дальше\"</b> (можно в любом написании)")
        else:
            await state.set_state(CreateForm.waiting_for_price)
            await message.answer("✅ <b>Максимальное количество фото получено!</b>\n\nТеперь укажите <b>цену</b> вашего товара в рублях (только цифры):")
    else:
        await message.answer("⚠️ Вы уже отправили максимальное количество фото (3). Переходим к указанию цены.")

@dp.message(CreateForm.waiting_for_price, F.text.regexp(r'^\d+$'))
async def process_price_valid(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
        if price > 2**63 - 1:  # Максимальное значение для SQLite INTEGER
            await message.answer("⚠️ Слишком большая цена. Пожалуйста, введите меньшую сумму.")
            return
        await state.update_data(price=price)
        await state.set_state(CreateForm.confirmation)
        await show_preview(message, state)
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректную цену (только цифры).")

@dp.message(CreateForm.waiting_for_price)
async def process_price_invalid(message: types.Message):
    await message.answer("⚠️ Пожалуйста, введите цену только цифрами (без букв, пробелов и других символов).\n\nПример: <code>15000</code>")

async def show_preview(message: types.Message, state: FSMContext):
    global preview_message_id
    data = await state.get_data()
    
    preview_text = (
        "🛒 <b>ПРЕДПРОСМОТР АНКЕТЫ</b> 🛒\n\n"
        f"🏷 <b>Название:</b> {data['title']}\n"
        f"📄 <b>Описание:</b> {data['description']}\n"
        f"💵 <b>Цена:</b> {data['price']} руб.\n\n"
        "✨ <b>Всё выглядит отлично?</b> ✨"
    )
    
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="✅ Да, опубликовать!", callback_data="confirm_yes"),
        types.InlineKeyboardButton(text="❌ Нет, отменить", callback_data="confirm_no")
    )
    
    if data.get('photos'):
        media = []
        for i, photo_id in enumerate(data['photos']):
            media.append(types.InputMediaPhoto(
                media=photo_id,
                caption=preview_text if i == 0 else None
            ))
        
        await message.answer_media_group(media=media)
        msg = await message.answer("Подтвердите создание анкеты:", reply_markup=builder.as_markup())
        preview_message_id = msg.message_id
    else:
        msg = await message.answer(preview_text, reply_markup=builder.as_markup())
        preview_message_id = msg.message_id

async def delete_preview_message(chat_id: int):
    global preview_message_id
    if preview_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=preview_message_id)
        except:
            pass
        preview_message_id = None

@dp.callback_query(CreateForm.confirmation, F.data == "confirm_yes")
async def confirm_yes(callback: types.CallbackQuery, state: FSMContext):
    await delete_preview_message(callback.message.chat.id)
    
    data = await state.get_data()
    
    # Создаем новое объявление
    new_listing = Listing(
        id=generate_id(),
        user_id=callback.from_user.id,
        title=data['title'],
        description=data['description'],
        photos=data.get('photos', []),
        price=data['price'],
        created_at=datetime.now().isoformat()
    )
    
    # Сохраняем в хранилище
    storage.add_listing(new_listing)
    
    success_message = """
🎉 <b>Анкета успешно создана!</b> 🎉

Ваше предложение теперь видно другим пользователям. 

<b>Что дальше?</b>
• Вы можете просмотреть свои анкеты в разделе <b>"💼 Мои анкеты"</b>
• Удалить анкету там же

Желаем быстрой продажи! 💰
"""
    await callback.message.answer(success_message)
    await state.clear()
    await callback.answer()

@dp.callback_query(CreateForm.confirmation, F.data == "confirm_no")
async def confirm_no(callback: types.CallbackQuery, state: FSMContext):
    await delete_preview_message(callback.message.chat.id)
    
    cancel_message = """
🛑 <b>Создание анкеты отменено</b> 🛑

Вы всегда можете создать новую анкету, нажав кнопку <b>"📝 Создать анкету"</b>

Если у вас возникли трудности, воспользуйтесь командой /help
"""
    await callback.message.answer(cancel_message)
    await state.clear()
    await callback.answer()

# ================== ПОИСК И ПРОСМОТР АНКЕТ ==================

@dp.message(F.text == "🔍 Поиск объявлений")
async def handle_search(message: types.Message):
    await show_random_listing(message)

async def show_random_listing(message: types.Message):
    # Получаем все активные объявления, кроме собственных
    all_listings = storage.get_active_listings(message.from_user.id)
    
    if not all_listings:
        await message.answer("🔍 Пока нет доступных объявлений. Попробуйте позже.")
        return
    
    # Получаем историю просмотров пользователя
    user_history = storage.get_user_history(message.from_user.id)
    
    # Исключаем уже просмотренные объявления
    available_listings = [
        listing for listing in all_listings
        if listing.id not in user_history.viewed_ids
    ]
    
    if not available_listings:
        # Если все просмотрены, сбрасываем историю
        storage.reset_viewed(message.from_user.id)
        available_listings = all_listings
        await message.answer("🔄 Вы просмотрели все объявления. Начинаем показ заново.")
    
    # Выбираем случайное объявление
    listing = random.choice(available_listings)
    
    # Помечаем как просмотренное
    storage.mark_as_viewed(message.from_user.id, listing.id)
    
    # Проверяем, есть ли в избранном
    is_favorite = listing.id in storage.get_user_history(message.from_user.id).favorites
    
    # Формируем сообщение
    response = (
        f"🛍 <b>{listing.title}</b>\n\n"
        f"📄 <b>Описание:</b>\n{listing.description}\n\n"
        f"💰 <b>Цена:</b> {listing.price} руб.\n"
        f"👤 <b>Продавец:</b> @{listing.user_id}\n\n"
    )
    
    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()
    
    if not is_favorite:
        builder.add(types.InlineKeyboardButton(
            text="❤️ Добавить в избранное",
            callback_data=f"fav_{listing.id}"
        ))
    else:
        builder.add(types.InlineKeyboardButton(
            text="💔 Удалить из избранного",
            callback_data=f"unfav_{listing.id}"
        ))
    
    builder.add(types.InlineKeyboardButton(
        text="➡️ Следующее объявление",
        callback_data="next_listing"
    ))
    
    # Если есть фото, отправляем их
    if listing.photos:
        media = []
        for i, photo_id in enumerate(listing.photos):
            media.append(types.InputMediaPhoto(
                media=photo_id,
                caption=response if i == 0 else None
            ))
        
        await message.answer_media_group(media=media)
        await message.answer("Выберите действие:", reply_markup=builder.as_markup())
    else:
        await message.answer(response, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "next_listing")
async def next_listing(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except:
        pass
    await show_random_listing(callback.message)

@dp.callback_query(F.data.startswith("fav_"))
async def add_favorite(callback: types.CallbackQuery):
    listing_id = callback.data.split('_')[1]
    
    try:
        storage.add_to_favorites(callback.from_user.id, listing_id)
        await callback.answer("❤️ Объявление добавлено в избранное!")
        
        # Обновляем кнопки
        builder = InlineKeyboardBuilder()
        builder.add(
            types.InlineKeyboardButton(
                text="💔 Удалить из избранного",
                callback_data=f"unfav_{listing_id}"
            ),
            types.InlineKeyboardButton(
                text="➡️ Следующее объявление",
                callback_data="next_listing"
            )
        )
        
        try:
            await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        except:
            pass
    except Exception as e:
        await callback.answer(f"⚠️ Ошибка: {str(e)}")

@dp.callback_query(F.data.startswith("unfav_"))
async def remove_favorite(callback: types.CallbackQuery):
    listing_id = callback.data.split('_')[1]
    
    try:
        storage.remove_from_favorites(callback.from_user.id, listing_id)
        await callback.answer("💔 Объявление удалено из избранного")
        
        # Обновляем кнопки
        builder = InlineKeyboardBuilder()
        builder.add(
            types.InlineKeyboardButton(
                text="❤️ Добавить в избранное",
                callback_data=f"fav_{listing_id}"
            ),
            types.InlineKeyboardButton(
                text="➡️ Следующее объявление",
                callback_data="next_listing"
            )
        )
        
        try:
            await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        except:
            pass
    except Exception as e:
        await callback.answer(f"⚠️ Ошибка: {str(e)}")

# ================== МОИ АНКЕТЫ ==================

@dp.message(F.text == "💼 Мои анкеты")
async def handle_my(message: types.Message):
    user_listings = storage.get_user_listings(message.from_user.id)
    
    if not user_listings:
        await message.answer("📭 У вас пока нет активных анкет.")
        return
    
    response = ["📂 <b>Ваши анкеты</b>\n"]
    for listing in user_listings:
        response.append(
            f"\n🆔 <b>ID:</b> {listing.id}\n"
            f"🏷 <b>Название:</b> {listing.title}\n"
            f"💰 <b>Цена:</b> {listing.price} руб.\n"
            f"📄 <b>Описание:</b> {listing.description[:100]}...\n"
        )
    
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="🗑 Удалить анкету", callback_data="delete_listing")
    )
    
    await message.answer("\n".join(response), reply_markup=builder.as_markup())

@dp.callback_query(F.data == "delete_listing")
async def delete_listing_prompt(callback: types.CallbackQuery):
    await callback.message.answer("✏️ Введите ID анкеты, которую хотите удалить:")

@dp.message(F.text.regexp(r'^\d+$'))
async def delete_listing_by_id(message: types.Message):
    listing_id = message.text
    
    if storage.deactivate_listing(listing_id, message.from_user.id):
        await message.answer("🗑 Объявление успешно удалено")
    else:
        await message.answer("⚠️ Вы не можете удалить это объявление или оно не найдено")

# ================== ИЗБРАННЫЕ АНКЕТЫ ==================

@dp.message(F.text == "♥️ Избранные анкеты")
async def handle_likes(message: types.Message):
    favorites = storage.get_favorites(message.from_user.id)
    
    if not favorites:
        await message.answer("❤️ У вас пока нет избранных объявлений.")
        return
    
    for listing in favorites:
        response = (
            f"❤️ <b>Избранное</b>\n\n"
            f"🏷 <b>Название:</b> {listing.title}\n"
            f"💰 <b>Цена:</b> {listing.price} руб.\n"
            f"👤 <b>Продавец:</b> @{listing.user_id}\n"
            f"📄 <b>Описание:</b>\n{listing.description}\n\n"
        )
        
        builder = InlineKeyboardBuilder()
        builder.add(
            types.InlineKeyboardButton(
                text="💬 Написать продавцу",
                url=f"tg://user?id={listing.user_id}"
            ),
            types.InlineKeyboardButton(
                text="💔 Удалить из избранного",
                callback_data=f"unfav_{listing.id}"
            )
        )
        
        if listing.photos:
            media = []
            for i, photo_id in enumerate(listing.photos):
                media.append(types.InputMediaPhoto(
                    media=photo_id,
                    caption=response if i == 0 else None
                ))
            
            await message.answer_media_group(media=media)
            await message.answer("Действия с объявлением:", reply_markup=builder.as_markup())
        else:
            await message.answer(response, reply_markup=builder.as_markup())

# ================== ЗАГЛУШКИ ==================

@dp.message(F.text == "🕑 История покупок")
async def handle_history(message: types.Message):
    await message.answer("🛒 <b>История покупок</b>\n\nВ этом разделе вы можете просмотреть все ваши завершенные сделки.")

# ================== ЗАПУСК БОТА ==================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())