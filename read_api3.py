with open('C:/Users/PROSPERO/Aethera/python/aethera/api.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i in range(298, 310):
        print(f'{i+1:4d}: {lines[i]}', end='')
