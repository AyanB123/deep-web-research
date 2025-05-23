"""
Connection Manager module for handling Tor and clearnet connections.
Provides robust error handling and fallback mechanisms for network requests.
"""

import time
import datetime
import requests
import random
from config import Config
from utils import log_action

class ConnectionManager:
    """
    Manages network connections with Tor and clearnet fallback capabilities.
    Handles circuit rotation, connection errors, and provides retry mechanisms.
    """
    
    def __init__(self, tor_enabled=True, clearnet_fallback=True):
        """
        Initialize the connection manager.
        
        Args:
            tor_enabled (bool): Whether to use Tor for connections
            clearnet_fallback (bool): Whether to fall back to clearnet if Tor fails
        """
        self.tor_enabled = tor_enabled
        self.clearnet_fallback = clearnet_fallback
        self.tor_session = None
        self.clearnet_session = None
        self.circuit_created_time = None
        self.max_circuit_age = Config.MAX_CIRCUIT_AGE_MINUTES * 60  # convert to seconds
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/109.0"
        ]
        self.request_count = 0
        self.max_requests_per_circuit = Config.MAX_REQUESTS_PER_CIRCUIT
    
    def get_session(self, force_clearnet=False):
        """
        Get the appropriate session based on availability and settings.
        
        Args:
            force_clearnet (bool): Whether to force using a clearnet session
            
        Returns:
            requests.Session: The appropriate session for making requests
        """
        if force_clearnet or not self.tor_enabled:
            return self._get_clearnet_session()
            
        # Try Tor first if enabled
        if self.tor_session is None or self._should_rotate_circuit():
            tor_success = self._initialize_tor_session()
            if not tor_success and self.clearnet_fallback:
                log_action("Tor connection failed. Falling back to clearnet session.")
                return self._get_clearnet_session()
                
        return self.tor_session
    
    def _initialize_tor_session(self):
        """
        Initialize a new Tor session with error handling.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            log_action("Starting Tor session via SOCKS proxy")
            
            # Close existing session if any
            if self.tor_session:
                self.tor_session.close()
            
            # Create new session
            self.tor_session = requests.Session()
            self.tor_session.proxies = {
                "http": f"socks5://{Config.TOR_PROXY}", 
                "https": f"socks5://{Config.TOR_PROXY}"
            }
            
            # Check if Tor proxy is reachable
            test_url = "https://check.torproject.org/api/ip"
            headers = {"User-Agent": random.choice(self.user_agents)}
            
            try:
                response = self.tor_session.get(test_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("IsTor", False):
                        log_action("Tor proxy connection successful")
                        self.circuit_created_time = time.time()
                        self.request_count = 0
                        return True
                    else:
                        log_action("Tor proxy connected but not routing through Tor network.")
                        return False
                else:
                    log_action(f"Unexpected response code from Tor check: {response.status_code}")
                    return False
            except Exception as e:
                log_action(f"Failed to connect to Tor proxy: {str(e)}")
                return False
                
        except Exception as e:
            log_action(f"Tor session initialization error: {str(e)}")
            return False
    
    def _get_clearnet_session(self):
        """
        Get or create a clearnet session.
        
        Returns:
            requests.Session: A standard requests session
        """
        if self.clearnet_session is None:
            self.clearnet_session = requests.Session()
            
        return self.clearnet_session
    
    def _should_rotate_circuit(self):
        """
        Check if we should rotate the Tor circuit based on age or request count.
        
        Returns:
            bool: True if circuit should be rotated, False otherwise
        """
        if self.circuit_created_time is None:
            return True
            
        # Check age of circuit
        circuit_age = time.time() - self.circuit_created_time
        if circuit_age > self.max_circuit_age:
            log_action(f"Rotating Tor circuit due to age: {circuit_age:.1f} seconds")
            return True
            
        # Check request count
        if self.request_count >= self.max_requests_per_circuit:
            log_action(f"Rotating Tor circuit due to request count: {self.request_count}")
            return True
            
        return False
    
    def perform_request(self, method, url, **kwargs):
        """
        Perform a request with the appropriate session and error handling.
        
        Args:
            method (str): HTTP method ('get', 'post', etc.)
            url (str): URL to request
            **kwargs: Additional arguments for requests
            
        Returns:
            requests.Response: Response from the request
            
        Raises:
            Exception: If the request fails after retries
        """
        force_clearnet = kwargs.pop('force_clearnet', False)
        max_retries = kwargs.pop('max_retries', 3)
        initial_delay = kwargs.pop('initial_delay', 1)
        backoff_factor = kwargs.pop('backoff_factor', 2)
        
        # Add random user agent if not specified
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        if 'User-Agent' not in kwargs['headers']:
            kwargs['headers']['User-Agent'] = random.choice(self.user_agents)
            
        session = self.get_session(force_clearnet)
        
        # Track request count for Tor circuit rotation
        if session == self.tor_session:
            self.request_count += 1
            
        # Perform request with retry logic
        last_exception = None
        delay = initial_delay
        
        for attempt in range(max_retries + 1):
            try:
                # Get the appropriate method from the session
                request_method = getattr(session, method.lower())
                response = request_method(url, **kwargs)
                response.raise_for_status()
                return response
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    log_action(f"Request attempt {attempt+1} failed for {url}: {str(e)}. Retrying in {delay} seconds...")
                    time.sleep(delay)
                    delay *= backoff_factor
                    
                    # If we have multiple failures with Tor, try rotating the circuit
                    if session == self.tor_session and attempt >= 1:
                        log_action("Rotating Tor circuit due to request failures")
                        self._initialize_tor_session()
                        
                        # If Tor still fails and clearnet fallback is enabled, switch to clearnet
                        if attempt >= 2 and self.clearnet_fallback:
                            log_action("Switching to clearnet fallback after multiple Tor failures")
                            session = self._get_clearnet_session()
                else:
                    log_action(f"All {max_retries+1} request attempts failed for {url}")
                    
        raise last_exception
    
    def close(self):
        """Close all active sessions."""
        if self.tor_session:
            self.tor_session.close()
            self.tor_session = None
            
        if self.clearnet_session:
            self.clearnet_session.close()
            self.clearnet_session = None
