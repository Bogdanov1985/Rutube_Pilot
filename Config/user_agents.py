"""
Актуальные User-Agent строки для Desktop и Mobile устройств
Обновлено: 2024 год
"""

# ==============================
# DESKTOP USER AGENTS
# ==============================

DESKTOP_USER_AGENTS = [
    # Chrome (последние версии)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',

    # Firefox (последние версии)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:131.0) Gecko/20100101 Firefox/131.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0',
    'Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0',
    'Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0',

    # Safari (Mac)
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',

    # Edge (Windows)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0',

    # Opera
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/116.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 OPR/115.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/116.0.0.0',

    # Более старые, но все еще популярные версии Chrome
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',

    # Более старые версии Firefox
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',

    # Windows 11 специфичные
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0',

    # Ubuntu/Linux
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',

    # macOS Sonoma/Ventura
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
]

# ==============================
# MOBILE USER AGENTS
# ==============================

MOBILE_USER_AGENTS = [
    # iPhone (iOS 17/18)
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/131.0.0.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1',

    # iPhone Chrome
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) CriOS/131.0.0.0 Mobile/15E148 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) CriOS/130.0.0.0 Mobile/15E148 Safari/537.36',

    # iPhone Firefox
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/130.0 Mobile/15E148 Safari/605.1.15',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/129.0 Mobile/15E148 Safari/605.1.15',

    # iPad
    'Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 17_6 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) CriOS/131.0.0.0 Mobile/15E148 Safari/537.36',

    # Android Phone (Samsung Galaxy S24/S23)
    'Mozilla/5.0 (Linux; Android 14; SM-S926B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',

    # Android Phone (Google Pixel 8/7)
    'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',

    # Android Phone (Xiaomi)
    'Mozilla/5.0 (Linux; Android 14; 23013PC75G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; 2304FPN6DG) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; 2210132G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',

    # Android Phone (OnePlus)
    'Mozilla/5.0 (Linux; Android 14; CPH2581) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; CPH2605) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',

    # Android Phone (Huawei)
    'Mozilla/5.0 (Linux; Android 14; LIO-AL00) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; TET-AN00) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',

    # Android Tablet (Samsung)
    'Mozilla/5.0 (Linux; Android 14; SM-X810) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; SM-X616B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; SM-P613) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',

    # Android Tablet (Lenovo)
    'Mozilla/5.0 (Linux; Android 14; Lenovo TB-X6C6F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; Lenovo TB-8505F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',

    # Android Chrome более старые версии
    'Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 13; SM-S906B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 13; SM-G996B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36',

    # Android Firefox
    'Mozilla/5.0 (Android 14; Mobile; rv:131.0) Gecko/131.0 Firefox/131.0',
    'Mozilla/5.0 (Android 14; Mobile; rv:130.0) Gecko/130.0 Firefox/130.0',
    'Mozilla/5.0 (Android 13; Mobile; rv:129.0) Gecko/129.0 Firefox/129.0',

    # Android Samsung Internet
    'Mozilla/5.0 (Linux; Android 14; SM-S926B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/24.0 Chrome/120.0.0.0 Mobile Safari/537.36',

    # Android Opera
    'Mozilla/5.0 (Linux; Android 14; SM-S926B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36 OPR/79.0.2254.73179',
    'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36 OPR/78.0.4093.184146',

    # Windows Phone (редкие, но могут встречаться)
    'Mozilla/5.0 (Windows Phone 10.0; Android 6.0.1; Microsoft; Lumia 950) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36 Edge/121.0.0.0',

    # Kindle
    'Mozilla/5.0 (Linux; Android 9; KFKAWI) AppleWebKit/537.36 (KHTML, like Gecko) Silk/124.0.0 like Chrome/124.0.0.0 Safari/537.36',
]

# ==============================
# MOBILE DEVICE CONFIGURATIONS
# ==============================

MOBILE_DEVICE_CONFIGS = {
    'iphone_14': {
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1',
        'viewport': 'width=390, height=844',
        'pixel_ratio': 3,
        'touch': True,
        'mobile': True
    },
    'iphone_14_pro': {
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1',
        'viewport': 'width=393, height=852',
        'pixel_ratio': 3,
        'touch': True,
        'mobile': True
    },
    'iphone_15': {
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1',
        'viewport': 'width=393, height=852',
        'pixel_ratio': 3,
        'touch': True,
        'mobile': True
    },
    'samsung_galaxy_s24': {
        'user_agent': 'Mozilla/5.0 (Linux; Android 14; SM-S926B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
        'viewport': 'width=412, height=915',
        'pixel_ratio': 2.625,
        'touch': True,
        'mobile': True
    },
    'samsung_galaxy_s23': {
        'user_agent': 'Mozilla/5.0 (Linux; Android 13; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
        'viewport': 'width=412, height=915',
        'pixel_ratio': 2.625,
        'touch': True,
        'mobile': True
    },
    'google_pixel_8': {
        'user_agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
        'viewport': 'width=412, height=915',
        'pixel_ratio': 2.625,
        'touch': True,
        'mobile': True
    },
    'google_pixel_7': {
        'user_agent': 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
        'viewport': 'width=412, height=915',
        'pixel_ratio': 2.625,
        'touch': True,
        'mobile': True
    },
    'ipad_pro_11': {
        'user_agent': 'Mozilla/5.0 (iPad; CPU OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1',
        'viewport': 'width=834, height=1194',
        'pixel_ratio': 2,
        'touch': True,
        'mobile': True
    },
    'samsung_tab_s9': {
        'user_agent': 'Mozilla/5.0 (Linux; Android 14; SM-X810) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'viewport': 'width=712, height=1138',
        'pixel_ratio': 2.25,
        'touch': True,
        'mobile': True
    },
    'xiaomi_13': {
        'user_agent': 'Mozilla/5.0 (Linux; Android 13; 2210132G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
        'viewport': 'width=393, height=873',
        'pixel_ratio': 2.75,
        'touch': True,
        'mobile': True
    },
    'oneplus_11': {
        'user_agent': 'Mozilla/5.0 (Linux; Android 13; CPH2451) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
        'viewport': 'width=412, height=915',
        'pixel_ratio': 2.625,
        'touch': True,
        'mobile': True
    }
}


