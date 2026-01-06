#!/usr/bin/env python3
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

        # Флаг для отслеживания состояния
        self.is_running = False

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
        self.logger.info("Поиск ChromeDriver...")

        # 1. Пользовательский путь
        if custom_path:
            self.logger.info(f"Проверяем пользовательский путь: {custom_path}")
            if os.path.exists(custom_path):
                self.logger.info(f"✓ Найден ChromeDriver по указанному пути")
                return custom_path
            else:
                self.logger.warning(f"✗ Указанный путь не существует: {custom_path}")

        # 2. Стандартные пути для macOS
        mac_paths = [
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

        for path in mac_paths:
            self.logger.debug(f"Проверяем путь: {path}")
            if path.exists():
                # Проверяем права
                if not os.access(str(path), os.X_OK):
                    try:
                        os.chmod(str(path), 0o755)
                        self.logger.info(f"Установлены права на выполнение для: {path}")
                    except Exception as e:
                        self.logger.warning(f"Не удалось установить права: {e}")

                self.logger.info(f"✓ Найден ChromeDriver: {path}")
                return str(path)

        # 3. Переменная окружения
        env_path = os.environ.get('CHROMEDRIVER_PATH')
        if env_path:
            self.logger.info(f"Проверяем переменную окружения: {env_path}")
            if os.path.exists(env_path):
                self.logger.info(f"✓ Найден ChromeDriver в переменной окружения")
                return env_path

        # 4. Ищем в PATH
        import shutil
        self.logger.info("Поиск ChromeDriver в PATH...")
        system_path = shutil.which("chromedriver")
        if system_path:
            self.logger.info(f"✓ Найден ChromeDriver в PATH: {system_path}")
            return system_path

        self.logger.warning("✗ ChromeDriver не найден локально. Будет использован webdriver-manager.")
        return None

    def _create_chrome_options(self) -> Options:
        """Создание настроек Chrome для macOS"""
        self.logger.info("Создание настроек Chrome...")

        options = Options()

        # Основные настройки для скрытия автоматизации
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Режимы
        if self.incognito:
            options.add_argument("--incognito")
            self.logger.info("Режим инкогнито: включен")

        if not self.gui_mode:
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            self.logger.info("Headless режим: включен")
        else:
            options.add_argument("--start-maximized")
            self.logger.info("GUI режим: включен")

        # Дополнительные опции
        options.add_argument("--disable-notifications")
        options.add_argument("--lang=ru-RU")
        options.add_argument("--disable-popup-blocking")

        # User-Agent для macOS
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        options.add_argument(f'user-agent={user_agent}')

        # Дополнительные опции для стабильности
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")

        self.logger.info("Настройки Chrome созданы успешно")
        return options

    def create_driver(self) -> bool:
        """Создание драйвера"""
        self.logger.info("=" * 50)
        self.logger.info("СОЗДАНИЕ CHROME ДРАЙВЕРА")
        self.logger.info("=" * 50)

        try:
            options = self._create_chrome_options()

            # Проверяем, есть ли локальный chromedriver
            if self.chromedriver_path and os.path.exists(self.chromedriver_path):
                self.logger.info(f"Используем локальный chromedriver: {self.chromedriver_path}")

                # Убедимся, что файл исполняемый
                if not os.access(self.chromedriver_path, os.X_OK):
                    self.logger.info("Устанавливаем права на выполнение...")
                    try:
                        os.chmod(self.chromedriver_path, 0o755)
                        self.logger.info("Права установлены успешно")
                    except Exception as e:
                        self.logger.error(f"Ошибка при установке прав: {e}")
                        return False

                try:
                    service = ChromeService(executable_path=self.chromedriver_path)
                    self.logger.info("ChromeService создан с локальным драйвером")
                except Exception as e:
                    self.logger.error(f"Ошибка создания ChromeService: {e}")
                    return False
            else:
                self.logger.info("Используем webdriver-manager для автоматической установки...")
                try:
                    # Добавляем отладку для webdriver-manager
                    import webdriver_manager
                    self.logger.info(f"Webdriver-manager версия: {webdriver_manager.__version__}")

                    driver_manager = ChromeDriverManager()
                    driver_path = driver_manager.install()
                    self.logger.info(f"ChromeDriver установлен в: {driver_path}")
                    service = ChromeService(driver_path)
                except Exception as e:
                    self.logger.error(f"Ошибка webdriver-manager: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())
                    return False

            self.logger.info("Инициализируем WebDriver...")
            try:
                self.driver = webdriver.Chrome(service=service, options=options)
                self.logger.info("✓ WebDriver успешно создан!")

                # Тестируем драйвер
                self.logger.info("Тестируем драйвер...")
                self.driver.get("about:blank")
                self.logger.info(f"Тестовая страница открыта. Заголовок: {self.driver.title}")

                # Устанавливаем размер окна
                if not self.gui_mode:
                    self.driver.set_window_size(1920, 1080)
                    self.logger.info("Размер окна установлен: 1920x1080")

                # Устанавливаем таймауты
                self.driver.set_page_load_timeout(30)
                self.driver.set_script_timeout(30)

                self.logger.info("=" * 50)
                self.logger.info("ДРАЙВЕР УСПЕШНО СОЗДАН И ГОТОВ К РАБОТЕ")
                self.logger.info("=" * 50)

                return True

            except Exception as e:
                self.logger.error(f"Ошибка при создании WebDriver: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                return False

        except Exception as e:
            self.logger.error(f"Критическая ошибка при создании драйвера: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def load_videos_from_file(self, filepath: str) -> List[str]:
        """Загрузка видео из файла"""
        self.logger.info(f"Загрузка видео из файла: {filepath}")

        if not os.path.exists(filepath):
            self.logger.error(f"✗ Файл не найден: {filepath}")
            return []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

            rutube_urls = [url for url in urls if "rutube" in url.lower()]

            if len(rutube_urls) < len(urls):
                self.logger.warning(f"Отфильтровано {len(urls) - len(rutube_urls)} не-RuTube ссылок")

            self.logger.info(f"✓ Загружено {len(rutube_urls)} видео из {filepath}")

            # Выводим первые 3 ссылки для проверки
            for i, url in enumerate(rutube_urls[:3], 1):
                self.logger.info(f"  {i}. {url}")
            if len(rutube_urls) > 3:
                self.logger.info(f"  ... и еще {len(rutube_urls) - 3} видео")

            return rutube_urls

        except Exception as e:
            self.logger.error(f"✗ Ошибка загрузки файла: {e}")
            return []

    def close_popups(self):
        """Закрытие попапов"""
        try:
            closed = 0
            for selector in POPUP_SELECTORS:
                try:
                    if selector.startswith("//"):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                    for element in elements[:2]:  # Проверяем первые 2 элемента
                        if element.is_displayed():
                            element.click()
                            closed += 1
                            time.sleep(0.5)
                            break
                except:
                    continue

            if closed > 0:
                self.logger.info(f"Закрыто {closed} попап(ов)")

        except Exception as e:
            self.logger.debug(f"Ошибка при закрытии попапов: {e}")

    def accept_cookies(self):
        """Принятие куки"""
        try:
            for selector in COOKIE_SELECTORS:
                try:
                    if selector.startswith("//"):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                    for element in elements[:2]:
                        if element.is_displayed() and element.is_enabled():
                            element.click()
                            self.logger.info("Куки приняты")
                            time.sleep(1)
                            return True
                except:
                    continue
        except Exception as e:
            self.logger.debug(f"Окно куки не найдено: {e}")

        return False

    def find_and_play_video(self) -> bool:
        """Поиск и воспроизведение видео"""
        try:
            # Ищем видео элемент
            video_element = None
            for selector in VIDEO_SELECTORS:
                try:
                    if selector == "video":
                        video_element = self.driver.find_element(By.TAG_NAME, "video")
                    else:
                        video_element = self.driver.find_element(By.CSS_SELECTOR, selector)

                    if video_element:
                        self.logger.info(f"Видео элемент найден с селектором: {selector}")
                        break
                except:
                    continue

            if not video_element:
                self.logger.warning("Видео элемент не найден")
                return False

            # Пытаемся запустить видео
            try:
                # Способ 1: JavaScript play
                self.driver.execute_script("arguments[0].play();", video_element)
                self.logger.info("Видео запущено через JavaScript")
            except:
                try:
                    # Способ 2: Клик на видео
                    video_element.click()
                    self.logger.info("Видео запущено кликом")
                except:
                    try:
                        # Способ 3: Поиск кнопки play
                        for selector in PLAY_BUTTON_SELECTORS:
                            try:
                                play_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                for btn in play_buttons:
                                    if btn.is_displayed():
                                        btn.click()
                                        self.logger.info("Видео запущено кнопкой play")
                                        break
                            except:
                                continue
                    except:
                        self.logger.warning("Не удалось запустить видео")
                        return False

            # Отключаем звук если нужно
            if self.mute_audio:
                try:
                    self.driver.execute_script("arguments[0].muted = true;", video_element)
                    self.logger.info("Звук отключен")
                except:
                    self.logger.warning("Не удалось отключить звук")

            return True

        except Exception as e:
            self.logger.error(f"Ошибка при воспроизведении видео: {e}")
            return False

    def watch_video(self, video_url: str, watch_time: int = DEFAULT_WATCH_TIME) -> bool:
        """Просмотр видео"""
        self.logger.info(f"Начинаем просмотр: {video_url}")

        try:
            # Переходим на страницу
            self.logger.info(f"Переход по ссылке...")
            self.driver.get(video_url)

            # Ждем загрузки страницы
            time.sleep(3)

            # Закрываем попапы и куки
            self.close_popups()
            self.accept_cookies()
            self.close_popups()

            # Пытаемся найти и запустить видео
            video_playing = self.find_and_play_video()

            if not video_playing:
                self.logger.warning("Не удалось запустить видео, но продолжаем...")

            # Имитация просмотра
            self.logger.info(f"Смотрим видео {watch_time} секунд...")

            start_time = time.time()
            elapsed = 0

            while elapsed < watch_time and self.is_running:
                current_elapsed = time.time() - start_time

                # Логируем каждые 30 секунд
                if int(current_elapsed) % 30 == 0 and int(current_elapsed) > elapsed:
                    self.logger.info(f"Просмотрено: {int(current_elapsed)}/{watch_time} сек")
                    elapsed = int(current_elapsed)

                # Случайные действия для реалистичности
                if random.random() < 0.1 and current_elapsed > 10:
                    try:
                        scroll_amount = random.randint(100, 300)
                        direction = random.choice([-1, 1])
                        self.driver.execute_script(f"window.scrollBy(0, {direction * scroll_amount});")
                        self.logger.debug(f"Прокрутка: {direction * scroll_amount}px")
                    except:
                        pass

                time.sleep(1)

            if not self.is_running:
                self.logger.info("Просмотр прерван")
                return False

            self.logger.info("✓ Просмотр завершен")
            return True

        except Exception as e:
            self.logger.error(f"✗ Ошибка при просмотре: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def run(self, video_urls: List[str], watch_time: int = DEFAULT_WATCH_TIME,
            shuffle: bool = False, max_videos: Optional[int] = None,
            cycles: int = 1, delay_between_cycles: int = DEFAULT_CYCLE_DELAY):
        """Основной запуск"""
        self.is_running = True

        try:
            print(f"\n{'=' * 60}")
            print(" " * 10 + "ЗАПУСК ПРОСМОТРА RUTUBE")
            print(f"{'=' * 60}")
            print(f"Количество видео: {len(video_urls)}")
            print(f"Время просмотра: {watch_time} сек")
            print(f"Перемешивание: {'Да' if shuffle else 'Нет'}")
            print(f"Циклы: {'бесконечно' if cycles == 0 else cycles}")
            print(f"Задержка между циклами: {delay_between_cycles} сек")
            print(f"{'=' * 60}\n")

            self.logger.info("=" * 60)
            self.logger.info("НАЧАЛО РАБОТЫ ПРОСМОТРЩИКА")
            self.logger.info("=" * 60)

            if not self.create_driver():
                self.logger.error("Не удалось создать драйвер! Завершаем работу.")
                return

            cycle_counter = 0
            total_videos_watched = 0

            # Бесконечный цикл если cycles == 0
            while self.is_running and (cycles == 0 or cycle_counter < cycles):
                cycle_counter += 1

                if cycles > 0:
                    self.logger.info(f"\nЦИКЛ {cycle_counter} из {cycles}")
                    print(f"\n[ЦИКЛ {cycle_counter}/{cycles}]")
                else:
                    self.logger.info(f"\nЦИКЛ {cycle_counter} (бесконечный режим)")
                    print(f"\n[ЦИКЛ {cycle_counter}]")

                # Перемешиваем если нужно
                if shuffle:
                    random.shuffle(video_urls)
                    self.logger.info("Список видео перемешан")

                # Ограничиваем количество видео если нужно
                videos_to_watch = video_urls
                if max_videos and max_videos > 0:
                    videos_to_watch = video_urls[:max_videos]
                    self.logger.info(f"Ограничение: {max_videos} видео за цикл")

                # Просмотр видео
                for i, url in enumerate(videos_to_watch, 1):
                    if not self.is_running:
                        break

                    self.logger.info(f"\n--- Видео {i}/{len(videos_to_watch)} ---")
                    print(f"\n[{i}/{len(videos_to_watch)}] {url[:80]}...")

                    success = self.watch_video(url, watch_time)

                    if success:
                        total_videos_watched += 1
                        self.stats['successful_views'] += 1
                        self.logger.info(f"✓ Видео успешно просмотрено (всего: {total_videos_watched})")
                    else:
                        self.stats['failed_views'] += 1
                        self.logger.warning("✗ Ошибка при просмотре видео")

                    self.stats['total_videos'] += 1

                    # Пауза между видео (кроме последнего)
                    if i < len(videos_to_watch) and self.is_running:
                        pause = random.randint(3, 7)
                        self.logger.info(f"Пауза {pause} сек перед следующим видео...")
                        print(f"Пауза {pause} сек...")
                        for sec in range(pause, 0, -1):
                            if not self.is_running:
                                break
                            time.sleep(1)

                # Проверяем, нужно ли продолжать
                if cycles > 0 and cycle_counter >= cycles:
                    self.logger.info(f"Достигнуто заданное количество циклов: {cycles}")
                    break

                # Пауза между циклами
                if self.is_running and (cycles == 0 or cycle_counter < cycles):
                    self.logger.info(f"\nПауза между циклами: {delay_between_cycles} сек...")
                    print(f"\nПауза между циклами: {delay_between_cycles} сек...")

                    for sec in range(delay_between_cycles, 0, -1):
                        if not self.is_running:
                            break
                        if sec % 30 == 0 or sec <= 10:
                            self.logger.info(f"До следующего цикла: {sec} сек")
                            print(f"До следующего цикла: {sec} сек")
                        time.sleep(1)

                    if self.is_running:
                        # Перезапускаем драйвер для нового цикла
                        self.logger.info("Перезапуск драйвера для нового цикла...")
                        try:
                            self.driver.quit()
                        except:
                            pass

                        time.sleep(2)

                        if not self.create_driver():
                            self.logger.error("Не удалось пересоздать драйвер! Завершаем работу.")
                            break

            self.logger.info("=" * 60)
            self.logger.info("РАБОТА ЗАВЕРШЕНА")
            self.logger.info("=" * 60)

            print(f"\n{'=' * 60}")
            print(" " * 15 + "ПРОСМОТР ЗАВЕРШЕН!")
            print(f"{'=' * 60}")
            print(f"Всего циклов: {cycle_counter}")
            print(f"Всего видео просмотрено: {total_videos_watched}")
            print(f"Успешных просмотров: {self.stats['successful_views']}")
            print(f"Ошибок: {self.stats['failed_views']}")
            print(f"{'=' * 60}")

        except KeyboardInterrupt:
            self.logger.info("\nОстановлено пользователем (Ctrl+C)")
            print("\n\nОстановлено пользователем")
        except Exception as e:
            self.logger.error(f"\nКритическая ошибка: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            print(f"\nКритическая ошибка: {e}")
        finally:
            self.is_running = False
            self._cleanup()

    def _cleanup(self):
        """Очистка ресурсов"""
        self.logger.info("Очистка ресурсов...")
        try:
            if self.driver:
                self.driver.quit()
                self.logger.info("Драйвер закрыт")
        except:
            pass

        # Сохраняем статистику
        try:
            data = {
                'stats': dict(self.stats),
                'videos_history': self.videos_history[-100:],
                'settings': {**self.settings, 'end_time': datetime.now().isoformat()}
            }

            with open(STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

            self.logger.info(f"Статистика сохранена в {STATS_FILE}")
        except Exception as e:
            self.logger.error(f"Ошибка сохранения статистики: {e}")


def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='Просмотр видео RuTube для macOS',
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="""
Примеры использования:
  %(prog)s --file videos.txt --time 60 --shuffle
  %(prog)s --file videos.txt --time 180 --no-gui --cycles 3
  %(prog)s --file videos.txt --time 120 --cycles 0 --delay-between-cycles 300
  %(prog)s --urls "https://rutube.ru/video/..." --time 90
                                     """)

    # Источники видео
    parser.add_argument('--file', help='Файл со списком видео (каждая ссылка на новой строке)')
    parser.add_argument('--urls', nargs='+', help='Ссылки на видео через пробел')

    # Параметры просмотра
    parser.add_argument('--time', type=int, default=DEFAULT_WATCH_TIME,
                        help=f'Время просмотра каждого видео в секундах (по умолчанию: {DEFAULT_WATCH_TIME})')
    parser.add_argument('--shuffle', action='store_true', help='Перемешивать порядок видео')
    parser.add_argument('--max', type=int, help='Максимальное количество видео за цикл')

    # Циклы
    parser.add_argument('--cycles', type=int, default=1,
                        help='Количество циклов (0 = бесконечно, по умолчанию: 1)')
    parser.add_argument('--delay-between-cycles', type=int, default=DEFAULT_CYCLE_DELAY,
                        help=f'Задержка между циклами в секундах (по умолчанию: {DEFAULT_CYCLE_DELAY})')

    # Настройки браузера
    parser.add_argument('--no-gui', action='store_true', help='Запуск без графического интерфейса (headless режим)')
    parser.add_argument('--chromedriver', help='Путь к ChromeDriver (если не указан, будет найден автоматически)')
    parser.add_argument('--no-mute', action='store_true', help='Не отключать звук при воспроизведении')

    args = parser.parse_args()

    # Валидация аргументов
    if not args.file and not args.urls:
        print("Ошибка: необходимо указать --file или --urls")
        parser.print_help()
        return

    if args.time < 5:
        print("Предупреждение: время просмотра менее 5 секунд может быть неэффективным")

    if args.cycles == 0:
        print("\n" + "!" * 60)
        print("ВНИМАНИЕ: Запущен БЕСКОНЕЧНЫЙ режим!")
        print("Для остановки нажмите Ctrl+C")
        print("!" * 60 + "\n")
        time.sleep(3)

    # Загружаем видео
    video_urls = []

    if args.urls:
        video_urls.extend(args.urls)
        print(f"Добавлено {len(args.urls)} видео из аргументов командной строки")

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

    # Обработка Ctrl+C
    import signal
    def signal_handler(sig, frame):
        print("\nПолучен сигнал остановки...")
        viewer.is_running = False

    signal.signal(signal.SIGINT, signal_handler)

    # Запуск
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