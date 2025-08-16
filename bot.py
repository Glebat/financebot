#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram бот для учёта личных расходов
Поддерживает множество пользователей с изолированными данными
Развёртывается на Render.com через вебхук
"""

import os
import sqlite3
import logging
from datetime import datetime, timedelta
import calendar
import pandas as pd
from io import BytesIO
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from telegram.constants import ParseMode

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
ADD_EXPENSE_NAME, ADD_EXPENSE_AMOUNT = range(2)

# Категории расходов
CATEGORIES = {
    'food_home': '🍽️ Еда дома',
    'food_out': '🍕 Еда на улице', 
    'transport': '🚇 Транспорт',
    'home': '🏡 Дом и уют',
    'clothes': '👕 Одежда',
    'subscriptions': '🔔 Подписки'
}

class ExpenseBot:
    def __init__(self):
        self.db_path = 'expenses.db'
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                amount REAL NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")
    
    def get_monthly_total(self, user_id: int) -> float:
        """Получить общую сумму трат за текущий месяц"""
        now = datetime.now()
        start_of_month = datetime(now.year, now.month, 1)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT SUM(amount) FROM expenses 
            WHERE user_id = ? AND timestamp >= ?
        ''', (user_id, start_of_month.strftime('%Y-%m-%d %H:%M:%S')))
        
        result = cursor.fetchone()[0]
        conn.close()
        
        return result if result else 0.0
    
    def add_expense(self, user_id: int, category: str, title: str, amount: float):
        """Добавить трату"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO expenses (user_id, category, title, amount, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, category, title, amount, timestamp))
        
        conn.commit()
        conn.close()
    
    def get_today_expenses(self, user_id: int, category: str) -> list:
        """Получить траты за сегодня в определённой категории"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, title, amount FROM expenses 
            WHERE user_id = ? AND category = ? AND DATE(timestamp) = ?
            ORDER BY timestamp DESC
        ''', (user_id, category, today))
        
        result = cursor.fetchall()
        conn.close()
        
        return result
    
    def delete_expense(self, expense_id: int, user_id: int) -> bool:
        """Удалить трату (с проверкой принадлежности пользователю)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM expenses WHERE id = ? AND user_id = ?
        ''', (expense_id, user_id))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def delete_all_expenses(self, user_id: int):
        """Удалить все траты пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM expenses WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
    
    def get_expenses_report(self, user_id: int, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Получить отчёт по тратам за период"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT category, SUM(amount) FROM expenses 
            WHERE user_id = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY category
        ''', (user_id, start_date.strftime('%Y-%m-%d %H:%M:%S'), 
              end_date.strftime('%Y-%m-%d %H:%M:%S')))
        
        category_totals = dict(cursor.fetchall())
        
        cursor.execute('''
            SELECT SUM(amount) FROM expenses 
            WHERE user_id = ? AND timestamp >= ? AND timestamp <= ?
        ''', (user_id, start_date.strftime('%Y-%m-%d %H:%M:%S'), 
              end_date.strftime('%Y-%m-%d %H:%M:%S')))
        
        total = cursor.fetchone()[0] or 0.0
        
        conn.close()
        
        return {
            'category_totals': category_totals,
            'total': total,
            'start_date': start_date,
            'end_date': end_date
        }
    
    def export_expenses_to_excel(self, user_id: int, start_date: datetime, end_date: datetime) -> BytesIO:
        """Экспорт трат в Excel файл с отдельными листами для каждой категории"""
        conn = sqlite3.connect(self.db_path)
        
        # Получаем все траты за период
        query = '''
            SELECT category, timestamp, title, amount FROM expenses 
            WHERE user_id = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp DESC
        '''
        
        df = pd.read_sql_query(query, conn, params=(
            user_id, 
            start_date.strftime('%Y-%m-%d %H:%M:%S'),
            end_date.strftime('%Y-%m-%d %H:%M:%S')
        ))
        
        conn.close()
        
        # Создаём Excel файл в памяти
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Создаём лист для каждой категории
            for category_key, category_name in CATEGORIES.items():
                # Фильтруем данные по категории
                category_data = df[df['category'] == category_key].copy()
                
                if not category_data.empty:
                    # Форматируем данные
                    category_data['Дата и время'] = pd.to_datetime(category_data['timestamp']).dt.strftime('%d.%m.%Y %H:%M')
                    category_data['Название'] = category_data['title']
                    category_data['Сумма (₽)'] = category_data['amount']
                    
                    # Выбираем только нужные колонки
                    export_data = category_data[['Дата и время', 'Название', 'Сумма (₽)']]
                else:
                    # Создаём пустой DataFrame с нужными колонками
                    export_data = pd.DataFrame(columns=['Дата и время', 'Название', 'Сумма (₽)'])
                
                # Записываем на лист (убираем эмодзи из названия листа)
                sheet_name = category_name.split(' ', 1)[1] if ' ' in category_name else category_name
                export_data.to_excel(writer, sheet_name=sheet_name, index=False)
        
        output.seek(0)
        return output

