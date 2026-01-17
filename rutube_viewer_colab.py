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
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service as ChromeService

# Константы для конфигурации
DEFAULT_WATCH_TIME = 30
DEFAULT_CYCLE_DELAY = 30
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
    ".volume-control",
    ".mute-button",
]

PLAY_BUTTON_SELECTORS = [
    "button[class*='play']",
    "button[title*='play']",
    "button[aria-label*='play']",
    ".play-button",
]


class AntiDetection:
    """Класс для скрытия автоматизации"""

    @staticmethod
    def get_stealth_scripts() -> List[str]:
        """Возвращает список скриптов для скрытия автоматизации"""
        return [
            # Скрытие webdriver флага
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """,
            # Переопределение window.chrome
            """
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            """,
        ]


class RuTubeViewer:
    """Оптимизированный просмотрщик видео RuTube для Colab"""

    def __init__(self, headless: bool = True, incognito: bool = True,
                 chromedriver_path: Optional[str] = None,
                 mute_audio: bool = True, stealth_mode: bool = True):
        self._setup_directories()
        self._setup_logging()

        self.headless = headless
        self.incognito = incognito
        self.mute_audio = mute_audio
        self.stealth_mode = stealth_mode
        self.chromedriver_path = chromedriver_path or "/usr/bin/chromedriver"
        self.driver = None
        self.anti_detection = AntiDetection()

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

            # Файловый хендлер
            file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
            file_handler.setFormatter(formatter)

            # Консольный хендлер
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
            'headless': self.headless,
            'incognito': self.incognito,
            'mute_audio': self.mute_audio,
            'stealth_mode': self.stealth_mode,
            'start_time': datetime.now().isoformat()
        }

    def _create_chrome_options(self) -> Options:
        """Создание настроек Chrome для Colab"""
        options = Options()

        # Базовые опции
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Headless режим для Colab
        if self.headless:
            options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        # Дополнительные опции
        if self.stealth_mode:
            options.add_argument("--disable-logging")
            options.add_argument("--log-level=3")

        # Режимы
        if self.incognito:
            options.add_argument("--incognito")

        # Настройки
        options.add_experimental_option('prefs', {
            'profile.default_content_setting_values.notifications': 2,
            'intl.accept_languages': 'ru-RU,ru',
        })

        # User-Agent
        user_agents = [
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        selected_ua = random.choice(user_agents)
        options.add_argument(f'user-agent={selected_ua}')

        return options

    def create_driver(self) -> bool:
        """Создание драйвера для Colab"""
        try:
            options = self._create_chrome_options()

            # Проверяем путь к драйверу
            if not os.path.exists(self.chromedriver_path):
                self.logger.error(f"ChromeDriver не найден по пути: {self.chromedriver_path}")
                # Пробуем найти альтернативные пути
                alt_paths = [
                    '/usr/bin/chromedriver',
                    '/usr/local/bin/chromedriver',
                    '/usr/lib/chromium-browser/chromedriver',
                ]
                for path in alt_paths:
                    if os.path.exists(path):
                        self.chromedriver_path = path
                        self.logger.info(f"Найден альтернативный путь: {path}")
                        break

            self.logger.info(f"Используется ChromeDriver: {self.chromedriver_path}")

            # Создаем сервис
            service = ChromeService(executable_path=self.chromedriver_path)

            # Создаем драйвер
            self.driver = webdriver.Chrome(service=service, options=options)

            # Установка размеров окна
            self.driver.set_window_size(1920, 1080)

            # Применяем stealth техники
            self._apply_stealth_techniques()

            # Установка таймаутов
            self.driver.set_page_load_timeout(30)
            self.driver.set_script_timeout(30)
            self.driver.implicitly_wait(5)

            self.logger.info("Драйвер успешно создан")
            return True

        except Exception as e:
            self.logger.error(f"Ошибка при создании драйвера: {str(e)}")
            self.logger.error("Для установки ChromeDriver выполните:")
            self.logger.error("1. !apt-get update")
            self.logger.error("2. !apt-get install -y wget unzip")
            self.logger.error(
                "3. !wget -q https://storage.googleapis.com/chrome-for-testing-public/last-known-good-versions-with-downloads.json")
            self.logger.error("4. Загрузите и установите chromedriver из JSON файла")
            return False

    def _apply_stealth_techniques(self):
        """Применяет техники stealth"""
        if not self.stealth_mode or not self.driver:
            return

        try:
            stealth_scripts = self.anti_detection.get_stealth_scripts()

            for script in stealth_scripts:
                try:
                    self.driver.execute_script(script)
                except:
                    pass

            self.logger.debug("Применены stealth техники")

        except Exception as e:
            self.logger.debug(f"Ошибка применения stealth техник: {e}")

    def _random_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Случайная задержка"""
        time.sleep(random.uniform(min_seconds, max_seconds))

    def close_popups(self):
        """Закрытие попапов"""
        closed = 0
        for selector in POPUP_SELECTORS:
            try:
                if selector.startswith("//"):
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                for element in elements[:3]:
                    try:
                        if element.is_displayed():
                            element.click()
                            closed += 1
                            self._random_delay(0.3, 0.7)
                            break
                    except:
                        try:
                            self.driver.execute_script("arguments[0].click();", element)
                            closed += 1
                            self._random_delay(0.3, 0.7)
                            break
                        except:
                            continue
            except:
                continue

        return closed

    def accept_cookies(self) -> bool:
        """Принятие куки"""
        try:
            for selector in COOKIE_SELECTORS:
                try:
                    if selector.startswith("//"):
                        element = WebDriverWait(self.driver, 2).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        element = WebDriverWait(self.driver, 2).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )

                    if element and element.is_displayed():
                        element.click()
                        self.logger.info("Куки приняты")
                        self._random_delay(0.5, 1)
                        return True
                except:
                    continue
        except Exception as e:
            self.logger.debug(f"Окно куки не найдено: {e}")

        return False

    def _find_video_element(self):
        """Поиск видео элемента"""
        for selector in VIDEO_SELECTORS:
            try:
                if selector == "video":
                    element = self.driver.find_element(By.TAG_NAME, "video")
                else:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)

                if element:
                    self.logger.debug(f"Видео найдено: {selector}")
                    return element
            except:
                continue

        return None

    def _mute_video(self, video_element=None) -> bool:
        """Отключение звука видео"""
        if not self.mute_audio:
            return False

        try:
            # Через JavaScript
            if video_element:
                try:
                    self.driver.execute_script("arguments[0].muted = true;", video_element)
                    self.driver.execute_script("arguments[0].volume = 0;", video_element)
                    self.stats['muted_videos'] += 1
                    self.logger.info("Звук отключен через JavaScript")
                    return True
                except:
                    pass

            # Глобальное отключение
            try:
                self.driver.execute_script("""
                    var videos = document.querySelectorAll('video');
                    for (var i = 0; i < videos.length; i++) {
                        videos[i].muted = true;
                        videos[i].volume = 0;
                    }
                """)
                self.stats['muted_videos'] += 1
                self.logger.info("Звук отключен глобально")
                return True
            except:
                pass

            return False

        except Exception as e:
            self.logger.debug(f"Ошибка при отключении звука: {e}")
            return False

    def watch_video(self, video_url: str, watch_time: int = DEFAULT_WATCH_TIME) -> bool:
        """Просмотр видео"""
        try:
            self.logger.info(f"Просмотр: {video_url} ({watch_time} сек)")

            self._random_delay(0.5, 2.0)

            # Переход на страницу
            self.driver.get(video_url)

            self._random_delay(1.5, 3.0)

            # Обработка всплывающих окон
            self.close_popups()
            self.accept_cookies()
            self.close_popups()

            # Ожидание загрузки
            WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Поиск и запуск видео
            video_element = self._find_video_element()
            if video_element:
                # Запуск видео
                try:
                    self.driver.execute_script("arguments[0].play();", video_element)
                    self.logger.debug("Воспроизведение запущено")
                except:
                    try:
                        video_element.click()
                    except:
                        pass

                # Отключение звука
                if self.mute_audio:
                    self._random_delay(0.5, 1.0)
                    self._mute_video(video_element)
            else:
                if self.mute_audio:
                    self._mute_video()

            # Просмотр
            start_time = time.time()
            last_log_time = 0

            while time.time() - start_time < watch_time:
                elapsed = time.time() - start_time

                # Логирование
                if int(elapsed) // 10 > last_log_time:
                    self.logger.debug(f"Просмотрено {int(elapsed)} сек")
                    last_log_time = int(elapsed) // 10

                # Случайные действия
                if random.random() < 0.1 and elapsed > 5:
                    scroll_pos = random.randint(100, 400)
                    self.driver.execute_script(f"window.scrollBy(0, {random.choice([-1, 1]) * scroll_pos});")

                # Задержка
                time.sleep(random.uniform(0.8, 1.5))

            self.logger.info(f"Завершено: {video_url}")
            return True

        except TimeoutException:
            self.logger.error(f"Таймаут: {video_url}")
        except Exception as e:
            self.logger.error(f"Ошибка: {video_url} - {str(e)}")

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
            'cycle': self.stats['cycles_completed'] + 1,
        })

    def save_stats(self):
        """Сохранение статистики"""
        try:
            data = {
                'stats': dict(self.stats),
                'videos_history': self.videos_history[-100:],
                'settings': {**self.settings, 'end_time': datetime.now().isoformat()}
            }

            with open(STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        except Exception as e:
            self.logger.error(f"Ошибка сохранения статистики: {e}")

    def process_videos(self, video_urls: List[str], watch_time: int = DEFAULT_WATCH_TIME,
                       shuffle: bool = False, max_videos: Optional[int] = None):
        """Обработка списка видео"""
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

        for i, video_url in enumerate(video_urls, 1):
            self.logger.info(f"\n[#{i}/{total}] {video_url}")

            # Проверка URL
            if not any(domain in video_url.lower() for domain in ["rutube.ru", "rutube.pl"]):
                self.logger.warning("Пропущена не-RuTube ссылка")
                self._update_stats(video_url, False, 0)
                continue

            # Пауза между видео
            if i > 1:
                time.sleep(random.randint(3, 7))

            # Просмотр видео
            success = self.watch_video(video_url, watch_time)
            self._update_stats(video_url, success, watch_time if success else 0)

            # Сохранение статистики
            if i % 5 == 0:
                self.save_stats()

    def run_cycles(self, video_urls: List[str], watch_time: int = DEFAULT_WATCH_TIME,
                   shuffle: bool = False, max_videos: Optional[int] = None,
                   cycles: int = 1, delay_between_cycles: int = DEFAULT_CYCLE_DELAY) -> bool:
        """Циклический просмотр"""
        try:
            # Вывод информации
            info = [
                f"{'=' * 50}",
                "ЦИКЛИЧЕСКИЙ ПРОСМОТР",
                f"{'=' * 50}",
                f"Циклов: {'бесконечно' if cycles == 0 else cycles}",
                f"Видео в цикле: {len(video_urls)}",
                f"Время просмотра: {watch_time} сек",
                f"Задержка между циклами: {delay_between_cycles} сек",
                f"Без звука: {'Да' if self.mute_audio else 'Нет'}",
                f"Stealth режим: {'Да' if self.stealth_mode else 'Нет'}",
                f"{'=' * 50}",
            ]

            for line in info:
                self.logger.info(line)

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

                self.process_videos(video_urls, watch_time, shuffle, max_videos)

                # Проверка условия остановки
                if cycles > 0 and current_cycle >= cycles:
                    break

                # Пауза между циклами
                self.logger.info(f"Пауза: {delay_between_cycles} сек")
                for remaining in range(delay_between_cycles, 0, -1):
                    if remaining % 10 == 0 or remaining <= 5:
                        self.logger.info(f"Осталось: {remaining} сек")
                    time.sleep(1)

                # Перезапуск драйвера
                self.logger.info("Перезапуск браузера...")
                try:
                    if self.driver:
                        self.driver.quit()
                except:
                    pass

                time.sleep(1)

                if not self.create_driver():
                    raise Exception("Не удалось создать драйвер")

            return True

        except KeyboardInterrupt:
            self.logger.info("Остановлено пользователем")
            return False
        except Exception as e:
            self.logger.error(f"Ошибка в циклическом просмотре: {e}")
            return False

    def run(self, video_urls: Union[str, List[str]], watch_time: int = DEFAULT_WATCH_TIME,
            shuffle: bool = False, max_videos: Optional[int] = None,
            cycles: int = 1, delay_between_cycles: int = DEFAULT_CYCLE_DELAY):
        """Основной запуск"""
        try:
            # Вывод стартовой информации
            info = [
                f"\n{'=' * 40}",
                f"Режим: {'Headless' if self.headless else 'GUI'}",
                f"Инкогнито: {'Да' if self.incognito else 'Нет'}",
                f"Без звука: {'Да' if self.mute_audio else 'Нет'}",
                f"Stealth режим: {'Да' if self.stealth_mode else 'Нет'}",
                f"Циклы: {'бесконечно' if cycles == 0 else cycles}",
                f"{'=' * 40}",
            ]

            for line in info:
                print(line)

            if not self.create_driver():
                return

            # Подготовка списка видео
            if isinstance(video_urls, str):
                video_urls = [video_urls]

            # Запуск
            if cycles != 1:
                self.run_cycles(video_urls, watch_time, shuffle, max_videos,
                                cycles, delay_between_cycles)
            else:
                self.process_videos(video_urls, watch_time, shuffle, max_videos)

            self.print_summary()

        except KeyboardInterrupt:
            self.logger.info("Остановлено")
        except Exception as e:
            self.logger.error(f"Ошибка: {e}")
        finally:
            self._cleanup()

    def _cleanup(self):
        """Очистка ресурсов"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

        # Финальное сохранение статистики
        self.save_stats()

    def print_summary(self):
        """Вывод итогов"""
        stats = [
            f"\n{'=' * 40}",
            "ИТОГИ",
            f"{'=' * 40}",
            f"Циклов: {self.stats['cycles_completed']}",
            f"Всего видео: {self.stats['total_videos']}",
            f"Успешно: {self.stats['successful_views']}",
            f"Ошибки: {self.stats['failed_views']}",
            f"Без звука: {self.stats['muted_videos']}",
        ]

        # Форматирование времени
        total_sec = self.stats['total_watch_time']
        if total_sec >= 3600:
            time_str = f"{total_sec // 3600}ч {(total_sec % 3600) // 60}м"
        elif total_sec >= 60:
            time_str = f"{total_sec // 60}м {total_sec % 60}с"
        else:
            time_str = f"{total_sec}с"

        stats.append(f"Общее время: {time_str}")
        stats.append(f"Статистика: {STATS_FILE}")
        stats.append(f"{'=' * 40}")

        for line in stats:
            print(line)


def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Просмотр видео на RuTube для Colab',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Источники видео
    parser.add_argument('--urls', nargs='+', help='Ссылки на видео')
    parser.add_argument('--file', help='Файл со списком видео')

    # Параметры просмотра
    parser.add_argument('--time', type=int, default=DEFAULT_WATCH_TIME,
                        help=f'Время просмотра (сек, по умолчанию: {DEFAULT_WATCH_TIME})')
    parser.add_argument('--shuffle', action='store_true', help='Перемешать видео')
    parser.add_argument('--max', type=int, help='Максимум видео в цикле')

    # Циклы
    parser.add_argument('--cycles', type=int, default=1,
                        help='Количество циклов (0=бесконечно)')
    parser.add_argument('--delay-between-cycles', type=int, default=DEFAULT_CYCLE_DELAY,
                        help=f'Задержка между циклами (сек, по умолчанию: {DEFAULT_CYCLE_DELAY})')

    # Настройки браузера
    parser.add_argument('--gui', action='store_true', help='С графическим интерфейсом (не для Colab)')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Без графического интерфейса (по умолчанию)')
    parser.add_argument('--incognito', action='store_true', default=True,
                        help='Режим инкогнито (по умолчанию)')
    parser.add_argument('--no-incognito', action='store_false', dest='incognito',
                        help='Без режима инкогнито')

    # Настройки звука
    parser.add_argument('--mute', action='store_true', default=True,
                        help='Отключить звук при воспроизведении (по умолчанию)')
    parser.add_argument('--no-mute', action='store_false', dest='mute',
                        help='Не отключать звук при воспроизведении')

    # Настройки stealth режима
    parser.add_argument('--stealth', action='store_true', default=True,
                        help='Включить stealth режим (по умолчанию)')
    parser.add_argument('--no-stealth', action='store_false', dest='stealth',
                        help='Отключить stealth режим')

    return parser.parse_args()


def validate_arguments(args):
    """Валидация аргументов"""
    if not args.urls and not args.file:
        print("Ошибка: укажите --urls или --file")
        return False

    if args.cycles < 0:
        print("Ошибка: количество циклов не может быть отрицательным")
        return False

    if args.delay_between_cycles < 0:
        print("Ошибка: задержка не может быть отрицательной")
        return False

    return True


def main():
    """Основная функция"""
    args = parse_arguments()

    if not validate_arguments(args):
        return

    # Предупреждение о бесконечном цикле
    if args.cycles == 0:
        print("\n⚠  ЗАПУЩЕН БЕСКОНЕЧНЫЙ ЦИКЛ!")
        print("Для остановки нажмите Ctrl+C\n")
        time.sleep(2)

    # Загрузка видео
    video_urls = []

    if args.urls:
        video_urls.extend(args.urls)

    if args.file:
        # Создаем временный объект для загрузки файла
        temp_viewer = RuTubeViewer(headless=True, incognito=True,
                                   mute_audio=True, stealth_mode=True)
        loaded = temp_viewer.load_videos_from_file(args.file)
        video_urls.extend(loaded)

    if not video_urls:
        print("Ошибка: не удалось загрузить видео")
        return

    # Запуск
    viewer = RuTubeViewer(
        headless=args.headless,
        incognito=args.incognito,
        mute_audio=args.mute,
        stealth_mode=args.stealth
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