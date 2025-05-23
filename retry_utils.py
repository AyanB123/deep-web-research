"""
Retry utilities for handling network operations with exponential backoff.
"""

import time
import random
from functools import wraps
from utils import log_action

def retry_with_backoff(max_retries=3, initial_delay=1, backoff_factor=2, exceptions=(Exception,)):
    """
    Decorator for retrying a function with exponential backoff.
    
    Args:
        max_retries (int): Maximum number of retry attempts
        initial_delay (float): Initial delay in seconds
        backoff_factor (float): Multiplicative factor for backoff
        exceptions (tuple): Tuple of exceptions to catch and retry
        
    Returns:
        Function decorator
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        # Add some randomness to avoid patterns
                        jitter = random.uniform(0, 0.5)
                        sleep_time = delay + jitter
                        
                        log_action(f"Attempt {attempt+1} failed with {type(e).__name__}: {str(e)}. "
                                   f"Retrying in {sleep_time:.2f} seconds...")
                        
                        time.sleep(sleep_time)
                        delay *= backoff_factor
                    else:
                        log_action(f"All {max_retries+1} attempts failed.")
                        
            raise last_exception
            
        return wrapper
    return decorator

def retry_operation(function, max_retries=3, initial_delay=1, backoff_factor=2, exceptions=(Exception,)):
    """
    Execute a function with exponential backoff retry logic.
    
    Args:
        function: Function to execute
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplicative factor for backoff
        exceptions: Tuple of exceptions to catch and retry
        
    Returns:
        Result of the function or raises the last exception
    """
    last_exception = None
    delay = initial_delay
    
    for attempt in range(max_retries + 1):
        try:
            return function()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                jitter = random.uniform(0, 0.5)
                sleep_time = delay + jitter
                
                log_action(f"Operation attempt {attempt+1} failed: {str(e)}. "
                           f"Retrying in {sleep_time:.2f} seconds...")
                
                time.sleep(sleep_time)
                delay *= backoff_factor
            else:
                log_action(f"All {max_retries+1} operation attempts failed.")
                
    raise last_exception
