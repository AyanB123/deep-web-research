"""
Crawler pool module for parallel crawling with proper rate limiting.
Provides efficient batch crawling while respecting site limitations.
"""

import concurrent.futures
import time
import random
import urllib.parse
from threading import Lock
from utils import log_action

class CrawlerPool:
    """
    Manages a pool of crawler workers for parallel crawling operations.
    Implements domain-based rate limiting to avoid overloading sites.
    """
    
    def __init__(self, max_workers=5, rate_limit_per_domain=1.0):
        """
        Initialize a crawler pool for parallel crawling.
        
        Args:
            max_workers (int): Maximum number of parallel crawlers
            rate_limit_per_domain (float): Minimum seconds between requests to same domain
        """
        self.max_workers = max_workers
        self.rate_limit = rate_limit_per_domain
        self.domain_last_crawl = {}  # Domain -> timestamp
        self.domain_lock = Lock()
        self.active = True
        
    def crawl_batch(self, crawler, urls, max_depth=1):
        """
        Crawl a batch of URLs in parallel.
        
        Args:
            crawler: EnhancedTorCrawler instance
            urls (list): List of URLs to crawl
            max_depth (int): Maximum crawl depth
            
        Returns:
            dict: URL -> crawl results
        """
        if not urls:
            return {}
            
        results = {}
        log_action(f"Starting parallel crawl of {len(urls)} URLs with {self.max_workers} workers")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all crawl tasks
            future_to_url = {
                executor.submit(self._rate_limited_crawl, crawler, url, max_depth): url
                for url in urls
            }
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    results[url] = future.result()
                    log_action(f"Completed parallel crawl of {url}")
                except Exception as e:
                    log_action(f"Error in parallel crawl of {url}: {str(e)}")
                    results[url] = {
                        "url": url, 
                        "content": "", 
                        "links": [], 
                        "errors": [str(e)]
                    }
                    
        log_action(f"Completed parallel crawl batch of {len(urls)} URLs")
        return results
    
    def _rate_limited_crawl(self, crawler, url, max_depth):
        """
        Crawl with rate limiting per domain.
        
        Args:
            crawler: EnhancedTorCrawler instance
            url (str): URL to crawl
            max_depth (int): Maximum crawl depth
            
        Returns:
            dict: Crawl results
        """
        if not self.active:
            return {"url": url, "content": "", "links": [], "errors": ["Crawler pool shutdown"]}
            
        domain = self._extract_domain(url)
        
        # Check and update domain rate limiting
        with self.domain_lock:
            now = time.time()
            last_crawl = self.domain_last_crawl.get(domain, 0)
            delay_needed = max(0, self.rate_limit - (now - last_crawl))
            
            if delay_needed > 0:
                # Add some randomness to avoid patterns
                jitter = random.uniform(0, 0.5)
                time.sleep(delay_needed + jitter)
                
            # Update last crawl time
            self.domain_last_crawl[domain] = time.time()
            
        # Perform the actual crawl
        return crawler.crawl_onion(url, max_depth=max_depth)
    
    def _extract_domain(self, url):
        """
        Extract domain from URL for rate limiting.
        
        Args:
            url (str): URL to extract domain from
            
        Returns:
            str: Domain extracted from URL
        """
        try:
            parsed_url = urllib.parse.urlparse(url)
            domain = parsed_url.netloc
            
            # If there's no netloc, use the path (for relative URLs)
            if not domain and parsed_url.path:
                # Take the first part of the path
                domain = parsed_url.path.split('/')[0]
                
            return domain
        except Exception:
            # If parsing fails, just return the URL as is
            return url
    
    def shutdown(self):
        """Shutdown the crawler pool."""
        self.active = False
