import time
import random
import argparse
from datetime import datetime
from typing import List, Optional, Union
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
import logging
import json
import os
import sys
from pathlib import Path


class RuTubeViewer:
    def __init__(self, gui_mode: bool = True, incognito: bool = True,
                 chromedriver_path: Optional[str] = None):
        self.setup_logging()
        self.gui_mode = gui_mode
        self.incognito = incognito
        self.chromedriver_path = self._find_chromedriver(chromedriver_path)
        self.driver = None

        self.stats = {
            'total_videos': 0,
            'successful_views': 0,
            'failed_views': 0,
            'total_watch_time': 0,
            'videos_history': [],
            'settings': {
                'gui_mode': gui_mode,
                'incognito': incognito,
                'chromedriver_path': str(self.chromedriver_path) if self.chromedriver_path else None,
                'start_time': datetime.now().isoformat()
            }
        }

    def _find_chromedriver(self, custom_path: Optional[str] = None) -> Optional[str]:
        """Поиск ChromeDriver"""
        # 1. Пользовательский путь
        if custom_path and os.path.exists(custom_path):
            self.logger.info(f"Используется указанный ChromeDriver: {custom_path}")
            return custom_path

        # 2. Каталог selenium-server
        paths_to_check = [
            Path(__file__).parent / "selenium-server" / "chromedriver.exe",
            Path(__file__).parent / "selenium-server" / "chromedriver",
            Path.cwd() / "selenium-server" / "chromedriver.exe",
            Path.cwd() / "selenium-server" / "chromedriver",
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

    def setup_logging(self):
        """Простая настройка логирования"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('rutube_viewer.log', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def create_driver(self):
        """Создание драйвера"""
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
            else:
                chrome_options.add_argument("--start-maximized")

            # Дополнительные опции
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--lang=ru-RU")

            # User-Agent
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
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

    def accept_cookies(self):
        """Принятие куки"""
        try:
            cookie_selectors = [
                "button[class*='cookie']",
                "button[class*='Cookie']",
                "//button[contains(text(), 'Принять')]",
                "//button[contains(text(), 'Согласен')]",
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

            # Куки
            self.accept_cookies()

            # Ждем загрузки
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Ищем видео
            video_element = None
            video_selectors = ["video", "iframe[src*='rutube']", ".video-js"]

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
            return False
        except Exception as e:
            self.logger.error(f"Ошибка: {video_url} - {e}")
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

        self.stats['total_videos'] = len(video_urls)

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
            }
            self.stats['videos_history'].append(video_stat)

            if success:
                self.stats['successful_views'] += 1
                self.stats['total_watch_time'] += watch_time
                self.logger.info("Успешно просмотрено")
            else:
                self.stats['failed_views'] += 1
                self.logger.error("Ошибка просмотра")

            # Сохранение статистики
            self.save_stats()

    def save_stats(self):
        """Сохранение статистики"""
        try:
            with open('viewer_stats.json', 'w', encoding='utf-8') as f:
                self.stats['settings']['end_time'] = datetime.now().isoformat()
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

    def run(self, video_urls: Union[str, List[str]], watch_time: int = 30,
            shuffle: bool = False, max_videos: Optional[int] = None):
        """Основной запуск"""
        try:
            # Информация о режиме
            print(f"\nРежим: {'GUI' if self.gui_mode else 'Headless'}")
            print(f"Инкогнито: {'Да' if self.incognito else 'Нет'}")
            if self.chromedriver_path:
                print(f"ChromeDriver: {self.chromedriver_path}")
            print("=" * 50)

            # Создаем драйвер
            if not self.create_driver():
                return

            # Обрабатываем видео
            if isinstance(video_urls, str):
                video_urls = [video_urls]

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
        print("\n" + "=" * 50)
        print("ИТОГИ")
        print("=" * 50)
        print(f"Всего видео: {self.stats['total_videos']}")
        print(f"Успешно: {self.stats['successful_views']}")
        print(f"Ошибки: {self.stats['failed_views']}")

        total_sec = self.stats['total_watch_time']
        hours = total_sec // 3600
        minutes = (total_sec % 3600) // 60
        seconds = total_sec % 60

        print(f"Общее время: {hours}ч {minutes}м {seconds}с")
        print(f"Статистика сохранена в viewer_stats.json")
        print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description='Просмотр видео на RuTube')

    # Основные аргументы
    parser.add_argument('--urls', nargs='+', help='Ссылки на видео')
    parser.add_argument('--file', type=str, help='Файл со списком видео')
    parser.add_argument('--time', type=int, default=30, help='Время просмотра (сек)')

    # Режимы
    parser.add_argument('--gui', action='store_true', default=True,
                        help='С графическим интерфейсом (по умолчанию)')
    parser.add_argument('--no-gui', action='store_false', dest='gui',
                        help='Без графического интерфейса')

    # Дополнительные
    parser.add_argument('--chromedriver', type=str, help='Путь к ChromeDriver')
    parser.add_argument('--incognito', action='store_true', default=True,
                        help='Режим инкогнито')
    parser.add_argument('--no-incognito', action='store_false', dest='incognito',
                        help='Без инкогнито')
    parser.add_argument('--shuffle', action='store_true', help='Перемешать видео')
    parser.add_argument('--max', type=int, help='Максимум видео')

    args = parser.parse_args()

    # Загружаем видео
    video_urls = []

    if args.urls:
        video_urls.extend(args.urls)

    if args.file:
        viewer = RuTubeViewer(gui_mode=args.gui, incognito=args.incognito)
        loaded = viewer.load_videos_from_file(args.file)
        video_urls.extend(loaded)

    if not video_urls:
        print("Ошибка: укажите видео через --urls или --file")
        return

    # Запускаем
    viewer = RuTubeViewer(
        gui_mode=args.gui,
        incognito=args.incognito,
        chromedriver_path=args.chromedriver
    )

    viewer.run(
        video_urls=video_urls,
        watch_time=args.time,
        shuffle=args.shuffle,
        max_videos=args.max
    )


if __name__ == "__main__":
    main()