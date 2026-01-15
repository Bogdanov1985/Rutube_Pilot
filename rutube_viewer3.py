import time
import random
import argparse
import json
import os
import sys
import logging
import threading
import subprocess
import tempfile
import shutil
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union, Dict, Any, Tuple
from itertools import cycle as itertools_cycle
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

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
DEFAULT_MAX_SESSIONS = 3  # Максимальное количество одновременных сессий
LOG_DIR = Path('Logs')
STATS_FILE = LOG_DIR / 'viewer_stats.json'
LOG_FILE = LOG_DIR / 'rutube_viewer.log'

# Глобальные селекторы для переиспользования
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
    "button[aria-label*='Выключить звук']",
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


class TimeParser:
    """Класс для парсинга времени с поддержкой интервалов"""

    @staticmethod
    def parse_time_input(time_input: str, default_value: int = DEFAULT_WATCH_TIME) -> Union[int, Tuple[int, int]]:
        """
        Парсит входную строку времени.

        Форматы:
        - "30" -> фиксированное 30 секунд
        - "30-60" -> случайное между 30 и 60 секунд (включительно)
        - "30:60" -> случайное между 30 и 60 секунд (включительно)

        Возвращает:
        - int: фиксированное время
        - tuple: (min_time, max_time) для случайного выбора
        """
        if not time_input:
            return default_value

        # Пробуем разделить по '-' или ':'
        separators = ['-', ':']
        for sep in separators:
            if sep in time_input:
                parts = time_input.split(sep)
                if len(parts) == 2:
                    try:
                        min_time = int(parts[0].strip())
                        max_time = int(parts[1].strip())

                        # Проверка корректности
                        if min_time < 0:
                            raise ValueError("Минимальное время должно быть >= 0")
                        if max_time < min_time:
                            raise ValueError(
                                f"Максимальное время ({max_time}) должно быть >= минимального ({min_time})")

                        return (min_time, max_time)
                    except ValueError as e:
                        raise ValueError(f"Некорректный формат интервала времени: {time_input}. Ошибка: {e}")

        # Если не интервал, пробуем как число
        try:
            time_value = int(time_input)
            if time_value < 0:
                raise ValueError("Время должно быть >= 0")
            return time_value
        except ValueError:
            raise ValueError(f"Некорректный формат времени: {time_input}. Используйте число (30) или интервал (30-60)")

    @staticmethod
    def get_random_time(time_spec: Union[int, Tuple[int, int]]) -> int:
        """
        Возвращает случайное время на основе спецификации.

        Аргументы:
        - time_spec: int (фиксированное время) или tuple (min, max)

        Возвращает:
        - int: время в секундах
        """
        if isinstance(time_spec, tuple):
            min_time, max_time = time_spec
            if min_time == max_time:
                return min_time
            return random.randint(min_time, max_time)
        else:
            return time_spec

    @staticmethod
    def format_time_spec(time_spec: Union[int, Tuple[int, int]], label: str = "сек") -> str:
        """Форматирует спецификацию времени для отображения"""
        if isinstance(time_spec, tuple):
            min_time, max_time = time_spec
            if min_time == max_time:
                return f"{min_time} {label} (фиксированно)"
            return f"{min_time}-{max_time} {label} (случайно)"
        else:
            return f"{time_spec} {label} (фиксированно)"

    @staticmethod
    def parse_and_get_random(time_input: str, default_value: int = DEFAULT_WATCH_TIME) -> int:
        """Парсит строку времени и возвращает случайное значение"""
        time_spec = TimeParser.parse_time_input(time_input, default_value)
        return TimeParser.get_random_time(time_spec)


