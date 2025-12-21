# -*- coding: utf-8 -*-
"""
Rutube Bot

Updated version for Rutube with improved proxy management
"""

import os
import sys
import time
import json
import asyncio
import aiohttp
from random import choice, randint
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from queue import Queue
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# Создаем директории перед настройкой логирования
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, 'Logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'rutube_bot.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# Прокси модуль
# ============================================================================

class ProxyManager:
    """Управление прокси-серверами"""

    def __init__(self, max_proxies=50, timeout=10):
        self.proxies = []
        self.working_proxies = []
        self.lock = Lock()
        self.max_proxies = max_proxies
        self.timeout = timeout
        self.test_urls = [
            'http://httpbin.org/ip',
            'https://api.ipify.org?format=json',
            'https://rutube.ru/api/play/options/'
        ]

    async def fetch_proxies(self, sources=None):
        """Получение прокси из различных источников"""
        if sources is None:
            sources = [
                os.path.join(BASE_DIR, 'Proxy', 'proxylist.txt'),
                'https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all',
                'https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt',
                'https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt',
                'https://www.proxy-list.download/api/v1/get?type=http'
            ]

        async def fetch_source(url):
            try:
                # Если это локальный файл
                if url.startswith('http'):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=10) as response:
                            if response.status == 200:
                                text = await response.text()
                                proxies = [p.strip() for p in text.split('\n') if p.strip()]
                                return proxies
                else:
                    # Чтение из локального файла
                    if os.path.exists(url):
                        with open(url, 'r') as f:
                            proxies = [p.strip() for p in f.readlines() if p.strip()]
                            return proxies
            except Exception as e:
                logger.debug(f"Ошибка при получении прокси из {url}: {e}")
                return []

        tasks = [fetch_source(source) for source in sources]
        results = await asyncio.gather(*tasks)

        all_proxies = []
        for proxy_list in results:
            if proxy_list:
                all_proxies.extend(proxy_list)

        # Убираем дубликаты
        self.proxies = list(set(all_proxies))[:self.max_proxies]
        logger.info(f"Найдено {len(self.proxies)} прокси")
        return self.proxies

    async def test_proxy(self, proxy):
        """Асинхронная проверка работоспособности прокси"""
        test_proxies = {
            'http': f'http://{proxy}',
            'https': f'http://{proxy}'
        }

        for test_url in self.test_urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                            test_url,
                            proxy=test_proxies['http'],
                            timeout=self.timeout
                    ) as response:
                        if response.status == 200:
                            try:
                                data = await response.json()
                                ip = data.get('origin') or data.get('ip')
                                if ip:
                                    logger.debug(f"Прокси {proxy} рабочий, IP: {ip}")
                                    return (proxy, ip)
                            except:
                                text = await response.text()
                                if 'origin' in text or 'ip' in text:
                                    logger.debug(f"Прокси {proxy} рабочий")
                                    return (proxy, None)
            except Exception as e:
                continue

        return None

    async def validate_proxies(self, max_workers=20):
        """Проверка всех прокси на работоспособность"""
        logger.info("Начинаем проверку прокси...")

        semaphore = asyncio.Semaphore(max_workers)

        async def test_with_semaphore(proxy):
            async with semaphore:
                return await self.test_proxy(proxy)

        tasks = [test_with_semaphore(proxy) for proxy in self.proxies]
        results = await asyncio.gather(*tasks)

        self.working_proxies = [result[0] for result in results if result]

        logger.info(f"Найдено {len(self.working_proxies)} рабочих прокси")

        # Сохраняем в файл
        log_file = os.path.join(LOG_DIR, 'working_proxies.json')
        with open(log_file, 'w') as f:
            json.dump(self.working_proxies, f, indent=2)

        logger.info(f"Рабочие прокси сохранены в {log_file}")
        return self.working_proxies

    def get_random_proxy(self):
        """Получение случайного рабочего прокси"""
        with self.lock:
            if not self.working_proxies:
                return None
            return choice(self.working_proxies)

    def mark_proxy_failed(self, proxy):
        """Пометить прокси как нерабочий"""
        with self.lock:
            if proxy in self.working_proxies:
                self.working_proxies.remove(proxy)
                logger.info(f"Прокси {proxy} удален из списка рабочих")

    def save_statistics(self):
        """Сохранение статистики"""
        stats = {
            'total_proxies': len(self.proxies),
            'working_proxies': len(self.working_proxies),
            'timestamp': datetime.now().isoformat(),
            'working_list': self.working_proxies
        }

        stats_file = os.path.join(BASE_DIR, 'Proxy', 'proxy_stats.json')
        os.makedirs(os.path.dirname(stats_file), exist_ok=True)

        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)


