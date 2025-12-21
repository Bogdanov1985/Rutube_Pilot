import time
import random
import argparse
import logging
import json
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


'''
# Desktop режим (по умолчанию)
python Script\rutube_viewer_conf.py --file videos.txt

# Mobile режим со случайным устройством
python Script\rutube_viewer_conf.py --file videos.txt --device mobile

# Конкретное мобильное устройство
python Script\rutube_viewer_conf.py --file videos.txt --device mobile --mobile-device iphone_15

# Показать список доступных устройств
python Script\rutube_viewer_conf.py --list-devices


4. Примеры использования:
Mobile просмотр:

bash
python Script\rutube_viewer_conf.py --file videos.txt --device mobile --mobile-device samsung_galaxy_s24 --no-gui --cycles 3
Desktop просмотр:

bash
python Script\rutube_viewer_conf.py --file videos.txt --device desktop --gui --time 45
Тестирование разных устройств:

bash
# iPhone
python Script\rutube_viewer_conf.py --urls "https://rutube.ru/video/..." --device mobile --mobile-device iphone_15 --gui

# Android
python Script\rutube_viewer_conf.py --urls "https://rutube.ru/video/..." --device mobile --mobile-device google_pixel_8 --no-gui

All mobile 
python Script\rutube_viewer_conf.py --file videos.txt --device mobile --cycles 0 --time 90 --no-gui
'''

# Импортируем user agents
try:
    from user_agents import (
        get_random_desktop_agent,
        get_random_mobile_agent,
        get_random_agent,
        get_device_config,
        get_mobile_chrome_options
    )

    HAS_USER_AGENTS = True
except ImportError:
    HAS_USER_AGENTS = False
    # Запасные user agents если файл не найден
    DEFAULT_USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    ]


