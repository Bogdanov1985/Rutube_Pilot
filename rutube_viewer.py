import time
import random
import argparse
import json
import os
import sys
import logging
import platform
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


class AntiDetection:
    """Класс для продвинутого скрытия автоматизации"""

    @staticmethod
    def get_stealth_scripts() -> List[str]:
        """Возвращает список скриптов для скрытия автоматизации"""
        return [
            # 1. Скрытие webdriver флага
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """,

            # 2. Переопределение window.chrome
            """
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            """,

            # 3. Переопределение permissions
            """
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
            """,

            # 4. Скрытие automation контролей
            """
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    rtt: 50,
                    downlink: 10,
                    effectiveType: '4g',
                    saveData: false,
                    type: 'wifi'
                })
            });
            """,

            # 5. Переопределение plugins
            """
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: Plugin}},
                    {0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: Plugin}}
                ]
            });
            """,

            # 6. Переопределение languages
            """
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en']
            });
            """,

            # 7. Скрытие automation свойства
            """
            Object.defineProperty(navigator, 'automation', {
                get: () => undefined
            });
            """,

            # 8. Скрытие window.document.documentElement.webdriver
            """
            Object.defineProperty(document.documentElement, 'webdriver', {
                get: () => undefined
            });
            """,

            # 9. Скрытие selenium
            """
            window.navigator.selenium = undefined;
            window.navigator.__proto__.selenium = undefined;
            """,

            # 10. Переопределение userAgent
            """
            const userAgent = navigator.userAgent;
            const patchedUserAgent = userAgent.replace(/HeadlessChrome\\//, 'Chrome/');
            Object.defineProperty(navigator, 'userAgent', {
                get: () => patchedUserAgent
            });
            """,

            # 11. Скрытие WebGL
            """
            const getParameter = WebGLRenderingContext.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter(parameter);
            };
            """,

            # 12. Скрытие Canvas fingerprinting
            """
            const originalGetContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(type, attributes) {
                const context = originalGetContext.call(this, type, attributes);
                if (context && type === '2d') {
                    const originalFillText = context.fillText;
                    context.fillText = function(...args) {
                        if (args[0] === 'window._Selenium_IDE_Recorder') return;
                        return originalFillText.apply(this, args);
                    };
                }
                return context;
            };
            """,

            # 13. Скрытие Audio fingerprinting
            """
            if (window.AudioContext) {
                const originalCreateOscillator = AudioContext.prototype.createOscillator;
                AudioContext.prototype.createOscillator = function() {
                    const oscillator = originalCreateOscillator.apply(this, arguments);
                    const originalStart = oscillator.start;
                    oscillator.start = function(...args) {
                        if (args[0] === 0) return;
                        return originalStart.apply(this, args);
                    };
                    return oscillator;
                };
            }
            """,

            # 14. Скрытие navigator.deviceMemory
            """
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8
            });
            """,

            # 15. Скрытие navigator.hardwareConcurrency
            """
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 4
            });
            """,

            # 16. Скрытие screen dimensions
            """
            Object.defineProperty(window.screen, 'width', {
                get: () => 1920
            });
            Object.defineProperty(window.screen, 'height', {
                get: () => 1080
            });
            Object.defineProperty(window.screen, 'availWidth', {
                get: () => 1920
            });
            Object.defineProperty(window.screen, 'availHeight', {
                get: () => 1080
            });
            """,

            # 17. Скрытие timezone
            """
            Object.defineProperty(Intl.DateTimeFormat.prototype, 'resolvedOptions', {
                get: function() {
                    const original = this.__proto__.__proto__.resolvedOptions;
                    const result = original.call(this);
                    result.timeZone = 'Europe/Moscow';
                    return result;
                }
            });
            """,

            # 18. Скрытие WebDriver свойств
            """
            Object.keys(window).forEach(key => {
                if (/\\$[a-z]\\d_/i.test(key)) {
                    delete window[key];
                }
            });
            """,

            # 19. Скрытие chrome.csi
            """
            if (window.chrome && !window.chrome.csi) {
                window.chrome.csi = function() {
                    return {
                        onloadT: Date.now(),
                        startE: Date.now() - Math.random() * 10000,
                        pageT: Date.now() - Math.random() * 5000,
                        tran: 15
                    };
                };
            }
            """,

            # 20. Скрытие chrome.loadTimes
            """
            if (window.chrome && !window.chrome.loadTimes) {
                window.chrome.loadTimes = function() {
                    return {
                        requestTime: Date.now() - Math.random() * 5000,
                        startLoadTime: Date.now() - Math.random() * 5000,
                        commitLoadTime: Date.now() - Math.random() * 3000,
                        finishDocumentLoadTime: Date.now() - Math.random() * 2000,
                        firstPaintTime: Date.now() - Math.random() * 1000,
                        firstPaintAfterLoadTime: 0,
                        navigationType: 'Other',
                        wasFetchedViaSpdy: true,
                        wasNpnNegotiated: true,
                        npnNegotiatedProtocol: 'h2',
                        connectionInfo: 'h2'
                    };
                };
            }
            """
        ]

    @staticmethod
    def get_human_mouse_movements(start_x, start_y, end_x, end_y, steps=20):
        """Генерирует человеческие движения мыши"""
        points = []
        for i in range(steps + 1):
            t = i / steps
            # Кривая Безье для естественного движения
            x = start_x + (end_x - start_x) * t + random.randint(-2, 2)
            y = start_y + (end_y - start_y) * t + random.randint(-2, 2)
            points.append((int(x), int(y)))
        return points

    @staticmethod
    def get_human_typing_pattern(text):
        """Генерирует человеческий паттерн печати"""
        delays = []
        for char in text:
            # Базовая задержка + случайная вариация
            base_delay = random.uniform(0.08, 0.15)
            variation = random.uniform(-0.03, 0.03)
            # Иногда делаем паузу (симулируя размышление)
            if random.random() < 0.05:
                base_delay += random.uniform(0.3, 0.8)
            delays.append(max(0.01, base_delay + variation))
        return delays


class RuTubeViewer:
    """Оптимизированный просмотрщик видео RuTube"""

    def __init__(self, gui_mode: bool = True, incognito: bool = True,
                 chromedriver_path: Optional[str] = None,
                 mute_audio: bool = True, stealth_mode: bool = True):
        self._setup_directories()
        self._setup_logging()

        self.gui_mode = gui_mode
        self.incognito = incognito
        self.mute_audio = mute_audio
        self.stealth_mode = stealth_mode
        self.chromedriver_path = self._resolve_chromedriver_path(chromedriver_path)
        self.driver = None
        self.anti_detection = AntiDetection()

        self._init_stats()

    def _setup_directories(self):
        """Создание необходимых директорий"""
        LOG_DIR.mkdir(exist_ok=True)

    def _setup_logging(self):
        """Настройка логирования с оптимизацией"""
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
            'gui_mode': self.gui_mode,
            'incognito': self.incognito,
            'mute_audio': self.mute_audio,
            'stealth_mode': self.stealth_mode,
            'start_time': datetime.now().isoformat()
        }

    def _resolve_chromedriver_path(self, custom_path: Optional[str]) -> Optional[str]:
        """Определение пути к ChromeDriver"""
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

        # Приоритет 5: webdriver-manager (будет использован позже)
        self.logger.warning("ChromeDriver не найден. Будет использован webdriver-manager.")
        return None

    def _create_chrome_options(self) -> Options:
        """Создание настроек Chrome с оптимизацией"""
        options = Options()

        # Базовые опции анти-детекта (всегда применяются)
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Дополнительные опции для stealth режима
        if self.stealth_mode:
            options.add_argument("--disable-logging")
            options.add_argument("--log-level=3")
            options.add_argument("--silent")
            options.add_experimental_option("excludeSwitches", [
                "enable-automation",
                "enable-logging",
                "disable-background-networking"
            ])

            # Более агрессивное скрытие
            options.add_argument("--disable-features=UserAgentClientHint")
            options.add_argument("--disable-client-side-phishing-detection")
            options.add_argument("--disable-component-update")
            options.add_argument("--disable-default-apps")
            options.add_argument("--disable-domain-reliability")
            options.add_argument("--disable-sync")
            options.add_argument("--metrics-recording-only")
            options.add_argument("--no-first-run")
            options.add_argument("--safebrowsing-disable-auto-update")
            options.add_argument("--password-store=basic")
            options.add_argument("--use-mock-keychain")

            # Опции для маскировки под обычный браузер
            options.add_argument("--disable-features=site-per-process")
            options.add_argument("--disable-web-security")
            options.add_argument("--allow-running-insecure-content")

            # Убираем признаки автоматизации
            options.add_argument("--disable-blink-features")
            options.add_argument("--disable-features=TranslateUI")
            options.add_argument("--disable-features=MediaRouter")

        # Дополнительные опции для скрытия автоматизации
        options.add_experimental_option('prefs', {
            'credentials_enable_service': False,
            'profile.password_manager_enabled': False,
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_setting_values.geolocation': 2,
            'profile.managed_default_content_settings.images': 1,
            'profile.default_content_setting_values.cookies': 1,
            'profile.default_content_setting_values.javascript': 1,
            'profile.default_content_setting_values.popups': 2,
            'intl.accept_languages': 'ru-RU,ru',
        })

        # Режимы
        if self.incognito:
            options.add_argument("--incognito")

        if not self.gui_mode:
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")

            # Дополнительные опции для headless режима
            if self.stealth_mode:
                options.add_argument("--disable-software-rasterizer")
                options.add_argument("--disable-webgl")
                options.add_argument("--disable-features=VizDisplayCompositor")
        else:
            options.add_argument("--start-maximized")
            options.add_argument("--disable-infobars")

        # Дополнительные опции (важные для функциональности)
        options.add_argument("--disable-notifications")
        options.add_argument("--lang=ru-RU")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-browser-side-navigation")
        options.add_argument("--disable-features=VizDisplayCompositor")

        # Улучшенный случайный User-Agent
        user_agents = self._get_realistic_user_agents()
        selected_ua = random.choice(user_agents)
        options.add_argument(f'user-agent={selected_ua}')

        # Дополнительные заголовки через экспериментальные опции
        if self.stealth_mode:
            options.add_experimental_option('prefs', {
                **options.experimental_options.get('prefs', {}),
                'hardware_acceleration_mode.enabled': True,
                'enable_do_not_track': True,
            })

        # Дополнительные языковые настройки
        options.add_argument("--accept-lang=ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7")
        options.add_argument("--accept-charset=utf-8")

        # Оптимизация сети и кэша
        options.add_argument("--disable-application-cache")
        options.add_argument("--media-cache-size=0")
        options.add_argument("--disk-cache-size=0")

        # Опции для улучшения стабильности
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")

        # Логирование выбранных настроек
        self.logger.debug(f"User-Agent: {selected_ua[:50]}...")
        self.logger.debug(f"Режим: {'GUI' if self.gui_mode else 'Headless'}")
        self.logger.debug(f"Инкогнито: {'Да' if self.incognito else 'Нет'}")
        self.logger.debug(f"Без звука: {'Да' if self.mute_audio else 'Нет'}")
        self.logger.debug(f"Stealth режим: {'Да' if self.stealth_mode else 'Нет'}")

        return options

    def _get_realistic_user_agents(self) -> List[str]:
        """Возвращает список реалистичных User-Agent строк"""
        # Современные реальные User-Agent
        return [
            # Windows + Chrome (самые популярные)
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',

            # macOS + Chrome
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',

            # Windows + Firefox
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0',

            # macOS + Safari
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',

            # Windows + Edge
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0',

            # Linux + Chrome
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        ]

    def _randomize_window(self):
        """Случайное изменение размера и позиции окна браузера с учетом stealth режима"""
        try:
            # Разные размеры окон для реалистичности
            if not self.gui_mode:
                # В headless режиме фиксированный размер
                self.driver.set_window_size(1920, 1080)
                self.logger.debug("Headless окно установлено: 1920x1080")
            else:
                # В GUI режиме случайный размер из популярных разрешений
                resolutions = [
                    (1920, 1080),  # Full HD - самый популярный
                    (1536, 864),  # MacBook-like
                    (1440, 900),  # Стандартное
                    (1366, 768),  # Ноутбуки
                    (1280, 720),  # HD
                    (1600, 900),  # HD+
                    (1680, 1050),  # WSXGA+
                ]

                width, height = random.choice(resolutions)

                # Случайная позиция (немного смещаем окно)
                max_x = 100
                max_y = 100
                x = random.randint(0, max_x)
                y = random.randint(0, max_y)

                self.driver.set_window_size(width, height)
                self.driver.set_window_position(x, y)
                self.logger.debug(f"GUI окно: {width}x{height} на позиции ({x},{y})")

        except Exception as e:
            self.logger.debug(f"Не удалось изменить размер окна: {e}")
            # Установим стандартный размер на случай ошибки
            try:
                self.driver.set_window_size(1920, 1080)
            except:
                pass

    def _apply_stealth_techniques(self):
        """Применяет техники stealth для скрытия автоматизации"""
        if not self.stealth_mode:
            return

        try:
            # 1. Инъекция stealth скриптов
            stealth_scripts = self.anti_detection.get_stealth_scripts()

            for i, script in enumerate(stealth_scripts):
                try:
                    self.driver.execute_script(script)
                    self.logger.debug(f"Применен stealth скрипт #{i + 1}")
                except Exception as e:
                    self.logger.debug(f"Ошибка применения stealth скрипта #{i + 1}: {e}")

            # 2. Удаление selenium свойств из window
            try:
                self.driver.execute_script("""
                    // Удаляем все переменные, которые могут указывать на selenium
                    const seleniumProps = [
                        '_selenium', 'callSelenium', '_Selenium_IDE_Recorder',
                        '__webdriver_script_fn', '__lastWatirAlert', '__lastWatirConfirm'
                    ];
                    seleniumProps.forEach(prop => {
                        try { delete window[prop]; } catch(e) {}
                    });

                    // Удаляем обработчики событий selenium
                    if (window._phantom) delete window._phantom;
                    if (window.callPhantom) delete window.callPhantom;
                """)
            except:
                pass

            # 3. Маскировка навигации
            try:
                self.driver.execute_script("""
                    // Скрываем признаки автоматической навигации
                    const originalPushState = history.pushState;
                    const originalReplaceState = history.replaceState;

                    history.pushState = function(state, title, url) {
                        setTimeout(() => {
                            originalPushState.apply(this, arguments);
                        }, Math.random() * 100 + 50);
                    };

                    history.replaceState = function(state, title, url) {
                        setTimeout(() => {
                            originalReplaceState.apply(this, arguments);
                        }, Math.random() * 100 + 50);
                    };
                """)
            except:
                pass

            self.logger.info("Применены stealth техники")

        except Exception as e:
            self.logger.error(f"Ошибка применения stealth техник: {e}")

    def create_driver(self) -> bool:
        """Оптимизированное создание драйвера с stealth режимом"""
        try:
            options = self._create_chrome_options()

            # Используем webdriver-manager для автоматического управления драйверами
            # или пользовательский путь
            if self.chromedriver_path and os.path.exists(self.chromedriver_path):
                service = ChromeService(executable_path=self.chromedriver_path)
                self.logger.info(f"Используется пользовательский ChromeDriver: {self.chromedriver_path}")
            else:
                service = ChromeService(ChromeDriverManager().install())
                self.logger.info("Драйвер создан через webdriver-manager")

            self.driver = webdriver.Chrome(service=service, options=options)

            # Случайное изменение размера и позиции окна
            self._randomize_window()

            # Применяем stealth техники
            self._apply_stealth_techniques()

            # Установка таймаутов с учетом stealth режима
            if self.stealth_mode:
                # Более реалистичные таймауты
                self.driver.set_page_load_timeout(random.randint(25, 40))
                self.driver.set_script_timeout(random.randint(20, 35))
                self.driver.implicitly_wait(random.randint(3, 7))
            else:
                self.driver.set_page_load_timeout(30)
                self.driver.set_script_timeout(30)
                self.driver.implicitly_wait(5)

            return True

        except Exception as e:
            self.logger.error(f"Ошибка при создании драйвера: {str(e)}")
            self.logger.error("Убедитесь, что установлен Google Chrome и есть интернет-соединение")
            return False

    def _random_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Оптимизированная случайная задержка с учетом stealth режима"""
        if self.stealth_mode:
            # Более реалистичные задержки с нормальным распределением
            mean = (min_seconds + max_seconds) / 2
            std = (max_seconds - min_seconds) / 4
            delay = random.normalvariate(mean, std)
            delay = max(min_seconds, min(max_seconds, delay))
            time.sleep(delay)
        else:
            time.sleep(random.uniform(min_seconds, max_seconds))

    def _human_like_move(self, element):
        """Человеко-подобное перемещение к элементу"""
        if not self.stealth_mode:
            return

        try:
            # Получаем координаты элемента
            location = element.location
            size = element.size

            # Вычисляем центр элемента
            center_x = location['x'] + size['width'] // 2
            center_y = location['y'] + size['height'] // 2

            # Генерируем человеческие движения
            movements = self.anti_detection.get_human_mouse_movements(
                0, 0, center_x, center_y, steps=random.randint(15, 25)
            )

            # Симулируем движение (в реальности мы не можем управлять мышью напрямую)
            # Но можем добавить небольшую задержку для имитации
            if movements:
                delay_per_step = random.uniform(0.01, 0.03)
                time.sleep(len(movements) * delay_per_step)

        except Exception as e:
            self.logger.debug(f"Ошибка при симуляции движения мыши: {e}")

    def _close_element_by_selectors(self, selectors: List[str], element_type: str = "попап") -> int:
        """Универсальный метод закрытия элементов по селекторам"""
        closed_count = 0

        for selector in selectors:
            try:
                is_xpath = selector.startswith("//")
                by = By.XPATH if is_xpath else By.CSS_SELECTOR

                elements = self.driver.find_elements(by, selector)
                for element in elements[:3]:  # Проверяем только первые 3 элемента
                    try:
                        if element.is_displayed() and element.is_enabled():
                            # Человеко-подобное движение в stealth режиме
                            if self.stealth_mode:
                                self._human_like_move(element)
                                self._random_delay(0.2, 0.5)

                            element.click()
                            closed_count += 1
                            self._random_delay(0.3, 0.7)
                            break
                    except:
                        # Пробуем JavaScript клик
                        try:
                            self.driver.execute_script("arguments[0].click();", element)
                            closed_count += 1
                            self._random_delay(0.3, 0.7)
                            break
                        except:
                            continue

            except Exception:
                continue

        if closed_count:
            self.logger.debug(f"Закрыто {closed_count} {element_type}(ов)")

        return closed_count

    def close_popups(self):
        """Оптимизированное закрытие попапов"""
        return self._close_element_by_selectors(POPUP_SELECTORS, "попап")

    def accept_cookies(self) -> bool:
        """Оптимизированное принятие куки"""
        try:
            for selector in COOKIE_SELECTORS:
                try:
                    is_xpath = selector.startswith("//")
                    by = By.XPATH if is_xpath else By.CSS_SELECTOR

                    element = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((by, selector))
                    )

                    if element and element.is_displayed():
                        # Человеко-подобное движение в stealth режиме
                        if self.stealth_mode:
                            self._human_like_move(element)
                            self._random_delay(0.3, 0.6)

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
        """Поиск видео элемента с оптимизацией"""
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

    def _find_and_click_button(self, selectors: List[str], button_type: str) -> bool:
        """Поиск и нажатие кнопки по селекторам"""
        for selector in selectors:
            try:
                buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for btn in buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        # Человеко-подобное движение в stealth режиме
                        if self.stealth_mode:
                            self._human_like_move(btn)
                            self._random_delay(0.2, 0.4)

                        try:
                            btn.click()
                            self.logger.debug(f"Кнопка '{button_type}' найдена и нажата")
                            self._random_delay(0.3, 0.7)
                            return True
                        except:
                            # Попробуем JavaScript клик
                            try:
                                self.driver.execute_script("arguments[0].click();", btn)
                                self.logger.debug(f"Кнопка '{button_type}' нажата через JS")
                                self._random_delay(0.3, 0.7)
                                return True
                            except:
                                continue
            except:
                continue

        # Также пробуем найти через XPath
        xpath_selectors = [
            f"//button[contains(@class, '{button_type.lower()}')]",
            f"//button[contains(text(), '{button_type}')]",
            f"//button[contains(@title, '{button_type.lower()}')]",
            f"//button[contains(@aria-label, '{button_type.lower()}')]",
        ]

        for xpath in xpath_selectors:
            try:
                buttons = self.driver.find_elements(By.XPATH, xpath)
                for btn in buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        if self.stealth_mode:
                            self._human_like_move(btn)
                            self._random_delay(0.2, 0.4)

                        try:
                            btn.click()
                            self.logger.debug(f"Кнопка '{button_type}' найдена по XPath и нажата")
                            self._random_delay(0.3, 0.7)
                            return True
                        except:
                            continue
            except:
                continue

        return False

    def _mute_video(self, video_element=None) -> bool:
        """Отключение звука видео"""
        if not self.mute_audio:
            return False

        try:
            # Способ 1: Через кнопку в интерфейсе
            if self._find_and_click_button(MUTE_BUTTON_SELECTORS, "mute"):
                self.stats['muted_videos'] += 1
                self.logger.info("Звук отключен через кнопку интерфейса")
                return True

            # Способ 2: Через JavaScript (прямое управление video элементом)
            if video_element:
                try:
                    self.driver.execute_script("arguments[0].muted = true;", video_element)
                    self.driver.execute_script("arguments[0].volume = 0;", video_element)
                    self.stats['muted_videos'] += 1
                    self.logger.info("Звук отключен через JavaScript")
                    return True
                except:
                    pass

            # Способ 3: Через поиск по классам volume/mute
            try:
                # Пробуем найти элементы с классами, связанными с громкостью
                volume_elements = self.driver.find_elements(By.CSS_SELECTOR,
                                                            "[class*='volume'], [class*='mute'], [class*='sound']")
                for elem in volume_elements:
                    if elem.is_displayed():
                        try:
                            elem.click()
                            self.stats['muted_videos'] += 1
                            self.logger.info("Звук отключен через поиск по классам")
                            return True
                        except:
                            continue
            except:
                pass

            # Способ 4: Через глобальный JavaScript для всех video элементов
            try:
                self.driver.execute_script("""
                    var videos = document.querySelectorAll('video');
                    for (var i = 0; i < videos.length; i++) {
                        videos[i].muted = true;
                        videos[i].volume = 0;
                    }
                """)
                self.stats['muted_videos'] += 1
                self.logger.info("Звук отключен через глобальный JavaScript")
                return True
            except:
                pass

            self.logger.debug("Не удалось отключить звук (возможно, он уже отключен или нет кнопки)")
            return False

        except Exception as e:
            self.logger.debug(f"Ошибка при отключении звука: {e}")
            return False

    def _start_video_playback(self, video_element) -> bool:
        """Попытка запуска воспроизведения видео"""
        attempts = [
            lambda: self.driver.execute_script("arguments[0].play();", video_element),
            lambda: video_element.click(),
            lambda: self._find_and_click_button(PLAY_BUTTON_SELECTORS, "play"),
        ]

        for i, attempt in enumerate(attempts, 1):
            try:
                attempt()
                self.logger.debug(f"Воспроизведение запущено (способ {i})")
                return True
            except:
                continue

        return False

    def watch_video(self, video_url: str, watch_time: int = DEFAULT_WATCH_TIME) -> bool:
        """Оптимизированный просмотр видео с stealth режимом"""
        try:
            self.logger.info(f"Просмотр: {video_url} ({watch_time} сек)")

            # Случайная задержка перед переходом (в stealth режиме)
            if self.stealth_mode:
                self._random_delay(0.5, 2.0)

            # Переход на страницу
            self.driver.get(video_url)

            # Реалистичная задержка после загрузки
            if self.stealth_mode:
                self._random_delay(1.5, 3.0)
            else:
                self._random_delay(1.5, 2.5)

            # Обработка всплывающих окон
            self.close_popups()
            self.accept_cookies()
            self.close_popups()

            # Ожидание загрузки с реалистичным таймаутом
            wait_time = random.randint(5, 10) if self.stealth_mode else 8
            WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Поиск и запуск видео
            video_element = self._find_video_element()
            if video_element:
                # Сначала запускаем видео
                playback_started = self._start_video_playback(video_element)

                # Затем отключаем звук (если включена опция)
                if playback_started and self.mute_audio:
                    delay = random.uniform(0.5, 1.5) if self.stealth_mode else random.uniform(0.5, 1.0)
                    time.sleep(delay)
                    self._mute_video(video_element)
            else:
                self.logger.warning("Видео элемент не найден, пробуем отключить звук глобально")
                if self.mute_audio:
                    self._mute_video()

            # Имитация человеческого просмотра
            start_time = time.time()
            last_log_time = 0
            last_action_time = 0

            while time.time() - start_time < watch_time:
                elapsed = time.time() - start_time

                # Логирование каждые 10 секунд
                if int(elapsed) // 10 > last_log_time:
                    self.logger.debug(f"Просмотрено {int(elapsed)} сек")
                    last_log_time = int(elapsed) // 10

                # Случайные человеческие действия
                if self.stealth_mode:
                    # Более реалистичные и редкие действия
                    action_chance = 0.12 if elapsed > 8 else 0.05
                    if random.random() < action_chance and time.time() - last_action_time > 5:
                        # Разные типы действий
                        action_type = random.choice(['scroll', 'move', 'pause'])

                        if action_type == 'scroll':
                            scroll_pos = random.randint(100, 400)
                            direction = random.choice([-1, 1])
                            self.driver.execute_script(f"window.scrollBy(0, {direction * scroll_pos});")
                            self.logger.debug(f"Прокрутка: {direction * scroll_pos}px")

                        elif action_type == 'move':
                            # Имитация движения мыши
                            scroll_x = random.randint(10, 100)
                            scroll_y = random.randint(10, 100)
                            self.driver.execute_script(f"""
                                window.dispatchEvent(new MouseEvent('mousemove', {{
                                    clientX: {scroll_x},
                                    clientY: {scroll_y},
                                    bubbles: true
                                }}));
                            """)
                            self.logger.debug(f"Движение мыши: ({scroll_x}, {scroll_y})")

                        elif action_type == 'pause':
                            # Имитация паузы (человек отошел)
                            pause_time = random.uniform(2, 8)
                            self.logger.debug(f"Пауза: {pause_time:.1f} сек")
                            time.sleep(pause_time)

                        last_action_time = time.time()

                        # Задержка после действия
                        self._random_delay(0.5, 1.5)
                else:
                    # Стандартные действия
                    if random.random() < 0.15 and elapsed > 5:
                        scroll_pos = random.randint(100, 400)
                        self.driver.execute_script(f"window.scrollBy(0, {random.choice([-1, 1]) * scroll_pos});")

                # Реалистичная задержка между проверками
                if self.stealth_mode:
                    sleep_time = random.uniform(1.0, 2.5)
                else:
                    sleep_time = random.uniform(0.8, 1.5)

                time.sleep(sleep_time)

            self.logger.info(f"Завершено: {video_url}")
            return True

        except TimeoutException:
            self.logger.error(f"Таймаут: {video_url}")
        except Exception as e:
            self.logger.error(f"Ошибка: {video_url} - {str(e)}")

        return False

    def load_videos_from_file(self, filepath: str) -> List[str]:
        """Оптимизированная загрузка видео из файла"""
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
            'cycle': self.stats['cycles_completed'] + 1,
            'muted': self.mute_audio,
            'stealth_mode': self.stealth_mode,
        })

    def save_stats(self):
        """Оптимизированное сохранение статистики"""
        try:
            data = {
                'stats': dict(self.stats),
                'videos_history': self.videos_history[-100:],  # Сохраняем только последние 100
                'settings': {**self.settings, 'end_time': datetime.now().isoformat()}
            }

            with open(STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        except Exception as e:
            self.logger.error(f"Ошибка сохранения статистики: {e}")

    def process_videos(self, video_urls: List[str], watch_time: int = DEFAULT_WATCH_TIME,
                       shuffle: bool = False, max_videos: Optional[int] = None):
        """Обработка списка видео с оптимизацией"""
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
                self.logger.warning(f"Пропущена не-RuTube ссылка")
                self._update_stats(video_url, False, 0)
                continue

            # Пауза между видео (реалистичная в stealth режиме)
            if i > 1:
                if self.stealth_mode:
                    pause = random.randint(5, 12)
                else:
                    pause = random.randint(3, 7)
                time.sleep(pause)

            # Просмотр видео
            success = self.watch_video(video_url, watch_time)
            self._update_stats(video_url, success, watch_time if success else 0)

            # Сохранение статистики каждые 5 видео
            if i % 5 == 0:
                self.save_stats()

    def run_cycles(self, video_urls: List[str], watch_time: int = DEFAULT_WATCH_TIME,
                   shuffle: bool = False, max_videos: Optional[int] = None,
                   cycles: int = 1, delay_between_cycles: int = DEFAULT_CYCLE_DELAY) -> bool:
        """Оптимизированный циклический просмотр"""
        try:
            self._print_cycle_info(video_urls, watch_time, cycles, delay_between_cycles)

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
                self._cycle_pause(delay_between_cycles)

                # Перезапуск драйвера
                self._restart_driver()

            return True

        except KeyboardInterrupt:
            self.logger.info("Остановлено пользователем")
            return False
        except Exception as e:
            self.logger.error(f"Ошибка в циклическом просмотре: {e}")
            return False

    def _print_cycle_info(self, video_urls: List[str], watch_time: int,
                          cycles: int, delay: int):
        """Вывод информации о цикле"""
        info = [
            f"{'=' * 50}",
            "ЦИКЛИЧЕСКИЙ ПРОСМОТР",
            f"{'=' * 50}",
            f"Циклов: {'бесконечно' if cycles == 0 else cycles}",
            f"Видео в цикле: {len(video_urls)}",
            f"Время просмотра: {watch_time} сек",
            f"Задержка между циклами: {delay} сек",
            f"Без звука: {'Да' if self.mute_audio else 'Нет'}",
            f"Stealth режим: {'Да' if self.stealth_mode else 'Нет'}",
            f"{'=' * 50}",
        ]

        for line in info:
            self.logger.info(line)

    def _cycle_pause(self, delay: int):
        """Пауза между циклами"""
        self.logger.info(f"Пауза: {delay} сек")

        for remaining in range(delay, 0, -1):
            if remaining % 10 == 0 or remaining <= 5:
                self.logger.info(f"Осталось: {remaining} сек")
            time.sleep(1)

    def _restart_driver(self):
        """Перезапуск драйвера"""
        self.logger.info("Перезапуск браузера...")

        try:
            if self.driver:
                self.driver.quit()
        except:
            pass

        time.sleep(1)

        if not self.create_driver():
            raise Exception("Не удалось создать драйвер")

    def run(self, video_urls: Union[str, List[str]], watch_time: int = DEFAULT_WATCH_TIME,
            shuffle: bool = False, max_videos: Optional[int] = None,
            cycles: int = 1, delay_between_cycles: int = DEFAULT_CYCLE_DELAY):
        """Основной запуск"""
        try:
            self._print_start_info(cycles)

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

    def _print_start_info(self, cycles: int):
        """Вывод стартовой информации"""
        info = [
            f"\n{'=' * 40}",
            f"Режим: {'GUI' if self.gui_mode else 'Headless'}",
            f"Инкогнито: {'Да' if self.incognito else 'Нет'}",
            f"Без звука: {'Да' if self.mute_audio else 'Нет'}",
            f"Stealth режим: {'Да' if self.stealth_mode else 'Нет'}",
            f"Циклы: {'бесконечно' if cycles == 0 else cycles}",
            f"{'=' * 40}",
        ]

        for line in info:
            print(line)

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
        """Оптимизированный вывод итогов"""
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
        stats.append(f"Режим Stealth: {'Да' if self.stealth_mode else 'Нет'}")
        stats.append(f"Статистика: {STATS_FILE}")
        stats.append(f"{'=' * 40}")

        for line in stats:
            print(line)


def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Оптимизированный просмотр видео на RuTube',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python viewer.py --file videos.txt --cycles 3
  python viewer.py --urls "https://rutube.ru/video/..." --no-gui --time 60
  python viewer.py --file list.txt --cycles 0 --delay-between-cycles 60
  python viewer.py --file videos.txt --no-mute  # с включенным звуком
  python viewer.py --file videos.txt --no-stealth  # без stealth режима
  python viewer.py --file videos.txt --stealth --no-gui  # максимальная скрытность
        """
    )

    # Источники видео
    sources = parser.add_argument_group('Источники видео')
    sources.add_argument('--urls', nargs='+', help='Ссылки на видео')
    sources.add_argument('--file', help='Файл со списком видео')

    # Параметры просмотра
    params = parser.add_argument_group('Параметры просмотра')
    params.add_argument('--time', type=int, default=DEFAULT_WATCH_TIME,
                        help=f'Время просмотра (сек, по умолчанию: {DEFAULT_WATCH_TIME})')
    params.add_argument('--shuffle', action='store_true', help='Перемешать видео')
    params.add_argument('--max', type=int, help='Максимум видео в цикле')

    # Циклы
    cycles = parser.add_argument_group('Циклы')
    cycles.add_argument('--cycles', type=int, default=1,
                        help='Количество циклов (0=бесконечно)')
    cycles.add_argument('--delay-between-cycles', type=int, default=DEFAULT_CYCLE_DELAY,
                        help=f'Задержка между циклами (сек, по умолчанию: {DEFAULT_CYCLE_DELAY})')

    # Настройки браузера
    browser = parser.add_argument_group('Настройки браузера')
    browser.add_argument('--gui', action='store_true', default=True,
                         help='С графическим интерфейсом (по умолчанию)')
    browser.add_argument('--no-gui', action='store_false', dest='gui',
                         help='Без графического интерфейса')
    browser.add_argument('--incognito', action='store_true', default=True,
                         help='Режим инкогнито (по умолчанию)')
    browser.add_argument('--no-incognito', action='store_false', dest='incognito',
                         help='Без режима инкогнито')
    browser.add_argument('--chromedriver', help='Путь к ChromeDriver')

    # Настройки звука
    browser.add_argument('--mute', action='store_true', default=True,
                         help='Отключить звук при воспроизведении (по умолчанию)')
    browser.add_argument('--no-mute', action='store_false', dest='mute',
                         help='Не отключать звук при воспроизведении')

    # Настройки stealth режима
    browser.add_argument('--stealth', action='store_true', default=True,
                         help='Включить stealth режим для скрытия автоматизации (по умолчанию)')
    browser.add_argument('--no-stealth', action='store_false', dest='stealth',
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

    if args.time < 5:
        print("Внимание: время просмотра менее 5 секунд может быть неэффективным")

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
        temp_viewer = RuTubeViewer(gui_mode=True, incognito=True, mute_audio=True, stealth_mode=True)
        loaded = temp_viewer.load_videos_from_file(args.file)
        video_urls.extend(loaded)

    if not video_urls:
        print("Ошибка: не удалось загрузить видео")
        return

    # Запуск
    viewer = RuTubeViewer(
        gui_mode=args.gui,
        incognito=args.incognito,
        chromedriver_path=args.chromedriver,
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