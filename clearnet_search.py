"""
Clearnet search module for fallback when Tor is unavailable.
Uses Tavily API to provide search results from the clearnet.
"""

import requests
import time
from config import Config
from utils import log_action

class TavilySearch:
    """
    Tavily API wrapper for clearnet search as fallback when Tor is unavailable.
    """
    
    def __init__(self, api_key=None):
        """
        Initialize the Tavily search client.
        
        Args:
            api_key (str, optional): Tavily API key. Defaults to Config.TAVILY_API_KEY.
        """
        self.api_key = api_key or Config.TAVILY_API_KEY
        self.base_url = "https://api.tavily.com/v1/search"
        
    def search(self, query, max_results=10, search_depth="advanced"):
        """
        Perform a clearnet search using Tavily API.
        
        Args:
            query (str): Search query
            max_results (int, optional): Maximum number of results. Defaults to 10.
            search_depth (str, optional): Search depth ('basic' or 'advanced'). 
                                         Defaults to 'advanced'.
            
        Returns:
            list: List of search results with url, title, content
        """
        if not self.api_key:
            log_action("Tavily API key not configured for clearnet fallback")
            return []
            
        try:
            # Prepare the request payload
            payload = {
                "api_key": self.api_key,
                "query": query,
                "search_depth": search_depth,
                "include_answer": False,
                "include_domains": [],
                "exclude_domains": [],
                "max_results": max_results
            }
            
            # Make the API request
            log_action(f"Performing clearnet search via Tavily API: {query}")
            response = requests.post(self.base_url, json=payload, timeout=30)
            
            # Check for successful response
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                # Format the results to match our expected structure
                formatted_results = []
                for result in results:
                    formatted_results.append({
                        "url": result.get("url", ""),
                        "title": result.get("title", ""),
                        "content": result.get("content", ""),
                        "score": result.get("score", 0),
                        "source": "tavily_api"
                    })
                
                log_action(f"Tavily API returned {len(formatted_results)} results")
                return formatted_results
            else:
                log_action(f"Tavily API error: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            log_action(f"Tavily API request error: {str(e)}")
            return []
    
    def extract_search_terms(self, url):
        """
        Extract search terms from an onion URL to use for clearnet search.
        
        Args:
            url (str): Onion URL to extract search terms from
            
        Returns:
            str: Search terms extracted from the URL
        """
        # Remove common onion domain parts
        search_terms = url.replace("http://", "").replace("https://", "")
        search_terms = search_terms.split(".onion")[0]
        
        # Remove common prefixes/suffixes
        for prefix in ["www.", "hidden.", "dark.", "onion."]:
            if search_terms.startswith(prefix):
                search_terms = search_terms[len(prefix):]
                
        # Replace special characters with spaces
        for char in ["-", "_", ".", "/"]:
            search_terms = search_terms.replace(char, " ")
            
        # Add context keywords for better results
        if len(search_terms.split()) < 3:
            search_terms += " dark web onion service"
            
        return search_terms.strip()
    
    def search_for_similar_content(self, content, max_results=5):
        """
        Search for similar content using relevant excerpts.
        
        Args:
            content (str): Original content to find similar results for
            max_results (int, optional): Maximum number of results. Defaults to 5.
            
        Returns:
            list: List of search results
        """
        # Extract meaningful keywords from content
        # Use a simple approach of taking the first few sentences
        excerpt = " ".join(content.split()[:50])
        
        # Perform the search
        return self.search(excerpt, max_results=max_results)
