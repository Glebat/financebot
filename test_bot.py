#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки основных функций бота
"""

import os
import sys
from datetime import datetime

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot import ExpenseBot, CATEGORIES

def test_expense_bot():
    """Тестирование основных функций бота"""
    print("🧪 Запуск тестов ExpenseBot...")
    
    # Создаём экземпляр бота
    bot = ExpenseBot()
    
    # Тестовый пользователь
    test_user_id = 12345
    
    print("\n1️⃣ Тест: Проверка пустой базы данных")
    monthly_total = bot.get_monthly_total(test_user_id)
    print(f"   Сумма за месяц: {monthly_total} ₽")
    assert monthly_total == 0.0, "Ошибка: сумма должна быть 0"
    print("   ✅ Тест пройден")
    
    print("\n2️⃣ Тест: Добавление трат")
    # Добавляем несколько трат
    bot.add_expense(test_user_id, 'food_home', 'Молоко', 80.0)
    bot.add_expense(test_user_id, 'food_home', 'Хлеб', 45.0)
    bot.add_expense(test_user_id, 'transport', 'Метро', 60.0)
    print("   Добавлены траты: Молоко (80₽), Хлеб (45₽), Метро (60₽)")
    
    monthly_total = bot.get_monthly_total(test_user_id)
    print(f"   Общая сумма за месяц: {monthly_total} ₽")
    assert monthly_total == 185.0, f"Ошибка: ожидалось 185, получено {monthly_total}"
    print("   ✅ Тест пройден")
    
    print("\n3️⃣ Тест: Получение трат за сегодня")
    today_expenses = bot.get_today_expenses(test_user_id, 'food_home')
    print(f"   Траты за сегодня в категории 'Еда дома': {len(today_expenses)} шт.")
    for expense_id, title, amount in today_expenses:
        print(f"   - {title}: {amount} ₽ (ID: {expense_id})")
    assert len(today_expenses) == 2, "Ошибка: должно быть 2 траты"
    print("   ✅ Тест пройден")
    
    print("\n4️⃣ Тест: Отчёт за период")
    start_date = datetime(2020, 1, 1)
    end_date = datetime.now()
    report = bot.get_expenses_report(test_user_id, start_date, end_date)
    
    print(f"   Общая сумма: {report['total']} ₽")
    print("   По категориям:")
    for category, amount in report['category_totals'].items():
        category_name = CATEGORIES.get(category, category)
        print(f"   - {category_name}: {amount} ₽")
    
    assert report['total'] == 185.0, "Ошибка: общая сумма не совпадает"
    assert 'food_home' in report['category_totals'], "Ошибка: категория 'food_home' не найдена"
    assert report['category_totals']['food_home'] == 125.0, "Ошибка: сумма по категории не совпадает"
    print("   ✅ Тест пройден")
    
    print("\n5️⃣ Тест: Удаление траты")
    if today_expenses:
        expense_to_delete = today_expenses[0][0]  # ID первой траты
        deleted = bot.delete_expense(expense_to_delete, test_user_id)
        print(f"   Удаление траты ID {expense_to_delete}: {'успешно' if deleted else 'неудачно'}")
        assert deleted, "Ошибка: трата не была удалена"
        
        # Проверяем, что сумма уменьшилась
        new_total = bot.get_monthly_total(test_user_id)
        print(f"   Новая сумма за месяц: {new_total} ₽")
        assert new_total < 185.0, "Ошибка: сумма должна была уменьшиться"
        print("   ✅ Тест пройден")
    
    print("\n6️⃣ Тест: Экспорт в Excel")
    try:
        excel_file = bot.export_expenses_to_excel(test_user_id, start_date, end_date)
        file_size = len(excel_file.getvalue())
        print(f"   Excel файл создан, размер: {file_size} байт")
        assert file_size > 0, "Ошибка: файл пустой"
        print("   ✅ Тест пройден")
    except Exception as e:
        print(f"   ❌ Ошибка при создании Excel: {e}")
        raise
    
    print("\n7️⃣ Тест: Удаление всех трат")
    bot.delete_all_expenses(test_user_id)
    final_total = bot.get_monthly_total(test_user_id)
    print(f"   Сумма после удаления всех трат: {final_total} ₽")
    assert final_total == 0.0, "Ошибка: все траты должны быть удалены"
    print("   ✅ Тест пройден")
    
    print("\n🎉 Все тесты успешно пройдены!")
    print("\n📋 Проверенные функции:")
    print("   ✅ Инициализация базы данных")
    print("   ✅ Добавление трат")
    print("   ✅ Подсчёт месячной суммы")
    print("   ✅ Получение трат за день")
    print("   ✅ Генерация отчётов")
    print("   ✅ Экспорт в Excel")
    print("   ✅ Удаление отдельных трат")
    print("   ✅ Удаление всех трат")
    print("\n🚀 Бот готов к развёртыванию!")

def test_categories():
    """Тест категорий"""
    print("\n📂 Проверка категорий:")
    for key, name in CATEGORIES.items():
        print(f"   {key}: {name}")
    
    assert len(CATEGORIES) == 6, "Ошибка: должно быть 6 категорий"
    print("   ✅ Все категории на месте")

if __name__ == '__main__':
    print("🤖 Тестирование Telegram бота для учёта расходов")
    print("=" * 50)
    
    try:
        test_categories()
        test_expense_bot()
        
        print("\n" + "=" * 50)
        print("🎯 РЕЗУЛЬТАТ: Все тесты пройдены успешно!")
        print("\n💡 Что дальше:")
        print("   1. Создай бота у @BotFather")
        print("   2. Получи токен")
        print("   3. Загрузи код на GitHub")
        print("   4. Разверни на Render.com")
        print("   5. Настрой переменные окружения")
        print("   6. Наслаждайся работающим ботом! 🚀")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        print("\n🔧 Проверь код и попробуй снова.")
        sys.exit(1)