class RuTubeViewer:
    def __init__(self, gui_mode: bool = True, incognito: bool = True,
                 chromedriver_path: Optional[str] = None,
                 clear_cookies_between_cycles: bool = True,
                 device_type: str = 'desktop',
                 mobile_device: Optional[str] = None):
        self.setup_logging()
        self.gui_mode = gui_mode
        self.incognito = incognito
        self.clear_cookies_between_cycles = clear_cookies_between_cycles
        self.device_type = device_type.lower()  # 'desktop' или 'mobile'
        self.mobile_device = mobile_device  # Название мобильного устройства
        self.chromedriver_path = self._find_chromedriver(chromedriver_path)
        self.driver = None
        self.profile_dir = Path('./chrome_temp_profile')

        # Константы для селекторов
        self.CLOSE_SELECTORS = [
            "svg.svg-icon--IconClose",
            "button[class*='close']",
            "button[class*='Close']",
            "div[class*='close'] button",
            "div[class*='Close'] button",
            "button[aria-label*='закрыть']",
            "button[aria-label*='Закрыть']",
            "button[title*='закрыть']",
            "button[title*='Закрыть']",
            "div[class*='modal'] button[class*='close']",
            "div[class*='popup'] button[class*='close']",
            "div[class*='dialog'] button[class*='close']",
        ]

        self.COOKIE_SELECTORS = [
            "button[class*='cookie']",
            "button[class*='Cookie']",
            "//button[contains(text(), 'Принять')]",
            "//button[contains(text(), 'Согласен')]",
            "//button[contains(text(), 'Принимаю')]",
            "//button[contains(text(), 'OK')]",
            "//button[contains(text(), 'Ok')]",
            "//button[contains(text(), 'ОК')]",
        ]

        self.VIDEO_SELECTORS = [
            "video",
            "iframe[src*='rutube']",
            ".video-js",
            "div[class*='video-player']",
            "div[class*='player']",
            "#video-player",
            "video[class*='player']",
        ]

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
                'clear_cookies_between_cycles': clear_cookies_between_cycles,
                'device_type': device_type,
                'mobile_device': mobile_device,
                'chromedriver_path': str(self.chromedriver_path) if self.chromedriver_path else None,
                'start_time': datetime.now().isoformat()
            }
        }

        self.logger.info(f"Инициализирован RuTubeViewer (GUI: {gui_mode}, Инкогнито: {incognito}, "
                         f"Очистка куков: {clear_cookies_between_cycles}, "
                         f"Тип устройства: {device_type}, Мобильное устройство: {mobile_device})")

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
        system_path = shutil.which("chromedriver") or shutil.which("chromedriver.exe")
        if system_path:
            self.logger.info(f"Найден ChromeDriver в PATH: {system_path}")
            return system_path

        self.logger.warning("ChromeDriver не найден. Будет использован webdriver-manager.")
        return None

    def setup_logging(self):
        """Настройка логирования"""
        # Создаем директорию для логов если её нет
        log_dir = Path('../logs')
        log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'rutube_viewer.log', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _get_user_agent(self):
        """Получение user agent в зависимости от типа устройства"""
        if HAS_USER_AGENTS:
            if self.device_type == 'mobile':
                if self.mobile_device:
                    config = get_device_config(self.mobile_device)
                    if config:
                        return config['user_agent']
                return get_random_mobile_agent()
            else:
                return get_random_desktop_agent()
        else:
            return random.choice(DEFAULT_USER_AGENTS)

    def create_driver(self) -> bool:
        """Создание драйвера с настройками для выбранного типа устройства"""
        try:
            chrome_options = Options()

            # ОСНОВНЫЕ НАСТРОЙКИ
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            # Базовые аргументы для стабильности
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')

            # Режимы
            if self.incognito:
                chrome_options.add_argument("--incognito")

            # Настройки для GUI/Headless
            if not self.gui_mode:
                chrome_options.add_argument("--headless=new")
            else:
                chrome_options.add_argument("--start-maximized")

            # Дополнительные настройки
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_argument("--lang=ru-RU")

            # Отключаем GPU для headless режима
            if not self.gui_mode:
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--disable-software-rasterizer')

            # Настройки для мобильных устройств
            if self.device_type == 'mobile':
                if HAS_USER_AGENTS and self.mobile_device:
                    try:
                        # Используем полную конфигурацию для мобильного устройства
                        mobile_options, user_agent, viewport = get_mobile_chrome_options(
                            self.mobile_device
                        )
                        # Копируем опции из mobile_options
                        for arg in mobile_options.arguments:
                            chrome_options.add_argument(arg)
                        for key, value in mobile_options.experimental_options.items():
                            chrome_options.add_experimental_option(key, value)
                    except:
                        # Запасной вариант
                        user_agent = self._get_user_agent()
                        chrome_options.add_argument(f'user-agent={user_agent}')
                        chrome_options.add_argument('--use-mobile-user-agent')
                else:
                    # Базовый мобильный user agent
                    user_agent = self._get_user_agent()
                    chrome_options.add_argument(f'user-agent={user_agent}')
                    chrome_options.add_argument('--use-mobile-user-agent')

                if not self.gui_mode:
                    # Для headless мобильного режима устанавливаем размер окна
                    chrome_options.add_argument('--window-size=412,915')
            else:
                # Desktop user agent
                user_agent = self._get_user_agent()
                chrome_options.add_argument(f'user-agent={user_agent}')
                if self.gui_mode:
                    chrome_options.add_argument('--window-size=1920,1080')

            # SSL настройки
            chrome_options.add_argument('--ignore-certificate-errors')
            chrome_options.add_argument('--ignore-ssl-errors')

            # Создаем профиль только если не очищаем куки между циклами
            if not self.clear_cookies_between_cycles:
                self.profile_dir.mkdir(exist_ok=True, parents=True)
                chrome_options.add_argument(f'--user-data-dir={self.profile_dir.absolute()}')
                self.logger.info(f"Используется профиль: {self.profile_dir}")

            # Убираем сообщения в консоли
            chrome_options.add_argument('--log-level=3')

            # Дополнительные опции
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--autoplay-policy=no-user-gesture-required')

            # Создание драйвера
            try:
                if self.chromedriver_path and os.path.exists(self.chromedriver_path):
                    service = Service(executable_path=self.chromedriver_path)
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    self.logger.info(f"Используется ChromeDriver: {self.chromedriver_path}")
                else:
                    self.driver = webdriver.Chrome(options=chrome_options)
                    self.logger.info("Используется системный ChromeDriver")

            except Exception as driver_error:
                self.logger.warning(f"Ошибка при создании драйвера: {driver_error}")
                # Пробуем webdriver-manager
                try:
                    from webdriver_manager.chrome import ChromeDriverManager
                    from selenium.webdriver.chrome.service import Service as ChromeService

                    service = ChromeService(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    self.logger.info("Драйвер загружен через webdriver-manager")
                except ImportError:
                    self.logger.error("webdriver-manager не установлен")
                    return False
                except Exception as wdm_error:
                    self.logger.error(f"Ошибка webdriver-manager: {wdm_error}")
                    return False

            # Скрываем автоматизацию
            try:
                self.driver.execute_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });

                    // Для мобильных устройств добавляем дополнительные скрипты
                    if (/Mobile|Android|iPhone|iPad|iPod/.test(navigator.userAgent)) {
                        Object.defineProperty(navigator, 'maxTouchPoints', {
                            get: () => 5
                        });
                        Object.defineProperty(navigator, 'platform', {
                            get: () => /iPhone|iPad|iPod/.test(navigator.userAgent) ? 'iOS' : 'Android'
                        });
                    }
                """)
            except:
                pass

            self.logger.info(f"Драйвер успешно создан (Тип: {self.device_type}, "
                             f"User-Agent: {user_agent[:80]}...)")

            # Проверяем, что драйвер работает
            try:
                self.driver.get("about:blank")
                time.sleep(1)
                return True
            except:
                self.logger.error("Драйвер создан, но не отвечает")
                return False

        except Exception as e:
            self.logger.error(f"Критическая ошибка при создании драйвера: {e}")
            return False

    def clear_profile_directory(self):
        """Очистка директории профиля Chrome"""
        try:
            if self.profile_dir.exists():
                shutil.rmtree(self.profile_dir, ignore_errors=True)
                self.logger.info(f"Директория профиля очищена: {self.profile_dir}")
                return True
        except Exception as e:
            self.logger.error(f"Ошибка при очистке профиля: {e}")
        return False

    def clear_driver_cookies(self):
        """Очистка куков драйвера"""
        try:
            if self.driver:
                self.driver.delete_all_cookies()
                self.logger.info("Куки драйвера очищены")
                return True
        except Exception as e:
            self.logger.error(f"Ошибка при очистке куков: {e}")
        return False

    def wait_random(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Случайная задержка с логированием"""
        delay = random.uniform(min_seconds, max_seconds)
        self.logger.debug(f"Задержка: {delay:.2f} секунд")
        time.sleep(delay)

    def close_popups(self) -> int:
        """Закрытие всплывающих окон"""
        closed_popups = 0

        for selector in self.CLOSE_SELECTORS:
            try:
                if selector.startswith("//"):
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                for element in elements:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            self.driver.execute_script("arguments[0].click();", element)
                            self.logger.debug(f"Закрыто всплывающее окно: {selector}")
                            closed_popups += 1
                            self.wait_random(0.5, 1)
                            break
                    except:
                        continue

            except Exception:
                continue

        if closed_popups > 0:
            self.logger.info(f"Закрыто {closed_popups} всплывающих окон")

        return closed_popups

    def accept_cookies(self) -> bool:
        """Принятие куки"""
        for selector in self.COOKIE_SELECTORS:
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
                    self.driver.execute_script("arguments[0].click();", element)
                    self.logger.info("Куки приняты")
                    self.wait_random(1, 2)
                    return True

            except (TimeoutException, Exception):
                continue

        return False

    def find_video_element(self):
        """Поиск видео элемента"""
        for selector in self.VIDEO_SELECTORS:
            try:
                if selector == "video":
                    element = self.driver.find_element(By.TAG_NAME, "video")
                else:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)

                if element:
                    self.logger.debug(f"Видео найдено с селектором: {selector}")
                    return element
            except Exception:
                continue
        return None

    def start_video_playback(self, video_element) -> bool:
        """Запуск воспроизведения видео"""
        try:
            # Пробуем через JavaScript
            self.driver.execute_script("arguments[0].play();", video_element)
            self.logger.info("Воспроизведение начато через JavaScript")
            return True
        except:
            pass

        try:
            # Пробуем клик
            video_element.click()
            self.logger.info("Воспроизведение начато по клику")
            return True
        except:
            pass

        try:
            # Ищем кнопку Play
            play_selectors = [
                "button[class*='play']",
                "button[title*='play']",
                "button[title*='воспроизвести']",
                "button[aria-label*='play']",
                "button[aria-label*='воспроизвести']",
                "div[class*='play-button']",
            ]

            for selector in play_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            self.driver.execute_script("arguments[0].click();", element)
                            self.logger.info(f"Нажата кнопка Play: {selector}")
                            return True
                except:
                    continue
        except:
            pass

        self.logger.warning("Не удалось начать воспроизведение")
        return False

    def simulate_human_interaction(self, start_time: float, watch_time: int):
        """Симуляция человеческого взаимодействия"""
        last_action_time = start_time

        while time.time() - start_time < watch_time:
            current_time = time.time()
            elapsed = current_time - start_time

            # Периодически показываем прогресс
            if int(elapsed) % 15 == 0 and int(elapsed) > 0:
                self.logger.info(f"Просмотрено {int(elapsed)} из {watch_time} сек")

            # Случайное действие каждые 10-20 секунд
            if current_time - last_action_time > random.randint(10, 20):
                # Прокрутка (меньше для мобильных)
                if self.device_type == 'mobile':
                    scroll_pos = random.randint(0, 300)
                else:
                    scroll_pos = random.randint(0, 500)

                self.driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
                self.logger.debug(f"Прокрутка до позиции {scroll_pos}")

                last_action_time = current_time

            # Случайная задержка между действиями
            time.sleep(random.uniform(1, 3))

    def watch_video(self, video_url: str, watch_time: int = 30) -> bool:
        """Просмотр одного видео"""
        try:
            self.logger.info(f"Начинаем просмотр: {video_url}")
            self.logger.info(f"Время просмотра: {watch_time} секунд")

            # Переход на страницу
            self.driver.get(video_url)
            self.wait_random(2, 4)

            # Ожидаем загрузки страницы
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Закрываем всплывающие окна
            self.close_popups()

            # Принимаем куки
            self.accept_cookies()

            # Еще раз проверяем всплывающие окна
            self.close_popups()

            # Даем время для полной загрузки
            self.wait_random(2, 3)

            # Ищем видео
            video_element = self.find_video_element()
            if not video_element:
                self.logger.warning("Видео элемент не найден, продолжаем просмотр страницы")
            else:
                # Пытаемся воспроизвести
                playback_started = self.start_video_playback(video_element)
                if not playback_started:
                    self.logger.warning("Воспроизведение не начато, продолжаем просмотр страницы")

            # Время просмотра
            start_time = time.time()

            # Симуляция человеческого поведения
            self.simulate_human_interaction(start_time, watch_time)

            self.logger.info(f"Просмотр завершен: {video_url}")
            return True

        except TimeoutException:
            self.logger.error(f"Таймаут при загрузке: {video_url}")
            return False
        except Exception as e:
            self.logger.error(f"Ошибка при просмотре {video_url}: {e}")
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
            if not self._is_valid_rutube_url(video_url):
                self.logger.warning(f"Невалидная RuTube ссылка: {video_url}")
                self.stats['failed_views'] += 1
                continue

            # Пауза между видео
            if i > 1:
                pause = random.randint(5, 15)
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
                'cycle': self.stats['cycles_completed'] + 1,
                'device_type': self.device_type,
                'mobile_device': self.mobile_device,
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

    def _is_valid_rutube_url(self, url: str) -> bool:
        """Проверка валидности RuTube ссылки"""
        rutube_domains = ['rutube.ru', 'rutube.pl', 'rutube.kz', 'rutube.ua']
        return any(domain in url for domain in rutube_domains)

    def save_stats(self):
        """Сохранение статистики"""
        try:
            stats_dir = Path('../stats')
            stats_dir.mkdir(exist_ok=True)

            stats_file = stats_dir / 'viewer_stats.json'
            self.stats['settings']['last_update'] = datetime.now().isoformat()

            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)

            self.logger.debug("Статистика сохранена")
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
                        # Нормализация URL
                        if not line.startswith(('http://', 'https://')):
                            line = f'https://{line}'
                        urls.append(line)

            # Фильтруем только rutube
            rutube_urls = [url for url in urls if self._is_valid_rutube_url(url)]

            filtered_count = len(urls) - len(rutube_urls)
            if filtered_count > 0:
                self.logger.warning(f"Отфильтровано {filtered_count} не-RuTube ссылок")

            self.logger.info(f"Загружено {len(rutube_urls)} видео из {filepath}")
            return rutube_urls

        except Exception as e:
            self.logger.error(f"Ошибка загрузки файла: {e}")
            return []

    def run_cycles(self, video_urls: List[str], watch_time: int = 30,
                   shuffle: bool = False, max_videos: Optional[int] = None,
                   cycles: int = 1, delay_between_cycles: int = 10) -> bool:
        """Запуск циклического просмотра"""
        try:
            # Информация о цикле
            self._print_cycle_info(cycles, len(video_urls), max_videos,
                                   watch_time, delay_between_cycles)

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
                    self._pause_between_cycles(delay_between_cycles)

                    # Перезапускаем драйвер между циклами
                    self._restart_driver()

            return True

        except KeyboardInterrupt:
            self.logger.info("Циклический просмотр остановлен пользователем")
            return False
        except Exception as e:
            self.logger.error(f"Ошибка в циклическом просмотре: {e}")
            return False

    def _print_cycle_info(self, cycles: int, video_count: int, max_videos: Optional[int],
                          watch_time: int, delay_between_cycles: int):
        """Вывод информации о цикле"""
        print(f"\n{'=' * 60}")
        print(f"ЦИКЛИЧЕСКИЙ ПРОСМОТР")
        print(f"{'=' * 60}")
        print(f"Количество циклов: {'бесконечно' if cycles == 0 else cycles}")
        print(f"Количество видео в цикле: {video_count}")
        if max_videos:
            print(f"Максимум видео в цикле: {max_videos}")
        print(f"Время просмотра каждого видео: {watch_time} сек")
        print(f"Задержка между циклами: {delay_between_cycles} сек")
        print(f"Тип устройства: {self.device_type}")
        if self.device_type == 'mobile' and self.mobile_device:
            print(f"Мобильное устройство: {self.mobile_device}")
        print(f"Очистка куков между циклами: {'Да' if self.clear_cookies_between_cycles else 'Нет'}")
        print(f"{'=' * 60}")

    def _pause_between_cycles(self, delay: int):
        """Пауза между циклами с отсчетом"""
        print(f"\nОжидание перед следующим циклом: {delay} секунд")
        self.logger.info(f"Пауза перед следующим циклом: {delay} сек")

        for remaining in range(delay, 0, -1):
            progress = '#' * (delay - remaining + 1) + '-' * (remaining - 1)
            print(f"\r[{progress}] Осталось: {remaining} сек ", end='')
            time.sleep(1)
        print(f"\rОжидание завершено{' ' * 50}")

    def _restart_driver(self):
        """Перезапуск драйвера с очисткой куков"""
        self.logger.info("Перезапуск браузера для нового цикла...")

        # Закрываем драйвер
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                self.logger.debug(f"Ошибка при закрытии драйвера: {e}")

        # Очищаем профиль если нужно
        if self.clear_cookies_between_cycles:
            self.clear_profile_directory()
        else:
            # Если не очищаем профиль, очищаем куки программно
            try:
                if self.driver:
                    self.clear_driver_cookies()
            except:
                pass

        # Создаем новый драйвер
        if not self.create_driver():
            raise Exception("Не удалось создать драйвер для нового цикла")

    def run(self, video_urls: Union[str, List[str]], watch_time: int = 30,
            shuffle: bool = False, max_videos: Optional[int] = None,
            cycles: int = 1, delay_between_cycles: int = 10):
        """Основной запуск с поддержкой циклов"""
        try:
            # Информация о режиме
            self._print_startup_info()

            # Создаем драйвер
            if not self.create_driver():
                self.logger.error("Не удалось создать драйвер")
                return

            # Обрабатываем видео
            if isinstance(video_urls, str):
                video_urls = [video_urls]

            # Запускаем циклы
            if cycles != 1:
                self.run_cycles(video_urls, watch_time, shuffle, max_videos,
                                cycles, delay_between_cycles)
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
            self._cleanup()

    def _print_startup_info(self):
        """Вывод информации о запуске"""
        print(f"\n{'=' * 50}")
        print(f"ЗАПУСК RUTUBE VIEWER")
        print(f"{'=' * 50}")
        print(f"Режим: {'GUI' if self.gui_mode else 'Headless'}")
        print(f"Инкогнито: {'Да' if self.incognito else 'Нет'}")
        print(f"Тип устройства: {self.device_type}")
        if self.device_type == 'mobile' and self.mobile_device:
            print(f"Мобильное устройство: {self.mobile_device}")
        print(f"Очистка куков между циклами: {'Да' if self.clear_cookies_between_cycles else 'Нет'}")
        if self.chromedriver_path:
            print(f"ChromeDriver: {self.chromedriver_path}")
        print(f"{'=' * 50}")

    def _cleanup(self):
        """Очистка ресурсов"""
        if self.driver:
            try:
                self.logger.info("Закрываем браузер")
                self.driver.quit()
            except Exception as e:
                self.logger.debug(f"Ошибка при закрытии браузера: {e}")

        # Очищаем профиль если нужно
        if self.clear_cookies_between_cycles:
            self.clear_profile_directory()

        # Сохраняем финальную статистику
        self.save_stats()

    def print_summary(self):
        """Итоговая статистика"""
        print("\n" + "=" * 60)
        print("ИТОГИ")
        print("=" * 60)
        print(f"Выполнено циклов: {self.stats['cycles_completed']}")
        print(f"Всего видео: {self.stats['total_videos']}")
        print(f"Успешно: {self.stats['successful_views']}")
        print(f"Ошибки: {self.stats['failed_views']}")
        print(f"Тип устройства: {self.device_type}")
        if self.device_type == 'mobile' and self.mobile_device:
            print(f"Мобильное устройство: {self.mobile_device}")

        if self.stats['successful_views'] > 0 and self.stats['total_videos'] > 0:
            success_rate = (self.stats['successful_views'] / self.stats['total_videos']) * 100
            print(f"Успешность: {success_rate:.1f}%")

        total_sec = self.stats['total_watch_time']
        hours = total_sec // 3600
        minutes = (total_sec % 3600) // 60
        seconds = total_sec % 60

        print(f"Общее время просмотра: {hours}ч {minutes}м {seconds}с")
        print(f"Статистика сохранена в stats/viewer_stats.json")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Циклический просмотр видео на RuTube с поддержкой Desktop и Mobile устройств',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Desktop режим (по умолчанию)
  python rutube_viewer.py --file videos.txt --time 45 --cycles 3

  # Mobile режим со случайным устройством
  python rutube_viewer.py --file videos.txt --device mobile --no-gui

  # Конкретное мобильное устройство
  python rutube_viewer.py --file videos.txt --device mobile --mobile-device iphone_15 --gui

  # Список доступных мобильных устройств
  python rutube_viewer.py --list-devices

  # Бесконечный цикл с очисткой куков
  python rutube_viewer.py --file playlist.txt --cycles 0 --no-gui --clear-cookies

  # Сохранение куков между циклами
  python rutube_viewer.py --file videos.txt --cycles 3 --no-clear-cookies