# ==============================
# UTILITY FUNCTIONS
# ==============================

def get_random_desktop_agent():
    """Получить случайный desktop user agent"""
    import random
    return random.choice(DESKTOP_USER_AGENTS)


def get_random_mobile_agent():
    """Получить случайный mobile user agent"""
    import random
    return random.choice(MOBILE_USER_AGENTS)


def get_random_agent(device_type='desktop'):
    """
    Получить случайный user agent по типу устройства

    Args:
        device_type (str): 'desktop' или 'mobile'

    Returns:
        str: user agent строка
    """
    import random
    if device_type.lower() == 'mobile':
        return random.choice(MOBILE_USER_AGENTS)
    else:
        return random.choice(DESKTOP_USER_AGENTS)


def get_device_config(device_name):
    """
    Получить конфигурацию мобильного устройства по имени

    Args:
        device_name (str): Имя устройства из MOBILE_DEVICE_CONFIGS

    Returns:
        dict: Конфигурация устройства или None если не найдено
    """
    return MOBILE_DEVICE_CONFIGS.get(device_name.lower())


def get_all_agents():
    """Получить все user agents"""
    return DESKTOP_USER_AGENTS + MOBILE_USER_AGENTS


def get_agent_count():
    """Получить количество доступных user agents"""
    return {
        'desktop': len(DESKTOP_USER_AGENTS),
        'mobile': len(MOBILE_USER_AGENTS),
        'total': len(DESKTOP_USER_AGENTS) + len(MOBILE_USER_AGENTS)
    }


# ==============================
# CHROME OPTIONS FOR MOBILE
# ==============================

def get_mobile_chrome_options(device_name=None):
    """
    Получить опции Chrome для мобильного устройства

    Args:
        device_name (str, optional): Имя устройства из MOBILE_DEVICE_CONFIGS

    Returns:
        tuple: (user_agent, viewport, pixel_ratio)
    """
    from selenium.webdriver.chrome.options import Options

    chrome_options = Options()

    if device_name and device_name.lower() in MOBILE_DEVICE_CONFIGS:
        config = MOBILE_DEVICE_CONFIGS[device_name.lower()]
        user_agent = config['user_agent']
        viewport = config['viewport']
        pixel_ratio = config['pixel_ratio']
    else:
        user_agent = get_random_mobile_agent()
        viewport = 'width=412, height=915'  # Средние размеры мобильного
        pixel_ratio = 2.625

    # Добавляем мобильные опции
    chrome_options.add_argument(f'user-agent={user_agent}')
    chrome_options.add_argument('--use-mobile-user-agent')
    chrome_options.add_argument('--enable-viewport')

    # Эмулируем сенсорный экран
    chrome_options.add_experimental_option("mobileEmulation", {
        "deviceMetrics": {
            "width": int(viewport.split('width=')[1].split(',')[0]),
            "height": int(viewport.split('height=')[1]),
            "pixelRatio": pixel_ratio,
            "touch": True
        },
        "userAgent": user_agent
    })

    return chrome_options, user_agent, viewport


# Экспорт основных списков
__all__ = [
    'DESKTOP_USER_AGENTS',
    'MOBILE_USER_AGENTS',
    'MOBILE_DEVICE_CONFIGS',
    'get_random_desktop_agent',
    'get_random_mobile_agent',
    'get_random_agent',
    'get_device_config',
    'get_all_agents',
    'get_agent_count',
    'get_mobile_chrome_options'
]

if __name__ == "__main__":
    # Пример использования
    print(f"Доступно Desktop User Agents: {len(DESKTOP_USER_AGENTS)}")
    print(f"Доступно Mobile User Agents: {len(MOBILE_USER_AGENTS)}")
    print(f"Всего User Agents: {len(DESKTOP_USER_AGENTS) + len(MOBILE_USER_AGENTS)}")

    # Пример случайного выбора
    print(f"\nСлучайный Desktop: {get_random_desktop_agent()[:80]}...")
    print(f"Случайный Mobile: {get_random_mobile_agent()[:80]}...")

    # Пример конфигурации устройства
    iphone_config = get_device_config('iphone_15')
    if iphone_config:
        print(f"\nКонфигурация iPhone 15:")
        print(f"  User Agent: {iphone_config['user_agent'][:80]}...")
        print(f"  Viewport: {iphone_config['viewport']}")
        print(f"  Pixel Ratio: {iphone_config['pixel_ratio']}")