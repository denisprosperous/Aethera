with open('C:/Users/PROSPERO/Aethera/python/aethera/agents/ghost.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines[50:100]):
        print(f'{i+51:4d}: {line}', end='')