Доступные мобильные устройства:
  iphone_14, iphone_14_pro, iphone_15, samsung_galaxy_s24, 
  samsung_galaxy_s23, google_pixel_8, google_pixel_7, ipad_pro_11,
  samsung_tab_s9, xiaomi_13, oneplus_11
        """
    )

    # Основные аргументы
    parser.add_argument('--urls', nargs='+', help='Ссылки на видео')
    parser.add_argument('--file', type=str, help='Файл со списком видео')
    parser.add_argument('--time', type=int, default=30,
                        help='Время просмотра каждого видео в секундах (по умолчанию: 30)')

    # Циклы
    parser.add_argument('--cycles', type=int, default=1,
                        help='Количество циклов (0 = бесконечно, по умолчанию: 1)')
    parser.add_argument('--delay-between-cycles', type=int, default=30,
                        help='Задержка между циклами в секундах (по умолчанию: 30)')

    # Режимы устройства
    parser.add_argument('--device', type=str, default='desktop',
                        choices=['desktop', 'mobile'],
                        help='Тип устройства (desktop или mobile, по умолчанию: desktop)')
    parser.add_argument('--mobile-device', type=str,
                        help='Конкретное мобильное устройство (см. список ниже)')
    parser.add_argument('--list-devices', action='store_true',
                        help='Показать список доступных мобильных устройств')

    # Режимы браузера
    parser.add_argument('--gui', action='store_true', default=True,
                        help='С графическим интерфейсом (по умолчанию)')
    parser.add_argument('--no-gui', action='store_false', dest='gui',
                        help='Без графического интерфейса')
    parser.add_argument('--incognito', action='store_true', default=True,
                        help='Режим инкогнито (по умолчанию)')
    parser.add_argument('--no-incognito', action='store_false', dest='incognito',
                        help='Без инкогнито')

    # Очистка куков
    parser.add_argument('--clear-cookies', action='store_true', default=True,
                        dest='clear_cookies', help='Очищать куки между циклами (по умолчанию)')
    parser.add_argument('--no-clear-cookies', action='store_false',
                        dest='clear_cookies', help='Не очищать куки между циклами')

    # Дополнительные
    parser.add_argument('--chromedriver', type=str, help='Путь к ChromeDriver')
    parser.add_argument('--shuffle', action='store_true',
                        help='Перемешать видео в каждом цикле')
    parser.add_argument('--max', type=int,
                        help='Максимум видео в каждом цикле')
    parser.add_argument('--debug', action='store_true',
                        help='Включить отладочный режим')

    args = parser.parse_args()

    # Показать список устройств и выйти
    if args.list_devices:
        print("\nДоступные мобильные устройства:")
        print("=" * 40)
        devices = [
            ('iphone_14', 'iPhone 14'),
            ('iphone_14_pro', 'iPhone 14 Pro'),
            ('iphone_15', 'iPhone 15'),
            ('samsung_galaxy_s24', 'Samsung Galaxy S24'),
            ('samsung_galaxy_s23', 'Samsung Galaxy S23'),
            ('google_pixel_8', 'Google Pixel 8'),
            ('google_pixel_7', 'Google Pixel 7'),
            ('ipad_pro_11', 'iPad Pro 11"'),
            ('samsung_tab_s9', 'Samsung Tab S9'),
            ('xiaomi_13', 'Xiaomi 13'),
            ('oneplus_11', 'OnePlus 11')
        ]
        for device_id, device_name in devices:
            print(f"  {device_id:25} - {device_name}")
        print("\nИспользование: --device mobile --mobile-device DEVICE_ID")
        return 0

    # Настройка уровня логирования
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Валидация аргументов
    if args.time <= 0:
        print("Ошибка: время просмотра должно быть положительным числом")
        return 1

    if args.cycles < 0:
        print("Ошибка: количество циклов не может быть отрицательным")
        return 1

    if args.delay_between_cycles < 0:
        print("Ошибка: задержка между циклами не может быть отрицательной")
        return 1

    # Проверка мобильного устройства
    if args.device == 'mobile' and args.mobile_device:
        try:
            from user_agents import MOBILE_DEVICE_CONFIGS
            if args.mobile_device.lower() not in MOBILE_DEVICE_CONFIGS:
                print(f"\nОшибка: неизвестное мобильное устройство '{args.mobile_device}'")
                print("Используйте --list-devices для просмотра доступных устройств")
                return 1
        except ImportError:
            print("Предупреждение: файл user_agents.py не найден, "
                  "используется случайный mobile user agent")

    # Загружаем видео
    video_urls = []

    if args.urls:
        video_urls.extend(args.urls)

    if args.file:
        # Создаем временный viewer для загрузки файла
        temp_viewer = RuTubeViewer(gui_mode=args.gui, incognito=args.incognito)
        loaded = temp_viewer.load_videos_from_file(args.file)
        video_urls.extend(loaded)

    if not video_urls:
        print("Ошибка: укажите видео через --urls или --file")
        print("Используйте --help для справки")
        return 1

    # Проверяем параметр циклов
    if args.cycles == 0:
        print("\n" + "!" * 60)
        print("ВНИМАНИЕ: Запущен бесконечный цикл просмотра!")
        print("Для остановки нажмите Ctrl+C")
        print("!" * 60 + "\n")

    # Запускаем
    viewer = RuTubeViewer(
        gui_mode=args.gui,
        incognito=args.incognito,
        chromedriver_path=args.chromedriver,
        clear_cookies_between_cycles=args.clear_cookies,
        device_type=args.device,
        mobile_device=args.mobile_device
    )

    try:
        viewer.run(
            video_urls=video_urls,
            watch_time=args.time,
            shuffle=args.shuffle,
            max_videos=args.max,
            cycles=args.cycles,
            delay_between_cycles=args.delay_between_cycles
        )
    except KeyboardInterrupt:
        print("\n\nПрограмма остановлена пользователем")
        return 0
    except Exception as e:
        print(f"\nКритическая ошибка: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())