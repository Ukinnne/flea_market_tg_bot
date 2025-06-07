from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize storage
storage = MemoryStorage()

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=storage)

# Define states for FSM
class CreateForm(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_photos = State()
    waiting_for_price = State()
    confirmation = State()

# Helper function to convert FormData to dict and back
def form_data_to_dict(form_data):
    return {
        'title': form_data.get('title', None),
        'description': form_data.get('description', None),
        'photos': form_data.get('photos', []),
        'price': form_data.get('price', None)
    }

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

    await message.answer(
        "<b>🌟 Привет, дружок!</b>\n\n"
        "Этот бот — твой удобный помощник для покупок и продаж прямо в Telegram! 🛍️💰\n\n"
        "<b>Что можно делать?</b>\n"
        "✅ <b>Продавать свои вещи</b> — быстро и без лишних хлопот!\n"
        "✅ <b>Покупать классные штуки</b> у других пользователей — выгодно и безопасно!\n\n"
        "🔹Просто нажми на кнопки, появившиеся снизу и начни! 😊\n\n"
        "<b>Давай начинать!</b> 🚀 Теперь твои ненужные вещи могут принести деньги, а найти что-то крутое — проще простого!",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@dp.message(F.text == "🔍 Поиск объявлений")
async def handle_search(message: types.Message):
    await message.answer("Доступные анкеты других пользователей:")

@dp.message(F.text == "📝 Создать анкету")
async def handle_create(message: types.Message, state: FSMContext):
    await state.set_state(CreateForm.waiting_for_title)
    await message.answer("Введите название вашего товара:")
    # Initialize form data as a dictionary
    await state.set_data({
        'title': None,
        'description': None,
        'photos': [],
        'price': None
    })

@dp.message(CreateForm.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    data = await state.get_data()
    data['title'] = message.text
    await state.set_data(data)
    await state.set_state(CreateForm.waiting_for_description)
    await message.answer("Отлично! Теперь введите описание товара:")

@dp.message(CreateForm.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    data['description'] = message.text
    await state.set_data(data)
    await state.set_state(CreateForm.waiting_for_photos)
    await message.answer("Хорошо! Теперь отправьте до 3 фотографий товара (или пропустите этот шаг, отправив 'Пропустить'):")

@dp.message(CreateForm.waiting_for_photos, F.text == "Пропустить")
async def skip_photos(message: types.Message, state: FSMContext):
    await state.set_state(CreateForm.waiting_for_price)
    await message.answer("Теперь укажите цену товара (в рублях):")

@dp.message(CreateForm.waiting_for_photos, F.photo)
async def process_photos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if len(data['photos']) < 3:
        data['photos'].append(message.photo[-1].file_id)
        await state.set_data(data)
        if len(data['photos']) < 3:
            await message.answer(f"Фото {len(data['photos'])}/3 получено. Можете отправить еще или нажать 'Пропустить'.")
        else:
            await state.set_state(CreateForm.waiting_for_price)
            await message.answer("Максимальное количество фото получено. Теперь укажите цену товара (в рублях):")
    else:
        await message.answer("Вы уже отправили максимальное количество фото (3). Переходим к указанию цены.")
        await state.set_state(CreateForm.waiting_for_price)

@dp.message(CreateForm.waiting_for_price, F.text.regexp(r'^\d+$'))
async def process_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    data['price'] = int(message.text)
    await state.set_data(data)
    await state.set_state(CreateForm.confirmation)
    
    # Формируем сообщение с предпросмотром анкеты
    preview_text = (
        f"<b>Предпросмотр анкеты:</b>\n\n"
        f"<b>Название:</b> {data['title']}\n"
        f"<b>Описание:</b> {data['description']}\n"
        f"<b>Цена:</b> {data['price']} руб.\n\n"
        f"Все верно?"
    )
    
    # Создаем клавиатуру с кнопками подтверждения
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="✅ Да, создать анкету", callback_data="confirm_yes"),
        types.InlineKeyboardButton(text="❌ Нет, отменить", callback_data="confirm_no")
    )
    
    # Если есть фото, отправляем их с подписью
    if data['photos']:
        media = []
        for i, photo_id in enumerate(data['photos']):
            media.append(types.InputMediaPhoto(
                media=photo_id,
                caption=preview_text if i == 0 else None
            ))
        
        await message.answer_media_group(media=media)
        await message.answer("Все верно?", reply_markup=builder.as_markup())
    else:
        await message.answer(preview_text, reply_markup=builder.as_markup())

@dp.callback_query(CreateForm.confirmation, F.data == "confirm_yes")
async def confirm_yes(callback: types.CallbackQuery, state: FSMContext):
    # Here you would save the form to your database
    data = await state.get_data()
    # Example: save_to_database(data)
    await callback.message.answer("✅ Анкета успешно создана!")
    await state.clear()
    await callback.answer()

@dp.callback_query(CreateForm.confirmation, F.data == "confirm_no")
async def confirm_no(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("❌ Создание анкеты отменено.")
    await state.clear()
    await callback.answer()

@dp.message(F.text == "💼 Мои анкеты")
async def handle_my(message: types.Message):
    await message.answer("Ваши анкеты:")

@dp.message(F.text == "🕑 История покупок")
async def handle_history(message: types.Message):
    await message.answer("История ваших покупок:")

@dp.message(F.text == "♥️ Избранные анкеты")
async def handle_likes(message: types.Message):
    await message.answer("Анкеты, которые вы добавили в избранные:")

@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer("Здесь будет помощь по использованию бота")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())