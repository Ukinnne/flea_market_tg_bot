from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

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
    await message.answer("Доступные анкеты других пользоваьелей:")

@dp.message(F.text == "📝 Создать анкету")
async def handle_create(message: types.Message):
    await message.answer("Хотите что-то продать? Опишите товар")

@dp.message(F.text == "💼 Мои анкеты")
async def handle_my(message: types.Message):
    await message.answer("Ваши анкеты:")

@dp.message(F.text == "🕑 История покупок")
async def handle_history(message: types.Message):
    await message.answer("История ваших покупок:")

@dp.message(F.text == "♥️ Избранные анкеты")
async def handle_liles(message: types.Message):
    await message.answer("Анкеты, которые вы добавили в избранные:")

@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer("Здесь будет помощь по использованию бота")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())