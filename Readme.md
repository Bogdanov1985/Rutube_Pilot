# Скачать драйвера Chromedriver  

https://www.chromedriverdownload.com/en/downloads/chromedriver-143-download


# Запуск скрипта 1 версия 
## Способ 1: Из файла
bash
```
python rutube_viewer.py --file videos.txt --time 60 --shuffle
```

## Способ 2: Прямое указание ссылок
bash
```
python rutube_viewer.py --urls "https://rutube.ru/video/1234567890/" "https://rutube.ru/video/0987654321/" --time 45
```

## Способ 3: Фоновый режим (headless)
bash
```
python rutube_viewer.py --file videos.txt --headless --time 30
```

## Способ 4: С ограничением количества видео
bash
```
python rutube_viewer.py --file videos.txt --max 5 --time 40
```

# Примеры использования с новой переменной GUI:
## 1. С графическим интерфейсом (по умолчанию)
bash
```
# Браузер будет виден на экране
python rutube_viewer.py --file videos.txt --gui
# или просто (так как --gui включен по умолчанию)
python rutube_viewer.py --file videos.txt
```

## 2. Без графического интерфейса (headless режим)
bash
```
# Браузер работает в фоновом режиме, окно не отображается
python rutube_viewer.py --file videos.txt --no-gui
```

## 3. Со всеми настройками
bash
```
python rutube_viewer.py \
  --file videos.txt \
  --no-gui \
  --no-incognito \
  --time 45 \
  --shuffle \
  --max 5
```

## 4. С GUI и без инкогнито
bash
```
python rutube_viewer_new.py --file videos.txt --gui --no-incognito
```

# 1. Поместите chromedriver в selenium-server и запускайте:
```
№ первая версия 
python rutube_viewer.py --file videos.txt

# версия с путями к драйверам 
python rutube_viewer_new.py --file videos.txt

# оптимизированный 
python rutube_viewer_opti.py --file videos.txt

# оптимизированный c зкрытием окна рекламы
python rutube_viewer_close.py --file videos.txt


# Headless режим
python rutube_viewer_opti.py --file videos.txt --no-gui
```

# 2. Или укажите явный путь:
```
python rutube_viewer.py --file videos.txt --chromedriver "./selenium-server/chromedriver.exe"
```

# 3. Через переменную окружения:
```
export CHROMEDRIVER_PATH=./selenium-server/chromedriver
python rutube_viewer.py --file videos.txt
```

# Основные изменения:
## 1. Переменная gui_mode - управляет отображением браузера:
* True (по умолчанию) - браузер отображается на экране
* False - headless режим, браузер работает в фоне

## 2. Аргументы командной строки:
* --gui - запуск с графическим интерфейсом (включено по умолчанию)
* --no-gui - запуск без графического интерфейса

## 3. Улучшенная визуализация:
* Красивое отображение информации о режиме работы
* Информация о настройках при запуске

## 4. Оптимизация для разных режимов:
* В GUI режиме - реальные движения мыши и видимое взаимодействие
* В headless режиме - оптимизированные имитации

## 5. Автоматическая установка драйвера:
* Добавлена поддержка webdriver-manager для автоматической загрузки ChromeDriver

# 6. Требуемая структура проекта:
text
```
ваш_проект/
├── rutube_viewer.py
├── selenium-server/           # Создайте этот каталог
│   ├── chromedriver.exe       # Для Windows
│   └── chromedriver           # Для Linux/Mac
├── videos.txt
└── requirements.txt
```