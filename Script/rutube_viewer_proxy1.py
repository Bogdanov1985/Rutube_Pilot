import time
import random
import argparse
import os
import sys
import json
import asyncio
import aiohttp
from datetime import datetime
from typing import List, Optional, Union
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

'''
# Базовый запуск
python rutube_viewer_proxy1.py --urls https://rutube.ru/video/... --time 60

# С прокси
python rutube_viewer_proxy1.py --urls https://rutube.ru/video/... --proxy --no-gui

# Из файла с прокси
python rutube_viewer_proxy1.py --file videos.txt --proxy --cycles 3 --delay-between-cycles 60
'''



# Определяем базовую директорию проекта
BASE_DIR = Path(__file__).parent.parent if "Proxy" in str(Path(__file__).parent) else Path(__file__).parent
LOG_DIR = BASE_DIR / "Logs"
PROXY_DIR = BASE_DIR / "Proxy"
SCRIPTS_DIR = BASE_DIR / "Script"

# Создаем директории
LOG_DIR.mkdir(exist_ok=True)
PROXY_DIR.mkdir(exist_ok=True)
SCRIPTS_DIR.mkdir(exist_ok=True)


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
                str(PROXY_DIR / 'proxylist.txt'),
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
        log_file = LOG_DIR / 'working_proxies.json'
        with open(log_file, 'w') as f:
            json.dump(self.working_proxies, f, indent=2)

        logger.info(f"Рабочие прокси сохранены в {log_file}")
        return self.working_proxies

    def get_random_proxy(self):
        """Получение случайного рабочего прокси"""
        with self.lock:
            if not self.working_proxies:
                return None
            return random.choice(self.working_proxies)

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

        stats_file = PROXY_DIR / 'proxy_stats.json'
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)


# ============================================================================
# RuTube Viewer с поддержкой прокси
# ============================================================================

