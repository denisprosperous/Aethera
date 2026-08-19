with open('C:/Users/PROSPERO/Aethera/python/aethera/api.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines[500:600], start=501):
        print(f'{i:4d}: {line}', end='')
