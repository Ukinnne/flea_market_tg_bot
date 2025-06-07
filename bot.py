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
import re

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

# Для хранения ID сообщения с предпросмотром
preview_message_id = None

def is_next_command(text: str) -> bool:
    """Проверяет, является ли текст командой 'дальше' в любом написании"""
    return re.fullmatch(r'дальше|дпльше|далше|далее|следующий шаг|продолжить|пропустить', text.lower()) is not None

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

@dp.message(F.text == "🔍 Поиск объявлений")
async def handle_search(message: types.Message):
    await message.answer("🔎 <b>Давайте найдем что-то интересное!</b>\n\nЗдесь будут отображаться все доступные объявления от других пользователей.")

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
    await state.update_data(price=int(message.text))
    await state.set_state(CreateForm.confirmation)
    await show_preview(message, state)

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
    
    success_message = """
🎉 <b>Анкета успешно создана!</b> 🎉

Ваше предложение теперь видно другим пользователям. 

<b>Что дальше?</b>
• Вы можете просмотреть свои анкеты в разделе <b>"💼 Мои анкеты"</b>
• Редактировать или удалить анкету там же

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

@dp.message(F.text == "💼 Мои анкеты")
async def handle_my(message: types.Message):
    await message.answer("📂 <b>Ваши анкеты</b>\n\nЗдесь будут отображаться все созданные вами объявления.")

@dp.message(F.text == "🕑 История покупок")
async def handle_history(message: types.Message):
    await message.answer("🛒 <b>История покупок</b>\n\nВ этом разделе вы можете просмотреть все ваши завершенные сделки.")

@dp.message(F.text == "♥️ Избранные анкеты")
async def handle_likes(message: types.Message):
    await message.answer("❤️ <b>Избранные анкеты</b>\n\nЗдесь сохраняются все понравившиеся вам предложения.")

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

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())