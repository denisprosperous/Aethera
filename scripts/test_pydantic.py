import sys
sys.path.insert(0, 'python')
from pydantic import BaseModel
from typing import List, Dict, Optional, Any

class TestRequest(BaseModel):
    polygons: List[Dict[str, Any]]
    global_enclosure: str
    global_area: float

data = {
    'polygons': [
        {'name': 'A', 'area': 100, 'neighbours': ['B']},
        {'name': 'B', 'area': None, 'neighbours': ['A']},
    ],
    'global_enclosure': 'World',
    'global_area': 500
}

try:
    req = TestRequest(**data)
    print('Parsed OK:', req)
except Exception as e:
    print('Error:', e)
