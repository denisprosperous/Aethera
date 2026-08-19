import sys
sys.path.insert(0, 'python')
import uvicorn

if __name__ == "__main__":
    uvicorn.run("aethera.api:app", host="0.0.0.0", port=8765, reload=False)
