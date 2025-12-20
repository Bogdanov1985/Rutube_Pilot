#!/usr/bin/env python3
"""
Пример запуска Rutube бота
"""

import asyncio
from rutube_viewer_proxy import RutubeBot, read_urls_from_file    ##  rutube_viewer_proxy  rutube_bot


async def main():

    # Способ 1: Использование напрямую
    #urls = [
    #    "https://rutube.ru/video/ваше_видео_1/",
    #    "https://rutube.ru/video/ваше_видео_2/",
    #]

    # Способ 2: Чтение из файла
    urls = read_urls_from_file("videos.txt")

    # Создаем бота
    bot = RutubeBot(
        video_urls=urls,
        visits=3,  # 3 просмотра для каждого видео
        use_proxy=True,
        headless=True
    )

    # Запускаем
    stats = await bot.run_async()
    print(f"Статистика: {stats}")


if __name__ == "__main__":
    asyncio.run(main())




"""
Использование:
bash
# Базовый запуск
python rutube_bot.py --urls https://rutube.ru/video/... --visits 5

# С файлом URL
python rutube_bot.py --file video_urls.txt --visits 3

# Без прокси (режим отладки)
python rutube_bot.py --urls https://rutube.ru/video/... --no-proxy --no-headless

# Тестирование прокси
python rutube_bot.py --test-proxy 123.45.67.89:8080
"""