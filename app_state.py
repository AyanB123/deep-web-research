"""
Centralized state management for the Dark Web Discovery System.
Provides a clean interface for state updates and notifications.
"""

import logging
import datetime
import uuid
from typing import Dict, List, Any, Optional, Callable
import json

class AppState:
    """
    Centralized state management for the Dark Web Discovery System.
    Provides a clean interface for state updates and notifications.
    """
    
    def __init__(self):
        """
        Initialize the application state.
        """
        self._state = {
            # Navigation state
            "current_page": "Dashboard",
            
            # System state
            "db_initialized": False,
            "initialized": False,
            "dark_mode": False,
            "auto_refresh": True,
            "refresh_interval": 5,  # seconds
            "version": "1.0.0",
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d"),
            
            # WebSocket state
            "websocket_enabled": False,
            "websocket_connected": False,
            "last_websocket_message": None,
            
            # Crawler operations
            "crawler_operations": {
                "active_crawls": {},
                "last_errors": [],
                "discovery_stats": {
                    "today_discovered": 0,
                    "total_discovered": 0,
                    "last_discovery": None,
                    "categories": {}
                }
            },
            
            # User interface
            "notifications": [],
            
            # Search state
            "last_search_query": "",
            "search_history": [],
            
            # Session information
            "session_id": str(uuid.uuid4())
        }
        
        self._validators = {}
        self._change_handlers = {}
        self._global_change_handlers = []
        self.logger = logging.getLogger("AppState")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a state value by key path.
        
        Args:
            key: Dot-notation key path (e.g., "crawler_operations.active_crawls")
            default: Default value if key doesn't exist
            
        Returns:
            The state value or default
        """
        parts = key.split(".")
        current = self._state
        
        try:
            for part in parts:
                current = current[part]
            return current
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> bool:
        """
        Set a state value by key path.
        
        Args:
            key: Dot-notation key path
            value: Value to set
            
        Returns:
            True if successful, False otherwise
        """
        # Validate the value
        if key in self._validators and not self._validators[key](value):
            self.logger.warning(f"Validation failed for {key}")
            return False
            
        # Find the parent object and the final key
        parts = key.split(".")
        current = self._state
        
        # Navigate to the correct nested dictionary
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
            
        # Set the value
        old_value = current.get(parts[-1])
        current[parts[-1]] = value
        
        # Notify change handlers
        self._notify_change_handlers(key, old_value, value)
        
        return True
    
    def register_validator(self, key: str, validator: Callable[[Any], bool]) -> None:
        """
        Register a validation function for a state key.
        
        Args:
            key: State key to validate
            validator: Function that takes a value and returns True if valid
        """
        self._validators[key] = validator
    
    def register_change_handler(self, key: str, handler: Callable[[str, Any, Any], None]) -> None:
        """
        Register a handler for state changes.
        
        Args:
            key: State key to watch
            handler: Function called with (key, old_value, new_value)
        """
        if key not in self._change_handlers:
            self._change_handlers[key] = []
        self._change_handlers[key].append(handler)
    
    def register_global_change_handler(self, handler: Callable[[str, Any, Any], None]) -> None:
        """
        Register a handler for all state changes.
        
        Args:
            handler: Function called with (key, old_value, new_value)
        """
        self._global_change_handlers.append(handler)
    
    def _notify_change_handlers(self, key: str, old_value: Any, new_value: Any) -> None:
        """
        Notify all relevant change handlers about a state change.
        
        Args:
            key: The changed state key
            old_value: Previous value
            new_value: New value
        """
        # Call specific handlers for this key
        handlers = self._change_handlers.get(key, [])
        for handler in handlers:
            try:
                handler(key, old_value, new_value)
            except Exception as e:
                self.logger.error(f"Error in change handler for {key}: {str(e)}", exc_info=True)
        
        # Call global handlers
        for handler in self._global_change_handlers:
            try:
                handler(key, old_value, new_value)
            except Exception as e:
                self.logger.error(f"Error in global change handler for {key}: {str(e)}", exc_info=True)
    
    def update_crawler_operation(self, crawler_id: str, data: Dict[str, Any]) -> None:
        """
        Update a crawler operation's state.
        
        Args:
            crawler_id: ID of the crawler
            data: Data to update
        """
        active_crawls = self.get("crawler_operations.active_crawls", {})
        if crawler_id not in active_crawls:
            active_crawls[crawler_id] = {}
        
        active_crawls[crawler_id].update(data)
        self.set("crawler_operations.active_crawls", active_crawls)
    
    def remove_crawler_operation(self, crawler_id: str) -> None:
        """
        Remove a crawler operation from active crawls.
        
        Args:
            crawler_id: ID of the crawler to remove
        """
        active_crawls = self.get("crawler_operations.active_crawls", {}).copy()
        if crawler_id in active_crawls:
            del active_crawls[crawler_id]
        self.set("crawler_operations.active_crawls", active_crawls)
    
    def add_notification(self, message: str, type: str = "info") -> None:
        """
        Add a notification to the state.
        
        Args:
            message: Notification message
            type: Notification type ("info", "warning", "error")
        """
        notifications = self.get("notifications", []).copy()
        notifications.append({
            "message": message,
            "type": type,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        # Keep only the 10 most recent notifications
        if len(notifications) > 10:
            notifications = notifications[-10:]
            
        self.set("notifications", notifications)
    
    def add_error(self, error_type: str, message: str, details: Dict[str, Any] = None) -> None:
        """
        Add an error to the recent errors list.
        
        Args:
            error_type: Type of error
            message: Error message
            details: Additional error details
        """
        last_errors = self.get("crawler_operations.last_errors", []).copy()
        last_errors.append({
            "type": error_type,
            "message": message,
            "timestamp": datetime.datetime.now().isoformat(),
            "details": details or {}
        })
        
        # Keep only the 10 most recent errors
        if len(last_errors) > 10:
            last_errors = last_errors[-10:]
            
        self.set("crawler_operations.last_errors", last_errors)
    
    def sync_to_streamlit(self, st) -> None:
        """
        Synchronize state to Streamlit session state.
        
        Args:
            st: Streamlit module
        """
        # Sync top-level keys
        for key, value in self._state.items():
            if isinstance(value, (str, int, float, bool, list)) or value is None:
                st.session_state[key] = value
            elif isinstance(value, dict) and key == "crawler_operations":
                # Special handling for crawler operations
                if "crawler_operations" not in st.session_state:
                    st.session_state.crawler_operations = {}
                
                # Sync active crawls
                st.session_state.crawler_operations["active_crawls"] = value.get("active_crawls", {})
                
                # Sync last errors
                st.session_state.crawler_operations["last_errors"] = value.get("last_errors", [])
                
                # Sync discovery stats
                st.session_state.crawler_operations["discovery_stats"] = value.get("discovery_stats", {})
            elif key == "notifications":
                st.session_state.notifications = value
    
    def sync_from_streamlit(self, st) -> None:
        """
        Synchronize state from Streamlit session state.
        
        Args:
            st: Streamlit module
        """
        # Only sync UI-related state from Streamlit
        ui_keys = ["current_page", "auto_refresh", "refresh_interval", "dark_mode"]
        
        for key in ui_keys:
            if key in st.session_state:
                self.set(key, st.session_state[key])
    
    def to_json(self) -> str:
        """
        Convert state to JSON string.
        
        Returns:
            JSON representation of the state
        """
        # Create a copy of the state with only serializable values
        serializable_state = {}
        
        for key, value in self._state.items():
            if isinstance(value, (str, int, float, bool, list, dict)) or value is None:
                serializable_state[key] = value
                
        return json.dumps(serializable_state)
    
    def from_json(self, json_str: str) -> None:
        """
        Load state from JSON string.
        
        Args:
            json_str: JSON representation of state
        """
        try:
            data = json.loads(json_str)
            
            # Update state with loaded values
            for key, value in data.items():
                self.set(key, value)
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding state JSON: {str(e)}")
