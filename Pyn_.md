```
python rutube_pro.py --file videos.txt --use-proxy --proxy-file proxies.txt


 python rutube_pro.py --proxy-only --max-proxies 1000 --max-workers 3

python rutube_viewer4.py --file videos.txt --cycles 0 --max-sessions 2 --gui --time 20-25 


# Фиксированное время 30 сек, фиксированная задержка 30 сек
python viewer.py --file videos.txt --time 30 --delay-between-cycles 30

# Случайное время 20-40 сек, фиксированная задержка 45 сек
python viewer.py --file videos.txt --time 20-40 --delay-between-cycles 45

# Фиксированное время 45 сек, случайная задержка 60-120 сек
python viewer.py --file videos.txt --time 45 --delay-between-cycles 60-120

# Случайное время 30-60 сек, случайная задержка 120-240 сек
python viewer.py --file videos.txt --time 30-60 --delay-between-cycles 120-240

# Комплексный пример
python viewer.py --file videos.txt --max-sessions 5 --time 20-40 --delay-between-cycles 30-60 --cycles 3

python rutube_viewer3.py --file videos.txt --cycles 0 --max-sessions 2 --gui --time 20-25 --delay-between-cycles 10-15

```
Параметр --time теперь принимает строку вместо int

Поддерживает форматы:

30 - фиксированное время 30 секунд

30-60 - случайное время между 30 и 60 секунд

45:90 - случайное время между 45 и 90 секунд

2. Обновлен параметр --delay-between-cycles:
Теперь принимает строку вместо int

Поддерживает те же форматы, что и --time:

30 - фиксированная задержка 30 секунд

30-60 - случайная задержка между 30 и 60 секунд

45:90 - случайная задержка между 45 и 90 секунд