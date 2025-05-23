"""
Streamlit WebSocket component for real-time updates in the Dark Web Discovery System.
Provides client-side JavaScript integration with the WebSocket server.
"""

import os
import json
import streamlit as st
import streamlit.components.v1 as components
import uuid
from typing import Dict, List, Any, Optional, Callable

from app_adapter import StreamlitAdapter
from websocket_auth import get_auth_manager

class StreamlitWebSocketComponent:
    """
    Streamlit component for WebSocket integration.
    Provides client-side JavaScript for real-time updates with enhanced
    reconnection logic, message queuing, and progress tracking.
    """
    
    def __init__(self, server_url="ws://localhost:8765", user_id=None, channels=None, 
                 reconnect_config=None, storage_dir=None, max_queue_size=100):
        """
        Initialize the WebSocket component.
        
        Args:
            server_url: WebSocket server URL
            user_id: User ID for authentication (generated if None)
            channels: List of channels to subscribe to
            reconnect_config: Configuration for reconnection (dict with max_retries, 
                             initial_delay, max_delay, jitter)
            storage_dir: Directory for persistent message storage (default: None)
            max_queue_size: Maximum size of message queue (default: 100)
        """
        self.server_url = server_url
        self.initialized = False
        self.message_handlers = {}
        self.auth_token = None
        self.connection_status = "disconnected"  # disconnected, connecting, connected, reconnecting
        self.last_connection_error = None
        self.reconnect_attempt = 0
        
        # Default reconnection configuration
        self.reconnect_config = reconnect_config or {
            "max_retries": 10,
            "initial_delay": 1.0,
            "max_delay": 60.0,
            "jitter": 0.1
        }
        
        # Message queue settings
        self.storage_dir = storage_dir
        self.max_queue_size = max_queue_size
        
        # Connection event handlers
        self.connection_event_handlers = {
            "connected": [],
            "disconnected": [],
            "reconnecting": [],
            "error": []
        }
        
        # Get a unique client ID from session state
        if "websocket_client_id" not in st.session_state:
            st.session_state.websocket_client_id = str(uuid.uuid4())
        
        self.client_id = st.session_state.websocket_client_id
        
        # Use provided user ID or generate one
        self.user_id = user_id or f"user_{self.client_id}"
        
        # Default channels
        self.channels = channels or ["public", "crawler", "discovery", "error"]
        
        # Room membership (for room-based messaging)
        self.rooms = set()
        
        # Generate auth token if not already in session state
        if "websocket_auth_token" not in st.session_state:
            auth_manager = get_auth_manager()
            st.session_state.websocket_auth_token = auth_manager.generate_token(
                self.user_id, self.channels
            )
        
        self.auth_token = st.session_state.websocket_auth_token
        
        # Track active operations (for progress tracking)
        self.active_operations = {}
        
        # Register default handlers
        self.register_message_handler("connection_status", self._handle_connection_status)
        self.register_message_handler("progress_update", self._handle_progress_update)
    
    def _handle_connection_status(self, data):
        """
        Handle connection status updates from the WebSocket client.
        
        Args:
            data: Connection status data
        """
        status = data.get("status")
        message = data.get("message")
        error = data.get("error")
        
        # Update connection status
        self.connection_status = status
        
        if status == "error":
            self.last_connection_error = error
        
        # Trigger event handlers
        self._trigger_connection_event(status, {
            "message": message,
            "error": error,
            "timestamp": data.get("timestamp", datetime.datetime.now().isoformat())
        })
    
    def _handle_progress_update(self, data):
        """
        Handle progress update from the WebSocket client.
        
        Args:
            data: Progress update data
        """
        operation_id = data.get("operation_id")
        if not operation_id:
            return
        
        # Update operation status
        self.active_operations[operation_id] = data
        
        # If progress manager is in session state, notify it
        if "progress_manager" in st.session_state and st.session_state.progress_manager:
            try:
                progress_manager = st.session_state.progress_manager
                tracker = progress_manager.get_tracker(operation_id)
                
                if tracker:
                    # Update existing tracker
                    tracker.update(
                        current_step=data.get("current_step"),
                        status=data.get("status"),
                        description=data.get("description"),
                        details=data.get("details")
                    )
                else:
                    # Create new tracker
                    tracker = progress_manager.create_tracker(
                        operation_type=data.get("operation_type", "generic"),
                        total_steps=data.get("total_steps", 100),
                        description=data.get("description", "Operation in progress"),
                        cancellable=data.get("cancellable", False)
                    )
                    tracker.start()
            except Exception as e:
                print(f"Error updating progress tracker: {str(e)}")
    
    def register_connection_handler(self, event_type, handler):
        """
        Register a handler for connection events.
        
        Args:
            event_type: Event type (connected, disconnected, reconnecting, error)
            handler: Handler function
        """
        if event_type in self.connection_event_handlers:
            self.connection_event_handlers[event_type].append(handler)
    
    def _trigger_connection_event(self, event_type, data=None):
        """
        Trigger connection event handlers.
        
        Args:
            event_type: Event type
            data: Event data
        """
        if event_type in self.connection_event_handlers:
            for handler in self.connection_event_handlers[event_type]:
                try:
                    handler(data or {})
                except Exception as e:
                    print(f"Error in connection handler: {str(e)}")
    
    def join_room(self, room_id):
        """
        Join a room for room-based messaging.
        
        Args:
            room_id: Room identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized or not self.is_connected():
            return False
        
        # Add to local rooms set
        self.rooms.add(room_id)
        
        # Send join room message
        self.send_message("join_room", {"room_id": room_id})
        return True
    
    def leave_room(self, room_id):
        """
        Leave a room.
        
        Args:
            room_id: Room identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized or not self.is_connected():
            return False
        
        # Remove from local rooms set
        if room_id in self.rooms:
            self.rooms.remove(room_id)
        
        # Send leave room message
        self.send_message("leave_room", {"room_id": room_id})
        return True
    
    def cancel_operation(self, operation_id):
        """
        Cancel an operation.
        
        Args:
            operation_id: Operation identifier
            
        Returns:
            True if cancellation request sent, False otherwise
        """
        if not self.initialized or not self.is_connected():
            return False
        
        # Send cancellation message
        self.send_message("cancel_operation", {"operation_id": operation_id})
        return True
    
    def is_connected(self):
        """
        Check if WebSocket is connected.
        
        Returns:
            True if connected, False otherwise
        """
        return self.initialized and self.connection_status == "connected"
    
    def get_connection_status(self):
        """
        Get current connection status.
        
        Returns:
            Dict with connection status information
        """
        return {
            "status": self.connection_status,
            "last_error": self.last_connection_error,
            "reconnect_attempt": self.reconnect_attempt,
            "user_id": self.user_id,
            "client_id": self.client_id,
            "server_url": self.server_url,
            "channels": self.channels,
            "rooms": list(self.rooms)
        }
        
    def register_message_handler(self, message_type, handler):
        """
        Register a handler for a specific message type.
        
        Args:
            message_type: Type of message to handle
            handler: Handler function
        """
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
        
        self.message_handlers[message_type].append(handler)
    
    def _handle_message(self, message_type, data):
        """
        Handle a message from the WebSocket server.
        
        Args:
            message_type: Type of message
            data: Message data
        """
        handlers = self.message_handlers.get(message_type, [])
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                st.error(f"Error in WebSocket handler: {str(e)}")
    
    def initialize(self):
        """
        Initialize the WebSocket component with enhanced reconnection and message queuing support.
        """
        if self.initialized:
            return
        
        # Get WebSocket manager from adapter
        adapter = st.session_state.adapter if hasattr(st.session_state, 'adapter') else None
        if not adapter:
            st.warning("Adapter not initialized")
            return
        
        websocket_manager = adapter.get_websocket_manager()
        if not websocket_manager:
            st.warning("WebSocket manager not initialized")
            return
        
        # Connect to server with authentication token and enhanced options
        websocket_manager.connect_client(
            server_url=self.server_url, 
            client_id=self.client_id,
            auth_token=self.auth_token,
            reconnect_config=self.reconnect_config,
            storage_dir=self.storage_dir,
            max_queue_size=self.max_queue_size
        )
        
        # Register message handlers
        for message_type, handlers in self.message_handlers.items():
            for handler in handlers:
                websocket_manager.register_client_handler(message_type, 
                                                       lambda msg_type, data, h=handler: h(data))
        
        # Register connection status handler
        websocket_manager.register_client_handler("connection", 
                                                lambda msg_type, data: self._handle_connection_status(data))
        
        # Register auth-related handlers
        websocket_manager.register_client_handler("auth_error", self._handle_auth_error)
        websocket_manager.register_client_handler("auth_success", self._handle_auth_success)
        
        # Store manager reference for sending messages
        self.websocket_manager = websocket_manager
        
        # Update status
        self.initialized = True
        self.connection_status = "connecting"
        
        # Log initialization
        st.session_state["websocket"] = self
        
        # Trigger connection event
        self._trigger_connection_event("connecting", {
            "message": f"Connecting to {self.server_url}",
            "timestamp": datetime.datetime.now().isoformat()
        })
        
    def send_message(self, message_type, data=None, priority="normal", retry=True):
        """
        Send a message to the WebSocket server.
        
        Args:
            message_type: Type of message to send
            data: Message data (dict)
            priority: Message priority (low, normal, high)
            retry: Whether to retry sending if disconnected
            
        Returns:
            True if sent or queued, False if failed
        """
        if not self.initialized:
            return False
        
        # Get WebSocket manager
        websocket_manager = getattr(self, "websocket_manager", None)
        if not websocket_manager:
            return False
        
        # Prepare message data
        message_data = data or {}
        
        # Add client information
        if "client_id" not in message_data:
            message_data["client_id"] = self.client_id
        
        if "user_id" not in message_data:
            message_data["user_id"] = self.user_id
        
        # Add timestamp if not present
        if "timestamp" not in message_data:
            message_data["timestamp"] = datetime.datetime.now().isoformat()
        
        # Send message with priority and retry options
        return websocket_manager.send_client_message(
            message_type=message_type,
            data=message_data,
            priority=priority,
            retry=retry
        )
        
    def _handle_auth_error(self, message_type, data):
        """
        Handle authentication error from server.
        
        Args:
            message_type: Message type
            data: Message data
        """
        error_message = data.get("message", "Authentication failed")
        st.error(f"WebSocket authentication error: {error_message}")
        
        # Try to regenerate token
        auth_manager = get_auth_manager()
        st.session_state.websocket_auth_token = auth_manager.generate_token(
            self.user_id, self.channels
        )
        self.auth_token = st.session_state.websocket_auth_token
        
    def _handle_auth_success(self, message_type, data):
        """
        Handle successful authentication from server.
        
        Args:
            message_type: Message type
            data: Message data
        """
        channels = data.get("channels", [])
        self.channels = channels
    
    def render(self):
        """
        Render the WebSocket component.
        """
        # Initialize if needed
        if not self.initialized:
            self.initialize()
        
        # Inject JavaScript for WebSocket connection
        js_code = self._generate_js_code()
        components.html(js_code, height=0)
    
    def _generate_js_code(self):
        """
        Generate JavaScript code for WebSocket connection.
        
        Returns:
            JavaScript code as string
        """
        return f"""
        <script>
            // WebSocket connection
            (function() {{
                // Check if already connected
                if (window.darkWebSocketConnection) {{
                    console.log('WebSocket already connected');
                    return;
                }}
                
                // Create connection
                const ws = new WebSocket('{self.server_url}');
                window.darkWebSocketConnection = ws;
                window.lastAuthToken = '{self.auth_token}';
                
                // Connection opened
                ws.addEventListener('open', (event) => {{
                    console.log('Connected to WebSocket server');
                }}); 
                
                // Handle authentication request
                function handleAuthRequest(data) {{
                    console.log('Authentication required');
                    
                    // Send authentication token
                    ws.send(JSON.stringify({{
                        type: 'auth',
                        data: {{
                            token: window.lastAuthToken
                        }}
                    }}));
                }}
                
                // Handle successful authentication
                function handleAuthSuccess(data) {{
                    console.log('Authentication successful');
                    
                    // Subscribe to topics
                    ws.send(JSON.stringify({{
                        type: 'subscribe',
                        data: {{
                            client_id: '{self.client_id}',
                            topics: ['public', 'crawler', 'discovery', 'error', 'system']
                        }}
                    }}));
                    
                    // Request history
                    ws.send(JSON.stringify({{
                        type: 'request_history',
                        data: {{
                            history_type: 'all'
                        }}
                    }}));
                }}
                
                // Listen for messages
                ws.addEventListener('message', (event) => {{
                    try {{
                        const message = JSON.parse(event.data);
                        console.log('WebSocket message:', message);
                        
                        // Handle specific message types
                        if (message.type === 'auth_required') {{
                            handleAuthRequest(message.data);
                            return;
                        }} else if (message.type === 'auth_success') {{
                            handleAuthSuccess(message.data);
                        }} else if (message.type === 'auth_error') {{
                            console.error('Authentication error:', message.data);
                        }}
                        
                        // Forward all messages to Streamlit
                        window.parent.postMessage({{
                            type: 'websocket_message',
                            message: message
                        }}, '*');
                    }} catch (error) {{
                        console.error('Error parsing WebSocket message:', error);
                    }}
                }});
                
                // Connection closed
                ws.addEventListener('close', (event) => {{
                    console.log('Disconnected from WebSocket server');
                    window.darkWebSocketConnection = null;
                    
                    // Try to reconnect after a delay
                    setTimeout(() => {{
                        console.log('Attempting to reconnect...');
                        window.parent.postMessage({{
                            type: 'websocket_reconnect',
                            message: {{}}
                        }}, '*');
                    }}, 5000);
                }});
                
                // Connection error
                ws.addEventListener('error', (event) => {{
                    console.error('WebSocket error:', event);
                }});
                
                // Keep connection alive with periodic pings
                setInterval(() => {{
                    if (ws.readyState === WebSocket.OPEN) {{
                        ws.send(JSON.stringify({{
                            type: 'ping',
                            data: {{
                                timestamp: new Date().toISOString()
                            }}
                        }}));
                    }}
                }}, 30000);
                
                // Handle page unload
                window.addEventListener('beforeunload', () => {{
                    if (ws.readyState === WebSocket.OPEN) {{
                        ws.close();
                    }}
                }});
            }})();
        </script>
        """

