#!/usr/bin/env python3
"""
Пример запуска Rutube бота

Использование:
    python run_example.py
    или
    python run_example.py --file videos.txt --visits 5 --no-headless

Аргументы командной строки:
    --help              Показать эту справку
    --file FILE         Файл со списком видео (по умолчанию: videos.txt)
    --visits N          Количество просмотров каждого видео (по умолчанию: 3)
    --use-proxy         Использовать прокси (по умолчанию: True)
    --no-proxy          Не использовать прокси
    --headless          Запуск в фоновом режиме (по умолчанию: True)
    --no-headless       Запуск с отображением браузера
    --test-proxy PROXY  Протестировать конкретный прокси (формат: ip:port)
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).parent))

try:
    from Proxy.rutube_viewer_proxy import RutubeBot, read_urls_from_file
except ImportError:
    print("Ошибка: Не удалось импортировать модуль Proxy.rutube_viewer_proxy1")
    print("Убедитесь, что файл находится в папке Proxy/")
    sys.exit(1)


def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Rutube Bot - инструмент для автоматического просмотра видео',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s                                    # Запуск с настройками по умолчанию
  %(prog)s --file my_videos.txt --visits 5    # 5 просмотров каждого видео из файла
  %(prog)s --no-headless --no-proxy          # Запуск с GUI и без прокси (отладка)
  %(prog)s --test-proxy 123.45.67.89:8080    # Тестирование конкретного прокси

Формат файла с видео:
  Каждая ссылка на видео на отдельной строке
  Пример:
    https://rutube.ru/video/abcdef123/
    https://rutube.ru/video/xyz789456/
        """
    )

    parser.add_argument(
        '--file',
        type=str,
        default='videos.txt',
        help='Файл со списком видео (по умолчанию: videos.txt)'
    )

    parser.add_argument(
        '--visits',
        type=int,
        default=3,
        help='Количество просмотров каждого видео (по умолчанию: 3)'
    )

    parser.add_argument(
        '--use-proxy',
        action='store_true',
        default=True,
        help='Использовать прокси (по умолчанию: True)'
    )

    parser.add_argument(
        '--no-proxy',
        action='store_false',
        dest='use_proxy',
        help='Не использовать прокси'
    )

    parser.add_argument(
        '--headless',
        action='store_true',
        default=True,
        help='Запуск в фоновом режиме (по умолчанию: True)'
    )

    parser.add_argument(
        '--no-headless',
        action='store_false',
        dest='headless',
        help='Запуск с отображением браузера'
    )

    parser.add_argument(
        '--test-proxy',
        type=str,
        help='Протестировать конкретный прокси (формат: ip:port)'
    )

    return parser.parse_args()


async def test_single_proxy(proxy_string):
    """Тестирование одного прокси"""
    from Proxy.rutube_viewer_proxy1 import ProxyManager

    print(f"\nТестирование прокси: {proxy_string}")
    print("-" * 40)

    proxy_manager = ProxyManager()

    try:
        result = await proxy_manager.test_proxy(proxy_string)
        if result:
            print(f"✓ Прокси РАБОЧИЙ")
            print(f"  IP адрес: {result[1] if result[1] else 'скрыт'}")
            print(f"  Прокси: {proxy_string}")
            return True
        else:
            print(f"✗ Прокси НЕ РАБОЧИЙ")
            print(f"  Прокси: {proxy_string}")
            return False
    except Exception as e:
        print(f"✗ Ошибка тестирования: {e}")
        return False


async def main_async(args):
    """Основная асинхронная функция"""

    # Тестирование прокси
    if args.test_proxy:
        await test_single_proxy(args.test_proxy)
        return

    # Проверка существования файла с видео
    if not os.path.exists(args.file):
        print(f"Ошибка: Файл '{args.file}' не найден!")
        print("Создайте файл videos.txt со списком ссылок или укажите другой файл через --file")
        return

    # Чтение URL из файла
    print(f"Чтение видео из файла: {args.file}")
    urls = read_urls_from_file(args.file)

    if not urls:
        print(f"Ошибка: Не найдено видео в файле {args.file}")
        print("Убедитесь, что файл содержит ссылки на Rutube в формате:")
        print("  https://rutube.ru/video/ваше_видео/")
        return

    print(f"Найдено {len(urls)} видео для просмотра")
    print(f"Каждое видео будет просмотрено {args.visits} раз")
    print(f"Режим работы: {'headless' if args.headless else 'с GUI'}")
    print(f"Использование прокси: {'Да' if args.use_proxy else 'Нет'}")
    print("-" * 60)

    # Создаем бота
    try:
        bot = RutubeBot(
            video_urls=urls,
            visits=args.visits,
            use_proxy=args.use_proxy,
            headless=args.headless
        )
    except Exception as e:
        print(f"Ошибка при создании бота: {e}")
        print("Убедитесь, что установлены все зависимости:")
        print("  pip install selenium webdriver-manager aiohttp")
        return

    # Запускаем бота
    print("\nЗапуск бота...")
    print("=" * 60)

    try:
        stats = await bot.run_async()

        # Вывод статистики
        print("\n" + "=" * 60)
        print("СТАТИСТИКА ВЫПОЛНЕНИЯ")
        print("=" * 60)
        print(f"Всего видео: {len(urls)}")
        print(f"Просмотров на видео: {args.visits}")
        print(f"Всего посещений: {stats.get('total_visits', 0)}")
        print(f"Успешных просмотров: {stats.get('successful_visits', 0)}")
        print(f"Неудачных просмотров: {stats.get('failed_visits', 0)}")

        # Расчет процента успеха
        total = stats.get('total_visits', 0)
        successful = stats.get('successful_visits', 0)
        if total > 0:
            success_rate = (successful / total) * 100
            print(f"Процент успеха: {success_rate:.1f}%")

        # Время выполнения
        if 'duration' in stats:
            print(f"Время выполнения: {stats['duration']}")

        print(f"Использовано прокси: {len(stats.get('proxies_used', []))}")
        print("=" * 60)

        # Сохранение полной статистики
        print(f"\nПолная статистика сохранена в Logs/bot_statistics.json")
        print(f"Логи работы сохранены в Logs/rutube_bot.log")

    except KeyboardInterrupt:
        print("\n\nПрограмма остановлена пользователем")
        print("Сохранение промежуточной статистики...")
        try:
            bot.save_statistics()
        except:
            pass
    except Exception as e:
        print(f"\nКритическая ошибка при работе бота: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Основная функция"""
    args = parse_arguments()

    print("\n" + "=" * 60)
    print("RUTUBE BOT - АВТОМАТИЧЕСКИЙ ПРОСМОТР ВИДЕО")
    print("=" * 60)

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\n\nПрограмма завершена")
    except Exception as e:
        print(f"\nНеожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()

    print("\nРабота завершена. Для повторного запуска используйте те же команды.")
    print("=" * 60)


if __name__ == "__main__":
    main()