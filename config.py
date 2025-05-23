import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Keys and Service Endpoints
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-pro-latest")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Optional for faster inferencing
    TOR_PROXY = os.getenv("TOR_PROXY", "127.0.0.1:9050")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", None)  # Optional clearnet fallback
    
    # Database Paths and Configuration
    CHROMA_DB_PATH = "chroma_db"
    ONION_DB_PATH = os.getenv("ONION_DB_PATH", "data/onion_links.db")
    DB_TRANSACTION_TIMEOUT = 30  # Seconds to wait for database locks
    DB_CACHE_ENABLED = True      # Whether to use database query caching
    DB_CACHE_TTL = 300           # Cache time-to-live in seconds
    DB_VACUUM_INTERVAL_HOURS = 24  # How often to run VACUUM for optimization
    
    # Crawling Parameters
    CRAWL_DEPTH = 10
    CRAWL_DELAY_MIN = 2
    CRAWL_DELAY_MAX = 5
    LINK_LIMIT_PER_PAGE = 5
    
    # Onion Discovery Parameters
    DISCOVERY_MODE = os.getenv("DISCOVERY_MODE", "passive")  # passive, active, aggressive
    DISCOVERY_SITES_LIMIT = 5  # Number of directory sites to crawl in one operation
    SEARCH_ENGINES_LIMIT = 3   # Number of search engines to query in one operation
    BATCH_CRAWL_SIZE = 15      # Number of sites to crawl in one batch
    RECRAWL_HOURS = 24         # Recrawl sites after this many hours
    MAX_BLACKLIST_AGE_DAYS = 30  # Consider removing from blacklist after this many days
    
    # Connection Management & Error Handling
    TOR_ENABLED = True         # Whether to use Tor for connections
    CLEARNET_FALLBACK_ENABLED = True  # Whether to fall back to clearnet if Tor fails
    MAX_CIRCUIT_AGE_MINUTES = 30      # Maximum age of a Tor circuit before rotation
    MAX_REQUESTS_PER_CIRCUIT = 30     # Maximum requests per circuit before rotation
    MAX_RETRIES = 3                   # Maximum retries for failed requests
    RETRY_INITIAL_DELAY = 1.0         # Initial delay for retry backoff (seconds)
    RETRY_BACKOFF_FACTOR = 2.0        # Multiplicative factor for retry backoff
    
    # Security Features
    SESSION_PERSISTENCE_ENABLED = True  # Whether to maintain persistent sessions per domain
    COOKIE_HANDLING_ENABLED = True      # Whether to store and reuse cookies
    HEADER_RANDOMIZATION_ENABLED = True # Whether to randomize HTTP headers
    ADVANCED_THROTTLING_ENABLED = True  # Whether to use response-time based throttling
    HTTP_HEADER_VARIATION = "high"      # Level of HTTP header variation (low, medium, high)
    IP_ROTATION_ENABLED = True          # Whether to rotate IP addresses via Tor
    
    # Content Safety & Filtering
    CONTENT_CATEGORIZATION_ENABLED = True
    CONTENT_PREVIEW_MAX_LENGTH = 500  # Maximum length of content preview to store
    NSFW_CONTENT_FILTERING = True     # Whether to filter NSFW content
    SAFETY_THRESHOLD = 7              # Threshold for safety filtering (0-10 scale)
    SAFETY_CATEGORIES = [             # Categories to filter when above threshold
        "NSFW", "Violence", "Illegal activity", "Hate speech", 
        "Harassment", "Self-harm", "Child exploitation"
    ]
    
    # Advanced Analytics
    ANALYTICS_ENABLED = True               # Whether to enable advanced analytics
    ENTITY_EXTRACTION_ENABLED = True       # Whether to extract entities from content
    SENTIMENT_ANALYSIS_ENABLED = True      # Whether to analyze sentiment in content
    TREND_DETECTION_ENABLED = True         # Whether to detect trends across content
    ANALYTICS_BATCH_SIZE = 100             # Batch size for analytics processing
    TREND_TIMEFRAMES_DAYS = [7, 30, 90]    # Timeframes for trend analysis in days
    
    # Parallel Crawling
    PARALLEL_CRAWLING_ENABLED = True  # Whether to enable parallel crawling
    MAX_CRAWLER_WORKERS = 5           # Maximum number of parallel crawler workers
    DOMAIN_RATE_LIMIT = 2.0           # Minimum seconds between requests to same domain
    
    # Memory Management
    MEMORY_MONITORING_ENABLED = True       # Whether to monitor memory usage
    MAX_MEMORY_PERCENT = 80.0              # Maximum memory usage threshold (percentage)
    MEMORY_CHECK_INTERVAL_SECONDS = 60     # How often to check memory usage
    CHUNK_PROCESSING_SIZE = 100            # Size of chunks for memory-efficient processing
    
    # Cache Configuration
    CACHE_DIR = os.path.join("data", "cache")  # Directory for cache files
    CONTENT_CACHE_ENABLED = True             # Whether to cache content
    CONTENT_CACHE_MAX_SIZE_MB = 500          # Maximum cache size in MB
    CONTENT_CACHE_TTL = 24 * 60 * 60         # Cache TTL in seconds (24 hours)
    
    # Gemini AI Parameters
    GEMINI_MODELS = ["gemini-2.0-flash-exp", "gemini-2.5-pro-preview-05-06"]
    DEFAULT_MODEL = "gemini-2.5-pro-preview-05-06"
    TEMPERATURE = 0.7
    MAX_TOKENS = 1000000
    
    # Directory Structure
    DATA_DIR = "data"
    EXPORT_DIR = os.path.join(DATA_DIR, "exports")
    TESTS_DIR = "tests"
    COOKIES_DIR = os.path.join(DATA_DIR, "cookies")
    ANALYTICS_DIR = os.path.join(DATA_DIR, "analytics")
    
    # Initialize required directories
    @classmethod
    def init_directories(cls):
        """Create necessary directories if they don't exist."""
        directories = [
            cls.DATA_DIR, 
            cls.EXPORT_DIR, 
            cls.TESTS_DIR,
            cls.CACHE_DIR,
            cls.COOKIES_DIR,
            cls.ANALYTICS_DIR
        ]
        
        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory)
                
    # Convenience methods for feature flags
    @classmethod
    def is_advanced_security_enabled(cls):
        """Check if advanced security features are enabled."""
        return cls.HEADER_RANDOMIZATION_ENABLED or \
               cls.COOKIE_HANDLING_ENABLED or \
               cls.SESSION_PERSISTENCE_ENABLED
    
    @classmethod
    def is_advanced_analytics_enabled(cls):
        """Check if advanced analytics features are enabled."""
        return cls.ANALYTICS_ENABLED and (
            cls.ENTITY_EXTRACTION_ENABLED or \
            cls.SENTIMENT_ANALYSIS_ENABLED or \
            cls.TREND_DETECTION_ENABLED
        )
