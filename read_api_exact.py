with open('C:/Users/PROSPERO/Aethera/python/aethera/api.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i in range(295, 315):
        print(f'{i+1:4d}: {repr(lines[i])}', end='')