class RuTubeViewer:
    def __init__(self, gui_mode: bool = True, incognito: bool = True,
                 chromedriver_path: Optional[str] = None,
                 use_proxy: bool = False, proxy: Optional[str] = None):
        self.setup_logging()
        self.gui_mode = gui_mode
        self.incognito = incognito
        self.use_proxy = use_proxy
        self.current_proxy = proxy
        self.chromedriver_path = self._find_chromedriver(chromedriver_path)
        self.driver = None
        self.proxy_manager = ProxyManager() if use_proxy else None

        self.stats = {
            'total_videos': 0,
            'successful_views': 0,
            'failed_views': 0,
            'total_watch_time': 0,
            'videos_history': [],
            'cycles_completed': 0,
            'settings': {
                'gui_mode': gui_mode,
                'incognito': incognito,
                'use_proxy': use_proxy,
                'current_proxy': proxy,
                'chromedriver_path': str(self.chromedriver_path) if self.chromedriver_path else None,
                'start_time': datetime.now().isoformat()
            }
        }

    def setup_logging(self):
        """Настройка логирования с учетом структуры каталогов"""
        # Настройка логгера
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # Очистка старых обработчиков
        if self.logger.handlers:
            self.logger.handlers.clear()

        # Форматтер
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        # Файловый обработчик
        log_file = LOG_DIR / 'rutube_viewer.log'
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)

        # Консольный обработчик
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

        # Добавляем обработчики
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _find_chromedriver(self, custom_path: Optional[str] = None) -> Optional[str]:
        """Поиск ChromeDriver"""
        # 1. Пользовательский путь
        if custom_path and os.path.exists(custom_path):
            self.logger.info(f"Используется указанный ChromeDriver: {custom_path}")
            return custom_path

        # 2. Проверяем различные пути
        paths_to_check = [
            SCRIPTS_DIR / "chromedriver.exe",
            SCRIPTS_DIR / "chromedriver",
            BASE_DIR / "chromedriver.exe",
            BASE_DIR / "chromedriver",
            Path.cwd() / "chromedriver.exe",
            Path.cwd() / "chromedriver",
        ]

        for path in paths_to_check:
            if path.exists():
                self.logger.info(f"Найден ChromeDriver: {path}")
                return str(path)

        # 3. Переменная окружения
        env_path = os.environ.get('CHROMEDRIVER_PATH')
        if env_path and os.path.exists(env_path):
            self.logger.info(f"Найден ChromeDriver в переменной окружения: {env_path}")
            return env_path

        # 4. Системный PATH
        import shutil
        system_path = shutil.which("chromedriver") or shutil.which("chromedriver.exe")
        if system_path:
            self.logger.info(f"Найден ChromeDriver в PATH: {system_path}")
            return system_path

        self.logger.warning("ChromeDriver не найден. Будет использован webdriver-manager.")
        return None

    def initialize_proxy(self):
        """Инициализация прокси"""
        if self.use_proxy and self.proxy_manager:
            try:
                # Запускаем асинхронно
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # Загружаем и проверяем прокси
                loop.run_until_complete(self.proxy_manager.fetch_proxies())
                loop.run_until_complete(self.proxy_manager.validate_proxies())
                self.proxy_manager.save_statistics()

                # Выбираем случайный прокси
                self.current_proxy = self.proxy_manager.get_random_proxy()
                if self.current_proxy:
                    self.logger.info(f"Используем прокси: {self.current_proxy}")
                else:
                    self.logger.warning("Нет доступных рабочих прокси")

                loop.close()
            except Exception as e:
                self.logger.error(f"Ошибка инициализации прокси: {e}")
                self.current_proxy = None

    def create_driver(self):
        """Создание драйвера с поддержкой прокси"""
        try:
            chrome_options = Options()

            # Базовые опции
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            # Режимы
            if self.incognito:
                chrome_options.add_argument("--incognito")

            if not self.gui_mode:
                chrome_options.add_argument("--headless=new")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
            else:
                chrome_options.add_argument("--start-maximized")

            # Прокси
            if self.use_proxy and self.current_proxy:
                chrome_options.add_argument(f'--proxy-server=http://{self.current_proxy}')
                self.logger.info(f"Добавлен прокси в опции: {self.current_proxy}")

            # Дополнительные опции
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--lang=ru-RU")

            # User-Agent
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
            ]
            chrome_options.add_argument(f'user-agent={random.choice(user_agents)}')

            # Создание драйвера
            if self.chromedriver_path and os.path.exists(self.chromedriver_path):
                service = Service(executable_path=self.chromedriver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.logger.info(f"Используется ChromeDriver: {self.chromedriver_path}")
            else:
                # Пробуем webdriver-manager
                try:
                    from webdriver_manager.chrome import ChromeDriverManager
                    from selenium.webdriver.chrome.service import Service as ChromeService

                    service = ChromeService(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    self.logger.info("Драйвер загружен через webdriver-manager")
                except ImportError:
                    # Системный драйвер
                    self.driver = webdriver.Chrome(options=chrome_options)
                    self.logger.info("Используется системный ChromeDriver")

            # Скрываем автоматизацию
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            return True

        except Exception as e:
            self.logger.error(f"Ошибка при создании драйвера: {e}")
            return False

    def wait_random(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Случайная задержка"""
        time.sleep(random.uniform(min_seconds, max_seconds))

    def close_popups(self):
        """Закрытие всплывающих окон"""
        try:
            self.logger.info("Проверяем всплывающие окна...")

            # Список селекторов для закрытия окон
            close_selectors = [
                "svg.svg-icon--IconClose",
                "button[class*='close']",
                "button[class*='Close']",
                "div[class*='close'] button",
                "div[class*='Close'] button",
                "button[aria-label*='закрыть']",
                "button[aria-label*='Закрыть']",
                "button[title*='закрыть']",
                "button[title*='Закрыть']",

                # Общие селекторы всплывающих окон
                "div[class*='modal'] button[class*='close']",
                "div[class*='popup'] button[class*='close']",
                "div[class*='dialog'] button[class*='close']",

                # XPath селекторы
                "//button[contains(@class, 'close')]",
                "//button[.//*[contains(@class, 'IconClose')]]",
                "//button[.//svg[contains(@class, 'IconClose')]]",
                "//button[contains(text(), '✕')]",
                "//button[contains(text(), '×')]",
                "//button[contains(text(), 'X')]",
                "//button[contains(text(), 'x')]",
            ]

            closed_popups = 0

            for selector in close_selectors:
                try:
                    # Для XPath селекторов
                    if selector.startswith("//"):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                    for element in elements:
                        try:
                            if element.is_displayed() and element.is_enabled():
                                element.click()
                                self.logger.info(f"Закрыто всплывающее окно: {selector}")
                                closed_popups += 1
                                self.wait_random(0.5, 1)
                                break
                        except:
                            continue

                except Exception as e:
                    continue

            if closed_popups > 0:
                self.logger.info(f"Закрыто {closed_popups} всплывающих окон")
            else:
                self.logger.debug("Всплывающих окон не найдено")

        except Exception as e:
            self.logger.debug(f"Ошибка при закрытии всплывающих окон: {e}")

    def accept_cookies(self):
        """Принятие куки"""
        try:
            cookie_selectors = [
                "button[class*='cookie']",
                "button[class*='Cookie']",
                "//button[contains(text(), 'Принять')]",
                "//button[contains(text(), 'Согласен')]",
                "//button[contains(text(), 'Принимаю')]",
                "//button[contains(text(), 'OK')]",
                "//button[contains(text(), 'Ok')]",
                "//button[contains(text(), 'ОК')]",
            ]

            for selector in cookie_selectors:
                try:
                    if selector.startswith("//"):
                        element = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        element = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )

                    if element and element.is_displayed():
                        element.click()
                        self.logger.info("Куки приняты")
                        self.wait_random(1, 2)
                        return True
                except:
                    continue

        except Exception as e:
            self.logger.debug(f"Окно куки не найдено: {e}")

        return False

    def watch_video(self, video_url: str, watch_time: int = 30):
        """Просмотр одного видео"""
        try:
            self.logger.info(f"Начинаем просмотр: {video_url}")
            self.logger.info(f"Время просмотра: {watch_time} секунд")

            # Переход на страницу
            self.driver.get(video_url)
            self.wait_random(2, 4)

            # Закрываем всплывающие окна
            self.close_popups()

            # Куки
            self.accept_cookies()

            # Еще раз проверяем всплывающие окна
            self.close_popups()

            # Ждем загрузки
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Ищем видео
            video_element = None
            video_selectors = [
                "video",
                "iframe[src*='rutube']",
                ".video-js",
                "div[class*='video-player']",
                "div[class*='player']",
                "#video-player",
                "video[class*='player']",
            ]

            for selector in video_selectors:
                try:
                    if selector == "video":
                        video_element = self.driver.find_element(By.TAG_NAME, "video")
                    else:
                        video_element = self.driver.find_element(By.CSS_SELECTOR, selector)

                    if video_element:
                        self.logger.info(f"Видео найдено: {selector}")
                        break
                except:
                    continue

            # Пытаемся воспроизвести
            if video_element:
                try:
                    self.driver.execute_script("arguments[0].play();", video_element)
                    self.logger.info("Воспроизведение начато")
                except:
                    try:
                        video_element.click()
                        self.logger.info("Клик на видео")
                    except:
                        try:
                            # Пробуем найти кнопку play
                            play_buttons = self.driver.find_elements(By.CSS_SELECTOR,
                                                                     "button[class*='play'], button[title*='play'], button[aria-label*='play']")
                            for btn in play_buttons:
                                if btn.is_displayed():
                                    btn.click()
                                    self.logger.info("Нажата кнопка Play")
                                    break
                        except:
                            self.logger.warning("Не удалось начать воспроизведение")

            # Время просмотра
            start_time = time.time()
            elapsed_time = 0

            while elapsed_time < watch_time:
                # Случайные действия
                if random.random() < 0.3:
                    # Прокрутка
                    scroll_pos = random.randint(0, 500)
                    self.driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
                    self.wait_random(0.5, 1.5)

                elapsed_time = time.time() - start_time

                # Прогресс
                if int(elapsed_time) % 15 == 0:
                    self.logger.info(f"Просмотрено {int(elapsed_time)} из {watch_time} сек")

                time.sleep(random.uniform(1, 2))

            self.logger.info(f"Просмотр завершен: {video_url}")
            return True

        except TimeoutException:
            self.logger.error(f"Таймаут: {video_url}")
            # Помечаем прокси как нерабочий
            if self.use_proxy and self.current_proxy and self.proxy_manager:
                self.proxy_manager.mark_proxy_failed(self.current_proxy)
            return False
        except Exception as e:
            self.logger.error(f"Ошибка: {video_url} - {e}")
            # Помечаем прокси как нерабочий
            if self.use_proxy and self.current_proxy and self.proxy_manager:
                self.proxy_manager.mark_proxy_failed(self.current_proxy)
            return False

    def process_videos(self, video_urls: List[str], watch_time: int = 30,
                       shuffle: bool = False, max_videos: Optional[int] = None):
        """Обработка списка видео"""
        if shuffle:
            random.shuffle(video_urls)
            self.logger.info("Список перемешан")

        if max_videos:
            video_urls = video_urls[:max_videos]
            self.logger.info(f"Ограничение: {max_videos} видео")

        total_videos_in_cycle = len(video_urls)
        self.stats['total_videos'] += total_videos_in_cycle

        for i, video_url in enumerate(video_urls, 1):
            self.logger.info(f"\n{'=' * 50}")
            self.logger.info(f"Видео {i}/{len(video_urls)}: {video_url}")
            self.logger.info(f"{'=' * 50}")

            # Проверка ссылки
            if "rutube.ru" not in video_url and "rutube.pl" not in video_url:
                self.logger.warning(f"Не RuTube ссылка: {video_url}")
                self.stats['failed_views'] += 1
                continue

            # Пауза между видео
            if i > 1:
                pause = random.randint(5, 10)
                self.logger.info(f"Пауза: {pause} секунд")
                time.sleep(pause)

            # Просмотр
            success = self.watch_video(video_url, watch_time)

            # Статистика
            video_stat = {
                'url': video_url,
                'timestamp': datetime.now().isoformat(),
                'watch_time': watch_time,
                'success': success,
                'proxy': self.current_proxy if self.use_proxy else None,
                'cycle': self.stats['cycles_completed'] + 1,
            }
            self.stats['videos_history'].append(video_stat)

            if success:
                self.stats['successful_views'] += 1
                self.stats['total_watch_time'] += watch_time
                self.logger.info("Успешно просмотрено")
            else:
                self.stats['failed_views'] += 1
                self.logger.error("Ошибка просмотра")

            # Сохранение статистики после каждого видео
            self.save_stats()

    def save_stats(self):
        """Сохранение статистики"""
        try:
            stats_file = LOG_DIR / 'viewer_stats.json'
            self.stats['settings']['end_time'] = datetime.now().isoformat()
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения статистики: {e}")

    def load_videos_from_file(self, filepath: str) -> List[str]:
        """Загрузка видео из файла"""
        try:
            if not os.path.exists(filepath):
                self.logger.error(f"Файл не найден: {filepath}")
                return []

            with open(filepath, 'r', encoding='utf-8') as f:
                urls = []
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        urls.append(line)

            # Фильтруем только rutube
            rutube_urls = [url for url in urls if "rutube" in url]

            if len(rutube_urls) < len(urls):
                self.logger.warning(f"Отфильтровано {len(urls) - len(rutube_urls)} ссылок")

            self.logger.info(f"Загружено {len(rutube_urls)} видео из {filepath}")
            return rutube_urls

        except Exception as e:
            self.logger.error(f"Ошибка загрузки файла: {e}")
            return []

    def run_cycles(self, video_urls: List[str], watch_time: int = 30,
                   shuffle: bool = False, max_videos: Optional[int] = None,
                   cycles: int = 1, delay_between_cycles: int = 10):
        """Запуск циклического просмотра"""
        try:
            # Информация о цикле
            print(f"\n{'=' * 60}")
            print(f"ЦИКЛИЧЕСКИЙ ПРОСМОТР")
            print(f"{'=' * 60}")
            print(f"Количество циклов: {'бесконечно' if cycles == 0 else cycles}")
            print(f"Количество видео в цикле: {len(video_urls)}")
            print(f"Использование прокси: {'Да' if self.use_proxy else 'Нет'}")
            if self.use_proxy:
                print(f"Текущий прокси: {self.current_proxy}")
            if max_videos:
                print(f"Максимум видео в цикле: {max_videos}")
            print(f"Время просмотра каждого видео: {watch_time} сек")
            print(f"Задержка между циклами: {delay_between_cycles} сек")
            print(f"{'=' * 60}")

            cycle_count = 0

            while True:
                cycle_count += 1
                self.stats['cycles_completed'] += 1

                print(f"\n{'=' * 60}")
                print(f"ЦИКЛ {cycle_count}")
                print(f"{'=' * 60}")
                self.logger.info(f"Начинаем цикл {cycle_count}")

                # Обрабатываем видео в текущем цикле
                self.process_videos(video_urls, watch_time, shuffle, max_videos)

                # Проверяем условие завершения
                if cycles > 0 and cycle_count >= cycles:
                    self.logger.info(f"Выполнено заданное количество циклов: {cycles}")
                    break

                # Пауза между циклами
                if cycles == 0 or cycle_count < cycles:
                    print(f"\nОжидание перед следующим циклом: {delay_between_cycles} секунд")
                    self.logger.info(f"Пауза перед следующим циклом: {delay_between_cycles} сек")

                    # Отсчет с прогресс-баром
                    for remaining in range(delay_between_cycles, 0, -1):
                        print(f"\rОсталось: {remaining} сек {' ' * 10}", end='')
                        time.sleep(1)
                    print(f"\rОжидание завершено{' ' * 30}")

                    # Перезапускаем драйвер между циклами для чистоты сессии
                    self.logger.info("Перезапуск браузера для нового цикла...")
                    try:
                        if self.driver:
                            self.driver.quit()
                    except:
                        pass

                    # Создаем новый драйвер с новым прокси
                    if self.use_proxy and self.proxy_manager:
                        # Выбираем новый прокси для следующего цикла
                        self.current_proxy = self.proxy_manager.get_random_proxy()
                        if self.current_proxy:
                            self.logger.info(f"Новый прокси для следующего цикла: {self.current_proxy}")
                        else:
                            self.logger.warning("Нет доступных рабочих прокси, перезагружаем список...")
                            self.initialize_proxy()

                    # Создаем новый драйвер
                    if not self.create_driver():
                        self.logger.error("Не удалось создать драйвер для нового цикла")
                        break

            return True

        except KeyboardInterrupt:
            self.logger.info("Циклический просмотр остановлен пользователем")
            return False
        except Exception as e:
            self.logger.error(f"Ошибка в циклическом просмотре: {e}")
            return False

    def run(self, video_urls: Union[str, List[str]], watch_time: int = 30,
            shuffle: bool = False, max_videos: Optional[int] = None,
            cycles: int = 1, delay_between_cycles: int = 10):
        """Основной запуск с поддержкой циклов"""
        try:
            # Информация о режиме
            print(f"\nРежим: {'GUI' if self.gui_mode else 'Headless'}")
            print(f"Инкогнито: {'Да' if self.incognito else 'Нет'}")
            print(f"Прокси: {'Да' if self.use_proxy else 'Нет'}")
            if self.chromedriver_path:
                print(f"ChromeDriver: {self.chromedriver_path}")
            print(f"Циклы: {'бесконечно' if cycles == 0 else cycles}")
            print("=" * 50)

            # Инициализация прокси
            if self.use_proxy:
                print("Инициализация прокси...")
                self.initialize_proxy()

            # Создаем драйвер
            if not self.create_driver():
                return

            # Обрабатываем видео
            if isinstance(video_urls, str):
                video_urls = [video_urls]

            # Запускаем циклы
            if cycles != 1:
                self.run_cycles(video_urls, watch_time, shuffle, max_videos, cycles, delay_between_cycles)
            else:
                # Одиночный запуск (обратная совместимость)
                self.process_videos(video_urls, watch_time, shuffle, max_videos)

            # Итоги
            self.print_summary()

        except KeyboardInterrupt:
            self.logger.info("Остановлено пользователем")
            self.print_summary()
        except Exception as e:
            self.logger.error(f"Критическая ошибка: {e}")
        finally:
            if self.driver:
                self.logger.info("Закрываем браузер")
                try:
                    self.driver.quit()
                except:
                    pass

    def print_summary(self):
        """Итоговая статистика"""
        print("\n" + "=" * 60)
        print("ИТОГИ")
        print("=" * 60)
        print(f"Выполнено циклов: {self.stats['cycles_completed']}")
        print(f"Всего видео: {self.stats['total_videos']}")
        print(f"Успешно: {self.stats['successful_views']}")
        print(f"Ошибки: {self.stats['failed_views']}")
        print(f"Использование прокси: {'Да' if self.use_proxy else 'Нет'}")

        total_sec = self.stats['total_watch_time']
        hours = total_sec // 3600
        minutes = (total_sec % 3600) // 60
        seconds = total_sec % 60

        print(f"Общее время: {hours}ч {minutes}м {seconds}с")
        print(f"Статистика сохранена в {LOG_DIR / 'viewer_stats.json'}")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Циклический просмотр видео на RuTube с поддержкой прокси')

    # Основные аргументы
    parser.add_argument('--urls', nargs='+', help='Ссылки на видео')
    parser.add_argument('--file', type=str, help='Файл со списком видео')
    parser.add_argument('--time', type=int, default=30, help='Время просмотра каждого видео (сек)')

    # Циклы
    parser.add_argument('--cycles', type=int, default=1,
                        help='Количество циклов (0 = бесконечно, 1 = по умолчанию)')
    parser.add_argument('--delay-between-cycles', type=int, default=30,
                        help='Задержка между циклами в секундах (по умолчанию: 30)')

    # Режимы
    parser.add_argument('--gui', action='store_true', default=True,
                        help='С графическим интерфейсом (по умолчанию)')
    parser.add_argument('--no-gui', action='store_false', dest='gui',
                        help='Без графического интерфейса')

    # Прокси
    parser.add_argument('--proxy', action='store_true', help='Использовать прокси')
    parser.add_argument('--no-proxy', action='store_false', dest='proxy',
                        help='Не использовать прокси (по умолчанию)')

    # Дополнительные
    parser.add_argument('--chromedriver', type=str, help='Путь к ChromeDriver')
    parser.add_argument('--incognito', action='store_true', default=True,
                        help='Режим инкогнито')
    parser.add_argument('--no-incognito', action='store_false', dest='incognito',
                        help='Без инкогнито')
    parser.add_argument('--shuffle', action='store_true', help='Перемешать видео в каждом цикле')
    parser.add_argument('--max', type=int, help='Максимум видео в каждом цикле')

    args = parser.parse_args()

    # Создаем глобальный логгер
    global logger
    logger = logging.getLogger(__name__)

    # Загружаем видео
    video_urls = []

    if args.urls:
        video_urls.extend(args.urls)

    viewer = RuTubeViewer(
        gui_mode=args.gui,
        incognito=args.incognito,
        chromedriver_path=args.chromedriver,
        use_proxy=args.proxy if hasattr(args, 'proxy') else False
    )

    if args.file:
        loaded = viewer.load_videos_from_file(args.file)
        video_urls.extend(loaded)

    if not video_urls:
        print("Ошибка: укажите видео через --urls или --file")
        return

    # Проверяем параметр циклов
    if args.cycles < 0:
        print("Ошибка: количество циклов не может быть отрицательным")
        return

    if args.cycles == 0:
        print("\nВНИМАНИЕ: Запущен бесконечный цикл просмотра!")
        print("Для остановки нажмите Ctrl+C\n")

    # Проверяем задержку между циклами
    if args.delay_between_cycles < 0:
        print("Ошибка: задержка между циклами не может быть отрицательной")
        return

    # Запускаем
    viewer.run(
        video_urls=video_urls,
        watch_time=args.time,
        shuffle=args.shuffle,
        max_videos=args.max,
        cycles=args.cycles,
        delay_between_cycles=args.delay_between_cycles
    )


if __name__ == "__main__":
    main()