# ============================================================================
# Rutube клиент
# ============================================================================

class RutubeClient:
    """Клиент для работы с Rutube"""

    def __init__(self, proxy=None, headless=True, user_agent=None):
        self.proxy = proxy
        self.headless = headless
        self.user_agent = user_agent or self._get_random_user_agent()
        self.driver = None
        self.timeout = 20

    def _get_random_user_agent(self):
        """Генерация случайного User-Agent"""
        user_agents = [
            # Chrome
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # Firefox
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
            # Safari
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            # Edge
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        ]
        return choice(user_agents)

    def _setup_driver(self):
        """Настройка драйвера Chrome"""
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument('--headless=new')

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # User-Agent
        chrome_options.add_argument(f'--user-agent={self.user_agent}')

        # Прокси
        if self.proxy:
            chrome_options.add_argument(f'--proxy-server=http://{self.proxy}')

        # Дополнительные настройки
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--disable-extensions')

        # Антидетект
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")

        # Отключаем автоматизацию
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)

            # Скрываем автоматизацию
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": self.user_agent
            })
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            return driver
        except Exception as e:
            logger.error(f"Ошибка при создании драйвера: {e}")
            raise

    def open_video(self, video_url):
        """Открытие видео на Rutube"""
        try:
            if not self.driver:
                self.driver = self._setup_driver()

            logger.info(f"Открываем видео: {video_url}")
            self.driver.get(video_url)

            # Ждем загрузки страницы
            time.sleep(3)

            # Принимаем куки, если есть
            try:
                cookie_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//button[contains(text(), 'Принять') or contains(text(), 'Accept')]"))
                )
                cookie_button.click()
                time.sleep(1)
            except:
                pass

            # Проверяем, что видео загрузилось
            try:
                WebDriverWait(self.driver, self.timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "video"))
                )
                logger.info("Видео успешно загружено")
                return True
            except TimeoutException:
                logger.warning("Не удалось найти видео на странице")
                return False

        except Exception as e:
            logger.error(f"Ошибка при открытии видео: {e}")
            return False

    def play_video(self):
        """Запуск воспроизведения видео"""
        try:
            # Ищем кнопку воспроизведения
            play_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button[aria-label='Воспроизвести'], .video-player__play-button, .play-button"))
            )
            play_button.click()
            logger.info("Видео запущено")
            return True
        except Exception as e:
            logger.warning(f"Не удалось запустить видео автоматически: {e}")
            return False

    def watch_video(self, watch_time=30):
        """Просмотр видео в течение указанного времени"""
        try:
            logger.info(f"Смотрим видео {watch_time} секунд...")

            start_time = time.time()
            last_action = start_time

            while time.time() - start_time < watch_time:
                current_time = time.time()

                # Периодически двигаем мышкой и скроллим
                if current_time - last_action > 5:
                    self._simulate_human_activity()
                    last_action = current_time

                # Проверяем, что видео еще играет
                try:
                    video = self.driver.find_element(By.TAG_NAME, "video")
                    is_paused = self.driver.execute_script("return arguments[0].paused", video)

                    if is_paused:
                        logger.info("Видео на паузе, возобновляем...")
                        self.driver.execute_script("arguments[0].play()", video)
                except:
                    pass

                time.sleep(1)

            logger.info("Просмотр завершен")
            return True

        except Exception as e:
            logger.error(f"Ошибка при просмотре видео: {e}")
            return False

    def _simulate_human_activity(self):
        """Симуляция человеческой активности"""
        try:
            # Случайный скроллинг
            scroll_amount = randint(100, 500)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")

            # Случайное движение мышкой
            width = self.driver.execute_script("return document.documentElement.scrollWidth")
            height = self.driver.execute_script("return document.documentElement.scrollHeight")

            x = randint(0, width)
            y = randint(0, height)

            self.driver.execute_script(f"""
                var evt = new MouseEvent('mousemove', {{
                    view: window,
                    bubbles: true,
                    cancelable: true,
                    clientX: {x},
                    clientY: {y}
                }});
                document.documentElement.dispatchEvent(evt);
            """)

        except:
            pass

    def get_video_info(self):
        """Получение информации о видео"""
        try:
            info = {}

            # Название видео
            try:
                title = self.driver.find_element(By.CSS_SELECTOR, "h1.video-info__title, .video-title, h1.title").text
                info['title'] = title
            except:
                info['title'] = "Не найдено"

            # Количество просмотров
            try:
                views = self.driver.find_element(By.CSS_SELECTOR,
                                                 ".video-info__views, .views-count, .statistics__views").text
                info['views'] = views
            except:
                info['views'] = "Не найдено"

            # Автор
            try:
                author = self.driver.find_element(By.CSS_SELECTOR,
                                                  ".video-info__author, .author-name, .channel-name").text
                info['author'] = author
            except:
                info['author'] = "Не найдено"

            return info

        except Exception as e:
            logger.error(f"Ошибка при получении информации о видео: {e}")
            return {}

    def close(self):
        """Закрытие браузера"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None


# ============================================================================
# Основной бот
# ============================================================================

class RutubeBot:
    """Основной бот для Rutube"""

    def __init__(self, video_urls=None, visits=1, use_proxy=True, headless=True):
        self.video_urls = video_urls or []
        self.visits = visits
        self.use_proxy = use_proxy
        self.headless = headless
        self.proxy_manager = ProxyManager()
        self.stats = {
            'total_visits': 0,
            'successful_visits': 0,
            'failed_visits': 0,
            'proxies_used': [],
            'start_time': datetime.now().isoformat()
        }

    async def initialize_proxies(self):
        """Инициализация прокси"""
        if self.use_proxy:
            logger.info("Инициализация системы прокси...")
            await self.proxy_manager.fetch_proxies()
            await self.proxy_manager.validate_proxies()
            self.proxy_manager.save_statistics()
        else:
            logger.info("Использование без прокси")

    def process_video(self, video_url, proxy=None):
        """Обработка одного видео"""
        logger.info(f"Обработка видео: {video_url}")

        client = None
        try:
            # Создаем клиент
            client = RutubeClient(
                proxy=proxy,
                headless=self.headless,
                user_agent=None
            )

            # Открываем видео
            if not client.open_video(video_url):
                logger.warning(f"Не удалось открыть видео: {video_url}")
                return False

            # Получаем информацию
            info = client.get_video_info()
            logger.info(f"Информация о видео: {info}")

            # Запускаем видео
            client.play_video()

            # Смотрим видео (случайное время от 30 до 120 секунд)
            watch_time = randint(30, 120)
            success = client.watch_video(watch_time)

            if success:
                logger.info(f"Успешно просмотрено видео: {info.get('title', 'Unknown')}")
                self.stats['successful_visits'] += 1
            else:
                logger.warning(f"Не удалось полностью просмотреть видео")
                self.stats['failed_visits'] += 1

            self.stats['total_visits'] += 1

            if proxy:
                self.stats['proxies_used'].append(proxy)

            return success

        except Exception as e:
            logger.error(f"Ошибка при обработке видео: {e}")
            self.stats['failed_visits'] += 1
            self.stats['total_visits'] += 1
            return False

        finally:
            if client:
                client.close()

            # Пауза между запросами
            sleep_time = randint(5, 15)
            logger.info(f"Пауза {sleep_time} секунд...")
            time.sleep(sleep_time)

    async def run_async(self):
        """Асинхронный запуск бота"""
        # Инициализируем прокси
        await self.initialize_proxies()

        logger.info(f"Начинаем обработку {len(self.video_urls)} видео, {self.visits} посещений каждое")

        # Обрабатываем каждое видео
        for video_url in self.video_urls:
            for visit in range(self.visits):
                logger.info(f"Посещение {visit + 1}/{self.visits} для {video_url}")

                # Выбираем прокси
                proxy = None
                if self.use_proxy:
                    proxy = self.proxy_manager.get_random_proxy()
                    if proxy:
                        logger.info(f"Используем прокси: {proxy}")
                    else:
                        logger.warning("Нет доступных рабочих прокси")
                        if self.proxy_manager.working_proxies:
                            proxy = choice(self.proxy_manager.working_proxies)

                # Обрабатываем видео
                success = self.process_video(video_url, proxy)

                # Если прокси не сработал, помечаем его
                if proxy and not success:
                    self.proxy_manager.mark_proxy_failed(proxy)

        # Сохраняем статистику
        self.save_statistics()

        logger.info("Работа завершена")
        return self.stats

    def run(self):
        """Синхронный запуск бота"""
        return asyncio.run(self.run_async())

    def save_statistics(self):
        """Сохранение статистики"""
        self.stats['end_time'] = datetime.now().isoformat()
        self.stats['duration'] = str(datetime.fromisoformat(self.stats['end_time']) -
                                     datetime.fromisoformat(self.stats['start_time']))

        stats_file = os.path.join(LOG_DIR, 'bot_statistics.json')
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Статистика сохранена в {stats_file}")
        logger.info(f"Итого: {self.stats['successful_visits']} успешных, "
                    f"{self.stats['failed_visits']} неудачных посещений")


# ============================================================================
# Утилиты
# ============================================================================

def read_urls_from_file(filename):
    """Чтение URL из файла"""
    urls = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url and url.startswith('http'):
                    urls.append(url)
    except Exception as e:
        logger.error(f"Ошибка при чтении файла {filename}: {e}")

    logger.info(f"Прочитано {len(urls)} URL из файла {filename}")
    return urls


def main():
    """Главная функция"""
    import argparse

    parser = argparse.ArgumentParser(description='Rutube Bot для увеличения просмотров')
    parser.add_argument('--urls', nargs='+', help='Список URL видео на Rutube')
    parser.add_argument('--file', help='Файл со списком URL (по одному на строку)')
    parser.add_argument('--visits', type=int, default=1, help='Количество посещений для каждого видео')
    parser.add_argument('--no-proxy', action='store_true', help='Не использовать прокси')
    parser.add_argument('--no-headless', action='store_true', help='Показать браузер')
    parser.add_argument('--max-proxies', type=int, default=50, help='Максимальное количество прокси для проверки')
    parser.add_argument('--test-proxy', help='Протестировать конкретный прокси (формат: ip:port)')

    args = parser.parse_args()

    # Тестирование прокси
    if args.test_proxy:
        import asyncio
        proxy_manager = ProxyManager()

        async def test():
            result = await proxy_manager.test_proxy(args.test_proxy)
            if result:
                print(f"✓ Прокси {args.test_proxy} рабочий")
                print(f"  IP: {result[1]}")
            else:
                print(f"✗ Прокси {args.test_proxy} не рабочий")

        asyncio.run(test())
        return

    # Сбор URL
    video_urls = []

    if args.urls:
        video_urls.extend(args.urls)

    if args.file:
        file_urls = read_urls_from_file(args.file)
        video_urls.extend(file_urls)

    if not video_urls:
        logger.error("Не указаны URL видео. Используйте --urls или --file")
        parser.print_help()
        return

    # Убираем дубликаты
    video_urls = list(set(video_urls))
    logger.info(f"Будет обработано {len(video_urls)} уникальных видео")

    # Создаем и запускаем бота
    bot = RutubeBot(
        video_urls=video_urls,
        visits=args.visits,
        use_proxy=not args.no_proxy,
        headless=not args.no_headless
    )

    if args.max_proxies:
        bot.proxy_manager.max_proxies = args.max_proxies

    # Запускаем
    try:
        stats = bot.run()
        logger.info(f"Работа завершена. Статистика: {stats}")
    except KeyboardInterrupt:
        logger.info("Работа прервана пользователем")
        bot.save_statistics()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()