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

# Настройка кодировки для Windows
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class RuTubeViewer:
    def __init__(self, gui_mode: bool = True, incognito: bool = True,
                 chromedriver_path: Optional[str] = None):
        """
        Инициализация RuTube просмотрщика

        Args:
            gui_mode (bool): True - с графическим интерфейсом, False - без графического интерфейса (headless)
            incognito (bool): Использовать режим инкогнито
            chromedriver_path (str): Путь к ChromeDriver (опционально)
        """
        self.setup_logging()
        self.gui_mode = gui_mode
        self.incognito = incognito

        # Определяем путь к ChromeDriver
        self.chromedriver_path = self._determine_chromedriver_path(chromedriver_path)

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

    def _determine_chromedriver_path(self, custom_path: Optional[str] = None) -> Optional[str]:
        """
        Определение пути к ChromeDriver

        Args:
            custom_path: Пользовательский путь к ChromeDriver

        Returns:
            Optional[str]: Путь к ChromeDriver или None если не найден
        """
        # 1. Используем пользовательский путь если указан
        if custom_path:
            if os.path.exists(custom_path):
                self.logger.info(f"Используется указанный ChromeDriver: {custom_path}")
                return custom_path
            else:
                self.logger.warning(f"Указанный ChromeDriver не найден: {custom_path}")

        # 2. Ищем в каталоге selenium-server
        selenium_server_paths = [
            # Относительно текущего файла
            Path(__file__).parent / "selenium-server" / "chromedriver.exe",  # Windows
            Path(__file__).parent / "selenium-server" / "chromedriver",  # Linux/Mac

            # Относительно рабочей директории
            Path.cwd() / "selenium-server" / "chromedriver.exe",
            Path.cwd() / "selenium-server" / "chromedriver",

            # В самой директории selenium-server (если скрипт запущен из нее)
            Path.cwd() / "chromedriver.exe",
            Path.cwd() / "chromedriver",
        ]

        for path in selenium_server_paths:
            if path.exists():
                self.logger.info(f"Найден ChromeDriver в selenium-server: {path}")
                return str(path)

        # 3. Проверяем переменную окружения
        env_path = os.environ.get('CHROMEDRIVER_PATH')
        if env_path and os.path.exists(env_path):
            self.logger.info(f"Найден ChromeDriver в переменной окружения: {env_path}")
            return env_path

        # 4. Ищем в системном PATH
        import shutil
        system_path = shutil.which("chromedriver") or shutil.which("chromedriver.exe")
        if system_path:
            self.logger.info(f"Найден ChromeDriver в системном PATH: {system_path}")
            return system_path

        self.logger.warning("ChromeDriver не найден. Будет использован webdriver-manager или системный драйвер.")
        return None

    def setup_logging(self):
        """Настройка логирования с поддержкой Unicode"""

        # Создаем форматтер с безопасными символами для Windows
        class SafeFormatter(logging.Formatter):
            def format(self, record):
                # Заменяем Unicode символы на ASCII аналоги для Windows
                if sys.platform == "win32":
                    message = record.getMessage()
                    # Заменяем проблемные символы
                    message = message.replace('✓', '[OK]').replace('✗', '[ERROR]')
                    record.msg = message
                return super().format(record)

        # Настраиваем обработчик для файла
        file_handler = logging.FileHandler('rutube_viewer.log', encoding='utf-8')
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)

        # Настраиваем обработчик для консоли
        console_handler = logging.StreamHandler()
        console_formatter = SafeFormatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)

        # Настраиваем логгер
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.handlers = []  # Очищаем существующие обработчики
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.propagate = False

    def create_driver(self):
        """Создание и настройка драйвера Selenium с выбранным режимом"""
        try:
            chrome_options = Options()

            # Базовые опции
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            # Режим инкогнито
            if self.incognito:
                chrome_options.add_argument("--incognito")
                self.logger.info("Режим инкогнито: ВКЛЮЧЕН")
            else:
                self.logger.info("Режим инкогнито: ВЫКЛЮЧЕН")

            # Режим графического интерфейса
            if not self.gui_mode:
                # Headless режим (без GUI)
                chrome_options.add_argument("--headless=new")  # Новый headless режим Chrome
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                self.logger.info("Режим отображения: БЕЗ ГРАФИЧЕСКОГО ИНТЕРФЕЙСА (Headless)")
            else:
                # Графический режим (с GUI)
                chrome_options.add_argument("--start-maximized")  # Запуск в максимизированном окне
                self.logger.info("Режим отображения: С ГРАФИЧЕСКИМ ИНТЕРФЕЙСОМ")

            # Дополнительные опции для более естественного поведения
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--lang=ru-RU")

            # Опции для улучшения производительности
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")

            # Случайный User-Agent
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ]
            selected_ua = random.choice(user_agents)
            chrome_options.add_argument(f'user-agent={selected_ua}')
            self.logger.debug(f"Используется User-Agent: {selected_ua}")

            # Для headless режима добавляем фейковые параметры для обхода обнаружения
            if not self.gui_mode:
                chrome_options.add_argument("--disable-blink-features=AutomationControlled")
                chrome_options.add_argument("--disable-features=VizDisplayCompositor")

            # Создаем драйвер с использованием найденного пути
            if self.chromedriver_path and os.path.exists(self.chromedriver_path):
                try:
                    # Для Linux/Mac устанавливаем права на выполнение
                    if sys.platform != 'win32':
                        try:
                            os.chmod(self.chromedriver_path, 0o755)
                            self.logger.debug(f"Установлены права на выполнение для: {self.chromedriver_path}")
                        except:
                            pass

                    service = Service(executable_path=self.chromedriver_path)
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    self.logger.info(f"Драйвер создан с использованием: {self.chromedriver_path}")

                except Exception as e:
                    self.logger.warning(f"Не удалось создать драйвер с указанным путем: {e}")
                    self.logger.info("Пробуем альтернативные методы...")
                    self.chromedriver_path = None  # Сбрасываем путь для использования альтернативных методов

            # Если путь не указан или не сработал, используем альтернативные методы
            if not self.driver:
                try:
                    # Пробуем использовать ChromeDriver Manager для автоматической загрузки драйвера
                    try:
                        from webdriver_manager.chrome import ChromeDriverManager
                        from selenium.webdriver.chrome.service import Service as ChromeService

                        service = ChromeService(ChromeDriverManager().install())
                        self.driver = webdriver.Chrome(service=service, options=chrome_options)
                        self.logger.info("Драйвер загружен через ChromeDriver Manager")

                    except ImportError:
                        # Если webdriver_manager не установлен, используем стандартный путь
                        self.logger.info("Используется системный ChromeDriver")
                        self.driver = webdriver.Chrome(options=chrome_options)

                except Exception as driver_error:
                    self.logger.warning(f"Ошибка при создании драйвера: {driver_error}")
                    self.logger.info("Пробуем альтернативный метод...")
                    self.driver = webdriver.Chrome(options=chrome_options)

            # Скрываем автоматизацию
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": self.driver.execute_script("return navigator.userAgent").replace("Headless", "")
            })

            # Для headless режима добавляем дополнительные меры
            if not self.gui_mode:
                self.driver.execute_script("""
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['ru-RU', 'ru', 'en-US', 'en']
                    });
                """)

            self.logger.info("Драйвер успешно создан")
            self.logger.info(f"Настройки: GUI={self.gui_mode}, Инкогнито={self.incognito}")
            if self.chromedriver_path:
                self.logger.info(f"Используется ChromeDriver: {self.chromedriver_path}")
            return True

        except Exception as e:
            self.logger.error(f"Ошибка при создании драйвера: {str(e)}")
            self.logger.error("Проверьте, что установлены:")
            self.logger.error("1. Google Chrome последней версии")
            self.logger.error("2. ChromeDriver (совместимый с версией Chrome)")
            self.logger.error("3. Selenium: pip install selenium")
            self.logger.error("4. Webdriver Manager (опционально): pip install webdriver-manager")
            return False

    def display_mode_info(self):
        """Вывод информации о текущем режиме работы"""
        # Используем ASCII символы для совместимости с Windows
        if sys.platform == "win32":
            mode_info = """
====================================================
                    РЕЖИМ РАБОТЫ
====================================================
"""
            if self.gui_mode:
                mode_info += """
  ГРАФИЧЕСКИЙ РЕЖИМ (С ОКНОМ БРАУЗЕРА)

  • Браузер будет отображаться на экране
  • Вы сможете видеть процесс просмотра
  • Полезно для отладки и тестирования
"""
            else:
                mode_info += """
  HEADLESS РЕЖИМ (БЕЗ ОКНА БРАУЗЕРА)

  • Браузер работает в фоновом режиме
  • Не отображается на экране
  • Меньше потребление ресурсов
  • Подходит для серверов и автоматизации
"""

            mode_info += """
"""
            if self.incognito:
                mode_info += """
  РЕЖИМ ИНКОГНИТО: ВКЛЮЧЕН
"""
            else:
                mode_info += """
  РЕЖИМ ИНКОГНИТО: ВЫКЛЮЧЕН
"""

            if self.chromedriver_path:
                driver_name = os.path.basename(self.chromedriver_path)
                mode_info += f"""
  ChromeDriver: {driver_name}
"""
            else:
                mode_info += """
  ChromeDriver: автоматический
"""

            mode_info += """
====================================================
"""
        else:
            # Для Linux/Mac используем Unicode символы
            mode_info = """
╔════════════════════════════════════════════════════════════╗
║                    РЕЖИМ РАБОТЫ                            ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║"""

            if self.gui_mode:
                mode_info += """
║  📺  ГРАФИЧЕСКИЙ РЕЖИМ (С ОКНОМ БРАУЗЕРА)                  ║
║                                                            ║
║  • Браузер будет отображаться на экране                    ║
║  • Вы сможете видеть процесс просмотра                     ║
║  • Полезно для отладки и тестирования                      ║"""
            else:
                mode_info += """
║  🖥️   HEADLESS РЕЖИМ (БЕЗ ОКНА БРАУЗЕРА)                   ║
║                                                            ║
║  • Браузер работает в фоновом режиме                       ║
║  • Не отображается на экране                               ║
║  • Меньше потребление ресурсов                             ║
║  • Подходит для серверов и автоматизации                   ║"""

            mode_info += """
║                                                            ║"""

            if self.incognito:
                mode_info += """
║  🔒  РЕЖИМ ИНКОГНИТО: ВКЛЮЧЕН                              ║"""
            else:
                mode_info += """
║  🔓  РЕЖИМ ИНКОГНИТО: ВЫКЛЮЧЕН                             ║"""

            if self.chromedriver_path:
                driver_name = os.path.basename(self.chromedriver_path)
                mode_info += f"""
║                                                            ║
║  🗂️   ChromeDriver: {driver_name:<35} ║"""
            else:
                mode_info += """
║                                                            ║
║  🗂️   ChromeDriver: автоматический                       ║"""

            mode_info += """
║                                                            ║
╚════════════════════════════════════════════════════════════╝
"""

        print(mode_info)

    def wait_random_time(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Случайная задержка для имитации человеческого поведения"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def simulate_human_interaction(self):
        """Имитация человеческого взаимодействия со страницей"""
        try:
            # В headless режиме имитация отличается
            if not self.gui_mode:
                # В headless режиме просто делаем случайные паузы
                if random.random() < 0.3:
                    time.sleep(random.uniform(0.5, 2))
                return

            # Только в GUI режиме делаем реальные движения мыши
            actions = ActionChains(self.driver)

            # Получаем размеры окна
            window_size = self.driver.get_window_size()
            width = window_size['width']
            height = window_size['height']

            # Случайные движения мыши
            for _ in range(random.randint(2, 5)):
                x_offset = random.randint(100, width - 100)
                y_offset = random.randint(100, height - 100)
                actions.move_by_offset(x_offset, y_offset)
                actions.pause(random.uniform(0.1, 0.5))

            # Прокрутка страницы
            scroll_amount = random.randint(200, 800)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            self.wait_random_time(0.5, 1.5)

            actions.perform()

        except Exception as e:
            self.logger.debug(f"Ошибка при имитации взаимодействия: {e}")

    def accept_cookies_if_present(self):
        """Принятие куки, если появилось окно"""
        try:
            # Попробуем найти кнопку принятия куки (селекторы могут меняться)
            cookie_selectors = [
                "button[class*='cookie']",
                "button[class*='Cookie']",
                "button[data-testid*='cookie']",
                "div[class*='cookie'] button",
                "//button[contains(text(), 'Принять')]",
                "//button[contains(text(), 'Согласен')]",
                "//button[contains(text(), 'OK')]",
                "//button[contains(text(), 'Принимаю')]"
            ]

            for selector in cookie_selectors:
                try:
                    if selector.startswith("//"):
                        element = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        element = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )

                    if element and element.is_displayed():
                        element.click()
                        self.logger.info("Куки приняты")
                        self.wait_random_time(1, 2)
                        return True
                except:
                    continue

        except Exception as e:
            self.logger.debug(f"Окно куки не найдено или ошибка: {e}")

        return False

    def watch_video(self, video_url: str, watch_time: int = 30):
        """
        Просмотр видео на RuTube

        Args:
            video_url (str): URL видео на RuTube
            watch_time (int): Время просмотра в секундах

        Returns:
            bool: Успешно ли было просмотрено видео
        """
        try:
            self.logger.info(f"Начинаем просмотр видео: {video_url}")
            self.logger.info(f"Запланированное время просмотра: {watch_time} секунд")

            # Переходим на страницу видео
            self.driver.get(video_url)
            self.wait_random_time(2, 4)

            # Принимаем куки, если есть
            self.accept_cookies_if_present()

            # Ждем загрузки страницы
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Находим видео элемент (селекторы для RuTube)
            video_selectors = [
                "video",
                "iframe[src*='rutube']",
                "div[class*='video-player']",
                "div[class*='player']",
                "#video-player",
                ".video-js",
                "video[class*='player']",
                "video[class*='video']"
            ]

            video_element = None
            for selector in video_selectors:
                try:
                    if selector == "video":
                        video_element = self.driver.find_element(By.TAG_NAME, "video")
                    elif selector.startswith("#") or selector.startswith("."):
                        video_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    else:
                        video_element = self.driver.find_element(By.CSS_SELECTOR, selector)

                    if video_element:
                        self.logger.info(f"Видео элемент найден с селектором: {selector}")
                        break
                except:
                    continue

            # Альтернативный метод поиска видео
            if not video_element:
                self.logger.warning("Видео элемент не найден стандартными методами, пробуем альтернативные...")

                # Попробуем найти через iframe
                try:
                    iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                    for iframe in iframes:
                        try:
                            src = iframe.get_attribute("src")
                            if src and ("rutube" in src or "video" in src):
                                self.driver.switch_to.frame(iframe)
                                video_element = self.driver.find_element(By.TAG_NAME, "video")
                                self.driver.switch_to.default_content()
                                break
                        except:
                            self.driver.switch_to.default_content()
                            continue
                except:
                    pass

            if video_element:
                self.logger.info("Видео элемент найден")

                # Пытаемся начать воспроизведение
                try:
                    self.driver.execute_script("arguments[0].play();", video_element)
                    self.logger.info("Воспроизведение начато через JavaScript")
                    self.wait_random_time(2, 3)
                except:
                    # Если скрипт не сработал, пытаемся кликнуть на видео
                    try:
                        video_element.click()
                        self.logger.info("Клик на видео выполнен")
                        self.wait_random_time(2, 3)
                    except:
                        # Пробуем кликнуть через JavaScript
                        try:
                            self.driver.execute_script("arguments[0].click();", video_element)
                            self.logger.info("Клик выполнен через JavaScript")
                        except:
                            self.logger.warning("Не удалось начать воспроизведение автоматически")
                            # Все равно продолжаем "просмотр"

                # Ждем немного перед имитацией взаимодействия
                self.wait_random_time(2, 4)

                # Время начала просмотра
                start_time = time.time()
                elapsed_time = 0
                self.last_progress = 0

                # Цикл просмотра
                while elapsed_time < watch_time:
                    # Имитация человеческого поведения
                    if random.random() < 0.3:  # 30% вероятность взаимодействия
                        self.simulate_human_interaction()

                    # Случайная прокрутка
                    if random.random() < 0.2:  # 20% вероятность прокрутки
                        scroll_pos = random.randint(0, 1000)
                        self.driver.execute_script(f"window.scrollTo(0, {scroll_pos});")

                    # Обновляем прошедшее время
                    current_time = time.time()
                    elapsed_time = current_time - start_time

                    # Выводим прогресс каждые 10 секунд
                    progress = int(elapsed_time)
                    if progress > 0 and progress % 10 == 0 and progress != self.last_progress:
                        self.logger.info(f"Просмотрено {progress} из {watch_time} секунд")
                        self.last_progress = progress

                    # Случайная пауза
                    pause_time = random.uniform(1, 3)
                    time.sleep(pause_time)

                self.logger.info(f"Просмотр видео завершен: {video_url}")
                return True

            else:
                self.logger.warning(f"Не удалось найти видео элемент для {video_url}")
                # Даже если не нашли видео, все равно "просматриваем" страницу указанное время
                self.logger.info("Симулируем просмотр страницы...")
                time.sleep(watch_time)
                return True

        except TimeoutException:
            self.logger.error(f"Таймаут при загрузке видео: {video_url}")
            return False
        except WebDriverException as e:
            self.logger.error(f"Ошибка WebDriver при просмотре {video_url}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при просмотре {video_url}: {e}")
            return False

    def process_video_list(self, video_urls: List[str], watch_time: int = 30,
                           shuffle: bool = False, max_videos: Optional[int] = None):
        """
        Обработка списка видео

        Args:
            video_urls (List[str]): Список URL видео
            watch_time (int): Время просмотра каждого видео в секундах
            shuffle (bool): Перемешивать ли список видео
            max_videos (Optional[int]): Максимальное количество видео для просмотра
        """
        if shuffle:
            random.shuffle(video_urls)
            self.logger.info("Список видео перемешан")

        if max_videos:
            video_urls = video_urls[:max_videos]
            self.logger.info(f"Ограничение на {max_videos} видео")

        self.stats['total_videos'] = len(video_urls)

        for i, video_url in enumerate(video_urls, 1):
            self.last_progress = 0
            self.logger.info(f"\n{'=' * 60}")
            self.logger.info(f"ВИДЕО {i}/{len(video_urls)}")
            self.logger.info(f"URL: {video_url}")
            self.logger.info(f"{'=' * 60}")

            # Проверяем, что это действительно ссылка на RuTube
            if "rutube.ru" not in video_url and "rutube.pl" not in video_url and "rutube.io" not in video_url:
                self.logger.warning(f"Ссылка {video_url} не похожа на RuTube, пропускаем")
                self.stats['failed_views'] += 1
                continue

            # Случайная пауза между видео
            if i > 1:
                pause_time = random.randint(5, 15)
                self.logger.info(f"Пауза между видео: {pause_time} секунд")
                time.sleep(pause_time)

            # Просмотр видео
            success = self.watch_video(video_url, watch_time)

            # Обновляем статистику
            video_stat = {
                'url': video_url,
                'timestamp': datetime.now().isoformat(),
                'watch_time': watch_time,
                'success': success,
                'video_number': i
            }
            self.stats['videos_history'].append(video_stat)

            if success:
                self.stats['successful_views'] += 1
                self.stats['total_watch_time'] += watch_time
                # Используем безопасные символы для Windows
                if sys.platform == "win32":
                    self.logger.info("[OK] Видео успешно просмотрено")
                else:
                    self.logger.info("✓ Видео успешно просмотрено")
            else:
                self.stats['failed_views'] += 1
                # Используем безопасные символы для Windows
                if sys.platform == "win32":
                    self.logger.error("[ERROR] Ошибка при просмотре видео")
                else:
                    self.logger.error("✗ Ошибка при просмотре видео")

            # Сохраняем статистику после каждого видео
            self.save_stats()

    def save_stats(self):
        """Сохранение статистики в файл"""
        try:
            stats_file = 'viewer_stats.json'
            self.stats['settings']['end_time'] = datetime.now().isoformat()

            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"Статистика сохранена в {stats_file}")
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении статистики: {e}")

    def load_videos_from_file(self, filepath: str) -> List[str]:
        """
        Загрузка списка видео из файла

        Args:
            filepath (str): Путь к файлу со списком видео

        Returns:
            List[str]: Список URL видео
        """
        try:
            if not os.path.exists(filepath):
                self.logger.error(f"Файл не найден: {filepath}")
                return []

            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Разные форматы файлов
            urls = []

            # Построчное чтение
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):  # Пропускаем пустые строки и комментарии
                    # Удаляем возможные кавычки
                    line = line.replace('"', '').replace("'", "")
                    urls.append(line)

            # Фильтруем только rutube ссылки
            rutube_urls = [url for url in urls if
                           any(domain in url for domain in ['rutube.ru', 'rutube.pl', 'rutube.io'])]

            if len(rutube_urls) < len(urls):
                self.logger.warning(f"Отфильтровано {len(urls) - len(rutube_urls)} не-RuTube ссылок")

            self.logger.info(f"Загружено {len(rutube_urls)} RuTube видео из файла {filepath}")
            return rutube_urls

        except Exception as e:
            self.logger.error(f"Ошибка при загрузке файла {filepath}: {e}")
            return []

    def run(self, video_urls: Union[str, List[str]], watch_time: int = 30,
            shuffle: bool = False, max_videos: Optional[int] = None):
        """
        Основной метод запуска просмотра

        Args:
            video_urls (Union[str, List[str]]): Список URL видео или один URL
            watch_time (int): Время просмотра каждого видео
            shuffle (bool): Перемешивать ли список видео
            max_videos (Optional[int]): Максимальное количество видео
        """
        try:
            # Выводим информацию о режиме работы
            self.display_mode_info()

            # Создаем драйвер
            if not self.create_driver():
                self.logger.error("Не удалось создать драйвер")
                return

            # Если передан один URL, делаем из него список
            if isinstance(video_urls, str):
                video_urls = [video_urls]

            # Запускаем просмотр
            self.process_video_list(video_urls, watch_time, shuffle, max_videos)

            # Выводим итоговую статистику
            self.print_summary()

        except KeyboardInterrupt:
            self.logger.info("\nПрограмма остановлена пользователем (Ctrl+C)")
            self.print_summary()
        except Exception as e:
            self.logger.error(f"Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.driver:
                self.logger.info("Закрываем браузер...")
                try:
                    self.driver.quit()
                except:
                    pass

    def print_summary(self):
        """Вывод итоговой статистики"""
        print("\n" + "=" * 60)
        print("ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 60)
        print(f"Всего видео в списке: {self.stats['total_videos']}")

        # Используем безопасные символы для Windows
        if sys.platform == "win32":
            print(f"Успешно просмотрено: {self.stats['successful_views']} [OK]")
            print(f"Не удалось просмотреть: {self.stats['failed_views']} [ERROR]")
        else:
            print(f"Успешно просмотрено: {self.stats['successful_views']} ✓")
            print(f"Не удалось просмотреть: {self.stats['failed_views']} ✗")

        total_seconds = self.stats['total_watch_time']
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        print(f"Общее время просмотра: {hours}ч {minutes}м {seconds}с")
        print(f"Режим GUI: {'ВКЛ' if self.gui_mode else 'ВЫКЛ'}")
        print(f"Режим инкогнито: {'ВКЛ' if self.incognito else 'ВЫКЛ'}")

        if self.chromedriver_path:
            driver_name = os.path.basename(self.chromedriver_path)
            print(f"Использован ChromeDriver: {driver_name}")

        if self.stats['videos_history']:
            print(f"\nПоследние просмотренные видео:")
            for video in self.stats['videos_history'][-5:]:  # Последние 5 видео
                status = "[OK]" if video.get('success') else "[ERROR]"
                print(f"  {status} {video.get('url', 'N/A')}")

        print(f"\nСтатистика сохранена в viewer_stats.json")
        print("=" * 60)


def main():
    # Настройка кодировки для Windows
    if sys.platform == "win32":
        os.system('chcp 65001 > nul')  # Устанавливаем UTF-8 кодировку в консоли Windows

    parser = argparse.ArgumentParser(
        description='Автоматизированный просмотр видео на RuTube',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # С автоматическим поиском ChromeDriver в selenium-server
  python rutube_viewer.py --file videos.txt --time 60 --gui

  # С указанием пути к ChromeDriver
  python rutube_viewer.py --file videos.txt --chromedriver "./selenium-server/chromedriver.exe"

  # Headless режим
  python rutube_viewer.py --urls "https://rutube.ru/video/123/" --time 30 --no-gui

  # С перемешиванием и ограничением
  python rutube_viewer.py --file list.txt --no-gui --shuffle --max 10

Формат файла со списком видео:
  # Это комментарий
  https://rutube.ru/video/1234567890abcdef/
  https://rutube.ru/video/0987654321/

Структура проекта:
  ваш_проект/
  ├── rutube_viewer.py
  ├── selenium-server/           # Каталог для ChromeDriver
  │   ├── chromedriver.exe       # Windows
  │   └── chromedriver           # Linux/Mac
  ├── videos.txt
  └── requirements.txt
        """
    )

    # Основные аргументы
    parser.add_argument('--urls', nargs='+', help='Список URL видео на RuTube')
    parser.add_argument('--file', type=str, help='Файл со списком URL видео (по одному на строку)')
    parser.add_argument('--time', type=int, default=30,
                        help='Время просмотра каждого видео в секундах (по умолчанию: 30)')

    # Режимы работы
    parser.add_argument('--gui', action='store_true', default=True,
                        help='Запуск с графическим интерфейсом (окно браузера видно) (по умолчанию: ВКЛ)')
    parser.add_argument('--no-gui', action='store_false', dest='gui',
                        help='Запуск без графического интерфейса (headless режим)')

    # Путь к ChromeDriver
    parser.add_argument('--chromedriver', '--driver', type=str,
                        help='Путь к исполняемому файлу ChromeDriver (опционально)')

    # Дополнительные опции
    parser.add_argument('--incognito', action='store_true', default=True,
                        help='Использовать режим инкогнито (по умолчанию: ВКЛ)')
    parser.add_argument('--no-incognito', action='store_false', dest='incognito',
                        help='Не использовать режим инкогнито')
    parser.add_argument('--shuffle', action='store_true', help='Перемешать список видео')
    parser.add_argument('--max', type=int, help='Максимальное количество видео для просмотра')

    args = parser.parse_args()

    # Проверяем наличие URL
    video_urls = []

    if args.urls:
        video_urls.extend(args.urls)
        print(f"Загружено {len(args.urls)} видео из аргументов командной строки")

    if args.file:
        # Создаем временный объект для загрузки файла
        temp_viewer = RuTubeViewer(gui_mode=args.gui, incognito=args.incognito,
                                   chromedriver_path=args.chromedriver)
        loaded_urls = temp_viewer.load_videos_from_file(args.file)
        video_urls.extend(loaded_urls)

    if not video_urls:
        print("Ошибка: Не указаны видео для просмотра!")
        print("Используйте --urls для указания ссылок или --file для загрузки из файла")
        print("\nПримеры:")
        print("  python rutube_viewer.py --file videos.txt")
        print("  python rutube_viewer.py --urls \"https://rutube.ru/video/123/\"")
        return

    print(f"\nЗагружено всего: {len(video_urls)} видео")
    print(f"Время просмотра каждого видео: {args.time} секунд")

    # Создаем и запускаем просмотрщик
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