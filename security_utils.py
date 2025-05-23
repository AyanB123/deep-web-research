"""
Security utilities for the Dark Web Discovery System.
Provides header randomization, cookie handling, and session management.
"""

import random
import time
import datetime
import logging
import os
import json
import hashlib
import re
from typing import Dict, List, Tuple, Any, Optional
from http.cookiejar import CookieJar, LWPCookieJar

import requests
from requests.structures import CaseInsensitiveDict
from urllib.parse import urlparse

from config import Config

# Configure logger
def log_action(message):
    """Log actions with timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    logging.info(message)


class RequestHeaderManager:
    """
    Manages HTTP headers for requests to avoid fingerprinting and detection.
    Provides realistic header variation similar to actual browser behavior.
    """
    
    # Common browser user agents
    USER_AGENTS = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0",
        # Safari on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
        # Chrome on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        # Firefox on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0",
        # Chrome on Linux
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        # Firefox on Linux
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0",
        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
        # Tor Browser
        "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0",
        "Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0"
    ]
    
    # Common language settings
    ACCEPT_LANGUAGES = [
        "en-US,en;q=0.9",
        "en-GB,en;q=0.9",
        "en-CA,en;q=0.9,fr-CA;q=0.8",
        "en;q=0.9",
        "en-US;q=0.9,en;q=0.8",
        "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "en-US,en;q=0.5"
    ]
    
    # Common accept headers
    ACCEPT_HEADERS = [
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    ]
    
    # Common encodings
    ACCEPT_ENCODINGS = [
        "gzip, deflate, br",
        "gzip, deflate",
        "br, gzip, deflate"
    ]
    
    def __init__(self, session_persistence: bool = True):
        """
        Initialize the header manager.
        
        Args:
            session_persistence (bool): Whether to maintain consistent headers per domain
        """
        self.session_persistence = session_persistence
        
        # Session store keyed by domain
        self.domain_sessions = {}
        
        # Store client settings by domain
        self.domain_profiles = {}
    
    def get_profile_for_domain(self, url: str) -> Dict[str, Any]:
        """
        Get or create a consistent profile for a domain.
        
        Args:
            url (str): URL to create profile for
            
        Returns:
            dict: Browser profile for the domain
        """
        domain = self._extract_domain(url)
        
        # Create new profile if it doesn't exist
        if domain not in self.domain_profiles:
            self.domain_profiles[domain] = {
                "user_agent": random.choice(self.USER_AGENTS),
                "accept_language": random.choice(self.ACCEPT_LANGUAGES),
                "accept": random.choice(self.ACCEPT_HEADERS),
                "accept_encoding": random.choice(self.ACCEPT_ENCODINGS),
                "sec_fetch_mode": random.choice(["navigate", "cors", "no-cors"]),
                "sec_fetch_site": random.choice(["none", "same-origin", "same-site", "cross-site"]),
                "sec_fetch_dest": random.choice(["document", "empty", "object"]),
                "sec_fetch_user": random.choice(["?1", ""]),
                "sec_ch_ua_platform": random.choice(['"Windows"', '"macOS"', '"Linux"']),
                "sec_ch_ua_mobile": random.choice(["?0", "?1"]),
                "upgrade_insecure_requests": "1" if random.random() > 0.2 else "",
                "do_not_track": "1" if random.random() > 0.8 else "",
                "fingerprint_id": self._generate_fingerprint()
            }
        
        return self.domain_profiles[domain]
    
    def get_headers(self, url: str, randomize_completely: bool = False) -> Dict[str, str]:
        """
        Get headers for a request with realistic variation.
        
        Args:
            url (str): URL for the request
            randomize_completely (bool): Ignore domain persistence and create random headers
            
        Returns:
            dict: HTTP headers
        """
        headers = {}
        
        if randomize_completely or not self.session_persistence:
            # Completely random headers for each request
            user_agent = random.choice(self.USER_AGENTS)
            
            headers = {
                "User-Agent": user_agent,
                "Accept": random.choice(self.ACCEPT_HEADERS),
                "Accept-Language": random.choice(self.ACCEPT_LANGUAGES),
                "Accept-Encoding": random.choice(self.ACCEPT_ENCODINGS),
                "DNT": "1" if random.random() > 0.8 else "",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1" if random.random() > 0.2 else "",
                "Cache-Control": random.choice(["max-age=0", "no-cache", ""]),
            }
            
            # Add Sec-Fetch headers (modern browsers)
            if random.random() > 0.2:
                headers["Sec-Fetch-Mode"] = random.choice(["navigate", "cors", "no-cors"])
                headers["Sec-Fetch-Site"] = random.choice(["none", "same-origin", "same-site", "cross-site"])
                headers["Sec-Fetch-Dest"] = random.choice(["document", "empty", "object"])
                if random.random() > 0.5:
                    headers["Sec-Fetch-User"] = "?1"
            
            # Randomize header order
            headers = self._randomize_header_order(headers)
        else:
            # Use consistent profile for domain with slight variations
            profile = self.get_profile_for_domain(url)
            
            headers = {
                "User-Agent": profile["user_agent"],
                "Accept": profile["accept"],
                "Accept-Language": profile["accept_language"],
                "Accept-Encoding": profile["accept_encoding"],
                "Connection": "keep-alive"
            }
            
            # Add conditional headers with some variation
            if profile["upgrade_insecure_requests"]:
                headers["Upgrade-Insecure-Requests"] = "1"
                
            if profile["do_not_track"]:
                headers["DNT"] = "1"
            
            # Add Sec-Fetch headers if in profile
            if profile["sec_fetch_mode"]:
                headers["Sec-Fetch-Mode"] = profile["sec_fetch_mode"]
                headers["Sec-Fetch-Site"] = profile["sec_fetch_site"]
                headers["Sec-Fetch-Dest"] = profile["sec_fetch_dest"]
                if profile["sec_fetch_user"]:
                    headers["Sec-Fetch-User"] = profile["sec_fetch_user"]
            
            # Add referrer occasionally if navigating on same domain
            if random.random() > 0.7:
                headers["Referer"] = self._get_plausible_referrer(url)
            
            # Random cache policy
            if random.random() > 0.6:
                headers["Cache-Control"] = random.choice(["max-age=0", "no-cache"])
            
            # Add some slight randomization
            if random.random() > 0.9:
                if "X-Forwarded-For" not in headers:
                    headers["X-Forwarded-For"] = self._generate_random_ip()
            
            # Randomize header order to prevent fingerprinting
            headers = self._randomize_header_order(headers)
        
        return headers
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            return urlparse(url).netloc
        except:
            # Fallback if URL parsing fails
            match = re.search(r'://([^/]+)', url)
            return match.group(1) if match else url
    
    def _generate_fingerprint(self) -> str:
        """Generate a unique fingerprint ID."""
        fingerprint_base = f"{random.randint(1, 1000000)}-{time.time()}"
        return hashlib.md5(fingerprint_base.encode()).hexdigest()
    
    def _randomize_header_order(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Randomize the order of headers to prevent fingerprinting."""
        headers_list = list(headers.items())
        random.shuffle(headers_list)
        return CaseInsensitiveDict(headers_list)
    
    def _generate_random_ip(self) -> str:
        """Generate a random IP address."""
        return f"{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"
    
    def _get_plausible_referrer(self, url: str) -> str:
        """Generate a plausible referrer for the URL."""
        domain = self._extract_domain(url)
        
        # Sometimes use a search engine referrer
        if random.random() > 0.7:
            search_engines = [
                "https://www.google.com/search?q=",
                "https://www.bing.com/search?q=",
                "https://search.yahoo.com/search?p=",
                "https://duckduckgo.com/?q="
            ]
            search_terms = [
                "onion+sites",
                "dark+web+search",
                "tor+hidden+services",
                domain.replace(".onion", ""),
                "anonymous+browsing"
            ]
            return random.choice(search_engines) + random.choice(search_terms)
        
        # Otherwise use the domain itself as referrer
        if ".onion" in domain:
            return f"http://{domain}/"
        else:
            return f"https://{domain}/"
    
    def clear_domain_data(self, domain: Optional[str] = None):
        """
        Clear stored data for a domain or all domains.
        
        Args:
            domain (str): Domain to clear, or None for all domains
        """
        if domain:
            if domain in self.domain_profiles:
                del self.domain_profiles[domain]
            if domain in self.domain_sessions:
                del self.domain_sessions[domain]
        else:
            self.domain_profiles.clear()
            self.domain_sessions.clear()


