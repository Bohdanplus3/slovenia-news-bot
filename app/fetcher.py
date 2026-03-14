import httpx
from app.config import REQUEST_TIMEOUT

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

client = httpx.Client(timeout=REQUEST_TIMEOUT, headers=HEADERS, follow_redirects=True)

def get_html(url: str) -> str:
    response = client.get(url)
    response.raise_for_status()
    return response.text