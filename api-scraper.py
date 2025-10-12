import requests, csv, time, logging, random
from pathlib import Path
from typing import List, Dict, Any

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

# ---------------- CONFIG ----------------
CONFIG = {
    "search_term": "Artificial intelligence",  # Change this to your topic
    "srlimit": 50,                             # Number of search results
    "output_file": "wikipedia_ai.csv",
    "headers": {"User-Agent": "Mozilla/5.0 (UniversalScraper/1.0)"},
    "delay": 1.0,
    "timeout": 30,
    "retries": 3,
    "retry_delay": 2
}

WIKI_API_URL = "https://en.wikipedia.org/w/api.php"

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# ---------------- API CLIENT ----------------
class APIClient:
    def __init__(self, headers: Dict[str, str], delay: float = 1.0, timeout: int = 30, retries: int = 3, retry_delay: float = 2):
        self.session = requests.Session()
        self.session.headers.update(headers)
        self.delay_time = delay
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay
        self.last_request = 0

    def _respect_delay(self):
        elapsed = time.time() - self.last_request
        wait = max(0, self.delay_time - elapsed)
        if wait > 0:
            time.sleep(wait)

    def fetch(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self._respect_delay()
        for attempt in range(self.retries + 1):
            try:
                r = self.session.get(WIKI_API_URL, params=params, timeout=self.timeout)
                if r.status_code == 429:
                    retry = int(r.headers.get("Retry-After", self.retry_delay))
                    logging.warning(f"Rate limited. Waiting {retry}s...")
                    time.sleep(retry)
                    continue
                r.raise_for_status()
                self.last_request = time.time()
                return r.json()
            except Exception as e:
                logging.warning(f"Attempt {attempt+1} failed: {e}")
                time.sleep(self.retry_delay * (2**attempt) + random.random())
        logging.error("All retries failed.")
        return {}

# ---------------- EXPORT ----------------
def save_csv(filename: str, data: List[Dict[str, str]]):
    if not data:
        logging.warning("No data to save.")
        return
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    logging.info(f"Saved {len(data)} records to {filename}")

# ---------------- SCRAPER ----------------
class WikipediaScraper:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = APIClient(
            headers=config["headers"],
            delay=config["delay"],
            timeout=config["timeout"],
            retries=config["retries"],
            retry_delay=config["retry_delay"]
        )
        self.data: List[Dict[str, str]] = []

    def run(self):
        # Step 1: Search for articles
        logging.info(f"Searching Wikipedia for: '{self.config['search_term']}'")
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": self.config["search_term"],
            "srlimit": self.config["srlimit"],
            "format": "json"
        }
        search_results = self.client.fetch(search_params).get("query", {}).get("search", [])
        logging.info(f"Found {len(search_results)} articles.")

        # Step 2: Fetch intro extract for each article
        pbar = tqdm(search_results, desc="Fetching articles") if tqdm else search_results
        for item in pbar:
            title = item.get("title","content")
            extract_params = {
                "action": "query",
                "prop": "extracts",
                "titles": title,
                "exintro": True,
                "explaintext": True,
                "format": "json"
            }
            page_data = self.client.fetch(extract_params).get("query", {}).get("pages", {})
            for page_id, page in page_data.items():
                extract = page.get("extract", "")
                self.data.append({"title": title, "extract": extract})

        # Step 3: Save results
        if self.data:
            save_csv(self.config["output_file"], self.data)
        logging.info("Scraping finished successfully.")

# ---------------- RUN ----------------
if __name__ == "__main__":
    logging.info("Wikipedia Scraper Starting...")
    scraper = WikipediaScraper(CONFIG)
    scraper.run()
