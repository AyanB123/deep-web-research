"""
Database utilities for ensuring data integrity, optimizing performance, and implementing caching.
"""

import sqlite3
import time
import logging
import functools
import datetime
import json
import os
import threading
from typing import Dict, List, Any, Optional, Tuple, Callable
from contextlib import contextmanager

import diskcache

from config import Config

# Configure logger
def log_action(message):
    """Log actions with timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    logging.info(message)

# Thread local storage for database connections
local_storage = threading.local()

class DatabaseManager:
    """
    Manages database connections, transactions, and provides optimizations.
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize the database manager.
        
        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path or Config.ONION_DB_PATH
        self.cache = diskcache.Cache(os.path.join(Config.DATA_DIR, "db_cache"))
        self.cache_enabled = Config.DB_CACHE_ENABLED
        self.cache_ttl = Config.DB_CACHE_TTL
        self.transaction_timeout = Config.DB_TRANSACTION_TIMEOUT
        
        # Ensure database directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize database with optimized settings
        self._init_database()
    
    def _init_database(self):
        """Initialize the database with optimized settings and indices."""
        with self.get_connection() as conn:
            # Enable WAL mode for better concurrency and performance
            conn.execute("PRAGMA journal_mode=WAL;")
            
            # Optimize for better performance
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA temp_store=MEMORY;")
            conn.execute("PRAGMA cache_size=-10000;")  # Use ~10MB of memory for cache
            conn.execute("PRAGMA mmap_size=268435456;")  # Use memory-mapped I/O (256MB)
            
            # Check if we need to create indices
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
            existing_indices = [row[0] for row in cursor.fetchall()]
            
            # Create indices if they don't exist
            if "idx_links_url" not in existing_indices:
                log_action("Creating database indices for performance optimization")
                try:
                    # Create indices for common query patterns
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_links_url ON links(url);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_links_status ON links(status);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_links_category ON links(category);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_links_last_checked ON links(last_checked);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_history_url ON crawl_history(url);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_history_timestamp ON crawl_history(timestamp);")
                    
                    log_action("Database indices created successfully")
                except Exception as e:
                    log_action(f"Error creating indices: {str(e)}")
    
    def get_connection(self):
        """
        Get a database connection from the connection pool or create a new one.
        Uses thread-local storage to maintain one connection per thread.
        
        Returns:
            sqlite3.Connection: Database connection
        """
        # Check if we already have a connection for this thread
        if not hasattr(local_storage, 'connection') or local_storage.connection is None:
            # Create a new connection with row factory for dict results
            connection = sqlite3.connect(self.db_path, timeout=self.transaction_timeout)
            connection.row_factory = self._dict_factory
            
            # Store the connection in thread-local storage
            local_storage.connection = connection
        
        return local_storage.connection
    
    @staticmethod
    def _dict_factory(cursor, row):
        """Convert SQLite row to dictionary."""
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    
    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions with automatic commit/rollback.
        
        Usage:
            with db_manager.transaction() as conn:
                conn.execute("INSERT INTO ...")
                conn.execute("UPDATE ...")
        """
        connection = self.get_connection()
        
        try:
            yield connection
            connection.commit()
        except Exception as e:
            connection.rollback()
            log_action(f"Transaction rolled back: {str(e)}")
            raise
    
    def close_connection(self):
        """Close the current thread's database connection."""
        if hasattr(local_storage, 'connection') and local_storage.connection is not None:
            local_storage.connection.close()
            local_storage.connection = None
    
    def vacuum_database(self):
        """
        Optimize the database by running VACUUM.
        Should be run periodically for maintenance.
        """
        with self.get_connection() as conn:
            log_action("Running database VACUUM for optimization")
            conn.execute("VACUUM;")
            log_action("Database VACUUM completed")
    
    def analyze_database(self):
        """
        Run ANALYZE to update database statistics for query optimization.
        """
        with self.get_connection() as conn:
            log_action("Running ANALYZE for query optimization")
            conn.execute("ANALYZE;")
            log_action("Database ANALYZE completed")
    
    def execute_with_cache(self, query: str, params: tuple = (), 
                          cache_key: Optional[str] = None, 
                          ttl: Optional[int] = None) -> List[Dict]:
        """
        Execute a read query with caching.
        
        Args:
            query (str): SQL query
            params (tuple): Query parameters
            cache_key (str): Custom cache key (if None, generated from query+params)
            ttl (int): Cache TTL in seconds (if None, use default)
            
        Returns:
            list: Query results as list of dictionaries
        """
        if not self.cache_enabled or query.strip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            # Skip cache for write operations
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.fetchall()
        
        # Generate cache key if not provided
        if cache_key is None:
            param_str = json.dumps(params, sort_keys=True) if params else ""
            cache_key = f"sql:{hash(query)}:{hash(param_str)}"
        
        # Check cache
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Execute query
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = cursor.fetchall()
        
        # Store in cache
        ttl = ttl or self.cache_ttl
        self.cache.set(cache_key, results, expire=ttl)
        
        return results
    
    def invalidate_cache(self, pattern: Optional[str] = None):
        """
        Invalidate cache entries.
        
        Args:
            pattern (str): Optional pattern to match cache keys
        """
        if pattern:
            # Delete specific pattern
            keys_to_delete = [k for k in self.cache if pattern in k]
            for key in keys_to_delete:
                del self.cache[key]
            log_action(f"Invalidated {len(keys_to_delete)} cache entries matching '{pattern}'")
        else:
            # Clear entire cache
            self.cache.clear()
            log_action("Cleared entire cache")


