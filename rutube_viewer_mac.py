import warnings
from urllib3.exceptions import NotOpenSSLWarning

warnings.filterwarnings("ignore", category=NotOpenSSLWarning)

import time
import random
import argparse
import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union
from itertools import cycle as itertools_cycle
from collections import defaultdict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService

# Константы для конфигурации
DEFAULT_WATCH_TIME = 30
DEFAULT_CYCLE_DELAY = 30
LOG_DIR = Path('Logs')
STATS_FILE = LOG_DIR / 'viewer_stats.json'
LOG_FILE = LOG_DIR / 'rutube_viewer.log'

# Глобальные селекторы
COOKIE_SELECTORS = [
    "button[class*='cookie']",
    "button[class*='Cookie']",
    "//button[contains(text(), 'Принять')]",
    "//button[contains(text(), 'Согласен')]",
    "//button[contains(text(), 'Принимаю')]",
    "//button[contains(text(), 'OK')]",
]

POPUP_SELECTORS = [
    "svg.svg-icon--IconClose",
    "button[class*='close']",
    "button[aria-label*='закрыть']",
    "div[class*='modal'] button[class*='close']",
    "//button[contains(text(), '×')]",
]

VIDEO_SELECTORS = [
    "video",
    ".video-js",
    "div[class*='video-player']",
    "#video-player",
]

MUTE_BUTTON_SELECTORS = [
    "button[class*='mute']",
    "button[class*='volume']",
    "button[aria-label*='volume']",
    "button[aria-label*='mute']",
    "button[aria-label*='звук']",
    "button[aria-label*='громкость']",
    "button[title*='mute']",
    "button[title*='volume']",
    "button[title*='звук']",
    "button[title*='громкость']",
    ".volume-control",
    ".mute-button",
    "[data-testid*='mute']",
    "[data-testid*='volume']",
]

PLAY_BUTTON_SELECTORS = [
    "button[class*='play']",
    "button[title*='play']",
    "button[aria-label*='play']",
    "button[aria-label*='воспроизвести']",
    ".play-button",
    "[data-testid*='play']",
]


