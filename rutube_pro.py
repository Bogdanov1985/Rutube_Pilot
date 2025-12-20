#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuTube Viewer Pro
Усовершенствованный бот для просмотра видео на RuTube с поддержкой прокси
"""

import time
import random
import argparse
import asyncio
import aiohttp
import json
import logging
import os
import sys
from datetime import datetime
from typing import List, Optional, Union, Dict, Any
from pathlib import Path
from queue import Queue
from threading import Lock
from concurrent.futures import ThreadPoolExecutor

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rutube_viewer_pro.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ProxyManager:
    """Управление прокси-серверами"""

    def __init__(self, max_proxies: int = 50, timeout: int = 10, verbose: bool = False):
        self.proxies = []
        self.working_proxies = []
        self.failed_proxies = []
        self.lock = Lock()
        self.max_proxies = max_proxies
        self.timeout = timeout
        self.verbose = verbose
        self.stats = {
            'total_found': 0,
            'total_checked': 0,
            'working_count': 0,
            'failed_count': 0,
            'last_update': None
        }

        # URL для проверки прокси
        self.test_urls = [
            'http://httpbin.org/ip',
            'https://api.ipify.org?format=json',
            'https://rutube.ru/api/play/options/'
        ]

    async def fetch_proxies(self, sources: Optional[List[str]] = None) -> List[str]:
        """Получение прокси из различных источников"""
        if sources is None:
            sources = [
                'https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all',
                'https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt',
                'https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt',
                'https://www.proxy-list.download/api/v1/get?type=http',
               # "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/all/data.txt   # не верный формат
                "https://vakhov.github.io/fresh-proxy-list/proxylist.txt"

            ]

        async def fetch_source(url: str) -> List[str]:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            text = await response.text()
                            proxies = [p.strip() for p in text.split('\n') if p.strip()]
                            return proxies
            except Exception as e:
                if self.verbose:
                    logger.debug(f"Ошибка при получении прокси из {url}: {e}")
                return []

        tasks = [fetch_source(source) for source in sources]
        results = await asyncio.gather(*tasks)

        all_proxies = []
        for proxy_list in results:
            all_proxies.extend(proxy_list)

        # Убираем дубликаты и ограничиваем количество
        unique_proxies = list(set(all_proxies))
        self.proxies = unique_proxies[:self.max_proxies]
        self.stats['total_found'] = len(self.proxies)
        self.stats['last_update'] = datetime.now().isoformat()

        logger.info(f"Найдено {len(self.proxies)} прокси")
        return self.proxies

    async def test_proxy(self, proxy: str) -> Optional[Dict[str, Any]]:
        """Асинхронная проверка работоспособности прокси"""
        test_proxies = {
            'http': f'http://{proxy}',
            'https': f'http://{proxy}'
        }

        ip_address = None
        country = None
        response_time = None

        for test_url in self.test_urls:
            try:
                start_time = time.time()
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                            test_url,
                            proxy=test_proxies['http'],
                            timeout=self.timeout
                    ) as response:
                        if response.status == 200:
                            response_time = time.time() - start_time
                            try:
                                data = await response.json()
                                ip_address = data.get('origin') or data.get('ip')
                                if ip_address and ',' in ip_address:
                                    ip_address = ip_address.split(',')[0].strip()
                                country = data.get('country', 'Unknown')
                            except:
                                text = await response.text()
                                if 'origin' in text or 'ip' in text:
                                    ip_address = proxy.split(':')[0]

                            if ip_address:
                                if self.verbose:
                                    logger.debug(
                                        f"✓ Прокси {proxy} рабочий, IP: {ip_address}, время: {response_time:.2f}с")

                                return {
                                    'proxy': proxy,
                                    'ip': ip_address,
                                    'response_time': response_time,
                                    'country': country,
                                    'last_checked': datetime.now().isoformat()
                                }
            except Exception as e:
                if self.verbose and 'rutube' in test_url:
                    continue

        if self.verbose:
            logger.debug(f"✗ Прокси {proxy} не рабочий")

        return None

    async def validate_proxies(self, max_workers: int = 20) -> List[str]:
        """Проверка всех прокси на работоспособность"""
        logger.info(f"Начинаем проверку {len(self.proxies)} прокси...")

        semaphore = asyncio.Semaphore(max_workers)

        async def test_with_semaphore(proxy: str) -> Optional[Dict[str, Any]]:
            async with semaphore:
                return await self.test_proxy(proxy)

        tasks = [test_with_semaphore(proxy) for proxy in self.proxies]
        results = await asyncio.gather(*tasks)

        # Фильтруем рабочие прокси
        self.working_proxies = [result['proxy'] for result in results if result]
        self.failed_proxies = [proxy for proxy in self.proxies if proxy not in self.working_proxies]

        self.stats['total_checked'] = len(self.proxies)
        self.stats['working_count'] = len(self.working_proxies)
        self.stats['failed_count'] = len(self.failed_proxies)

        # Сортируем по времени отклика
        working_details = [result for result in results if result]
        working_details.sort(key=lambda x: x.get('response_time', float('inf')))
        self.working_proxies = [item['proxy'] for item in working_details]

        logger.info(f"Найдено {len(self.working_proxies)} рабочих прокси")

        # Сохраняем результаты
        self.save_results()

        return self.working_proxies

    def get_random_proxy(self) -> Optional[str]:
        """Получение случайного рабочего прокси"""
        with self.lock:
            if not self.working_proxies:
                return None
            return random.choice(self.working_proxies)

    def get_fastest_proxy(self) -> Optional[str]:
        """Получение самого быстрого прокси"""
        with self.lock:
            if not self.working_proxies:
                return None
            return self.working_proxies[0] if self.working_proxies else None

    def mark_proxy_failed(self, proxy: str):
        """Пометить прокси как нерабочий"""
        with self.lock:
            if proxy in self.working_proxies:
                self.working_proxies.remove(proxy)
                self.failed_proxies.append(proxy)
                self.stats['working_count'] = len(self.working_proxies)
                self.stats['failed_count'] = len(self.failed_proxies)

                if self.verbose:
                    logger.info(f"Прокси {proxy} помечен как нерабочий")

    def save_results(self):
        """Сохранение результатов проверки прокси"""
        results = {
            'working_proxies': self.working_proxies,
            'failed_proxies': self.failed_proxies,
            'stats': self.stats,
            'timestamp': datetime.now().isoformat()
        }

        try:
            with open('proxy_results.json', 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info("Результаты проверки прокси сохранены в proxy_results.json")
        except Exception as e:
            logger.error(f"Ошибка сохранения результатов прокси: {e}")

    def load_previous_results(self) -> bool:
        """Загрузка предыдущих результатов проверки прокси"""
        try:
            if os.path.exists('proxy_results.json'):
                with open('proxy_results.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Проверяем, не устарели ли результаты (старше 1 часа)
                if 'timestamp' in data:
                    last_update = datetime.fromisoformat(data['timestamp'])
                    if (datetime.now() - last_update).total_seconds() < 3600:
                        self.working_proxies = data.get('working_proxies', [])
                        self.failed_proxies = data.get('failed_proxies', [])
                        self.stats = data.get('stats', self.stats)

                        logger.info(f"Загружено {len(self.working_proxies)} рабочих прокси из сохраненного файла")
                        return True
                    else:
                        logger.info("Сохраненные прокси устарели (старше 1 часа)")
                else:
                    logger.info("Нет timestamp в сохраненном файле")
            else:
                logger.info("Файл с сохраненными прокси не найден")
        except Exception as e:
            logger.error(f"Ошибка загрузки сохраненных прокси: {e}")

        return False

    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики прокси"""
        return {
            **self.stats,
            'current_working': len(self.working_proxies),
            'current_failed': len(self.failed_proxies)
        }


