"""
Adapter to bridge between the new architecture and Streamlit.
Provides a clean interface for component access and state management.
"""

import logging
import streamlit as st
from typing import Dict, Any, Optional

from config import Config
from app_components import AppComponents
from app_state import AppState

class StreamlitAdapter:
    """
    Adapter to bridge between the new architecture and Streamlit.
    """
    
    def __init__(self):
        """
        Initialize the Streamlit adapter.
        """
        self.logger = logging.getLogger("StreamlitAdapter")
        self.config = Config
        self.components = None
        self.state = None
        self.notification_system = None
        self.websocket_component = None
        
    def initialize(self) -> bool:
        """
        Initialize the application components and state.
        
        Returns:
            True if initialization was successful
        """
        if hasattr(st.session_state, 'adapter_initialized') and st.session_state.adapter_initialized:
            self.logger.info("Adapter already initialized")
            # Retrieve existing instances
            self.components = st.session_state.components
            self.state = st.session_state.app_state
            return True
            
        try:
            # Initialize components
            if not hasattr(st.session_state, 'components'):
                self.logger.info("Creating AppComponents")
                self.components = AppComponents(self.config)
                st.session_state.components = self.components
            else:
                self.components = st.session_state.components
                
            # Initialize state
            if not hasattr(st.session_state, 'app_state'):
                self.logger.info("Creating AppState")
                self.state = AppState()
                st.session_state.app_state = self.state
            else:
                self.state = st.session_state.app_state
                
            # Initialize components
            self.components.initialize_all()
            
            # Initialize notification system
            from notification_system import create_notification_system
            self.notification_system = create_notification_system(self)
            
            # Initialize WebSocket component
            websocket_manager = self.get_websocket_manager()
            if websocket_manager:
                # Start the WebSocket server if not already running
                if not websocket_manager.running:
                    websocket_manager.start_server()
            
            # Update state
            self.state.set("db_initialized", True)
            self.state.set("initialized", True)
            
            # Sync to Streamlit
            self.state.sync_to_streamlit(st)
            
            # Mark as initialized
            st.session_state.adapter_initialized = True
            
            # Store adapter in session state for access from pages
            st.session_state.adapter = self
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing adapter: {str(e)}", exc_info=True)
            return False
            
    def get_component(self, name: str):
        """
        Get a component by name.
        
        Args:
            name: Component name
            
        Returns:
            The requested component or None
        """
        if not self.components:
            return None
            
        try:
            return self.components.get(name)
        except Exception as e:
            self.logger.error(f"Error getting component {name}: {str(e)}")
            return None
            
    def update_state(self, key: str, value):
        """
        Update application state.
        
        Args:
            key: State key
            value: New value
        """
        if not self.state:
            return
            
        self.state.set(key, value)
        self.state.sync_to_streamlit(st)
        
    def sync_from_streamlit(self):
        """
        Sync state from Streamlit session.
        """
        if not self.state:
            return
            
        self.state.sync_from_streamlit(st)
        
    def add_notification(self, 
                        title: str, 
                        message: str, 
                        notification_type: str = "system", 
                        level: str = "info", 
                        data: Optional[Dict] = None):
        """
        Add a notification using the notification system.
        
        Args:
            title: Notification title
            message: Notification message
            notification_type: Type of notification (system, discovery, etc.)
            level: Notification level (info, warning, error, success)
            data: Additional notification data
            
        Returns:
            Notification ID if created, None otherwise
        """
        if not self.notification_system:
            # Initialize notification system if needed
            from notification_system import create_notification_system
            self.notification_system = create_notification_system(self)
            
        if self.notification_system:
            return self.notification_system.send_notification(
                notification_type, title, message, level, data
            )
        
        # Fallback to old notification system
        if self.state:
            self.state.add_notification(message, level)
            self.state.sync_to_streamlit(st)
            
        return None
        
    def add_error(self, error_type: str, message: str, details=None):
        """
        Add an error and create an error notification.
        
        Args:
            error_type: Error type
            message: Error message
            details: Additional details
        """
        if not self.state:
            return
            
        # Add to state errors
        self.state.add_error(error_type, message, details)
        self.state.sync_to_streamlit(st)
        
        # Also create a notification
        self.add_notification(
            f"Error: {error_type}",
            message,
            "error",
            "error",
            details
        )
        
        # Send via WebSocket if available
        websocket_manager = self.get_websocket_manager()
        if websocket_manager:
            websocket_manager.emit_error(error_type, message, details)
        
    def get_link_db(self):
        """Convenience method to get the link database."""
        return self.get_component("link_db")
        
    def get_crawler(self):
        """Convenience method to get the crawler."""
        return self.get_component("crawler")
        
    def get_websocket_manager(self):
        """Convenience method to get the WebSocket manager."""
        return self.get_component("websocket_manager")
        
    def get_network_visualizer(self):
        """Convenience method to get the network visualizer."""
        return self.get_component("network_visualizer")
        
    def get_export_manager(self):
        """Convenience method to get the export manager."""
        return self.get_component("export_manager")
        
    def get_content_analyzer(self):
        """Convenience method to get the content analyzer."""
        return self.get_component("content_analyzer")
        
    def get_trend_analyzer(self):
        """Convenience method to get the trend analyzer."""
        return self.get_component("trend_analyzer")
        
    def get_notification_system(self):
        """Convenience method to get the notification system."""
        if not self.notification_system:
            from notification_system import create_notification_system
            self.notification_system = create_notification_system(self)
        return self.notification_system
    
    def get_websocket_component(self, server_url="ws://localhost:8765"):
        """
        Get the WebSocket component for Streamlit integration.
        
        Args:
            server_url: WebSocket server URL
            
        Returns:
            StreamlitWebSocketComponent instance
        """
        if not self.websocket_component:
            from streamlit_websocket_component import create_websocket_component
            self.websocket_component = create_websocket_component(server_url)
        return self.websocket_component
    
    def emit_event(self, event_type: str, data: Dict):
        """Emit an event via the WebSocket manager."""
        websocket_manager = self.get_websocket_manager()
        if websocket_manager:
            websocket_manager.emit_event(event_type, data)
            
    def emit_system_status(self, status: str, details: Dict = None):
        """Emit system status event."""
        websocket_manager = self.get_websocket_manager()
        if websocket_manager:
            websocket_manager.emit_system_status(status, details)
            
    def emit_discovery(self, url: str, source: str, details: Dict = None):
        """Emit discovery event."""
        websocket_manager = self.get_websocket_manager()
        if websocket_manager:
            websocket_manager.emit_discovery(url, source, details)