class RuTubeViewer:
    """Просмотрщик видео RuTube для macOS"""

    def __init__(self, gui_mode: bool = True, incognito: bool = True,
                 chromedriver_path: Optional[str] = None, mute_audio: bool = True):
        self._setup_directories()
        self._setup_logging()

        self.gui_mode = gui_mode
        self.incognito = incognito
        self.mute_audio = mute_audio
        self.chromedriver_path = self._resolve_chromedriver_path(chromedriver_path)
        self.driver = None

        self._init_stats()

    def _setup_directories(self):
        """Создание необходимых директорий"""
        LOG_DIR.mkdir(exist_ok=True)

    def _setup_logging(self):
        """Настройка логирования"""
        self.logger = logging.getLogger(__name__)

        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)

            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )

            file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
            file_handler.setFormatter(formatter)

            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)

            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def _init_stats(self):
        """Инициализация статистики"""
        self.stats = defaultdict(int, {
            'total_videos': 0,
            'successful_views': 0,
            'failed_views': 0,
            'total_watch_time': 0,
            'cycles_completed': 0,
            'muted_videos': 0,
        })

        self.videos_history = []
        self.settings = {
            'gui_mode': self.gui_mode,
            'incognito': self.incognito,
            'mute_audio': self.mute_audio,
            'start_time': datetime.now().isoformat()
        }

    def _resolve_chromedriver_path(self, custom_path: Optional[str]) -> Optional[str]:
        """Определение пути к ChromeDriver для macOS"""
        # 1. Пользовательский путь
        if custom_path:
            if os.path.exists(custom_path):
                self.logger.info(f"Используется указанный ChromeDriver: {custom_path}")
                return custom_path
            else:
                self.logger.warning(f"Указанный путь не существует: {custom_path}")

        # 2. Стандартные пути для macOS
        paths_to_check = [
            # В папке проекта
            Path.cwd() / "selenium-server" / "chromedriver",
            # Homebrew установки
            Path("/usr/local/bin/chromedriver"),
            Path("/opt/homebrew/bin/chromedriver"),
            # WebDriver Manager кэш
            Path.home() / ".wdm" / "drivers" / "chromedriver" / "mac64" / "chromedriver",
            # Альтернативные пути
            Path.cwd() / "chromedriver",
            Path.home() / "chromedriver",
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

        # 4. Ищем в PATH
        import shutil
        system_path = shutil.which("chromedriver")
        if system_path:
            self.logger.info(f"Найден ChromeDriver в PATH: {system_path}")
            return system_path

        self.logger.warning("ChromeDriver не найден локально. Будет использован webdriver-manager.")
        return None

    def _create_chrome_options(self) -> Options:
        """Создание настроек Chrome для macOS"""
        options = Options()

        # Основные настройки
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        if self.incognito:
            options.add_argument("--incognito")

        if not self.gui_mode:
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
        else:
            options.add_argument("--start-maximized")

        # Дополнительные опции
        options.add_argument("--disable-notifications")
        options.add_argument("--lang=ru-RU")
        options.add_argument("--disable-popup-blocking")
        options.add_argument(
            f'user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        return options

    def create_driver(self) -> bool:
        """Создание драйвера"""
        try:
            self.logger.info("Создание Chrome драйвера...")

            options = self._create_chrome_options()

            # Проверяем, есть ли локальный chromedriver
            if self.chromedriver_path and os.path.exists(self.chromedriver_path):
                self.logger.info(f"Используем локальный chromedriver: {self.chromedriver_path}")

                # Убедимся, что файл исполняемый
                if not os.access(self.chromedriver_path, os.X_OK):
                    self.logger.info("Устанавливаем права на выполнение...")
                    os.chmod(self.chromedriver_path, 0o755)

                service = ChromeService(executable_path=self.chromedriver_path)
            else:
                self.logger.info("Используем webdriver-manager...")
                service = ChromeService(ChromeDriverManager().install())

            self.logger.info("Инициализируем WebDriver...")
            self.driver = webdriver.Chrome(service=service, options=options)

            # Устанавливаем размер окна
            if self.gui_mode:
                self.driver.maximize_window()
            else:
                self.driver.set_window_size(1920, 1080)

            self.logger.info("Драйвер успешно создан!")
            return True

        except Exception as e:
            self.logger.error(f"Ошибка при создании драйвера: {e}")
            return False

    def load_videos_from_file(self, filepath: str) -> List[str]:
        """Загрузка видео из файла"""
        if not os.path.exists(filepath):
            self.logger.error(f"Файл не найден: {filepath}")
            return []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

            rutube_urls = [url for url in urls if "rutube" in url.lower()]
            self.logger.info(f"Загружено {len(rutube_urls)} видео из {filepath}")
            return rutube_urls

        except Exception as e:
            self.logger.error(f"Ошибка загрузки файла: {e}")
            return []

    def watch_video(self, video_url: str, watch_time: int = DEFAULT_WATCH_TIME) -> bool:
        """Просмотр видео"""
        try:
            self.logger.info(f"Начинаем просмотр: {video_url}")

            self.driver.get(video_url)
            time.sleep(3)  # Ждем загрузки

            # Пытаемся найти и запустить видео
            try:
                video = self.driver.find_element(By.TAG_NAME, "video")
                # Запускаем видео
                self.driver.execute_script("arguments[0].play();", video)

                # Отключаем звук если нужно
                if self.mute_audio:
                    self.driver.execute_script("arguments[0].muted = true;", video)
                    self.logger.info("Звук отключен")
            except:
                self.logger.warning("Не удалось найти видео элемент, продолжаем...")

            # Имитация просмотра
            self.logger.info(f"Смотрим видео {watch_time} секунд...")
            time.sleep(watch_time)

            self.logger.info("Просмотр завершен")
            return True

        except Exception as e:
            self.logger.error(f"Ошибка при просмотре: {e}")
            return False

    def run(self, video_urls: List[str], watch_time: int = DEFAULT_WATCH_TIME,
            shuffle: bool = False, max_videos: Optional[int] = None,
            cycles: int = 1, delay_between_cycles: int = DEFAULT_CYCLE_DELAY):
        """Основной запуск"""
        try:
            print(f"\n{'=' * 50}")
            print("ЗАПУСК ПРОСМОТРА RUTUBE")
            print(f"{'=' * 50}")
            print(f"Видео: {len(video_urls)}")
            print(f"Время просмотра: {watch_time} сек")
            print(f"Циклы: {cycles}")
            print(f"{'=' * 50}\n")

            if not self.create_driver():
                print("Ошибка: Не удалось создать драйвер!")
                return

            for cycle in range(cycles):
                if cycles > 1:
                    print(f"\nЦИКЛ {cycle + 1} из {cycles}")

                if shuffle:
                    random.shuffle(video_urls)

                videos_to_watch = video_urls[:max_videos] if max_videos else video_urls

                for i, url in enumerate(videos_to_watch, 1):
                    print(f"\n[{i}/{len(videos_to_watch)}] {url}")

                    success = self.watch_video(url, watch_time)

                    if i < len(videos_to_watch):
                        pause = random.randint(2, 5)
                        print(f"Пауза {pause} сек...")
                        time.sleep(pause)

                if cycle + 1 < cycles:
                    print(f"\nПауза между циклами: {delay_between_cycles} сек...")
                    time.sleep(delay_between_cycles)

            print(f"\n{'=' * 50}")
            print("ПРОСМОТР ЗАВЕРШЕН!")
            print(f"{'=' * 50}")

        except KeyboardInterrupt:
            print("\nОстановлено пользователем")
        except Exception as e:
            print(f"\nОшибка: {e}")
        finally:
            if self.driver:
                self.driver.quit()


def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='Просмотр видео RuTube')
    parser.add_argument('--file', help='Файл со списком видео')
    parser.add_argument('--urls', nargs='+', help='Ссылки на видео')
    parser.add_argument('--time', type=int, default=DEFAULT_WATCH_TIME, help='Время просмотра (сек)')
    parser.add_argument('--shuffle', action='store_true', help='Перемешать видео')
    parser.add_argument('--max', type=int, help='Максимум видео в цикле')
    parser.add_argument('--cycles', type=int, default=1, help='Количество циклов')
    parser.add_argument('--delay-between-cycles', type=int, default=DEFAULT_CYCLE_DELAY, help='Задержка между циклами')
    parser.add_argument('--no-gui', action='store_true', help='Без графического интерфейса')
    parser.add_argument('--chromedriver', help='Путь к ChromeDriver')
    parser.add_argument('--no-mute', action='store_true', help='Не отключать звук')

    args = parser.parse_args()

    # Загружаем видео
    video_urls = []

    if args.urls:
        video_urls.extend(args.urls)

    if args.file:
        temp_viewer = RuTubeViewer()
        loaded = temp_viewer.load_videos_from_file(args.file)
        video_urls.extend(loaded)

    if not video_urls:
        print("Ошибка: нет видео для просмотра")
        return

    # Создаем и запускаем просмотрщик
    viewer = RuTubeViewer(
        gui_mode=not args.no_gui,
        chromedriver_path=args.chromedriver,
        mute_audio=not args.no_mute
    )

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