# Инициализируем бота
expense_bot = ExpenseBot()

# Функции для создания клавиатур
def get_main_menu_keyboard():
    """Главное меню"""
    keyboard = [
        [InlineKeyboardButton("🍽️ Еда дома", callback_data="category_food_home"),
         InlineKeyboardButton("🍕 Еда на улице", callback_data="category_food_out")],
        [InlineKeyboardButton("🚇 Транспорт", callback_data="category_transport"),
         InlineKeyboardButton("🏡 Дом и уют", callback_data="category_home")],
        [InlineKeyboardButton("👕 Одежда", callback_data="category_clothes"),
         InlineKeyboardButton("🔔 Подписки", callback_data="category_subscriptions")],
        [InlineKeyboardButton("📊 Отчёт", callback_data="report"),
         InlineKeyboardButton("📥 Выгрузить траты", callback_data="export")],
        [InlineKeyboardButton("❌ Удалить все траты", callback_data="delete_all")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_category_menu_keyboard():
    """Меню категории"""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить трату", callback_data="add_expense")],
        [InlineKeyboardButton("❌ Удалить трату", callback_data="delete_expense")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_menu_keyboard():
    """Кнопки возврата"""
    keyboard = [
        [InlineKeyboardButton("🏠 В меню", callback_data="back_to_main"),
         InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_report_period_keyboard():
    """Выбор периода для отчёта"""
    keyboard = [
        [InlineKeyboardButton("За день", callback_data="report_day")],
        [InlineKeyboardButton("За неделю", callback_data="report_week")],
        [InlineKeyboardButton("За месяц", callback_data="report_month")],
        [InlineKeyboardButton("За всё время", callback_data="report_all")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_export_period_keyboard():
    """Выбор периода для экспорта"""
    keyboard = [
        [InlineKeyboardButton("За день", callback_data="export_day")],
        [InlineKeyboardButton("За неделю", callback_data="export_week")],
        [InlineKeyboardButton("За месяц", callback_data="export_month")],
        [InlineKeyboardButton("За всё время", callback_data="export_all")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_confirmation_keyboard(action):
    """Клавиатура подтверждения"""
    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_{action}"),
         InlineKeyboardButton("❌ Отмена", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    
    # Получаем сумму трат за текущий месяц
    monthly_total = expense_bot.get_monthly_total(user_id)
    
    # Формируем сообщение
    now = datetime.now()
    start_of_month = datetime(now.year, now.month, 1)
    
    if monthly_total > 0:
        message = (
            f"👋 Привет! Это твой финансовый помощник.\n\n"
            f"💰 Ты уже потратил в этом месяце: {monthly_total:.0f} ₽\n"
            f"(с {start_of_month.strftime('%d.%m.%Y')} по {now.strftime('%d.%m.%Y')})"
        )
    else:
        message = "👋 Привет! Это твой финансовый помощник.\n\n💰 Ты ещё ничего не потратил в этом месяце."
    
    await update.message.reply_text(
        message,
        reply_markup=get_main_menu_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    # Обработка выбора категории
    if data.startswith('category_'):
        category = data.replace('category_', '')
        context.user_data['selected_category'] = category
        
        category_name = CATEGORIES[category]
        await query.edit_message_text(
            f"Выбрана категория: {category_name}. Что хочешь сделать?",
            reply_markup=get_category_menu_keyboard()
        )
    
    # Добавление траты
    elif data == 'add_expense':
        await query.edit_message_text(
            "На что потратил? Напиши название.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="back")]
            ])
        )
        return ADD_EXPENSE_NAME
    
    # Удаление траты
    elif data == 'delete_expense':
        category = context.user_data.get('selected_category')
        if not category:
            await query.edit_message_text(
                "Ошибка: категория не выбрана.",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        today_expenses = expense_bot.get_today_expenses(user_id, category)
        
        if not today_expenses:
            await query.edit_message_text(
                "У тебя нет трат за сегодня в этой категории.",
                reply_markup=get_category_menu_keyboard()
            )
        else:
            keyboard = []
            for expense_id, title, amount in today_expenses:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{title} — {amount:.0f} ₽",
                        callback_data=f"delete_expense_{expense_id}_{title}_{amount}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back")])
            
            await query.edit_message_text(
                "Выбери трату для удаления:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    # Подтверждение удаления конкретной траты
    elif data.startswith('delete_expense_'):
        parts = data.split('_', 4)  # delete_expense_ID_title_amount
        expense_id = int(parts[2])
        title = parts[3]
        amount = float(parts[4])
        
        context.user_data['delete_expense_id'] = expense_id
        
        await query.edit_message_text(
            f"Ты уверен, что хочешь удалить «{title} — {amount:.0f} ₽»?",
            reply_markup=get_confirmation_keyboard(f"expense_{expense_id}")
        )
    
    # Подтверждение удаления
    elif data.startswith('confirm_'):
        if data == 'confirm_delete_all':
            expense_bot.delete_all_expenses(user_id)
            await query.edit_message_text(
                "🗑️ Все твои траты успешно удалены.",
                reply_markup=get_main_menu_keyboard()
            )
        elif data.startswith('confirm_expense_'):
            expense_id = context.user_data.get('delete_expense_id')
            if expense_id and expense_bot.delete_expense(expense_id, user_id):
                await query.edit_message_text(
                    "❌ Трата удалена.",
                    reply_markup=get_back_to_menu_keyboard()
                )
            else:
                await query.edit_message_text(
                    "Ошибка при удалении траты.",
                    reply_markup=get_back_to_menu_keyboard()
                )
    
    # Удаление всех трат
    elif data == 'delete_all':
        await query.edit_message_text(
            "⚠️ Внимание! Ты собираешься удалить все свои траты за всё время. "
            "Это действие нельзя отменить. Уверен?",
            reply_markup=get_confirmation_keyboard("delete_all")
        )
    
    # Отчёты
    elif data == 'report':
        await query.edit_message_text(
            "Выбери период для отчёта:",
            reply_markup=get_report_period_keyboard()
        )
    
    elif data.startswith('report_'):
        period = data.replace('report_', '')
        await generate_report(query, user_id, period)
    
    # Экспорт
    elif data == 'export':
        await query.edit_message_text(
            "Выбери период для выгрузки:",
            reply_markup=get_export_period_keyboard()
        )
    
    elif data.startswith('export_'):
        period = data.replace('export_', '')
        await export_expenses(query, user_id, period)
    
    # Навигация
    elif data == 'back_to_main':
        await start_from_callback(query)
    
    elif data == 'back':
        category = context.user_data.get('selected_category')
        if category:
            category_name = CATEGORIES[category]
            await query.edit_message_text(
                f"Выбрана категория: {category_name}. Что хочешь сделать?",
                reply_markup=get_category_menu_keyboard()
            )
        else:
            await start_from_callback(query)

async def start_from_callback(query):
    """Возврат в главное меню из callback"""
    user_id = query.from_user.id
    
    monthly_total = expense_bot.get_monthly_total(user_id)
    now = datetime.now()
    start_of_month = datetime(now.year, now.month, 1)
    
    if monthly_total > 0:
        message = (
            f"👋 Привет! Это твой финансовый помощник.\n\n"
            f"💰 Ты уже потратил в этом месяце: {monthly_total:.0f} ₽\n"
            f"(с {start_of_month.strftime('%d.%m.%Y')} по {now.strftime('%d.%m.%Y')})"
        )
    else:
        message = "👋 Привет! Это твой финансовый помощник.\n\n💰 Ты ещё ничего не потратил в этом месяце."
    
    await query.edit_message_text(
        message,
        reply_markup=get_main_menu_keyboard()
    )

async def add_expense_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение названия траты"""
    context.user_data['expense_name'] = update.message.text
    
    await update.message.reply_text(
        "Сколько потратил? Введи число.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="back")]
        ])
    )
    
    return ADD_EXPENSE_AMOUNT

async def add_expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение суммы траты"""
    try:
        amount = float(update.message.text.replace(',', '.'))
        
        if amount <= 0:
            await update.message.reply_text(
                "⚠️ Ошибка: сумма должна быть больше нуля. Попробуй ещё раз."
            )
            return ADD_EXPENSE_AMOUNT
        
        # Сохраняем трату
        user_id = update.effective_user.id
        category = context.user_data['selected_category']
        title = context.user_data['expense_name']
        
        expense_bot.add_expense(user_id, category, title, amount)
        
        category_name = CATEGORIES[category]
        
        await update.message.reply_text(
            f"✅ Трата «{title}» на сумму {amount:.0f} ₽ добавлена в категорию «{category_name}».",
            reply_markup=get_back_to_menu_keyboard()
        )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "⚠️ Ошибка: введи число (например, 250). Попробуй ещё раз."
        )
        return ADD_EXPENSE_AMOUNT

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена разговора"""
    return ConversationHandler.END

async def generate_report(query, user_id: int, period: str):
    """Генерация отчёта"""
    now = datetime.now()
    
    if period == 'day':
        start_date = datetime(now.year, now.month, now.day)
        end_date = now
        period_name = "день"
    elif period == 'week':
        start_date = now - timedelta(days=7)
        end_date = now
        period_name = "неделю"
    elif period == 'month':
        start_date = datetime(now.year, now.month, 1)
        end_date = now
        period_name = "месяц"
    else:  # all
        start_date = datetime(2020, 1, 1)
        end_date = now
        period_name = "всё время"
    
    report = expense_bot.get_expenses_report(user_id, start_date, end_date)
    
    if report['total'] == 0:
        await query.edit_message_text(
            "У тебя нет трат за выбранный период.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 В меню", callback_data="back_to_main")]
            ])
        )
        return
    
    # Формируем отчёт
    message = f"📊 Отчёт за {period_name}\n\n"
    message += f"🕒 Период: {start_date.strftime('%d.%m.%Y %H:%M')} — {end_date.strftime('%d.%m.%Y %H:%M')}\n\n"
    
    for category, amount in report['category_totals'].items():
        category_name = CATEGORIES.get(category, category)
        message += f"{category_name}: {amount:.0f} ₽\n"
    
    message += f"\n🧮 Общая сумма: {report['total']:.0f} ₽"
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 В меню", callback_data="back_to_main")]
        ])
    )

async def export_expenses(query, user_id: int, period: str):
    """Экспорт трат в Excel"""
    now = datetime.now()
    
    if period == 'day':
        start_date = datetime(now.year, now.month, now.day)
        end_date = now
        period_name = "день"
    elif period == 'week':
        start_date = now - timedelta(days=7)
        end_date = now
        period_name = "неделю"
    elif period == 'month':
        start_date = datetime(now.year, now.month, 1)
        end_date = now
        period_name = "месяц"
    else:  # all
        start_date = datetime(2020, 1, 1)
        end_date = now
        period_name = "всё время"
    
    # Проверяем, есть ли данные
    report = expense_bot.get_expenses_report(user_id, start_date, end_date)
    
    if report['total'] == 0:
        await query.edit_message_text(
            "Нет данных для выгрузки.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 В меню", callback_data="back_to_main")]
            ])
        )
        return
    
    # Генерируем Excel файл
    excel_file = expense_bot.export_expenses_to_excel(user_id, start_date, end_date)
    
    # Отправляем файл
    filename = f"expenses_{period}_{now.strftime('%Y%m%d')}.xlsx"
    
    await query.message.reply_document(
        document=excel_file,
        filename=filename,
        caption=f"📎 Траты за {period_name}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 В меню", callback_data="back_to_main")]
        ])
    )

def main():
    # Получаем переменные окружения
    token = os.getenv('BOT_TOKEN')
    port = int(os.getenv('PORT', 8000))
    app_name = os.getenv('RENDER_SERVICE_NAME', 'financebot')
    
    if not token:
        logger.error("BOT_TOKEN не установлен в переменных окружения")
        return
    
    # Создаём приложение
    application = Application.builder().token(token).build()
    
    # Создаём ConversationHandler для добавления трат
    add_expense_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^add_expense$')],
        states={
            ADD_EXPENSE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_name)],
            ADD_EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_amount)],
        },
        fallbacks=[
            CallbackQueryHandler(button_handler, pattern='^back$'),
            CallbackQueryHandler(button_handler, pattern='^back_to_main$'),
            CommandHandler('start', start)
        ]
    )
    
    # Добавляем обработчики
    application.add_handler(CommandHandler('start', start))
    application.add_handler(add_expense_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Настраиваем вебхук для Render.com
    webhook_url = f"https://{app_name}.onrender.com/{token}"
    
    logger.info(f"Запуск бота на порту {port}")
    logger.info(f"Webhook URL: {webhook_url}")
    
    # Запускаем бота с вебхуком
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=webhook_url,
        url_path=token,
        secret_token=None
    )

if __name__ == '__main__':
    main()