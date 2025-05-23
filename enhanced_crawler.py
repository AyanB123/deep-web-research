"""
Enhanced Tor Crawler module with OnionLinkDatabase integration.
This module provides advanced dark web crawling capabilities with
onion link discovery, search engine integration, and database storage.
Includes robust error handling, content filtering, and parallel crawling.
"""

import requests
from bs4 import BeautifulSoup
import random
import time
import re
import datetime
import json
import urllib.parse
from urllib.parse import urljoin, urlparse

from config import Config
from utils import log_action, randomize_delay
from onion_database import OnionLinkDatabase
from connection_manager import ConnectionManager
from retry_utils import retry_with_backoff, retry_operation
from content_safety import ContentSafetyClassifier
from crawler_pool import CrawlerPool
from clearnet_search import TavilySearch

class EnhancedTorCrawler:
    """
    Enhanced Tor Crawler with database integration and advanced discovery features.
    Includes robust error handling, content filtering, and parallel crawling capabilities.
    """
    
    def __init__(self, link_db=None):
        """
        Initialize the enhanced crawler with an optional database connection.
        
        Args:
            link_db: OnionLinkDatabase instance (optional). If not provided, a new one will be created.
        """
        # Database and configuration
        self.link_db = link_db or OnionLinkDatabase()
        self.discovery_mode = Config.DISCOVERY_MODE
        
        # Initialize connection manager for robust Tor/clearnet handling
        self.connection_manager = ConnectionManager(
            tor_enabled=Config.TOR_ENABLED,
            clearnet_fallback=Config.CLEARNET_FALLBACK_ENABLED
        )
        self.session = None  # Will be set by start_tor_session
        
        # Initialize content safety classifier if filtering is enabled
        self.content_safety = ContentSafetyClassifier() if Config.NSFW_CONTENT_FILTERING else None
        
        # Initialize parallel crawling components
        self.parallel_enabled = Config.PARALLEL_CRAWLING_ENABLED
        self.crawler_pool = CrawlerPool(
            max_workers=Config.MAX_CRAWLER_WORKERS,
            rate_limit_per_domain=Config.DOMAIN_RATE_LIMIT
        )
        
        # Initialize clearnet fallback search
        self.tavily_search = TavilySearch() if Config.CLEARNET_FALLBACK_ENABLED else None
        
        # Error tracking
        self.error_count = 0
        self.max_consecutive_errors = 5
        
        # Expanded list of user agents for better stealth
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"
        ]
        
        # Initialize directories if necessary
        Config.init_directories()
    
    def start_tor_session(self):
        """Start a new Tor session using the connection manager."""
        log_action("Starting Tor session via connection manager")
        # Get a session from the connection manager
        self.session = self.connection_manager.get_session(force_clearnet=False)
        
        # Check if Tor proxy is reachable
        connection_status = self.check_tor_connection()
        if connection_status:
            log_action("Tor connection successful")
        else:
            log_action("Warning: Tor connection failed. Using fallback if enabled.")
    
    def check_tor_connection(self):
        """
        Check if the Tor proxy is reachable by attempting a simple request.
        Returns True if connection is successful, False otherwise.
        Uses the connection manager for robust error handling.
        """
        log_action("Checking Tor connection...")
        if not self.session:
            log_action("Session not initialized. Initializing connection.")
            self.session = self.connection_manager.get_session()
        
        test_url = "https://check.torproject.org/api/ip"
        
        try:
            # Use the connection manager's perform_request method for robust error handling
            response = self.connection_manager.perform_request(
                "get",
                test_url,
                timeout=10,
                max_retries=2
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("IsTor", False):
                    return True
                else:
                    log_action("Connected but not routing through Tor network.")
                    return False
            else:
                log_action(f"Unexpected response code from Tor check: {response.status_code}")
                return False
        except Exception as e:
            log_action(f"Failed to connect to Tor: {str(e)}")
            return False
    
    def check_onion_status(self, url, timeout=10):
        """
        Check if an onion site is up by attempting a simple HEAD request.
        
        Args:
            url (str): The onion URL to check
            timeout (int): Request timeout in seconds
            
        Returns:
            bool: True if site is up, False otherwise
        """
        try:
            # Get the appropriate session
            if not self.session:
                self.start_tor_session()
                
            # Use the connection manager to perform the request
            start_time = time.time()
            
            # Use a HEAD request (faster than GET)
            response = self.connection_manager.perform_request(
                "head",
                url,
                timeout=timeout,
                max_retries=1
            )
            
            # Calculate response time
            response_time = time.time() - start_time
            
            # Record the successful check in the database
            self.link_db.add_crawl_history(url, "success", response_time=response_time)
            return True
            
        except Exception as e:
            # Calculate response time even for failures
            response_time = time.time() - start_time if 'start_time' in locals() else 0
            error_message = str(e)
            
            # Record the failed check in the database
            self.link_db.add_crawl_history(url, "error", response_time=response_time, error_message=error_message)
            return False
    
    def crawl_with_recovery(self, url, max_depth=Config.CRAWL_DEPTH):
        """
        Crawl with automatic recovery from failures.
        
        Args:
            url (str): The onion URL to crawl
            max_depth (int): Maximum recursion depth
            
        Returns:
            dict: Crawled data including content, links, and errors
        """
        try:
            # Use retry_operation from retry_utils for automatic retry with backoff
            return retry_operation(
                lambda: self.crawl_onion(url, max_depth),
                max_retries=Config.MAX_RETRIES,
                initial_delay=Config.RETRY_INITIAL_DELAY,
                backoff_factor=Config.RETRY_BACKOFF_FACTOR
            )
        except Exception as e:
            self.error_count += 1
            log_action(f"Error crawling {url} after multiple retries: {str(e)}")
            
            if self.error_count >= self.max_consecutive_errors and Config.CLEARNET_FALLBACK_ENABLED:
                log_action("Too many consecutive errors, switching to clearnet mode")
                # Switch to clearnet fallback
                return self._clearnet_fallback(url)
                
            return {
                "url": url, 
                "content": "", 
                "links": [], 
                "errors": [str(e)],
                "title": ""
            }
    
    def crawl_onion(self, url, max_depth=Config.CRAWL_DEPTH, store_in_db=True):
        """
        Crawl an onion site and its links up to a specified depth.
        
        Args:
            url (str): The onion URL to crawl
            max_depth (int): Maximum recursion depth
            store_in_db (bool): Whether to store the results in the database
            
        Returns:
            dict: Crawled data including content, links, and errors
        """
        if not self.session:
            self.start_tor_session()
        
        headers = {"User-Agent": random.choice(self.user_agents)}
        crawled_data = {"url": url, "content": "", "links": [], "errors": [], "title": "", "response_time": 0}
        
        try:
            log_action(f"Crawling: {url}")
            start_time = time.time()
            response = self.session.get(url, headers=headers, timeout=30)
            response_time = time.time() - start_time
            crawled_data["response_time"] = response_time
            
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extract title
            title_tag = soup.find("title")
            if title_tag:
                crawled_data["title"] = title_tag.get_text(strip=True)
            
            # Extract meta description
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                crawled_data["description"] = meta_desc.get("content", "")
            
            # Extract text content
            crawled_data["content"] = soup.get_text(separator=" ", strip=True)
            
            # Extract all links
            for a_tag in soup.find_all("a", href=True):
                href = a_tag.get("href")
                # Handle relative links
                if not href.startswith(("http://", "https://")):
                    href = urljoin(url, href)
                
                # Only add onion links
                if ".onion" in href:
                    crawled_data["links"].append(href)
                    
                    # If storing in DB, add discovered links to the database
                    if store_in_db:
                        link_text = a_tag.get_text(strip=True)
                        self.link_db.add_link(
                            url=href,
                            title=link_text[:100] if link_text else "",
                            discovery_source=url
                        )
            
            # Update the database with crawled data if requested
            if store_in_db:
                content_preview = crawled_data["content"][:Config.CONTENT_PREVIEW_MAX_LENGTH]
                metadata = {
                    "last_crawled": datetime.datetime.now().isoformat(),
                    "response_time": response_time
                }
                
                if crawled_data["was_filtered"]:
                    metadata["filtered"] = True
                    metadata["filter_reason"] = crawled_data["filter_reason"]
                
                self.link_db.update_link(
                    url=url,
                    title=crawled_data["title"],
                    description=crawled_data.get("description", ""),
                    content_preview=content_preview,
                    status="active",
                    metadata=metadata
                )
                
                # Add successful crawl to history
                self.link_db.add_crawl_history(url, "success", response_time=response_time)
            
            # Reset error count on successful crawl
            self.error_count = 0
            
            # Recursive crawling if depth allows
            if max_depth > 0:
                # Use parallel crawling if enabled for subpages
                links_to_crawl = crawled_data["links"][:Config.LINK_LIMIT_PER_PAGE]
                
                if self.parallel_enabled and len(links_to_crawl) > 1 and max_depth > 1:
                    # Parallel crawling for efficiency
                    log_action(f"Parallel crawling {len(links_to_crawl)} subpages from {url}")
                    sub_results = self.crawler_pool.crawl_batch(
                        self, links_to_crawl, max_depth=max_depth-1
                    )
                    
                    # Combine results
                    for link, sub_data in sub_results.items():
                        if sub_data.get("content"):
                            crawled_data["content"] += f"\n\n--- Subpage: {link} ---\n{sub_data['content']}"
                        crawled_data["links"].extend(sub_data.get("links", []))
                        crawled_data["errors"].extend(sub_data.get("errors", []))
                else:
                    # Sequential crawling
                    for link in links_to_crawl:
                        randomize_delay(Config.CRAWL_DELAY_MIN, Config.CRAWL_DELAY_MAX)
                        sub_data = self.crawl_onion(link, max_depth - 1, store_in_db)
                        if sub_data.get("content"):
                            crawled_data["content"] += f"\n\n--- Subpage: {link} ---\n{sub_data['content']}"
                        crawled_data["links"].extend(sub_data.get("links", []))
                        crawled_data["errors"].extend(sub_data.get("errors", []))
            
        except Exception as e:
            error_msg = f"Error crawling {url}: {str(e)}"
            log_action(error_msg)
            crawled_data["errors"].append(error_msg)
            
            # Update database with error status if requested
            if store_in_db:
                self.link_db.update_link_status(url, "error")
                self.link_db.add_crawl_history(
                    url, "error", 
                    response_time=time.time() - start_time if "start_time" in locals() else 0,
                    error_message=str(e)
                )
                
            # Increment error count
            self.error_count += 1
        
        return crawled_data
        
    def _clearnet_fallback(self, url):
        """
        Attempt to get data via clearnet APIs instead of Tor.
        
        Args:
            url (str): The onion URL that failed to load
            
        Returns:
            dict: Data formatted to match crawl_onion output
        """
        if not self.tavily_search:
            return {"url": url, "content": "", "links": [], 
                    "errors": ["No clearnet fallback available"], "title": ""}
            
        # Extract search terms from URL and use clearnet search
        search_terms = self.tavily_search.extract_search_terms(url)
        log_action(f"Using clearnet fallback for {url} with search terms: {search_terms}")
        
        results = self.tavily_search.search(search_terms)
        
        if not results:
            return {"url": url, "content": "", "links": [], 
                    "errors": ["No results from clearnet fallback"], "title": ""}
        
        # Format results to match crawl_onion output
        combined_content = "\n\n".join([f"--- {r.get('title', '')} ---\n{r.get('content', '')}" 
                               for r in results])
        
        fallback_data = {
            "url": url,
            "content": f"[CLEARNET FALLBACK RESULTS]\n\n{combined_content}",
            "links": [r.get("url") for r in results],
            "errors": [],
            "title": f"Clearnet results for {search_terms}",
            "from_clearnet": True,
            "clearnet_results": results
        }
        
        # Store in database that we used clearnet fallback
        self.link_db.update_link(
            url=url,
            status="clearnet_fallback",
            metadata={
                "last_checked": datetime.datetime.now().isoformat(),
                "clearnet_fallback": True,
                "search_terms": search_terms
            }
        )
        
        return fallback_data
    
    def discover_from_directories(self, max_sites=Config.DISCOVERY_SITES_LIMIT):
        """
        Extract links from directory sites using parallel crawling when enabled.
        
        Args:
            max_sites (int): Maximum number of directory sites to crawl
            
        Returns:
            int: Number of new onion links discovered
        """
        directories = self.link_db.get_links_by_category("directory", limit=max_sites)
        discovered_count = 0
        
        if not directories:
            log_action("No directory sites found in database. Run seed_data module first.")
            return 0
        
        # Use parallel crawling if enabled
        if self.parallel_enabled and len(directories) > 1:
            log_action(f"Parallel discovery from {len(directories)} directories")
            
            # Prepare URLs for parallel crawling
            directory_urls = [d["url"] for d in directories]
            
            # Use the crawler pool for parallel execution
            results = self.crawler_pool.crawl_batch(
                self, directory_urls, max_depth=0
            )
            
            # Process results
            for url, data in results.items():
                if data and "links" in data:
                    log_action(f"Discovered {len(data['links'])} links from {url}")
                    discovered_count += len(data["links"])
                else:
                    log_action(f"No links discovered from {url} or crawl failed")
        else:
            # Sequential discovery
            for directory in directories:
                try:
                    url = directory["url"]
                    log_action(f"Discovering links from directory: {directory['title']} ({url})")
                    
                    # Use crawl_with_recovery for robust error handling
                    data = self.crawl_with_recovery(url, max_depth=0)
                    
                    # Count new links discovered
                    if data and "links" in data:
                        discovered_count += len(data["links"])
                        log_action(f"Discovered {len(data['links'])} links from {url}")
                    
                    # Apply delay between directory crawls
                    randomize_delay(Config.CRAWL_DELAY_MIN, Config.CRAWL_DELAY_MAX)
                    
                except Exception as e:
                    log_action(f"Error discovering from directory {directory['url']}: {str(e)}")
        
        return discovered_count
    
    def format_search_url(self, engine_url, query):
        """
        Format a search query URL for different dark web search engines.
        
        Args:
            engine_url (str): Base URL of the search engine
            query (str): Search query
            
        Returns:
            str: Formatted search URL
        """
        query_encoded = requests.utils.quote(query)
        
        # Different formatting for different engines
        if "ahmia" in engine_url:
            return f"{engine_url}/search/?q={query_encoded}"
        elif "torch" in engine_url:
            return f"{engine_url}/search?query={query_encoded}"
        elif "haystak" in engine_url:
            return f"{engine_url}/search?q={query_encoded}"
        elif "demon" in engine_url:
            return f"{engine_url}/search?q={query_encoded}"
        else:
            # Generic search query format
            return f"{engine_url}/search?q={query_encoded}"
    
    def search_engines_query(self, query, max_engines=Config.SEARCH_ENGINES_LIMIT):
        """
        Query dark web search engines for a specific search term.
        Uses parallel crawling when enabled and falls back to clearnet search if configured.
        
        Args:
            query (str): Search query
            max_engines (int): Maximum number of search engines to query
            
        Returns:
            list: List of discovered onion URLs
        """
        engines = self.link_db.get_links_by_category("search_engine", limit=max_engines)
        discovered_urls = []
        
        if not engines:
            log_action("No search engines found in database. Run seed_data module first.")
            
            # Try clearnet fallback if enabled
            if Config.CLEARNET_FALLBACK_ENABLED and self.tavily_search:
                log_action("Using clearnet search as fallback")
                clearnet_results = self.tavily_search.search(query)
                
                for result in clearnet_results:
                    if result.get("url") and ".onion" in result.get("url"):
                        discovered_urls.append(result["url"])
                        
                        # Store in database with search metadata
                        self.link_db.add_link(
                            url=result["url"],
                            title=result.get("title", ""),
                            description=result.get("content", "")[:200] if result.get("content") else "",
                            discovery_source="clearnet_search",
                            metadata={
                                "search_query": query,
                                "search_engine": "clearnet_tavily",
                                "discovery_date": datetime.datetime.now().isoformat()
                            }
                        )
                
                log_action(f"Discovered {len(discovered_urls)} onion links from clearnet search")
                return discovered_urls
            
            return []
        
        # Prepare search URLs
        search_urls = [self.format_search_url(engine["url"], query) for engine in engines]
        engine_map = {self.format_search_url(e["url"], query): e for e in engines}
        
        # Use parallel crawling if enabled and multiple engines are available
        if self.parallel_enabled and len(search_urls) > 1:
            log_action(f"Parallel querying of {len(search_urls)} search engines")
            
            # Use the crawler pool for parallel execution
            results = self.crawler_pool.crawl_batch(
                self, search_urls, max_depth=0
            )
            
            # Process results from all engines
            for search_url, data in results.items():
                if data and "links" in data:
                    engine = engine_map.get(search_url, {"title": "unknown", "url": search_url})
                    
                    # Extract and store discovered links
                    for link in data["links"]:
                        if ".onion" in link and link != engine["url"] and link not in discovered_urls:
                            # Add the link to our results
                            discovered_urls.append(link)
                            
                            # Store in database with search metadata
                            self.link_db.add_link(
                                url=link,
                                discovery_source=f"search:{engine['title']}",
                                metadata={
                                    "search_query": query,
                                    "search_engine": engine["title"],
                                    "discovery_date": datetime.datetime.now().isoformat()
                                }
                            )
                    
                    log_action(f"Discovered {len(data['links'])} links from search engine {engine['url']}")
        else:
            # Sequential querying
            for engine in engines:
                try:
                    url = engine["url"]
                    log_action(f"Querying search engine: {engine['title']} ({url})")
                    
                    # Format the search URL
                    search_url = self.format_search_url(url, query)
                    
                    # Use crawl_with_recovery for robust error handling
                    data = self.crawl_with_recovery(search_url, max_depth=0)
                    
                    # Extract and store discovered links
                    if data and "links" in data:
                        for link in data["links"]:
                            if ".onion" in link and link != url and link not in discovered_urls:
                                # Add the link to our results
                                discovered_urls.append(link)
                                
                                # Store in database with search metadata
                                self.link_db.add_link(
                                    url=link,
                                    discovery_source=f"search:{engine['title']}",
                                    metadata={
                                        "search_query": query,
                                        "search_engine": engine["title"],
                                        "discovery_date": datetime.datetime.now().isoformat()
                                    }
                                )
                        
                        log_action(f"Discovered {len(data['links'])} links from search engine {url}")
                    
                    # Apply delay between search engine queries
                    randomize_delay(Config.CRAWL_DELAY_MIN * 2, Config.CRAWL_DELAY_MAX * 2)
                    
                except Exception as e:
                    log_action(f"Error querying search engine {engine['url']}: {str(e)}")
                    
                    # Try clearnet fallback if enabled and all onion searches failed
                    if Config.CLEARNET_FALLBACK_ENABLED and self.tavily_search and not discovered_urls:
                        log_action("Using clearnet search as fallback after onion search failure")
                        self._try_clearnet_search(query, discovered_urls)
        
        return discovered_urls
    
    def _try_clearnet_search(self, query, discovered_urls):
        """
        Helper method to try clearnet search and update discovered URLs list.
        
        Args:
            query (str): Search query
            discovered_urls (list): List to update with discovered onion URLs
        """
        if not self.tavily_search:
            return
            
        clearnet_results = self.tavily_search.search(query)
        
        for result in clearnet_results:
            if result.get("url") and ".onion" in result.get("url") and result["url"] not in discovered_urls:
                discovered_urls.append(result["url"])
                
                # Store in database with search metadata
                self.link_db.add_link(
                    url=result["url"],
                    title=result.get("title", ""),
                    description=result.get("content", "")[:200] if result.get("content") else "",
                    discovery_source="clearnet_search",
                    metadata={
                        "search_query": query,
                        "search_engine": "clearnet_tavily",
                        "discovery_date": datetime.datetime.now().isoformat()
                    }
                )
        
        log_action(f"Discovered {len(clearnet_results)} onion links from clearnet search")
    
    def batch_crawl(self, batch_size=Config.BATCH_CRAWL_SIZE):
        """
        Crawl a batch of unchecked or outdated onion links.
        Uses parallel crawling when enabled for increased efficiency.
        
        Args:
            batch_size (int): Number of sites to crawl in the batch
            
        Returns:
            dict: Results including successful and failed crawls
        """
        # Get links that need to be crawled
        links = self.link_db.get_unchecked_links(
            limit=batch_size, 
            older_than_hours=Config.RECRAWL_HOURS
        )
        
        results = {
            "total": len(links),
            "successful": 0,
            "failed": 0,
            "new_links_discovered": 0,
            "filtered_for_safety": 0
        }
        
        if not links:
            log_action("No links to crawl in batch")
            return results
        
        # Use parallel crawling if enabled and multiple links are available
        if self.parallel_enabled and len(links) > 1:
            log_action(f"Parallel batch crawling of {len(links)} links")
            
            # Use the crawler pool for parallel execution
            crawl_results = self.crawler_pool.crawl_batch(
                self, links, max_depth=1
            )
            
            # Process results
            for url, data in crawl_results.items():
                if data:
                    if not data.get("errors"):
                        results["successful"] += 1
                        results["new_links_discovered"] += len(data.get("links", []))
                        
                        # Track filtered content
                        if data.get("was_filtered"):
                            results["filtered_for_safety"] += 1
                    else:
                        results["failed"] += 1
                else:
                    results["failed"] += 1
        else:
            # Sequential crawling
            for link in links:
                try:
                    log_action(f"Batch crawling: {link}")
                    
                    # Use crawl_with_recovery for robust error handling
                    data = self.crawl_with_recovery(link, max_depth=1)
                    
                    if data and not data.get("errors"):
                        results["successful"] += 1
                        results["new_links_discovered"] += len(data.get("links", []))
                        
                        # Track filtered content
                        if data.get("was_filtered"):
                            results["filtered_for_safety"] += 1
                    else:
                        results["failed"] += 1
                    
                    # Apply delay between crawls
                    randomize_delay(Config.CRAWL_DELAY_MIN, Config.CRAWL_DELAY_MAX)
                    
                except Exception as e:
                    log_action(f"Error in batch crawl for {link}: {str(e)}")
                    results["failed"] += 1
        
        log_action(f"Batch crawl completed: {results['successful']} successful, {results['failed']} failed, {results['filtered_for_safety']} filtered")
        return results
    
    def categorize_content(self, url, content):
        """
        Use Gemini AI to categorize the content of an onion site.
        
        Args:
            url (str): The onion URL
            content (str): The site content
            
        Returns:
            str: Predicted category
        """
        if not Config.CONTENT_CATEGORIZATION_ENABLED:
            return "uncategorized"
            
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            
            categorizer = ChatGoogleGenerativeAI(
                model=Config.DEFAULT_MODEL,
                google_api_key=Config.GEMINI_API_KEY,
                temperature=0.2
            )
            
            # Truncate content to a reasonable length
            trimmed_content = content[:5000]
            
            prompt = f"""
            Analyze this dark web content and categorize it into one of these categories:
            - marketplace (e.g., selling goods/services)
            - forum (e.g., discussion boards)
            - news (e.g., information/articles)
            - services (e.g., email, hosting)
            - social (e.g., social networking)
            - technical (e.g., technical tools, wikis)
            - financial (e.g., cryptocurrency, banking)
            - other
            
            Content from {url}:
            {trimmed_content}
            
            Return ONLY the category name and nothing else.
            """
            
            category = categorizer.invoke(prompt).content.strip().lower()
            log_action(f"Categorized {url} as: {category}")
            
            # Update the category in the database
            self.link_db.update_link(url=url, category=category)
            
            return category
            
        except Exception as e:
            log_action(f"Error categorizing content for {url}: {str(e)}")
            return "uncategorized"
    
    def deep_discovery_run(self, query=None):
        """
        Perform a comprehensive discovery run including directory crawling,
        search engine queries, and batch crawling.
        
        Args:
            query (str, optional): Search query for search engines
            
        Returns:
            dict: Discovery statistics
        """
        stats = {
            "directories_crawled": 0,
            "search_engines_queried": 0,
            "sites_crawled": 0,
            "new_links_discovered": 0
        }
        
        log_action("Starting deep discovery run...")
        
        # 1. Discover from directories
        log_action("Phase 1: Discovering from directories")
        dir_limit = Config.DISCOVERY_SITES_LIMIT
        if self.discovery_mode == "aggressive":
            dir_limit *= 2
        
        discovered = self.discover_from_directories(max_sites=dir_limit)
        stats["directories_crawled"] = dir_limit
        stats["new_links_discovered"] += discovered
        
        # 2. Query search engines if a query is provided
        if query:
            log_action(f"Phase 2: Querying search engines for: {query}")
            engine_limit = Config.SEARCH_ENGINES_LIMIT
            if self.discovery_mode == "aggressive":
                engine_limit *= 2
                
            search_results = self.search_engines_query(query, max_engines=engine_limit)
            stats["search_engines_queried"] = engine_limit
            stats["new_links_discovered"] += len(search_results)
        
        # 3. Batch crawl discovered sites
        log_action("Phase 3: Batch crawling discovered sites")
        batch_size = Config.BATCH_CRAWL_SIZE
        if self.discovery_mode == "aggressive":
            batch_size *= 2
        elif self.discovery_mode == "passive":
            batch_size = max(5, batch_size // 2)
            
        crawl_results = self.batch_crawl(batch_size=batch_size)
        stats["sites_crawled"] = crawl_results["successful"] + crawl_results["failed"]
        
        log_action(f"Deep discovery run completed. Statistics: {stats}")
        return stats
    
    def close(self):
        """Close the crawler sessions and database connections."""
        if self.session:
            log_action("Closing Tor session")
            self.session.close()
            self.session = None
        
        if self.link_db:
            self.link_db.close()