def with_transaction(func):
    """
    Decorator for methods that should be executed within a transaction.
    
    Usage:
        @with_transaction
        def add_item(self, ...):
            ...
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Check if self has a db_manager attribute
        if hasattr(self, 'db_manager'):
            with self.db_manager.transaction() as conn:
                # Add connection as a keyword argument
                kwargs['conn'] = conn
                return func(self, *args, **kwargs)
        else:
            # Fall back to default behavior if no db_manager
            return func(self, *args, **kwargs)
    
    return wrapper


class QueryBuilder:
    """Helper class to build SQL queries with proper escaping."""
    
    @staticmethod
    def build_select(table: str, columns: List[str] = None, 
                    where: Dict[str, Any] = None, 
                    order_by: Optional[str] = None,
                    limit: Optional[int] = None,
                    offset: Optional[int] = None) -> Tuple[str, List]:
        """
        Build a SELECT query with parameters.
        
        Args:
            table (str): Table name
            columns (list): Columns to select (None for *)
            where (dict): WHERE conditions as key-value pairs
            order_by (str): ORDER BY clause
            limit (int): LIMIT clause
            offset (int): OFFSET clause
            
        Returns:
            tuple: (query, params)
        """
        columns_str = "*" if columns is None or len(columns) == 0 else ", ".join(columns)
        query = f"SELECT {columns_str} FROM {table}"
        params = []
        
        if where:
            conditions = []
            for key, value in where.items():
                if value is None:
                    conditions.append(f"{key} IS NULL")
                else:
                    conditions.append(f"{key} = ?")
                    params.append(value)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        if limit is not None:
            query += f" LIMIT {limit}"
            
        if offset is not None:
            query += f" OFFSET {offset}"
        
        return query, params
    
    @staticmethod
    def build_insert(table: str, data: Dict[str, Any]) -> Tuple[str, List]:
        """
        Build an INSERT query with parameters.
        
        Args:
            table (str): Table name
            data (dict): Data to insert as key-value pairs
            
        Returns:
            tuple: (query, params)
        """
        columns = list(data.keys())
        placeholders = ["?"] * len(columns)
        
        query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        params = list(data.values())
        
        return query, params
    
    @staticmethod
    def build_update(table: str, data: Dict[str, Any], 
                    where: Dict[str, Any]) -> Tuple[str, List]:
        """
        Build an UPDATE query with parameters.
        
        Args:
            table (str): Table name
            data (dict): Data to update as key-value pairs
            where (dict): WHERE conditions as key-value pairs
            
        Returns:
            tuple: (query, params)
        """
        set_clauses = [f"{key} = ?" for key in data.keys()]
        params = list(data.values())
        
        query = f"UPDATE {table} SET {', '.join(set_clauses)}"
        
        if where:
            conditions = []
            for key, value in where.items():
                if value is None:
                    conditions.append(f"{key} IS NULL")
                else:
                    conditions.append(f"{key} = ?")
                    params.append(value)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        return query, params


class MemoryManager:
    """
    Manages memory usage for large crawl operations.
    Provides utilities for efficient data processing and memory monitoring.
    """
    
    def __init__(self, max_memory_percent: float = 80.0):
        """
        Initialize memory manager.
        
        Args:
            max_memory_percent (float): Maximum memory usage threshold (percentage)
        """
        self.max_memory_percent = max_memory_percent
        self.memory_monitoring = False
        self.monitoring_thread = None
    
    def start_memory_monitoring(self, interval: int = 5):
        """
        Start background memory monitoring.
        
        Args:
            interval (int): Monitoring interval in seconds
        """
        if self.memory_monitoring:
            return
        
        self.memory_monitoring = True
        self.monitoring_thread = threading.Thread(
            target=self._memory_monitor_task,
            args=(interval,),
            daemon=True
        )
        self.monitoring_thread.start()
        log_action("Memory monitoring started")
    
    def stop_memory_monitoring(self):
        """Stop background memory monitoring."""
        if not self.memory_monitoring:
            return
        
        self.memory_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1)
            self.monitoring_thread = None
        log_action("Memory monitoring stopped")
    
    def _memory_monitor_task(self, interval: int):
        """Background task for memory monitoring."""
        import psutil
        process = psutil.Process(os.getpid())
        
        while self.memory_monitoring:
            # Get memory usage
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            
            # Log if approaching threshold
            if memory_percent > self.max_memory_percent * 0.8:
                log_action(f"Warning: High memory usage - {memory_percent:.1f}% "
                          f"({memory_info.rss / (1024 * 1024):.1f} MB)")
            
            # Sleep for interval
            time.sleep(interval)
    
    def check_memory_usage(self) -> Tuple[float, bool]:
        """
        Check current memory usage.
        
        Returns:
            tuple: (memory_percent, is_critical)
        """
        import psutil
        process = psutil.Process(os.getpid())
        memory_percent = process.memory_percent()
        is_critical = memory_percent > self.max_memory_percent
        
        return memory_percent, is_critical
    
    def clear_memory_if_needed(self, force: bool = False) -> bool:
        """
        Clear memory if usage exceeds threshold.
        
        Args:
            force (bool): Force clearing regardless of threshold
            
        Returns:
            bool: True if memory was cleared
        """
        memory_percent, is_critical = self.check_memory_usage()
        
        if is_critical or force:
            # Force garbage collection
            import gc
            gc.collect()
            
            # Log action
            log_action(f"Memory cleared (was at {memory_percent:.1f}%)")
            return True
        
        return False
    
    @staticmethod
    def chunk_list(items: List, chunk_size: int) -> List[List]:
        """
        Split a list into chunks for memory-efficient processing.
        
        Args:
            items (list): List to chunk
            chunk_size (int): Chunk size
            
        Returns:
            list: List of chunks
        """
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
    
    @staticmethod
    def process_in_chunks(items: List, process_func: Callable, 
                         chunk_size: int = 100) -> List:
        """
        Process a large list in chunks to manage memory usage.
        
        Args:
            items (list): Items to process
            process_func (callable): Function to process each chunk
            chunk_size (int): Chunk size
            
        Returns:
            list: Combined results
        """
        chunks = MemoryManager.chunk_list(items, chunk_size)
        results = []
        
        for i, chunk in enumerate(chunks):
            # Process chunk
            chunk_results = process_func(chunk)
            results.extend(chunk_results)
            
            # Log progress
            if i % 10 == 0 and i > 0:
                log_action(f"Processed {i}/{len(chunks)} chunks ({len(results)} items)")
            
            # Check memory usage every few chunks
            if i % 5 == 0 and i > 0:
                try:
                    memory_percent, is_critical = MemoryManager().check_memory_usage()
                    if is_critical:
                        log_action(f"Warning: High memory usage during chunk processing - {memory_percent:.1f}%")
                        MemoryManager().clear_memory_if_needed(force=True)
                except:
                    pass  # Ignore if psutil not available
        
        return results
