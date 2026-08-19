with open('C:/Users/PROSPERO/Aethera/python/aethera/api.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    print("Lines 89-110:")
    for i in range(88, 110):
        print(f'{i+1:4d}: {lines[i]}', end='')
    print("\n\nLines 284-310:")
    for i in range(283, 310):
        print(f'{i+1:4d}: {lines[i]}', end='')