class RuTubeViewerPro:
    """Усовершенствованный просмотрщик RuTube с поддержкой прокси"""

    def __init__(self,
                 gui_mode: bool = True,
                 incognito: bool = True,
                 use_proxy: bool = True,
                 proxy_manager: Optional[ProxyManager] = None,
                 chromedriver_path: Optional[str] = None,
                 verbose: bool = False):

        self.setup_logging(verbose)
        self.gui_mode = gui_mode
        self.incognito = incognito
        self.use_proxy = use_proxy
        self.verbose = verbose

        # Менеджер прокси
        if use_proxy:
            self.proxy_manager = proxy_manager or ProxyManager(verbose=verbose)
            self.current_proxy = None
        else:
            self.proxy_manager = None
            self.current_proxy = None

        # Путь к драйверу
        self.chromedriver_path = self._find_chromedriver(chromedriver_path)
        self.driver = None

        # Статистика
        self.stats = {
            'total_videos': 0,
            'successful_views': 0,
            'failed_views': 0,
            'total_watch_time': 0,
            'videos_history': [],
            'cycles_completed': 0,
            'proxies_used': [],
            'settings': {
                'gui_mode': gui_mode,
                'incognito': incognito,
                'use_proxy': use_proxy,
                'chromedriver_path': str(self.chromedriver_path) if self.chromedriver_path else None,
                'start_time': datetime.now().isoformat()
            }
        }

        # Пользовательские агенты
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        ]

    def setup_logging(self, verbose: bool):
        """Настройка логирования"""
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.getLogger().setLevel(log_level)
        self.logger = logger

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

    async def initialize_proxies(self) -> bool:
        """Инициализация системы прокси"""
        if not self.use_proxy or not self.proxy_manager:
            self.logger.info("Режим без прокси")
            return True

        # Пробуем загрузить сохраненные прокси
        if self.proxy_manager.load_previous_results():
            self.logger.info(f"Используем {len(self.proxy_manager.working_proxies)} сохраненных прокси")
            return True

        # Если нет сохраненных, ищем новые
        self.logger.info("Инициализация системы прокси...")
        try:
            await self.proxy_manager.fetch_proxies()
            await self.proxy_manager.validate_proxies()

            if not self.proxy_manager.working_proxies:
                self.logger.warning("Не найдено рабочих прокси. Продолжаем без прокси.")
                self.use_proxy = False
                return False

            self.logger.info(f"Инициализировано {len(self.proxy_manager.working_proxies)} рабочих прокси")
            return True

        except Exception as e:
            self.logger.error(f"Ошибка инициализации прокси: {e}")
            self.use_proxy = False
            return False

    def get_next_proxy(self) -> Optional[str]:
        """Получение следующего прокси для использования"""
        if not self.use_proxy or not self.proxy_manager:
            return None

        # Выбираем случайный прокси
        proxy = self.proxy_manager.get_random_proxy()
        if proxy:
            self.current_proxy = proxy
            self.stats['proxies_used'].append({
                'proxy': proxy,
                'timestamp': datetime.now().isoformat(),
                'success': True  # Временно, обновится после использования
            })

        return proxy

    def mark_proxy_status(self, success: bool):
        """Обновление статуса текущего прокси"""
        if self.current_proxy and self.proxy_manager:
            if not success:
                self.proxy_manager.mark_proxy_failed(self.current_proxy)

                # Обновляем статистику
                for item in self.stats['proxies_used']:
                    if item['proxy'] == self.current_proxy:
                        item['success'] = False
                        break

            self.current_proxy = None

    def create_driver(self, proxy: Optional[str] = None) -> bool:
        """Создание драйвера с возможным использованием прокси"""
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

            # Прокси
            if proxy:
                chrome_options.add_argument(f'--proxy-server=http://{proxy}')
                self.logger.info(f"Используем прокси: {proxy}")

            # Дополнительные опции
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--lang=ru-RU")

            # User-Agent
            user_agent = random.choice(self.user_agents)
            chrome_options.add_argument(f'user-agent={user_agent}')

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
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": user_agent
            })

            return True

        except Exception as e:
            self.logger.error(f"Ошибка при создании драйвера: {e}")
            return False

    def wait_random(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Случайная задержка"""
        sleep_time = random.uniform(min_seconds, max_seconds)
        time.sleep(sleep_time)

    def close_popups(self):
        """Закрытие всплывающих окон"""
        try:
            if self.verbose:
                self.logger.debug("Проверяем всплывающие окна...")

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
                "div[class*='modal'] button[class*='close']",
                "div[class*='popup'] button[class*='close']",
                "div[class*='dialog'] button[class*='close']",
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
                    if selector.startswith("//"):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                    for element in elements:
                        try:
                            if element.is_displayed() and element.is_enabled():
                                element.click()
                                if self.verbose:
                                    self.logger.debug(f"Закрыто всплывающее окно: {selector}")
                                closed_popups += 1
                                self.wait_random(0.5, 1)
                                break
                        except:
                            continue

                except Exception as e:
                    continue

            if self.verbose and closed_popups > 0:
                self.logger.debug(f"Закрыто {closed_popups} всплывающих окон")

        except Exception as e:
            if self.verbose:
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
                "//button[contains(text(), 'cookie')]",
                "//button[contains(text(), 'Cookie')]",
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
            if self.verbose:
                self.logger.debug(f"Окно куки не найдено: {e}")

        return False

    def simulate_human_behavior(self):
        """Симуляция человеческого поведения"""
        try:
            # Случайное движение мыши
            action = ActionChains(self.driver)

            # Получаем размеры окна
            window_size = self.driver.get_window_size()
            width = window_size['width']
            height = window_size['height']

            # Случайные координаты
            x = random.randint(0, width)
            y = random.randint(0, height)

            # Движение мыши
            action.move_by_offset(x, y).perform()
            self.wait_random(0.1, 0.5)

            # Случайный скролл
            scroll_amount = random.randint(-300, 300)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")

            # Случайные клики (не на интерактивных элементах)
            if random.random() < 0.3:
                action.move_by_offset(random.randint(-50, 50), random.randint(-50, 50))
                action.click().perform()

            self.wait_random(0.5, 1)

        except Exception as e:
            if self.verbose:
                self.logger.debug(f"Ошибка при симуляции поведения: {e}")

    def watch_video(self, video_url: str, watch_time: int = 30) -> bool:
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
                "div[class*='video-container'] video",
                "div[class*='player-container'] video",
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
            play_success = False
            if video_element:
                try:
                    self.driver.execute_script("arguments[0].play();", video_element)
                    self.logger.info("Воспроизведение начато (через JavaScript)")
                    play_success = True
                except:
                    try:
                        video_element.click()
                        self.logger.info("Клик на видео")
                        play_success = True
                    except:
                        try:
                            play_buttons = self.driver.find_elements(By.CSS_SELECTOR,
                                                                     "button[class*='play'], "
                                                                     "button[title*='play'], "
                                                                     "button[aria-label*='play'], "
                                                                     "button[class*='Play'], "
                                                                     "button[title*='Play'], "
                                                                     "button[aria-label*='Play']")
                            for btn in play_buttons:
                                if btn.is_displayed():
                                    btn.click()
                                    self.logger.info("Нажата кнопка Play")
                                    play_success = True
                                    break
                        except:
                            self.logger.warning("Не удалось начать воспроизведение автоматически")

            # Если не удалось запустить, пытаемся через JavaScript на странице
            if not play_success:
                try:
                    self.driver.execute_script("""
                        var videos = document.querySelectorAll('video');
                        for (var i = 0; i < videos.length; i++) {
                            videos[i].play();
                        }
                    """)
                    self.logger.info("Воспроизведение через JavaScript (все видео)")
                except:
                    pass

            # Время просмотра с симуляцией человеческого поведения
            start_time = time.time()
            elapsed_time = 0
            last_activity = start_time

            while elapsed_time < watch_time:
                current_time = time.time()
                elapsed_time = current_time - start_time

                # Симуляция активности каждые 5-10 секунд
                if current_time - last_activity > random.uniform(5, 10):
                    self.simulate_human_behavior()
                    last_activity = current_time

                # Прогресс каждые 15 секунд
                if int(elapsed_time) % 15 == 0:
                    self.logger.info(f"Просмотрено {int(elapsed_time)} из {watch_time} сек")

                # Случайная пауза
                time.sleep(random.uniform(0.5, 1.5))

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

        total_videos_in_cycle = len(video_urls)
        self.stats['total_videos'] += total_videos_in_cycle

        for i, video_url in enumerate(video_urls, 1):
            self.logger.info(f"\n{'=' * 60}")
            self.logger.info(f"Видео {i}/{len(video_urls)}: {video_url}")
            self.logger.info(f"{'=' * 60}")

            # Проверка ссылки
            if not any(domain in video_url for domain in ['rutube.ru', 'rutube.pl', 'rutube.io']):
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
                'cycle': self.stats['cycles_completed'] + 1,
                'proxy': self.current_proxy
            }
            self.stats['videos_history'].append(video_stat)

            if success:
                self.stats['successful_views'] += 1
                self.stats['total_watch_time'] += watch_time
                self.logger.info("✓ Успешно просмотрено")
                self.mark_proxy_status(True)
            else:
                self.stats['failed_views'] += 1
                self.logger.error("✗ Ошибка просмотра")
                self.mark_proxy_status(False)

            # Сохранение статистики после каждого видео
            self.save_stats()

    def save_stats(self):
        """Сохранение статистики"""
        try:
            self.stats['settings']['end_time'] = datetime.now().isoformat()

            # Статистика прокси, если используется
            if self.use_proxy and self.proxy_manager:
                self.stats['proxy_stats'] = self.proxy_manager.get_stats()

            with open('viewer_stats.json', 'w', encoding='utf-8') as f:
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
            rutube_urls = [url for url in urls if
                           any(domain in url for domain in ['rutube.ru', 'rutube.pl', 'rutube.io'])]

            if len(rutube_urls) < len(urls):
                self.logger.warning(f"Отфильтровано {len(urls) - len(rutube_urls)} ссылок")

            self.logger.info(f"Загружено {len(rutube_urls)} видео из {filepath}")
            return rutube_urls

        except Exception as e:
            self.logger.error(f"Ошибка загрузки файла: {e}")
            return []

    async def run_cycle(self, video_urls: List[str], watch_time: int = 30,
                        shuffle: bool = False, max_videos: Optional[int] = None) -> bool:
        """Выполнение одного цикла просмотра"""
        try:
            # Получаем прокси для этого цикла
            proxy = None
            if self.use_proxy:
                proxy = self.get_next_proxy()
                if not proxy:
                    self.logger.warning("Нет доступных прокси для этого цикла")
                    return False

            # Создаем драйвер с прокси
            if not self.create_driver(proxy):
                self.logger.error("Не удалось создать драйвер")
                self.mark_proxy_status(False)
                return False

            # Обрабатываем видео
            self.process_videos(video_urls, watch_time, shuffle, max_videos)

            # Закрываем драйвер
            try:
                if self.driver:
                    self.driver.quit()
            except:
                pass

            return True

        except Exception as e:
            self.logger.error(f"Ошибка в цикле: {e}")
            return False

    async def run_cycles_async(self, video_urls: List[str], watch_time: int = 30,
                               shuffle: bool = False, max_videos: Optional[int] = None,
                               cycles: int = 1, delay_between_cycles: int = 10):
        """Асинхронный запуск циклического просмотра"""
        try:
            # Инициализируем прокси
            if self.use_proxy:
                await self.initialize_proxies()

            # Информация о цикле
            print(f"\n{'=' * 60}")
            print(f"ЦИКЛИЧЕСКИЙ ПРОСМОТР С ПРОКСИ")
            print(f"{'=' * 60}")
            print(f"Количество циклов: {'бесконечно' if cycles == 0 else cycles}")
            print(f"Количество видео в цикле: {len(video_urls)}")
            if max_videos:
                print(f"Максимум видео в цикле: {max_videos}")
            print(f"Время просмотра каждого видео: {watch_time} сек")
            print(f"Задержка между циклами: {delay_between_cycles} сек")
            if self.use_proxy and self.proxy_manager:
                print(f"Доступно прокси: {len(self.proxy_manager.working_proxies)}")
            print(f"{'=' * 60}")

            cycle_count = 0

            while True:
                cycle_count += 1
                self.stats['cycles_completed'] += 1

                print(f"\n{'=' * 60}")
                print(f"ЦИКЛ {cycle_count}")
                print(f"{'=' * 60}")
                self.logger.info(f"Начинаем цикл {cycle_count}")

                # Выполняем цикл
                success = await self.run_cycle(video_urls, watch_time, shuffle, max_videos)

                if not success:
                    self.logger.warning(f"Цикл {cycle_count} завершился с ошибками")

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
        """Основной запуск с поддержкой циклов и прокси"""
        try:
            # Информация о режиме
            print(f"\n{'=' * 60}")
            print(f"RuTube Viewer Pro")
            print(f"{'=' * 60}")
            print(f"Режим: {'GUI' if self.gui_mode else 'Headless'}")
            print(f"Инкогнито: {'Да' if self.incognito else 'Нет'}")
            print(f"Прокси: {'Да' if self.use_proxy else 'Нет'}")
            print(f"Циклы: {'бесконечно' if cycles == 0 else cycles}")
            print(f"Подробный режим: {'Да' if self.verbose else 'Нет'}")
            if self.chromedriver_path:
                print(f"ChromeDriver: {self.chromedriver_path}")
            print(f"{'=' * 60}")

            # Обрабатываем видео
            if isinstance(video_urls, str):
                video_urls = [video_urls]

            # Запускаем асинхронно если есть циклы или прокси
            if cycles != 1 or self.use_proxy:
                asyncio.run(self.run_cycles_async(
                    video_urls, watch_time, shuffle, max_videos, cycles, delay_between_cycles
                ))
            else:
                # Одиночный запуск (обратная совместимость)
                proxy = self.get_next_proxy() if self.use_proxy else None
                if self.create_driver(proxy):
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

        if self.use_proxy:
            print(f"Использовано прокси: {len(set([p['proxy'] for p in self.stats['proxies_used'] if 'proxy' in p]))}")

        total_sec = self.stats['total_watch_time']
        hours = total_sec // 3600
        minutes = (total_sec % 3600) // 60
        seconds = total_sec % 60

        print(f"Общее время просмотра: {hours}ч {minutes}м {seconds}с")
        print(f"Статистика сохранена в viewer_stats.json")

        if self.use_proxy and self.proxy_manager:
            proxy_stats = self.proxy_manager.get_stats()
            print(f"Прокси: {proxy_stats['working_count']} рабочих, {proxy_stats['failed_count']} нерабочих")

        print("=" * 60)


async def manage_proxies_only(args):
    """Режим только управления прокси"""
    print(f"\n{'=' * 60}")
    print(f"РЕЖИМ УПРАВЛЕНИЯ ПРОКСИ")
    print(f"{'=' * 60}")

    proxy_manager = ProxyManager(
        max_proxies=args.max_proxies,
        timeout=args.proxy_timeout,
        verbose=args.verbose
    )

    if args.proxy_file:
        # Загружаем прокси из файла
        try:
            with open(args.proxy_file, 'r', encoding='utf-8') as f:
                proxies = [line.strip() for line in f if line.strip()]
            proxy_manager.proxies = proxies[:proxy_manager.max_proxies]
            print(f"Загружено {len(proxy_manager.proxies)} прокси из файла")
        except Exception as e:
            print(f"Ошибка загрузки прокси из файла: {e}")
            return
    else:
        # Получаем прокси из интернета
        print("Получение прокси из интернета...")
        await proxy_manager.fetch_proxies()

    # Проверяем прокси
    print("Проверка прокси на работоспособность...")
    working_proxies = await proxy_manager.validate_proxies(max_workers=args.max_workers)

    # Выводим результаты
    print(f"\nРезультаты проверки:")
    print(f"Всего прокси: {len(proxy_manager.proxies)}")
    print(f"Рабочих: {len(working_proxies)}")
    print(f"Нерабочих: {len(proxy_manager.failed_proxies)}")

    if working_proxies:
        print(f"\nТоп-10 самых быстрых прокси:")
        for i, proxy in enumerate(working_proxies[:10], 1):
            print(f"  {i:2d}. {proxy}")

    # Сохраняем в файл
    proxy_manager.save_results()
    print(f"\nРезультаты сохранены в proxy_results.json")


def main():
    parser = argparse.ArgumentParser(
        description='RuTube Viewer Pro - Усовершенствованный бот для просмотра видео на RuTube с поддержкой прокси',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Примеры использования:
  # Просмотр одного видео с прокси
  python rutube_pro.py --urls https://rutube.ru/video/... --use-proxy

  # Циклический просмотр с прокси
  python rutube_pro.py --file videos.txt --cycles 3 --use-proxy

  # Просмотр без GUI с прокси
  python rutube_pro.py --urls https://rutube.ru/video/... --no-gui --use-proxy

  # Только управление прокси
  python rutube_pro.py --proxy-only --max-proxies 100

  # Тестирование конкретного прокси
  python rutube_pro.py --test-proxy 123.45.67.89:8080
        '''
    )

    # Основные аргументы
    main_group = parser.add_argument_group('Основные аргументы')
    main_group.add_argument('--urls', nargs='+', help='Ссылки на видео')
    main_group.add_argument('--file', type=str, help='Файл со списком видео')
    main_group.add_argument('--time', type=int, default=30, help='Время просмотра каждого видео (сек)')

    # Циклы
    cycle_group = parser.add_argument_group('Настройки циклов')
    cycle_group.add_argument('--cycles', type=int, default=1,
                             help='Количество циклов (0 = бесконечно, 1 = по умолчанию)')
    cycle_group.add_argument('--delay-between-cycles', type=int, default=30,
                             help='Задержка между циклами в секундах (по умолчанию: 30)')

    # Режимы браузера
    browser_group = parser.add_argument_group('Настройки браузера')
    browser_group.add_argument('--gui', action='store_true', default=True,
                               help='С графическим интерфейсом (по умолчанию)')
    browser_group.add_argument('--no-gui', action='store_false', dest='gui',
                               help='Без графического интерфейса')
    browser_group.add_argument('--incognito', action='store_true', default=True,
                               help='Режим инкогнито')
    browser_group.add_argument('--no-incognito', action='store_false', dest='incognito',
                               help='Без инкогнито')
    browser_group.add_argument('--chromedriver', type=str, help='Путь к ChromeDriver')

    # Прокси
    proxy_group = parser.add_argument_group('Настройки прокси')
    proxy_group.add_argument('--use-proxy', action='store_true', default=False,
                             help='Использовать прокси')
    proxy_group.add_argument('--no-proxy', action='store_false', dest='use_proxy',
                             help='Не использовать прокси')
    proxy_group.add_argument('--proxy-file', type=str, help='Файл со списком прокси')
    proxy_group.add_argument('--max-proxies', type=int, default=50,
                             help='Максимальное количество прокси для проверки')
    proxy_group.add_argument('--proxy-timeout', type=int, default=10,
                             help='Таймаут проверки прокси в секундах')
    proxy_group.add_argument('--max-workers', type=int, default=20,
                             help='Максимальное количество одновременных проверок прокси')
    proxy_group.add_argument('--proxy-only', action='store_true',
                             help='Только управление прокси (без просмотра видео)')
    proxy_group.add_argument('--test-proxy', type=str, help='Тестирование конкретного прокси')

    # Дополнительные
    other_group = parser.add_argument_group('Дополнительные настройки')
    other_group.add_argument('--shuffle', action='store_true', help='Перемешать видео в каждом цикле')
    other_group.add_argument('--max', type=int, help='Максимум видео в каждом цикле')
    other_group.add_argument('--verbose', '-v', action='store_true', help='Подробный вывод')
    other_group.add_argument('--quiet', '-q', action='store_true', help='Тихий режим')

    args = parser.parse_args()

    # Настройка логирования
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    # Режим только управления прокси
    if args.proxy_only:
        asyncio.run(manage_proxies_only(args))
        return

    # Тестирование конкретного прокси
    if args.test_proxy:
        async def test_single_proxy():
            proxy_manager = ProxyManager(verbose=True)
            result = await proxy_manager.test_proxy(args.test_proxy)
            if result:
                print(f"\n✓ Прокси {args.test_proxy} рабочий")
                print(f"  IP адрес: {result['ip']}")
                print(f"  Время отклика: {result['response_time']:.2f} секунд")
                if result.get('country'):
                    print(f"  Страна: {result['country']}")
            else:
                print(f"\n✗ Прокси {args.test_proxy} не рабочий")

        asyncio.run(test_single_proxy())
        return

    # Загружаем видео
    video_urls = []

    if args.urls:
        video_urls.extend(args.urls)

    if args.file:
        viewer = RuTubeViewerPro(
            gui_mode=args.gui,
            incognito=args.incognito,
            use_proxy=args.use_proxy,
            verbose=args.verbose
        )
        loaded = viewer.load_videos_from_file(args.file)
        video_urls.extend(loaded)

    if not video_urls:
        print("Ошибка: укажите видео через --urls или --file")
        return

    # Проверяем параметры
    if args.cycles < 0:
        print("Ошибка: количество циклов не может быть отрицательным")
        return

    if args.delay_between_cycles < 0:
        print("Ошибка: задержка между циклами не может быть отрицательной")
        return

    if args.cycles == 0:
        print("\n" + "!" * 60)
        print("ВНИМАНИЕ: Запущен бесконечный цикл просмотра!")
        print("Для остановки нажмите Ctrl+C")
        print("!" * 60 + "\n")

    # Запускаем
    viewer = RuTubeViewerPro(
        gui_mode=args.gui,
        incognito=args.incognito,
        use_proxy=args.use_proxy,
        chromedriver_path=args.chromedriver,
        verbose=args.verbose
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