class CookieManager:
    """
    Manages cookies for persistent sessions with domains.
    """
    
    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize the cookie manager.
        
        Args:
            storage_dir (str): Directory to store cookies
        """
        self.storage_dir = storage_dir or os.path.join(Config.DATA_DIR, "cookies")
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Cookie jar for each domain
        self.domain_cookies = {}
    
    def get_cookie_jar(self, domain: str) -> CookieJar:
        """
        Get cookie jar for a domain.
        
        Args:
            domain (str): Domain to get cookies for
            
        Returns:
            CookieJar: Cookie jar for the domain
        """
        if domain not in self.domain_cookies:
            # Create a new cookie jar for this domain
            cookie_jar = LWPCookieJar(filename=self._get_cookie_file(domain))
            
            # Try to load existing cookies
            try:
                if os.path.exists(cookie_jar.filename):
                    cookie_jar.load(ignore_discard=True, ignore_expires=True)
                    log_action(f"Loaded cookies for domain: {domain}")
            except Exception as e:
                log_action(f"Error loading cookies for {domain}: {str(e)}")
            
            self.domain_cookies[domain] = cookie_jar
        
        return self.domain_cookies[domain]
    
    def save_cookies(self, domain: str):
        """
        Save cookies for a domain.
        
        Args:
            domain (str): Domain to save cookies for
        """
        if domain in self.domain_cookies:
            try:
                self.domain_cookies[domain].save(ignore_discard=True, ignore_expires=True)
                log_action(f"Saved cookies for domain: {domain}")
            except Exception as e:
                log_action(f"Error saving cookies for {domain}: {str(e)}")
    
    def apply_to_session(self, session: requests.Session, domain: str):
        """
        Apply cookies to a requests session.
        
        Args:
            session (requests.Session): Session to apply cookies to
            domain (str): Domain to get cookies for
        """
        session.cookies = self.get_cookie_jar(domain)
    
    def _get_cookie_file(self, domain: str) -> str:
        """Get the cookie file path for a domain."""
        # Sanitize domain for filename
        safe_domain = re.sub(r'[^\w\-_.]', '_', domain)
        return os.path.join(self.storage_dir, f"{safe_domain}_cookies.txt")
    
    def clear_cookies(self, domain: Optional[str] = None):
        """
        Clear cookies for a domain or all domains.
        
        Args:
            domain (str): Domain to clear, or None for all domains
        """
        if domain:
            if domain in self.domain_cookies:
                cookie_file = self._get_cookie_file(domain)
                if os.path.exists(cookie_file):
                    os.remove(cookie_file)
                del self.domain_cookies[domain]
                log_action(f"Cleared cookies for domain: {domain}")
        else:
            # Clear all cookies
            for cookie_file in os.listdir(self.storage_dir):
                if cookie_file.endswith("_cookies.txt"):
                    os.remove(os.path.join(self.storage_dir, cookie_file))
            self.domain_cookies.clear()
            log_action("Cleared all cookies")


class ThrottleManager:
    """
    Advanced request throttling based on site response times.
    Adapts crawl rate based on site performance and response patterns.
    """
    
    def __init__(self, 
                base_delay: float = 2.0,
                response_factor: float = 1.5,
                error_backoff: float = 2.0,
                max_delay: float = 30.0,
                jitter: float = 0.2):
        """
        Initialize the throttle manager.
        
        Args:
            base_delay (float): Base delay between requests in seconds
            response_factor (float): Multiplier for response time
            error_backoff (float): Backoff factor after errors
            max_delay (float): Maximum delay in seconds
            jitter (float): Random jitter factor to add variation
        """
        self.base_delay = base_delay
        self.response_factor = response_factor
        self.error_backoff = error_backoff
        self.max_delay = max_delay
        self.jitter = jitter
        
        # Store domain statistics
        self.domain_stats = {}
        
        # Last request time by domain
        self.last_request_time = {}
    
    def record_request(self, url: str, 
                      response_time: Optional[float] = None,
                      status_code: Optional[int] = None,
                      error: bool = False):
        """
        Record request statistics for a domain.
        
        Args:
            url (str): URL of the request
            response_time (float): Response time in seconds
            status_code (int): HTTP status code
            error (bool): Whether the request resulted in an error
        """
        domain = self._extract_domain(url)
        
        # Initialize stats for new domain
        if domain not in self.domain_stats:
            self.domain_stats[domain] = {
                "requests": 0,
                "errors": 0,
                "response_times": [],
                "status_codes": [],
                "last_error": None,
                "consecutive_errors": 0
            }
        
        # Update statistics
        stats = self.domain_stats[domain]
        stats["requests"] += 1
        
        if response_time is not None:
            stats["response_times"].append(response_time)
            # Keep only recent response times
            if len(stats["response_times"]) > 10:
                stats["response_times"] = stats["response_times"][-10:]
        
        if status_code is not None:
            stats["status_codes"].append(status_code)
            # Keep only recent status codes
            if len(stats["status_codes"]) > 20:
                stats["status_codes"] = stats["status_codes"][-20:]
        
        if error:
            stats["errors"] += 1
            stats["last_error"] = time.time()
            stats["consecutive_errors"] += 1
        else:
            stats["consecutive_errors"] = 0
        
        # Record last request time
        self.last_request_time[domain] = time.time()
    
    def get_delay(self, url: str) -> float:
        """
        Calculate appropriate delay for a domain based on statistics.
        
        Args:
            url (str): URL for the request
            
        Returns:
            float: Recommended delay in seconds
        """
        domain = self._extract_domain(url)
        
        # Use base delay for new domains
        if domain not in self.domain_stats:
            return self._apply_jitter(self.base_delay)
        
        stats = self.domain_stats[domain]
        delay = self.base_delay
        
        # Adjust based on average response time
        if stats["response_times"]:
            avg_response_time = sum(stats["response_times"]) / len(stats["response_times"])
            delay = max(delay, avg_response_time * self.response_factor)
        
        # Increase delay after errors
        if stats["consecutive_errors"] > 0:
            delay *= (self.error_backoff ** min(stats["consecutive_errors"], 3))
        
        # Add delay for server errors (5xx)
        if stats["status_codes"] and any(code >= 500 for code in stats["status_codes"][-3:]):
            delay *= 1.5
        
        # Add delay for rate limiting (429)
        if stats["status_codes"] and any(code == 429 for code in stats["status_codes"][-5:]):
            delay *= 2.0
        
        # Cap at maximum delay
        delay = min(delay, self.max_delay)
        
        # Apply random jitter
        return self._apply_jitter(delay)
    
    def wait_if_needed(self, url: str):
        """
        Wait if needed before making a request to respect throttling.
        
        Args:
            url (str): URL for the request
        """
        domain = self._extract_domain(url)
        
        if domain in self.last_request_time:
            # Calculate time since last request
            elapsed = time.time() - self.last_request_time[domain]
            
            # Get recommended delay
            delay = self.get_delay(url)
            
            # Wait if needed
            if elapsed < delay:
                wait_time = delay - elapsed
                time.sleep(wait_time)
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            return urlparse(url).netloc
        except:
            # Fallback if URL parsing fails
            match = re.search(r'://([^/]+)', url)
            return match.group(1) if match else url
    
    def _apply_jitter(self, delay: float) -> float:
        """Apply random jitter to delay value."""
        jitter_amount = delay * self.jitter
        return delay + random.uniform(-jitter_amount, jitter_amount)


class SecurityProfile:
    """
    Complete security profile for making requests.
    Combines header randomization, cookie management, and throttling.
    """
    
    def __init__(self,
                headers_manager: Optional[RequestHeaderManager] = None,
                cookie_manager: Optional[CookieManager] = None,
                throttle_manager: Optional[ThrottleManager] = None,
                session_persistence: bool = True):
        """
        Initialize the security profile.
        
        Args:
            headers_manager (RequestHeaderManager): Header manager
            cookie_manager (CookieManager): Cookie manager
            throttle_manager (ThrottleManager): Throttle manager
            session_persistence (bool): Whether to maintain consistent sessions per domain
        """
        self.headers_manager = headers_manager or RequestHeaderManager(session_persistence)
        self.cookie_manager = cookie_manager or CookieManager()
        self.throttle_manager = throttle_manager or ThrottleManager()
        self.session_persistence = session_persistence
        
        # Domain-specific sessions
        self.domain_sessions = {}
    
    def get_session(self, url: str) -> requests.Session:
        """
        Get a session for a domain with appropriate cookies and headers.
        
        Args:
            url (str): URL for the request
            
        Returns:
            requests.Session: Configured session
        """
        domain = self._extract_domain(url)
        
        if self.session_persistence and domain in self.domain_sessions:
            # Return existing session
            return self.domain_sessions[domain]
        
        # Create a new session
        session = requests.Session()
        
        # Apply cookies if session persistence is enabled
        if self.session_persistence:
            self.cookie_manager.apply_to_session(session, domain)
            self.domain_sessions[domain] = session
        
        return session
    
    def prepare_request(self, url: str, 
                       session: Optional[requests.Session] = None,
                       randomize_headers: bool = False) -> Tuple[requests.Session, Dict[str, str]]:
        """
        Prepare a session and headers for a request.
        
        Args:
            url (str): URL for the request
            session (requests.Session): Existing session, or None to create one
            randomize_headers (bool): Whether to completely randomize headers
            
        Returns:
            tuple: (session, headers)
        """
        # Get a session if not provided
        if session is None:
            session = self.get_session(url)
        
        # Get headers
        headers = self.headers_manager.get_headers(url, randomize_headers)
        
        # Wait if needed for throttling
        self.throttle_manager.wait_if_needed(url)
        
        return session, headers
    
    def record_response(self, url: str, 
                       response_time: float,
                       status_code: Optional[int] = None,
                       error: bool = False):
        """
        Record response statistics for throttling.
        
        Args:
            url (str): URL of the request
            response_time (float): Response time in seconds
            status_code (int): HTTP status code
            error (bool): Whether the request resulted in an error
        """
        self.throttle_manager.record_request(
            url, response_time, status_code, error
        )
        
        # Save cookies if successful
        if not error and self.session_persistence:
            domain = self._extract_domain(url)
            self.cookie_manager.save_cookies(domain)
    
    def clear_domain_data(self, domain: Optional[str] = None):
        """
        Clear all stored data for a domain or all domains.
        
        Args:
            domain (str): Domain to clear, or None for all domains
        """
        self.headers_manager.clear_domain_data(domain)
        self.cookie_manager.clear_cookies(domain)
        
        if domain:
            if domain in self.domain_sessions:
                del self.domain_sessions[domain]
        else:
            self.domain_sessions.clear()
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            return urlparse(url).netloc
        except:
            # Fallback if URL parsing fails
            match = re.search(r'://([^/]+)', url)
            return match.group(1) if match else url
