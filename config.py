# config.py
DEFAULT_SETTINGS = {
    # Режим запуска
    "GUI_MODE": True,  # True - с графическим интерфейсом, False - headless
    "INCOGNITO_MODE": True,  # Режим инкогнито

    # Настройки просмотра
    "DEFAULT_WATCH_TIME": 20,  # Секунд
    "SHUFFLE_VIDEOS": False,
    "MAX_VIDEOS_PER_SESSION": None,

    # Задержки (в секундах)
    "MIN_DELAY_BETWEEN_ACTIONS": 1.0,
    "MAX_DELAY_BETWEEN_ACTIONS": 3.0,
    "MIN_DELAY_BETWEEN_VIDEOS": 5,
    "MAX_DELAY_BETWEEN_VIDEOS": 15,

    # Поведение
    "SIMULATE_HUMAN_INTERACTION": True,
    "ACCEPT_COOKIES": True,

    # Браузер
    "WINDOW_WIDTH": 1920,
    "WINDOW_HEIGHT": 1080,
    "USER_AGENTS": [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
}