class ChromeDriverResolver:
    """Класс для разрешения проблем с ChromeDriver"""

    @staticmethod
    def get_chrome_version() -> Optional[str]:
        """Получает версию установленного Chrome"""
        try:
            if sys.platform == "win32":
                # Для Windows
                import winreg
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
                    version, _ = winreg.QueryValueEx(key, "version")
                    winreg.CloseKey(key)
                    return version.split('.')[0]  # Возвращаем мажорную версию
                except:
                    try:
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Google\Chrome\BLBeacon")
                        version, _ = winreg.QueryValueEx(key, "version")
                        winreg.CloseKey(key)
                        return version.split('.')[0]
                    except:
                        pass
            elif sys.platform == "darwin":
                # Для macOS
                result = subprocess.run(
                    ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--version'],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    return result.stdout.strip().split()[-1].split('.')[0]
            else:
                # Для Linux
                result = subprocess.run(['google-chrome', '--version'], capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip().split()[-1].split('.')[0]
        except Exception as e:
            logging.getLogger(__name__).debug(f"Не удалось получить версию Chrome: {e}")
        return None

    @staticmethod
    def get_system_architecture() -> str:
        """Определяет архитектуру системы"""
        if sys.platform == "win32":
            # Проверяем, является ли система 64-битной
            import struct
            return "64" if struct.calcsize("P") * 8 == 64 else "32"
        else:
            import platform
            arch = platform.machine()
            if '64' in arch:
                return "64"
            return "32"

    @staticmethod
    def download_chromedriver() -> Optional[str]:
        """Загружает ChromeDriver с помощью webdriver-manager"""
        try:
            logger = logging.getLogger(__name__)
            logger.info("Загрузка ChromeDriver через webdriver-manager...")

            # Загружаем ChromeDriver
            driver_path = ChromeDriverManager().install()
            logger.info(f"ChromeDriver загружен: {driver_path}")
            return driver_path
        except Exception as e:
            logging.getLogger(__name__).error(f"Ошибка загрузки ChromeDriver: {e}")
            return None

    @staticmethod
    def check_chromedriver_compatibility(driver_path: str) -> bool:
        """Проверяет совместимость ChromeDriver"""
        try:
            # Пробуем запустить chromedriver
            if sys.platform == "win32":
                cmd = [driver_path, "--version"]
            else:
                cmd = [driver_path, "--version"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False


class SessionManager:
    """Менеджер сессий браузера для управления несколькими инкогнито сессиями"""

    def __init__(self, max_sessions: int = DEFAULT_MAX_SESSIONS, gui_mode: bool = True,
                 stealth_mode: bool = True, mute_audio: bool = True,
                 chromedriver_path: Optional[str] = None):
        self.max_sessions = max_sessions
        self.gui_mode = gui_mode
        self.stealth_mode = stealth_mode
        self.mute_audio = mute_audio
        self.session_pool = []
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self.chromedriver_path = None

        # Решаем проблему с ChromeDriver
        self._resolve_chromedriver(chromedriver_path)

    def _resolve_chromedriver(self, custom_path: Optional[str] = None):
        """Разрешает проблемы с ChromeDriver с учетом пользовательского пути"""
        # 1. Проверяем пользовательский путь
        if custom_path and os.path.exists(custom_path):
            self.chromedriver_path = custom_path
            self.logger.info(f"Используется указанный ChromeDriver: {custom_path}")
            return True

        # 2. Проверяем каталог selenium-server
        paths_to_check = [
            Path(__file__).parent / "selenium-server" / "chromedriver.exe",
            Path(__file__).parent / "selenium-server" / "chromedriver",
            Path.cwd() / "selenium-server" / "chromedriver.exe",
            Path.cwd() / "selenium-server" / "chromedriver",
        ]

        for path in paths_to_check:
            if path.exists():
                self.chromedriver_path = str(path)
                self.logger.info(f"Найден ChromeDriver в selenium-server: {path}")
                return True

        # 3. Проверяем переменную окружения
        env_path = os.environ.get('CHROMEDRIVER_PATH')
        if env_path and os.path.exists(env_path):
            self.chromedriver_path = env_path
            self.logger.info(f"Найден ChromeDriver в переменной окружения: {env_path}")
            return True

        # 4. Проверяем системный PATH
        system_path = shutil.which("chromedriver") or shutil.which("chromedriver.exe")
        if system_path:
            self.chromedriver_path = system_path
            self.logger.info(f"Найден ChromeDriver в PATH: {system_path}")
            return True

        # 5. Загружаем через webdriver-manager
        try:
            self.logger.info("ChromeDriver не найден в стандартных местах. Загрузка через webdriver-manager...")
            downloaded_path = ChromeDriverResolver.download_chromedriver()
            if downloaded_path:
                self.chromedriver_path = downloaded_path
                self.logger.info(f"ChromeDriver загружен: {downloaded_path}")
                return True
        except Exception as e:
            self.logger.error(f"Ошибка загрузки ChromeDriver: {e}")

        # 6. Проверяем наличие в текущей директории
        local_paths = [
            Path.cwd() / "chromedriver.exe",
            Path.cwd() / "chromedriver",
            Path(__file__).parent / "chromedriver.exe",
            Path(__file__).parent / "chromedriver",
        ]

        for path in local_paths:
            if path.exists():
                self.chromedriver_path = str(path)
                self.logger.info(f"Найден ChromeDriver в локальной директории: {path}")
                return True

        self.logger.error("ChromeDriver не найден ни в одном из стандартных мест!")
        self.logger.info("Пожалуйста, выполните одно из следующих действий:")
        self.logger.info("1. Укажите путь через --chromedriver аргумент")
        self.logger.info("2. Поместите chromedriver.exe в папку selenium-server/")
        self.logger.info("3. Установите ChromeDriver в PATH")
        self.logger.info("4. Установите переменную окружения CHROMEDRIVER_PATH")

        return False

    def create_new_session(self) -> Optional[webdriver.Chrome]:
        """Создает новую сессию браузера в режиме инкогнито"""
        try:
            options = self._create_chrome_options()

            # Создаем временную директорию для профиля
            temp_dir = tempfile.mkdtemp(prefix="chrome_profile_")
            options.add_argument(f"--user-data-dir={temp_dir}")

            # Гарантируем инкогнито режим
            options.add_argument("--incognito")

            # Добавляем опции для обхода блокировок
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            options.add_experimental_option('useAutomationExtension', False)

            # Случайный User-Agent
            user_agents = self._get_realistic_user_agents()
            selected_ua = random.choice(user_agents)
            options.add_argument(f'user-agent={selected_ua}')

            # Создаем драйвер с использованием найденного пути
            if self.chromedriver_path and os.path.exists(self.chromedriver_path):
                self.logger.debug(f"Создаем сессию с ChromeDriver: {self.chromedriver_path}")
                service = ChromeService(executable_path=self.chromedriver_path)
                driver = webdriver.Chrome(service=service, options=options)
            else:
                # Используем webdriver-manager как запасной вариант
                self.logger.debug("Используем webdriver-manager для создания драйвера")
                service = ChromeService(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)

            # Применяем stealth техники
            self._apply_stealth_techniques(driver)

            # Настраиваем размер окна
            self._setup_window(driver)

            # Устанавливаем таймауты
            driver.set_page_load_timeout(30)
            driver.set_script_timeout(20)
            driver.implicitly_wait(5)

            self.logger.debug(f"Создана новая сессия с User-Agent: {selected_ua[:50]}...")
            return driver

        except Exception as e:
            self.logger.error(f"Ошибка создания сессии: {str(e)}")

            # Пытаемся определить точную причину ошибки
            if "WinError 193" in str(e):
                self.logger.error("Проблема с архитектурой ChromeDriver (32-bit vs 64-bit).")
                self.logger.error("Убедитесь, что скачали правильную версию (win32 или win64).")
            elif "executable needs to be in PATH" in str(e):
                self.logger.error("ChromeDriver не найден. Укажите правильный путь.")

            return None

    def _create_chrome_options(self) -> Options:
        """Создание настроек Chrome"""
        options = Options()

        # Базовые опции
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        if not self.gui_mode:
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
        else:
            options.add_argument("--start-maximized")
            options.add_argument("--disable-infobars")

        # Дополнительные опции для предотвращения детектирования
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        options.add_argument("--disable-site-isolation-trials")

        # Языковые настройки
        options.add_argument("--lang=ru-RU")
        options.add_argument("--accept-lang=ru-RU,ru")

        # Оптимизация
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-renderer-backgrounding")

        # Отключение функций, которые могут мешать
        options.add_argument("--disable-component-update")
        options.add_argument("--disable-domain-reliability")
        options.add_argument("--disable-sync")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--no-first-run")

        # Настройки профиля
        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.geolocation": 2,
            "intl.accept_languages": "ru-RU,ru",
            "excludeSwitches": ["enable-automation"],
            "useAutomationExtension": False
        }
        options.add_experimental_option("prefs", prefs)

        return options

    def _get_realistic_user_agents(self) -> List[str]:
        """Возвращает список реалистичных User-Agent строк"""
        return [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]

    def _apply_stealth_techniques(self, driver):
        """Применяет stealth техники к драйверу"""
        if not self.stealth_mode:
            return

        try:
            # Основные скрипты для скрытия автоматизации
            scripts = [
                # Скрытие webdriver флага
                """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                """,

                # Переопределение chrome
                """
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                """,

                # Скрытие automation свойств
                """
                Object.defineProperty(navigator, 'automation', {
                    get: () => undefined
                });
                """
            ]

            for script in scripts:
                try:
                    driver.execute_script(script)
                except:
                    pass

        except Exception as e:
            self.logger.debug(f"Ошибка применения stealth техник: {e}")

    def _setup_window(self, driver):
        """Настройка размера окна браузера"""
        try:
            if not self.gui_mode:
                driver.set_window_size(1920, 1080)
            else:
                resolutions = [(1920, 1080), (1366, 768), (1536, 864)]
                width, height = random.choice(resolutions)
                driver.set_window_size(width, height)

                # Случайная позиция
                if random.random() > 0.5:
                    driver.set_window_position(
                        random.randint(0, 100),
                        random.randint(0, 100)
                    )
        except Exception as e:
            self.logger.debug(f"Не удалось настроить окно: {e}")

    def get_session(self) -> Optional[webdriver.Chrome]:
        """Получение сессии из пула или создание новой"""
        with self.lock:
            # Проверяем количество активных сессий
            if len(self.session_pool) >= self.max_sessions:
                # Ждем, пока не освободится место
                self.logger.debug(f"Достигнут лимит сессий ({self.max_sessions}), ждем...")
                time.sleep(random.uniform(1, 3))

                # Пробуем получить сессию из пула
                for session in self.session_pool:
                    try:
                        # Проверяем, что сессия жива
                        session.current_url
                        return session
                    except:
                        continue

            # Создаем новую сессию
            return self.create_new_session()

    def return_session(self, session: webdriver.Chrome):
        """Возвращает сессию в пул с автоматическим закрытием"""
        if not session:
            return

        with self.lock:
            try:
                # Закрываем сессию вместо возврата в пул
                # Это обеспечивает закрытие окна после просмотра
                try:
                    # Останавливаем видео если оно играет
                    session.execute_script("""
                        var videos = document.querySelectorAll('video');
                        videos.forEach(function(video) {
                            video.pause();
                        });
                    """)
                except:
                    pass

                # Закрываем окно браузера
                session.quit()
                self.logger.debug("Окно браузера закрыто после просмотра")

                # Уменьшаем размер пула
                if session in self.session_pool:
                    self.session_pool.remove(session)

            except Exception as e:
                self.logger.debug(f"Ошибка при закрытии сессии: {e}")
                try:
                    session.quit()
                except:
                    pass

    def close_all_sessions(self):
        """Закрывает все сессии"""
        with self.lock:
            for session in self.session_pool:
                try:
                    session.quit()
                except:
                    pass
            self.session_pool.clear()


class VideoViewer:
    """Класс для просмотра видео в отдельной сессии"""

    def __init__(self, session_manager: SessionManager, logger: logging.Logger):
        self.session_manager = session_manager
        self.logger = logger
        self.driver = None

    def watch_video(self, video_url: str, watch_time_spec: Union[int, Tuple[int, int]]) -> bool:
        """Просмотр видео в отдельной сессии с автоматическим закрытием окна"""
        max_retries = 2
        retry_count = 0

        # Получаем случайное время просмотра
        watch_time = TimeParser.get_random_time(watch_time_spec)

        while retry_count <= max_retries:
            try:
                # Получаем сессию
                self.driver = self.session_manager.get_session()
                if not self.driver:
                    self.logger.error(f"Не удалось получить сессию для видео: {video_url}")
                    retry_count += 1
                    time.sleep(2)
                    continue

                self.logger.info(f"Начинаем просмотр: {video_url} ({watch_time} сек)")

                # Случайная задержка перед переходом
                time.sleep(random.uniform(0.5, 1.5))

                # Переход на страницу
                self.driver.get(video_url)

                # Ожидание загрузки
                time.sleep(random.uniform(2, 3))

                # Обработка всплывающих окон
                self._handle_popups()

                # Поиск и запуск видео
                video_element = self._find_video_element()
                if video_element:
                    self._start_video_playback(video_element)
                    self._mute_video(video_element)

                # Имитация просмотра с автоматическим закрытием по таймеру
                success = self._simulate_watching_with_auto_close(watch_time)

                if success:
                    self.logger.info(f"Завершен просмотр: {video_url} ({watch_time} сек)")
                    return True
                else:
                    self.logger.warning(f"Проблемы при просмотре: {video_url}")
                    retry_count += 1

            except TimeoutException:
                self.logger.warning(f"Таймаут при просмотре: {video_url}")
                retry_count += 1
            except Exception as e:
                self.logger.error(f"Ошибка при просмотре видео {video_url}: {str(e)}")
                retry_count += 1
            finally:
                # ВСЕГДА закрываем окно браузера после просмотра
                self._close_browser_window()

            # Задержка перед повторной попыткой
            if retry_count <= max_retries:
                self.logger.debug(f"Повторная попытка {retry_count}/{max_retries}")
                time.sleep(random.uniform(3, 5))

        self.logger.error(f"Не удалось просмотреть видео после {max_retries} попыток: {video_url}")
        return False

    def _close_browser_window(self):
        """Закрывает окно браузера"""
        if self.driver:
            try:
                # Останавливаем все видео
                self.driver.execute_script("""
                    var videos = document.querySelectorAll('video');
                    videos.forEach(function(video) {
                        video.pause();
                        video.currentTime = 0;
                    });
                """)
            except:
                pass

            # Возвращаем сессию (которая автоматически ее закроет)
            self.session_manager.return_session(self.driver)
            self.driver = None

            # Небольшая задержка для уверенности, что окно закрыто
            time.sleep(0.5)

    def _handle_popups(self):
        """Обработка всплывающих окон и cookie"""
        try:
            # Небольшая задержка для появления попапов
            time.sleep(1)

            # Попытка закрыть cookie уведомление
            for selector in COOKIE_SELECTORS:
                try:
                    is_xpath = selector.startswith("//")
                    by = By.XPATH if is_xpath else By.CSS_SELECTOR
                    elements = self.driver.find_elements(by, selector)
                    for element in elements[:3]:  # Проверяем первые 3 элемента
                        try:
                            if element.is_displayed() and element.is_enabled():
                                element.click()
                                self.logger.debug("Закрыто cookie уведомление")
                                time.sleep(0.5)
                                break
                        except:
                            try:
                                # Пробуем клик через JavaScript
                                self.driver.execute_script("arguments[0].click();", element)
                                self.logger.debug("Закрыто cookie уведомление (через JS)")
                                time.sleep(0.5)
                                break
                            except:
                                continue
                except:
                    continue

            # Закрытие попапов
            time.sleep(0.5)
            for selector in POPUP_SELECTORS:
                try:
                    is_xpath = selector.startswith("//")
                    by = By.XPATH if is_xpath else By.CSS_SELECTOR
                    elements = self.driver.find_elements(by, selector)
                    for element in elements[:3]:
                        try:
                            if element.is_displayed() and element.is_enabled():
                                element.click()
                                self.logger.debug("Закрыт попап")
                                time.sleep(0.3)
                                break
                        except:
                            try:
                                self.driver.execute_script("arguments[0].click();", element)
                                self.logger.debug("Закрыт попап (через JS)")
                                time.sleep(0.3)
                                break
                            except:
                                continue
                except:
                    continue

        except Exception as e:
            self.logger.debug(f"Ошибка при обработке всплывающих окон: {e}")

    def _find_video_element(self):
        """Поиск видео элемента"""
        for selector in VIDEO_SELECTORS:
            try:
                if selector == "video":
                    # Ищем все video элементы
                    elements = self.driver.find_elements(By.TAG_NAME, "video")
                    if elements:
                        return elements[0]  # Возвращаем первый найденный
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        return elements[0]
            except:
                continue

        # Дополнительный поиск через JavaScript
        try:
            video_elements = self.driver.execute_script("""
                return document.querySelectorAll('video');
            """)
            if video_elements:
                return video_elements[0]
        except:
            pass

        return None

    def _start_video_playback(self, video_element):
        """Запуск воспроизведения видео"""
        attempts = [
            # Способ 1: JavaScript play
            lambda: self.driver.execute_script("arguments[0].play();", video_element),
            # Способ 2: Клик по видео
            lambda: video_element.click(),
            # Способ 3: Поиск кнопки play
            lambda: self._click_play_button(),
        ]

        for i, attempt in enumerate(attempts, 1):
            try:
                attempt()
                time.sleep(1)
                self.logger.debug(f"Воспроизведение запущено (способ {i})")
                return True
            except Exception as e:
                self.logger.debug(f"Способ {i} не сработал: {e}")
                continue

        # Последняя попытка: клик в центр видео
        try:
            self.driver.execute_script("""
                var video = arguments[0];
                var rect = video.getBoundingClientRect();
                var x = rect.left + rect.width / 2;
                var y = rect.top + rect.height / 2;

                var clickEvent = new MouseEvent('click', {
                    view: window,
                    bubbles: true,
                    cancelable: true,
                    clientX: x,
                    clientY: y
                });
                video.dispatchEvent(clickEvent);
            """, video_element)
            time.sleep(1)
            self.logger.debug("Воспроизведение запущено (клик в центр)")
            return True
        except:
            pass

        return False

    def _click_play_button(self):
        """Поиск и нажатие кнопки play"""
        for selector in PLAY_BUTTON_SELECTORS:
            try:
                buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for btn in buttons:
                    try:
                        if btn.is_displayed() and btn.is_enabled():
                            btn.click()
                            return True
                    except:
                        try:
                            self.driver.execute_script("arguments[0].click();", btn)
                            return True
                        except:
                            continue
            except:
                continue
        return False

    def _mute_video(self, video_element):
        """Отключение звука видео"""
        if not video_element:
            return False

        try:
            # Способ 1: JavaScript
            self.driver.execute_script("arguments[0].muted = true;", video_element)
            self.driver.execute_script("arguments[0].volume = 0;", video_element)

            # Способ 2: Поиск кнопки mute
            for selector in MUTE_BUTTON_SELECTORS:
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in buttons:
                        try:
                            if btn.is_displayed() and btn.is_enabled():
                                btn.click()
                                break
                        except:
                            continue
                except:
                    continue

            return True
        except:
            return False

    def _simulate_watching_with_auto_close(self, watch_time: int) -> bool:
        """Имитация просмотра видео с автоматическим закрытием окна по таймеру"""
        try:
            start_time = time.time()
            actions = 0

            while time.time() - start_time < watch_time:
                elapsed = time.time() - start_time

                # Случайные действия пользователя
                if actions < 3 and elapsed > 5 and random.random() < 0.2:
                    action_type = random.choice(['scroll', 'move_mouse', 'pause'])

                    if action_type == 'scroll':
                        scroll_pos = random.randint(100, 300)
                        direction = random.choice([-1, 1])
                        self.driver.execute_script(f"window.scrollBy(0, {direction * scroll_pos});")
                        actions += 1

                    elif action_type == 'move_mouse':
                        # Имитация движения мыши
                        scroll_x = random.randint(10, 100)
                        scroll_y = random.randint(10, 100)
                        self.driver.execute_script(f"""
                            var event = new MouseEvent('mousemove', {{
                                clientX: {scroll_x},
                                clientY: {scroll_y},
                                bubbles: true
                            }});
                            document.dispatchEvent(event);
                        """)
                        actions += 1

                    elif action_type == 'pause':
                        pause_time = random.uniform(1, 3)
                        time.sleep(pause_time)
                        actions += 1

                # Случайная задержка между проверками
                sleep_time = random.uniform(1.0, 2.0)
                time.sleep(min(sleep_time, watch_time - (time.time() - start_time)))

            # Время вышло - закрываем окно
            self.logger.debug(f"Время просмотра ({watch_time} сек) истекло, закрываем окно")
            return True

        except Exception as e:
            self.logger.debug(f"Ошибка при имитации просмотра: {e}")
            return False


class RuTubeViewer:
    """Оптимизированный просмотрщик видео RuTube с управлением сессиями"""

    def __init__(self, gui_mode: bool = True, incognito: bool = True,
                 max_sessions: int = DEFAULT_MAX_SESSIONS,
                 mute_audio: bool = True, stealth_mode: bool = True,
                 chromedriver_path: Optional[str] = None):
        self._setup_directories()
        self._setup_logging()

        self.gui_mode = gui_mode
        self.incognito = incognito
        self.max_sessions = max_sessions
        self.mute_audio = mute_audio
        self.stealth_mode = stealth_mode
        self.chromedriver_path = chromedriver_path

        # Проверяем наличие Chrome
        self._check_chrome_installation()

        # Инициализация менеджера сессий
        self.session_manager = SessionManager(
            max_sessions=max_sessions,
            gui_mode=gui_mode,
            stealth_mode=stealth_mode,
            mute_audio=mute_audio,
            chromedriver_path=chromedriver_path
        )

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

    def _check_chrome_installation(self):
        """Проверка установки Chrome"""
        try:
            version = ChromeDriverResolver.get_chrome_version()
            if version:
                self.logger.info(f"Найдена версия Chrome: {version}")
            else:
                self.logger.warning("Chrome не найден. Установите Google Chrome.")

            arch = ChromeDriverResolver.get_system_architecture()
            self.logger.info(f"Архитектура системы: {arch}-bit")

            if self.chromedriver_path:
                self.logger.info(f"Указан путь к ChromeDriver: {self.chromedriver_path}")
        except Exception as e:
            self.logger.debug(f"Ошибка при проверке Chrome: {e}")

    def _init_stats(self):
        """Инициализация статистики"""
        self.stats = defaultdict(int, {
            'total_videos': 0,
            'successful_views': 0,
            'failed_views': 0,
            'total_watch_time': 0,
            'cycles_completed': 0,
            'sessions_created': 0,
            'random_time_used': False,
            'random_delay_used': False,
        })

        self.videos_history = []
        self.cycle_delays = []  # История задержек между циклами

    def load_videos_from_file(self, filepath: str) -> List[str]:
        """Загрузка видео из файла"""
        if not os.path.exists(filepath):
            self.logger.error(f"Файл не найден: {filepath}")
            return []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

            rutube_urls = [url for url in urls if "rutube" in url.lower()]

            if len(rutube_urls) < len(urls):
                self.logger.warning(f"Отфильтровано {len(urls) - len(rutube_urls)} не-RuTube ссылок")

            self.logger.info(f"Загружено {len(rutube_urls)} видео из {filepath}")
            return rutube_urls

        except Exception as e:
            self.logger.error(f"Ошибка загрузки файла: {e}")
            return []

    def _update_stats(self, video_url: str, success: bool, watch_time: int):
        """Обновление статистики"""
        self.stats['total_videos'] += 1

        if success:
            self.stats['successful_views'] += 1
            self.stats['total_watch_time'] += watch_time
        else:
            self.stats['failed_views'] += 1

        self.videos_history.append({
            'url': video_url,
            'timestamp': datetime.now().isoformat(),
            'watch_time': watch_time,
            'success': success,
            'muted': self.mute_audio,
        })

    def save_stats(self):
        """Сохранение статистики"""
        try:
            data = {
                'stats': dict(self.stats),
                'videos_history': self.videos_history[-100:],
                'cycle_delays': self.cycle_delays[-20:],  # Сохраняем последние 20 задержек
                'settings': {
                    'gui_mode': self.gui_mode,
                    'incognito': self.incognito,
                    'max_sessions': self.max_sessions,
                    'mute_audio': self.mute_audio,
                    'stealth_mode': self.stealth_mode,
                    'chromedriver_path': self.chromedriver_path,
                    'start_time': datetime.now().isoformat()
                }
            }

            with open(STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        except Exception as e:
            self.logger.error(f"Ошибка сохранения статистики: {e}")

    def process_videos_parallel(self, video_urls: List[str], watch_time_spec: Union[int, Tuple[int, int]],
                                shuffle: bool = False, max_videos: Optional[int] = None):
        """Параллельная обработка видео с использованием нескольких сессий"""
        if not video_urls:
            self.logger.warning("Нет видео для обработки")
            return

        if shuffle:
            random.shuffle(video_urls)
            self.logger.info("Список перемешан")

        if max_videos:
            video_urls = video_urls[:max_videos]
            self.logger.info(f"Ограничение: {max_videos} видео")

        total = len(video_urls)
        time_format = TimeParser.format_time_spec(watch_time_spec)
        self.logger.info(f"Начинаем обработку {total} видео в {self.max_sessions} параллельных сессиях")
        self.logger.info(f"Время просмотра: {time_format}")
        self.logger.info(f"Каждое окно будет автоматически закрыто после просмотра")

        # Используем ThreadPoolExecutor для параллельной обработки
        with ThreadPoolExecutor(max_workers=min(self.max_sessions, len(video_urls))) as executor:
            futures = []

            for i, video_url in enumerate(video_urls, 1):
                # Проверка URL
                if not any(domain in video_url.lower() for domain in ["rutube.ru", "rutube.pl"]):
                    self.logger.warning(f"Пропущена не-RuTube ссылка: {video_url}")
                    self._update_stats(video_url, False, 0)
                    continue

                # Создаем задачу на просмотр видео
                viewer = VideoViewer(self.session_manager, self.logger)
                future = executor.submit(viewer.watch_video, video_url, watch_time_spec)
                futures.append((future, video_url, i, total))

                # Небольшая задержка между запусками задач
                if i < len(video_urls):
                    time.sleep(random.uniform(0.5, 1.5))

            # Обработка результатов
            for future, video_url, i, total in futures:
                try:
                    # Вычисляем максимальное время ожидания
                    max_watch_time = TimeParser.get_random_time(watch_time_spec)
                    success = future.result(timeout=max_watch_time + 60)

                    # Получаем фактическое время просмотра
                    expected_time = TimeParser.get_random_time(watch_time_spec)
                    self._update_stats(video_url, success, expected_time if success else 0)

                    if success:
                        self.logger.info(f"[#{i}/{total}] Успешно: {video_url} (окно закрыто)")
                    else:
                        self.logger.warning(f"[#{i}/{total}] Не удалось: {video_url}")

                except Exception as e:
                    self.logger.error(f"[#{i}/{total}] Исключение: {video_url} - {e}")
                    self._update_stats(video_url, False, 0)

                # Сохраняем статистику каждые 5 видео
                if i % 5 == 0:
                    self.save_stats()

        self.save_stats()

    def run_cycles(self, video_urls: List[str], watch_time_spec: Union[int, Tuple[int, int]],
                   shuffle: bool = False, max_videos: Optional[int] = None,
                   cycles: int = 1,
                   delay_between_cycles_spec: Union[int, Tuple[int, int]] = DEFAULT_CYCLE_DELAY) -> bool:
        """Циклический просмотр видео с случайными задержками между циклами"""
        try:
            self._print_cycle_info(video_urls, watch_time_spec, cycles, delay_between_cycles_spec)

            cycle_generator = range(cycles) if cycles > 0 else itertools_cycle([0])

            for cycle_num in cycle_generator:
                if cycles > 0:
                    current_cycle = cycle_num + 1
                else:
                    current_cycle = cycle_num

                self.stats['cycles_completed'] += 1
                self.logger.info(f"\n{'=' * 40}")
                self.logger.info(f"ЦИКЛ {current_cycle if cycles > 0 else '∞'}")
                self.logger.info(f"{'=' * 40}")

                self.process_videos_parallel(video_urls, watch_time_spec, shuffle, max_videos)

                if cycles > 0 and current_cycle >= cycles:
                    break

                # Пауза между циклами со случайным выбором времени
                self._cycle_pause(delay_between_cycles_spec)

            return True

        except KeyboardInterrupt:
            self.logger.info("Остановлено пользователем")
            return False
        except Exception as e:
            self.logger.error(f"Ошибка в циклическом просмотре: {e}")
            return False

    def _print_cycle_info(self, video_urls: List[str], watch_time_spec: Union[int, Tuple[int, int]],
                          cycles: int, delay_spec: Union[int, Tuple[int, int]]):
        """Вывод информации о цикле"""
        time_format = TimeParser.format_time_spec(watch_time_spec)
        delay_format = TimeParser.format_time_spec(delay_spec, label="сек")

        info = [
            f"{'=' * 50}",
            "ПАРАЛЛЕЛЬНЫЙ ПРОСМОТР RUTUBE",
            f"{'=' * 50}",
            f"Циклов: {'бесконечно' if cycles == 0 else cycles}",
            f"Видео в цикле: {len(video_urls)}",
            f"Время просмотра: {time_format}",
            f"Задержка между циклами: {delay_format}",
            f"Макс. параллельных сессий: {self.max_sessions}",
            f"Режим: {'GUI' if self.gui_mode else 'Headless'}",
            f"Инкогнито: Включен",
            f"Без звука: {'Да' if self.mute_audio else 'Нет'}",
            f"Stealth режим: {'Да' if self.stealth_mode else 'Нет'}",
            f"ChromeDriver: {self.chromedriver_path if self.chromedriver_path else 'автоопределение'}",
            f"{'=' * 50}",
        ]

        for line in info:
            self.logger.info(line)

    def _cycle_pause(self, delay_spec: Union[int, Tuple[int, int]]):
        """Пауза между циклами со случайным выбором времени"""
        if isinstance(delay_spec, tuple):
            min_delay, max_delay = delay_spec
            actual_delay = TimeParser.get_random_time(delay_spec)
            if min_delay != max_delay:
                self.stats['random_delay_used'] = True
                self.logger.info(
                    f"Случайная задержка между циклами: {actual_delay} сек (из интервала {min_delay}-{max_delay} сек)")
            else:
                self.logger.info(f"Задержка между циклами: {actual_delay} сек")
        else:
            actual_delay = delay_spec
            self.logger.info(f"Задержка между циклами: {actual_delay} сек")

        # Сохраняем фактическую задержку в историю
        self.cycle_delays.append({
            'delay': actual_delay,
            'timestamp': datetime.now().isoformat(),
            'spec': delay_spec if isinstance(delay_spec, tuple) else delay_spec
        })

        if actual_delay <= 0:
            return

        # Пауза с прогресс-баром
        for remaining in range(actual_delay, 0, -10):
            if remaining <= 30 or remaining % 30 == 0:
                self.logger.info(f"Осталось: {remaining} сек")
            time.sleep(min(10, remaining))

    def run(self, video_urls: Union[str, List[str]], watch_time_spec: Union[int, Tuple[int, int]],
            shuffle: bool = False, max_videos: Optional[int] = None,
            cycles: int = 1, delay_between_cycles_spec: Union[int, Tuple[int, int]] = DEFAULT_CYCLE_DELAY):
        """Основной запуск"""
        try:
            time_format = TimeParser.format_time_spec(watch_time_spec)
            delay_format = TimeParser.format_time_spec(delay_between_cycles_spec, label="сек")
            self._print_start_info(cycles, time_format, delay_format)

            # Подготовка списка видео
            if isinstance(video_urls, str):
                video_urls = [video_urls]

            # Запуск
            if cycles != 1:
                self.run_cycles(video_urls, watch_time_spec, shuffle, max_videos,
                                cycles, delay_between_cycles_spec)
            else:
                self.process_videos_parallel(video_urls, watch_time_spec, shuffle, max_videos)

            self.print_summary()

        except KeyboardInterrupt:
            self.logger.info("Остановлено пользователем")
        except Exception as e:
            self.logger.error(f"Ошибка: {e}")
        finally:
            self._cleanup()

    def _print_start_info(self, cycles: int, time_format: str, delay_format: str):
        """Вывод стартовой информации"""
        info = [
            f"\n{'=' * 40}",
            f"ПАРАЛЛЕЛЬНЫЙ ПРОСМОТР RUTUBE",
            f"{'=' * 40}",
            f"Версия: 2.0 (случайное время и задержки)",
            f"Максимум сессий: {self.max_sessions}",
            f"Каждое видео в новой сессии инкогнито",
            f"Время просмотра: {time_format}",
            f"Задержка между циклами: {delay_format}",
            f"ChromeDriver: {self.chromedriver_path if self.chromedriver_path else 'автоопределение'}",
            f"Циклы: {'бесконечно' if cycles == 0 else cycles}",
            f"{'=' * 40}",
        ]

        for line in info:
            print(line)

    def _cleanup(self):
        """Очистка ресурсов"""
        try:
            self.session_manager.close_all_sessions()
        except:
            pass

        self.save_stats()

    def print_summary(self):
        """Вывод итогов"""
        stats = [
            f"\n{'=' * 40}",
            "ИТОГИ ПРОСМОТРА",
            f"{'=' * 40}",
            f"Циклов завершено: {self.stats['cycles_completed']}",
            f"Всего видео: {self.stats['total_videos']}",
            f"Успешно: {self.stats['successful_views']}",
            f"Ошибки: {self.stats['failed_views']}",
        ]

        total_sec = self.stats['total_watch_time']
        if total_sec >= 3600:
            time_str = f"{total_sec // 3600}ч {(total_sec % 3600) // 60}м"
        elif total_sec >= 60:
            time_str = f"{total_sec // 60}м {total_sec % 60}с"
        else:
            time_str = f"{total_sec}с"

        stats.append(f"Общее время просмотра: {time_str}")

        if self.stats['total_videos'] > 0:
            success_rate = (self.stats['successful_views'] / self.stats['total_videos']) * 100
            stats.append(f"Успешность: {success_rate:.1f}%")

        # Добавляем информацию о случайных задержках, если они использовались
        if self.stats['random_delay_used']:
            stats.append(f"Использованы случайные задержки между циклами: Да")

        stats.append(f"Статистика сохранена в: {STATS_FILE}")
        stats.append(f"{'=' * 40}")

        for line in stats:
            print(line)


def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Параллельный просмотр видео на RuTube с отдельными сессиями',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Фиксированное время 30 секунд, фиксированная задержка 30 секунд
  python viewer.py --file videos.txt --cycles 3 --time 30 --delay-between-cycles 30

  # Случайное время между 30 и 60 секунд, фиксированная задержка 45 секунд
  python viewer.py --file videos.txt --time 30-60 --delay-between-cycles 45

  # Фиксированное время 45 секунд, случайная задержка между 60 и 120 секунд
  python viewer.py --file videos.txt --time 45 --delay-between-cycles 60-120

  # Случайное время между 20 и 40 секунд, случайная задержка между 45 и 90 секунд
  python viewer.py --file videos.txt --time 20:40 --delay-between-cycles 45:90

  # Использование драйвера из папки selenium-server
  python viewer.py --file videos.txt --chromedriver "selenium-server/chromedriver.exe" --time 20-40 --delay-between-cycles 30-60

  # Headless режим с 5 сессиями, случайным временем 60-120 сек и случайной задержкой 120-240 сек
  python viewer.py --file videos.txt --max-sessions 5 --no-gui --time 60-120 --delay-between-cycles 120-240

Форматы времени и задержек:
  • "30"       - фиксированно 30 секунд
  • "30-60"    - случайно между 30 и 60 секунд
  • "45:90"    - случайно между 45 и 90 секунд

Применяется для:
  --time                  - время просмотра каждого видео
  --delay-between-cycles  - задержка между циклами
        """
    )

    # Источники видео
    parser.add_argument('--urls', nargs='+', help='Ссылки на видео')
    parser.add_argument('--file', help='Файл со списком видео')

    # Параметры просмотра
    parser.add_argument('--time', type=str, default=str(DEFAULT_WATCH_TIME),
                        help=f'Время просмотра в секундах. Форматы: число (30) или интервал (30-60). По умолчанию: {DEFAULT_WATCH_TIME}')
    parser.add_argument('--shuffle', action='store_true', help='Перемешать видео')
    parser.add_argument('--max', type=int, help='Максимум видео в цикле')

    # Циклы
    parser.add_argument('--cycles', type=int, default=1,
                        help='Количество циклов (0=бесконечно)')
    parser.add_argument('--delay-between-cycles', type=str, default=str(DEFAULT_CYCLE_DELAY),
                        help=f'Задержка между циклами в секундах. Форматы: число (30) или интервал (30-60). По умолчанию: {DEFAULT_CYCLE_DELAY}')

    # Настройки сессий
    parser.add_argument('--max-sessions', type=int, default=DEFAULT_MAX_SESSIONS,
                        help=f'Максимум одновременных сессий (по умолчанию: {DEFAULT_MAX_SESSIONS})')

    # Настройки браузера
    parser.add_argument('--gui', action='store_true', default=True,
                        help='С графическим интерфейсом (по умолчанию)')
    parser.add_argument('--no-gui', action='store_false', dest='gui',
                        help='Без графического интерфейса (headless)')
    parser.add_argument('--mute', action='store_true', default=True,
                        help='Отключить звук (по умолчанию)')
    parser.add_argument('--no-mute', action='store_false', dest='mute',
                        help='Не отключать звук')
    parser.add_argument('--stealth', action='store_true', default=True,
                        help='Включить stealth режим (по умолчанию)')
    parser.add_argument('--no-stealth', action='store_false', dest='stealth',
                        help='Отключить stealth режим')

    # Путь к ChromeDriver
    parser.add_argument('--chromedriver', help='Путь к ChromeDriver')

    return parser.parse_args()


def validate_arguments(args):
    """Валидация аргументов"""
    if not args.urls and not args.file:
        print("Ошибка: укажите --urls или --file")
        return False

    if args.max_sessions < 1:
        print("Ошибка: max-sessions должен быть >= 1")
        return False

    # Парсим время просмотра
    try:
        watch_time_spec = TimeParser.parse_time_input(args.time, DEFAULT_WATCH_TIME)

        # Проверяем минимальное время
        if isinstance(watch_time_spec, tuple):
            min_time, max_time = watch_time_spec
            if min_time < 1:
                print("Ошибка: минимальное время просмотра должно быть >= 1 секунды")
                return False
            if max_time < min_time:
                print(f"Ошибка: максимальное время просмотра ({max_time}) должно быть >= минимального ({min_time})")
                return False
        else:
            if watch_time_spec < 1:
                print("Ошибка: время просмотра должно быть >= 1 секунды")
                return False

    except ValueError as e:
        print(f"Ошибка в параметре --time: {e}")
        return False

    # Парсим задержку между циклами
    try:
        delay_spec = TimeParser.parse_time_input(args.delay_between_cycles, DEFAULT_CYCLE_DELAY)

        # Проверяем минимальную задержку
        if isinstance(delay_spec, tuple):
            min_delay, max_delay = delay_spec
            if min_delay < 0:
                print("Ошибка: минимальная задержка должна быть >= 0")
                return False
            if max_delay < min_delay:
                print(f"Ошибка: максимальная задержка ({max_delay}) должна быть >= минимальной ({min_delay})")
                return False
        else:
            if delay_spec < 0:
                print("Ошибка: задержка должна быть >= 0")
                return False

    except ValueError as e:
        print(f"Ошибка в параметре --delay-between-cycles: {e}")
        return False

    return True


def main():
    """Основная функция"""
    args = parse_arguments()

    if not validate_arguments(args):
        return

    # Предупреждение о бесконечном цикле
    if args.cycles == 0:
        print("\n" + "=" * 50)
        print("⚠  ЗАПУЩЕН БЕСКОНЕЧНЫЙ ЦИКЛ!")
        print("Для остановки нажмите Ctrl+C")
        print("=" * 50 + "\n")
        time.sleep(3)

    # Загрузка видео
    video_urls = []

    if args.urls:
        video_urls.extend(args.urls)

    if args.file:
        temp_viewer = RuTubeViewer()
        loaded = temp_viewer.load_videos_from_file(args.file)
        video_urls.extend(loaded)

    if not video_urls:
        print("Ошибка: не удалось загрузить видео")
        return

    # Парсим время просмотра
    watch_time_spec = TimeParser.parse_time_input(args.time, DEFAULT_WATCH_TIME)

    # Парсим задержку между циклами
    delay_spec = TimeParser.parse_time_input(args.delay_between_cycles, DEFAULT_CYCLE_DELAY)

    # Запуск
    viewer = RuTubeViewer(
        gui_mode=args.gui,
        incognito=True,  # Всегда инкогнито
        max_sessions=args.max_sessions,
        mute_audio=args.mute,
        stealth_mode=args.stealth,
        chromedriver_path=args.chromedriver
    )

    viewer.run(
        video_urls=video_urls,
        watch_time_spec=watch_time_spec,
        shuffle=args.shuffle,
        max_videos=args.max,
        cycles=args.cycles,
        delay_between_cycles_spec=delay_spec
    )


if __name__ == "__main__":
    main()