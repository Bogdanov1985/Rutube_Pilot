import time
import random
import argparse
from datetime import datetime
from typing import List, Optional
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


class RuTubeViewer:
    def __init__(self, headless: bool = False, incognito: bool = True):
        """
        Инициализация RuTube просмотрщика

        Args:
            headless (bool): Запуск в режиме без графического интерфейса
            incognito (bool): Использовать режим инкогнито
        """
        self.setup_logging()
        self.headless = headless
        self.incognito = incognito
        self.driver = None
        self.stats = {
            'total_videos': 0,
            'successful_views': 0,
            'failed_views': 0,
            'total_watch_time': 0,
            'videos_history': []
        }

    def setup_logging(self):
        """Настройка логирования"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('rutube_viewer.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def create_driver(self):
        """Создание и настройка драйвера Selenium"""
        try:
            chrome_options = Options()

            # Базовые опции
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            # Режим инкогнито
            if self.incognito:
                chrome_options.add_argument("--incognito")

            # Режим без графического интерфейса
            if self.headless:
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")

            # Дополнительные опции для более естественного поведения
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--lang=ru-RU")

            # Случайный User-Agent
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ]
            chrome_options.add_argument(f'user-agent={random.choice(user_agents)}')

            # Создаем драйвер
            self.driver = webdriver.Chrome(options=chrome_options)

            # Скрываем автоматизацию
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            self.logger.info("Драйвер успешно создан")
            return True

        except Exception as e:
            self.logger.error(f"Ошибка при создании драйвера: {e}")
            return False

    def wait_random_time(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Случайная задержка для имитации человеческого поведения"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def simulate_human_interaction(self):
        """Имитация человеческого взаимодействия со страницей"""
        try:
            # Случайные движения мыши
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
                "//button[contains(text(), 'OK')]"
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
                ".video-js"
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
                        break
                except:
                    continue

            if not video_element:
                self.logger.warning("Видео элемент не найден, попробуем альтернативный метод")
                # Попробуем найти через iframe
                try:
                    iframe = self.driver.find_element(By.TAG_NAME, "iframe")
                    self.driver.switch_to.frame(iframe)
                    video_element = self.driver.find_element(By.TAG_NAME, "video")
                    self.driver.switch_to.default_content()
                except:
                    pass

            if video_element:
                self.logger.info("Видео элемент найден")

                # Пытаемся начать воспроизведение
                try:
                    self.driver.execute_script("arguments[0].play();", video_element)
                    self.logger.info("Воспроизведение начато")
                except:
                    # Если скрипт не сработал, пытаемся кликнуть на видео
                    try:
                        video_element.click()
                        self.logger.info("Клик на видео выполнен")
                    except:
                        self.logger.warning("Не удалось начать воспроизведение автоматически")

                # Ждем немного перед имитацией взаимодействия
                self.wait_random_time(2, 4)

                # Время начала просмотра
                start_time = time.time()
                elapsed_time = 0

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
                    elapsed_time = time.time() - start_time

                    # Выводим прогресс каждые 10 секунд
                    if int(elapsed_time) % 10 == 0:
                        self.logger.info(f"Просмотрено {int(elapsed_time)} из {watch_time} секунд")

                    # Случайная пауза
                    pause_time = random.uniform(1, 3)
                    time.sleep(pause_time)

                self.logger.info(f"Просмотр видео завершен: {video_url}")
                return True

            else:
                self.logger.error(f"Не удалось найти видео элемент для {video_url}")
                return False

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

        if max_videos:
            video_urls = video_urls[:max_videos]

        self.stats['total_videos'] = len(video_urls)

        for i, video_url in enumerate(video_urls, 1):
            self.logger.info(f"Видео {i}/{len(video_urls)}")

            # Проверяем, что это действительно ссылка на RuTube
            if "rutube.ru" not in video_url and "rutube.pl" not in video_url:
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
                'success': success
            }
            self.stats['videos_history'].append(video_stat)

            if success:
                self.stats['successful_views'] += 1
                self.stats['total_watch_time'] += watch_time
            else:
                self.stats['failed_views'] += 1

            # Сохраняем статистику после каждого видео
            self.save_stats()

    def save_stats(self):
        """Сохранение статистики в файл"""
        try:
            stats_file = 'viewer_stats.json'
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
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Разные форматы файлов
            urls = []

            # Построчное чтение
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):  # Пропускаем пустые строки и комментарии
                    urls.append(line)

            self.logger.info(f"Загружено {len(urls)} видео из файла {filepath}")
            return urls

        except FileNotFoundError:
            self.logger.error(f"Файл не найден: {filepath}")
            return []
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке файла {filepath}: {e}")
            return []

    def run(self, video_urls: List[str], watch_time: int = 30,
            shuffle: bool = False, max_videos: Optional[int] = None):
        """
        Основной метод запуска просмотра

        Args:
            video_urls (List[str]): Список URL видео или один URL
            watch_time (int): Время просмотра каждого видео
            shuffle (bool): Перемешивать ли список видео
            max_videos (Optional[int]): Максимальное количество видео
        """
        try:
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
            self.logger.info("Программа остановлена пользователем")
            self.print_summary()
        except Exception as e:
            self.logger.error(f"Критическая ошибка: {e}")
        finally:
            if self.driver:
                self.logger.info("Закрываем браузер...")
                self.driver.quit()

    def print_summary(self):
        """Вывод итоговой статистики"""
        print("\n" + "=" * 50)
        print("ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 50)
        print(f"Всего видео в списке: {self.stats['total_videos']}")
        print(f"Успешно просмотрено: {self.stats['successful_views']}")
        print(f"Не удалось просмотреть: {self.stats['failed_views']}")
        print(f"Общее время просмотра: {self.stats['total_watch_time']} секунд")
        print(f"Статистика сохранена в viewer_stats.json")
        print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description='Автоматизированный просмотр видео на RuTube')
    parser.add_argument('--urls', nargs='+', help='Список URL видео на RuTube')
    parser.add_argument('--file', type=str, help='Файл со списком URL видео (по одному на строку)')
    parser.add_argument('--time', type=int, default=30,
                        help='Время просмотра каждого видео в секундах (по умолчанию: 30)')
    parser.add_argument('--headless', action='store_true', help='Запуск в фоновом режиме (без графического интерфейса)')
    parser.add_argument('--no-incognito', action='store_true', help='Не использовать режим инкогнито')
    parser.add_argument('--shuffle', action='store_true', help='Перемешать список видео')
    parser.add_argument('--max', type=int, help='Максимальное количество видео для просмотра')

    args = parser.parse_args()

    # Проверяем наличие URL
    video_urls = []

    if args.urls:
        video_urls.extend(args.urls)

    if args.file:
        viewer = RuTubeViewer(headless=args.headless, incognito=not args.no_incognito)
        loaded_urls = viewer.load_videos_from_file(args.file)
        video_urls.extend(loaded_urls)

    if not video_urls:
        print("Ошибка: Не указаны видео для просмотра!")
        print("Используйте --urls для указания ссылок или --file для загрузки из файла")
        return

    # Создаем и запускаем просмотрщик
    viewer = RuTubeViewer(headless=args.headless, incognito=not args.no_incognito)
    viewer.run(
        video_urls=video_urls,
        watch_time=args.time,
        shuffle=args.shuffle,
        max_videos=args.max
    )


if __name__ == "__main__":
    main()