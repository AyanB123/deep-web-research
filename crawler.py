import requests
from bs4 import BeautifulSoup
import random
from config import Config
from utils import log_action, randomize_delay

class TorCrawler:
    def __init__(self):
        self.proxy = Config.TOR_PROXY
        self.session = None
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
            # Add more user agents
        ]

    def start_tor_session(self):
        log_action("Starting Tor session via SOCKS proxy")
        self.session = requests.Session()
        self.session.proxies = {"http": f"socks5://{self.proxy}", "https": f"socks5://{self.proxy}"}
        # Check if Tor proxy is reachable
        connection_status = self.check_tor_connection()
        if connection_status:
            log_action("Tor proxy connection successful")
        else:
            log_action("Warning: Tor proxy connection failed. Crawling may not work as expected.")

    def check_tor_connection(self):
        """
        Check if the Tor proxy is reachable by attempting a simple request.
        Returns True if connection is successful, False otherwise.
        """
        log_action("Checking Tor proxy connection...")
        if not self.session:
            log_action("Session not initialized. Cannot check Tor connection.")
            return False
        
        test_url = "https://check.torproject.org/api/ip"
        headers = {"User-Agent": random.choice(self.user_agents)}
        try:
            response = self.session.get(test_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("IsTor", False):
                    return True
                else:
                    log_action("Tor proxy connected but not routing through Tor network.")
                    return False
            else:
                log_action(f"Unexpected response code from Tor check: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            log_action(f"Failed to connect to Tor proxy due to request error: {str(e)}")
            return False
        except Exception as e:
            log_action(f"Failed to connect to Tor proxy due to unexpected error: {str(e)}")
            return False

    def crawl_onion(self, url, max_depth=Config.CRAWL_DEPTH):
        if not self.session:
            self.start_tor_session()
        
        headers = {"User-Agent": random.choice(self.user_agents)}
        crawled_data = {"url": url, "content": "", "links": [], "errors": []}
        
        try:
            log_action(f"Crawling: {url}")
            response = self.session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extract text and links
            crawled_data["content"] = soup.get_text(separator=" ", strip=True)
            crawled_data["links"] = [a["href"] for a in soup.find_all("a", href=True) if ".onion" in a["href"]]
            
            # Recursive crawling
            if max_depth > 0:
                for link in crawled_data["links"][:Config.LINK_LIMIT_PER_PAGE]:
                    randomize_delay(Config.CRAWL_DELAY_MIN, Config.CRAWL_DELAY_MAX)
                    sub_data = self.crawl_onion(link, max_depth - 1)
                    crawled_data["content"] += f"\n\n--- Subpage: {link} ---\n{sub_data['content']}"
                    crawled_data["links"].extend(sub_data["links"])
                    crawled_data["errors"].extend(sub_data["errors"])
            
        except Exception as e:
            error_msg = f"Error crawling {url}: {str(e)}"
            log_action(error_msg)
            crawled_data["errors"].append(error_msg)
        
        return crawled_data

    def close(self):
        if self.session:
            log_action("Closing Tor session")
            self.session.close()