def create_websocket_component(server_url="ws://localhost:8765", user_id=None, channels=None):
    """
    Create a WebSocket component for Streamlit.
    
    Args:
        server_url: WebSocket server URL
        user_id: User ID for authentication
        channels: List of channels to subscribe to
    
    Returns:
        WebSocket component
    """
    if "websocket_component" not in st.session_state:
        st.session_state.websocket_component = StreamlitWebSocketComponent(
            server_url=server_url,
            user_id=user_id,
            channels=channels
        )
    
    return st.session_state.websocket_component

def get_latest_websocket_message():
    """
    Get the latest WebSocket message from JavaScript.
    
    Returns:
        Latest message or None
    """
    from streamlit_javascript import st_javascript
    
    message = st_javascript("""
    window.addEventListener('message', (event) => {
        if (event.data.type === 'websocket_message') {
            window.streamlitLastWebSocketMessage = event.data.message;
        }
    });
    
    if (window.streamlitLastWebSocketMessage) {
        const message = window.streamlitLastWebSocketMessage;
        window.streamlitLastWebSocketMessage = null;
        return message;
    }
    
    return null;
    """)
    
    return message

def process_websocket_messages(adapter):
    """
    Process WebSocket messages and update application state.
    
    Args:
        adapter: StreamlitAdapter instance
    """
    message = get_latest_websocket_message()
    
    if not message:
        return
    
    try:
        message_type = message.get("type")
        data = message.get("data", {})
        
        if message_type == "crawl_progress":
            # Update crawler operations
            crawler_id = data.get("crawler_id", "")
            if crawler_id:
                adapter.state.update_crawler_operation(crawler_id, data)
        
        elif message_type == "discovery":
            # Update discovery stats
            stats = adapter.state.get("crawler_operations.discovery_stats", {})
            stats["total_discovered"] = stats.get("total_discovered", 0) + 1
            
            # Check if discovered today
            import datetime
            today = datetime.datetime.now().date().isoformat()
            timestamp = data.get("timestamp", "")
            if timestamp and timestamp.startswith(today):
                stats["today_discovered"] = stats.get("today_discovered", 0) + 1
            
            # Update last discovery time
            stats["last_discovery"] = timestamp
            
            # Update state
            adapter.update_state("crawler_operations.discovery_stats", stats)
        
        elif message_type == "error":
            # Add error to recent errors
            adapter.state.add_error(
                data.get("error_type", "unknown"),
                data.get("message", "Unknown error"),
                data
            )
        
        elif message_type == "system":
            # System status update
            status = data.get("status", "")
            if status:
                adapter.update_state("system_status", status)
    
    except Exception as e:
        st.error(f"Error processing WebSocket message: {str(e)}")
