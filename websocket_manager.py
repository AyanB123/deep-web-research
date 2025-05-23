"""
WebSocket manager for real-time updates in the Dark Web Discovery System.
Provides event-based communication between crawler and UI.
"""

import json
import logging
import threading
import asyncio
import queue
import websockets
import datetime
import time
import uuid
from typing import Dict, List, Any, Optional, Set, Callable, Union, Tuple

from websocket_client import WebSocketClient
from websocket_auth import get_auth_manager, WebSocketAuthManager

from websockets.server import WebSocketServerProtocol
import websockets.exceptions

# Configure logger
def log_action(message):
    """Log actions with timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    logging.info(message)

class WebSocketManager:
    """
    Manages WebSocket connections for real-time updates.
    Acts as a bridge between the crawler and the UI.
    Provides both server and client functionality for WebSocket communication.
    """
    
    def __init__(self, host: str = "localhost", port: int = 8765, auth_required: bool = True):
        """
        Initialize the WebSocket manager.
        
        Args:
            host (str): WebSocket server host
            port (int): WebSocket server port
            auth_required (bool): Whether authentication is required for connections
        """
        self.host = host
        self.port = port
        self.clients: Dict[WebSocketServerProtocol, Dict[str, Any]] = {}
        self.server = None
        self.running = False
        self.message_queue = queue.Queue()
        self.server_thread = None
        self.queue_processor_thread = None
        
        # Authentication
        self.auth_required = auth_required
        self.auth_manager = get_auth_manager() if auth_required else None
        
        # Client for connecting to WebSocket servers
        self.client = None
        self.client_handlers = {}
        self.client_connected = False
        self.client_auth_token = None
        
        # Channel subscriptions
        self.channels = {
            "public": set(),  # Public channel for all clients
            "admin": set(),  # Admin channel for privileged operations
            "crawler": set(),  # Crawler channel for crawler events
            "discovery": set(),  # Discovery channel for new findings
            "error": set()  # Error channel for error notifications
        }
        
        # Event handlers
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # Event history for new clients
        self.event_history: Dict[str, List[Dict]] = {
            "crawl_progress": [],
            "discovery": [],
            "error": [],
            "system": []
        }
        self.max_history_items = 50
        
        # Message compression
        self.enable_compression = True
        
        # Initialize logging
        self.logger = logging.getLogger("WebSocketManager")
    
    async def _handler(self, websocket: WebSocketServerProtocol, path: str):
        """Handle WebSocket connections."""
        client_id = str(id(websocket))
        client_info = {
            "id": client_id,
            "authenticated": False,
            "user_id": None,
            "channels": [],
            "connected_at": datetime.datetime.now().isoformat(),
            "remote": websocket.remote_address
        }
        
        self.logger.info(f"New WebSocket connection from {websocket.remote_address}, client_id: {client_id}")
        
        # Add to clients with pending authentication
        self.clients[websocket] = client_info
        
        try:
            # If authentication is required, wait for auth message first
            if self.auth_required:
                authenticated = await self._authenticate_client(websocket, client_info)
                if not authenticated:
                    # Authentication failed or timed out
                    self.logger.warning(f"Authentication failed for client {client_id}")
                    return
            else:
                # No authentication required, add to public channel
                client_info["authenticated"] = True
                client_info["channels"] = ["public"]
                self.channels["public"].add(websocket)
                
                # Send welcome message
                await websocket.send(json.dumps({
                    "type": "connection",
                    "data": {
                        "status": "connected",
                        "client_id": client_id,
                        "channels": client_info["channels"],
                        "message": "Connected to WebSocket server"
                    }
                }))
            
            # Send initial state to the client
            await self._send_initial_state(websocket)
            
            # Listen for messages from client
            async for message in websocket:
                try:
                    data = json.loads(message)
                    event_type = data.get("type")
                    event_data = data.get("data", {})
                    
                    # Handle client events
                    if event_type == "subscribe":
                        # Client subscribing to specific events
                        await self._handle_subscription(websocket, client_info, event_data)
                    elif event_type == "request_history":
                        # Client requesting event history
                        history_type = event_data.get("history_type", "all")
                        await self._send_history(websocket, history_type)
                    elif event_type == "ping":
                        # Client ping to keep connection alive
                        await websocket.send(json.dumps({
                            "type": "pong",
                            "timestamp": datetime.datetime.now().isoformat()
                        }))
                    else:
                        # Validate client has permission for this event type
                        if await self._check_event_permission(websocket, client_info, event_type):
                            # Trigger event handlers
                            await self._trigger_event_handlers(event_type, event_data, websocket)
                        else:
                            # Client doesn't have permission
                            await websocket.send(json.dumps({
                                "type": "error",
                                "data": {
                                    "message": "Permission denied",
                                    "error_type": "permission_denied"
                                }
                            }))
                
                except json.JSONDecodeError:
                    self.logger.warning(f"Received invalid JSON from client {client_id}")
                except Exception as e:
                    self.logger.error(f"Error handling client message: {str(e)}")
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"Client disconnected: {client_id}")
        finally:
            # Unregister client from channels
            for channel in client_info.get("channels", []):
                if channel in self.channels and websocket in self.channels[channel]:
                    self.channels[channel].remove(websocket)
            
            # Remove client
            if websocket in self.clients:
                del self.clients[websocket]
    
    async def _send_initial_state(self, websocket: WebSocketServerProtocol):
        """Send initial state to a new client."""
        try:
            # Send welcome message
            await websocket.send(json.dumps({
                "type": "welcome",
                "data": {
                    "message": "Connected to Dark Web Discovery System",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "server_version": "1.0.0"
                }
            }))
            
            # Send system status
            await websocket.send(json.dumps({
                "type": "system_status",
                "data": {
                    "status": "running",
                    "active_crawls": len(self.event_history["crawl_progress"]),
                    "timestamp": datetime.datetime.now().isoformat()
                }
            }))
        
        except Exception as e:
            log_action(f"Error sending initial state: {str(e)}")
    
    async def _send_history(self, websocket: WebSocketServerProtocol, history_type: str):
        """Send event history to client."""
        try:
            if history_type == "all":
                # Send all history
                for event_type, events in self.event_history.items():
                    if events:
                        await websocket.send(json.dumps({
                            "type": "history",
                            "data": {
                                "event_type": event_type,
                                "events": events
                            }
                        }))
            elif history_type in self.event_history:
                # Send specific history type
                await websocket.send(json.dumps({
                    "type": "history",
                    "data": {
                        "event_type": history_type,
                        "events": self.event_history[history_type]
                    }
                }))
        
        except Exception as e:
            log_action(f"Error sending history: {str(e)}")
    
    async def _authenticate_client(self, websocket: WebSocketServerProtocol, client_info: Dict) -> bool:
        """Authenticate a client connection.
        
        Args:
            websocket: Client WebSocket connection
            client_info: Client information dict
            
        Returns:
            True if authenticated, False otherwise
        """
        try:
            # Set a timeout for authentication
            auth_timeout = 30  # seconds
            auth_deadline = time.time() + auth_timeout
            
            # Send authentication request
            await websocket.send(json.dumps({
                "type": "auth_required",
                "data": {
                    "message": "Authentication required",
                    "timeout": auth_timeout
                }
            }))
            
            # Wait for authentication message
            while time.time() < auth_deadline:
                try:
                    # Set per-message timeout
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    
                    try:
                        data = json.loads(message)
                        
                        if data.get("type") == "auth":
                            auth_data = data.get("data", {})
                            token = auth_data.get("token")
                            
                            if token:
                                # Validate token
                                is_valid, token_data = self.auth_manager.validate_token(token)
                                
                                if is_valid and token_data:
                                    # Authentication successful
                                    user_id = token_data.get("user_id")
                                    channels = token_data.get("channels", ["public"])
                                    
                                    # Update client info
                                    client_info["authenticated"] = True
                                    client_info["user_id"] = user_id
                                    client_info["channels"] = channels
                                    
                                    # Add to channels
                                    for channel in channels:
                                        if channel in self.channels:
                                            self.channels[channel].add(websocket)
                                    
                                    # Send success response
                                    await websocket.send(json.dumps({
                                        "type": "auth_success",
                                        "data": {
                                            "user_id": user_id,
                                            "channels": channels,
                                            "expires": token_data.get("exp")
                                        }
                                    }))
                                    
                                    self.logger.info(f"Client {client_info['id']} authenticated as user {user_id}")
                                    return True
                                else:
                                    # Invalid token
                                    await websocket.send(json.dumps({
                                        "type": "auth_error",
                                        "data": {
                                            "message": "Invalid authentication token"
                                        }
                                    }))
                            else:
                                # Missing token
                                await websocket.send(json.dumps({
                                    "type": "auth_error",
                                    "data": {
                                        "message": "Authentication token required"
                                    }
                                }))
                        
                    except json.JSONDecodeError:
                        # Invalid JSON
                        await websocket.send(json.dumps({
                            "type": "error",
                            "data": {
                                "message": "Invalid message format"
                            }
                        }))
                
                except asyncio.TimeoutError:
                    # Timeout for this attempt, continue loop
                    continue
            
            # Authentication timeout
            await websocket.send(json.dumps({
                "type": "auth_error",
                "data": {
                    "message": "Authentication timeout"
                }
            }))
            
            return False
        
        except (websockets.exceptions.ConnectionClosed, Exception) as e:
            self.logger.error(f"Error during authentication: {str(e)}")
            return False
    
    async def _handle_subscription(self, websocket: WebSocketServerProtocol, client_info: Dict, data: Dict) -> None:
        """Handle client subscription request.
        
        Args:
            websocket: Client WebSocket connection
            client_info: Client information dict
            data: Subscription data
        """
        # Get requested topics
        topics = data.get("topics", [])
        
        if not topics:
            return
        
        # Check permissions for each topic/channel
        allowed_topics = []
        denied_topics = []
        
        for topic in topics:
            # Check if this is a valid channel
            if topic not in self.channels:
                denied_topics.append(topic)
                continue
            
            # Check if client has permission for this channel
            if self.auth_required:
                user_id = client_info.get("user_id")
                if not user_id or not self.auth_manager.can_access_channel(user_id, topic):
                    denied_topics.append(topic)
                    continue
            
            # Add to allowed topics
            allowed_topics.append(topic)
            
            # Add to channel if not already present
            if topic not in client_info["channels"]:
                client_info["channels"].append(topic)
                self.channels[topic].add(websocket)
        
        # Send response
        await websocket.send(json.dumps({
            "type": "subscription_result",
            "data": {
                "subscribed": allowed_topics,
                "denied": denied_topics
            }
        }))
        
        self.logger.info(f"Client {client_info['id']} subscribed to: {allowed_topics}")
    
    async def _check_event_permission(self, websocket: WebSocketServerProtocol, client_info: Dict, event_type: str) -> bool:
        """Check if client has permission for an event type.
        
        Args:
            websocket: Client WebSocket connection
            client_info: Client information dict
            event_type: Event type
            
        Returns:
            True if permitted, False otherwise
        """
        # If no authentication required, allow all events
        if not self.auth_required:
            return True
        
        # Map event types to required channels
        event_channels = {
            "crawl_progress": "crawler",
            "discovery": "discovery",
            "error": "error",
            "system": "admin"
        }
        
        # Default to public channel if not in mapping
        required_channel = event_channels.get(event_type, "public")
        
        # Check if client has access to required channel
        return required_channel in client_info.get("channels", [])
    
    async def _broadcast(self, message: Dict, channel: str = "public", exclude_clients: List = None, 
                  priority: str = "normal", filter_func: Callable = None):
        """
        Broadcast a message to clients in a channel with filtering options.
        
        Args:
            message: Message to broadcast
            channel: Channel to broadcast to (default: public)
            exclude_clients: List of client websockets to exclude
            priority: Message priority (low, normal, high)
            filter_func: Optional function to filter clients (takes client_info, returns bool)
        """
        if channel not in self.channels:
            self.logger.warning(f"Channel '{channel}' does not exist")
            return
            
        if not self.channels[channel]:
            return
            
        # Setup for selective broadcasting
        exclude_clients = exclude_clients or []
        recipients = []
        
        # Apply filters
        for websocket in self.channels[channel]:
            # Skip excluded clients
            if websocket in exclude_clients:
                continue
                
            # Get client info
            client_info = self.clients.get(websocket, {})
            
            # Apply custom filter if provided
            if filter_func and not filter_func(client_info):
                continue
                
            recipients.append(websocket)
            
        if not recipients:
            return
            
        self.logger.debug(f"Broadcasting to {len(recipients)} clients in channel '{channel}'")
        
        # Add message ID and timestamp if not present
        if isinstance(message, dict):
            if "id" not in message:
                message["id"] = str(uuid.uuid4())
            if "timestamp" not in message:
                message["timestamp"] = datetime.datetime.now().isoformat()
            json_message = json.dumps(message)
        else:
            json_message = message
            
        # Send to all selected clients
        for websocket in recipients:
            try:
                # Store in message queue with appropriate priority
                priority_value = {
                    "low": 0,
                    "normal": 1,
                    "high": 2
                }.get(priority, 1)
                
                # Add to message queue
                self.message_queue.put((priority_value, websocket, json_message))
            except Exception as e:
                self.logger.error(f"Error queueing broadcast message: {str(e)}")
                self.logger.error(f"Error sending message to client: {str(e)}")
    
    async def _trigger_event_handlers(self, event_type: str, event_data: Dict, 
                                    client: Optional[WebSocketServerProtocol] = None):
        """Trigger event handlers for an event type."""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(event_data, client)
                except Exception as e:
                    log_action(f"Error in event handler for {event_type}: {str(e)}")
    
    def register_event_handler(self, event_type: str, handler: Callable):
        """
        Register an event handler.
        
        Args:
            event_type (str): Event type to handle
            handler (callable): Async function to handle the event
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
    
    def start_server(self):
        """Start the WebSocket server in a separate thread."""
        if self.running:
            self.logger.info("WebSocket server already running")
            return
            
        self.running = True
        
        # Start server thread
        self.server_thread = threading.Thread(target=self._run_server_thread)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Start message queue processor
        self.queue_processor_thread = threading.Thread(target=self._process_message_queue)
        self.queue_processor_thread.daemon = True
        self.queue_processor_thread.start()
        
        self.logger.info(f"WebSocket server started on {self.host}:{self.port}")
        
        log_action(f"WebSocket server started on ws://{self.host}:{self.port}")
    
    def stop_server(self):
        """Stop the WebSocket server."""
        if not self.running:
            self.logger.info("WebSocket server not running")
            return
            
        self.running = False
        
        # Stop server
        if self.server:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.server.close())
            loop.close()
            
        # Wait for server thread to end
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5.0)
            
        # Stop client if running
        self.stop_client()
            
        self.logger.info("WebSocket server stopped")
    
    def _run_server_thread(self):
        """Run the WebSocket server in a thread."""
        # Define async server
        async def start_server():
            self.server = await websockets.serve(
                self._handler, self.host, self.port
            )
            self.logger.info(f"WebSocket server started on {self.host}:{self.port}")
            await asyncio.Future()  # Run forever
        
        # Set up event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(start_server())
        except Exception as e:
            self.logger.error(f"Error running WebSocket server: {str(e)}")
        finally:
            loop.close()
    
    def _process_message_queue(self):
        """Process the message queue in a separate thread."""
        while self.running:
            try:
                # Get a message from the queue (priority, websocket, message)
                priority, websocket, message = self.message_queue.get(block=True, timeout=0.1)
                
                # Check if websocket is still connected
                if websocket not in self.clients:
                    # Client disconnected
                    self.logger.debug("Skipping message for disconnected client")
                    self.message_queue.task_done()
                    continue
                
                # Send the message
                try:
                    asyncio.run_coroutine_threadsafe(
                        websocket.send(message),
                        self.loop
                    )
                except Exception as e:
                    self.logger.error(f"Error sending message to client: {str(e)}")
                
                # Mark as done
                self.message_queue.task_done()
            except queue.Empty:
                # No messages in queue
                pass
            except Exception as e:
                self.logger.error(f"Error processing message queue: {str(e)}")
                time.sleep(0.1)
    
    async def _process_message(self, message: Dict):
        """Process a message from the queue."""
        # Store in event history
        event_type = message.get("type")
        if event_type in self.event_history:
            # Add timestamp if not present
            if "data" in message and "timestamp" not in message["data"]:
                message["data"]["timestamp"] = datetime.datetime.now().isoformat()
            
            # Add to history
            self.event_history[event_type].append(message["data"])
            
            # Limit history size
            if len(self.event_history[event_type]) > self.max_history_items:
                self.event_history[event_type] = self.event_history[event_type][-self.max_history_items:]
        
        # Determine target channel based on event type
        target_channel = {
            "crawl_progress": "crawler",
            "discovery": "discovery",
            "error": "error",
            "system": "admin"
        }.get(event_type, "public")
        
        # Broadcast to appropriate channel and public channel
        await self._broadcast(message, target_channel)
        if target_channel != "public":
            await self._broadcast(message, "public")
            crawler_id (str): Unique ID of the crawler
            url (str): URL being crawled
            status (str): Status of the crawl (starting, running, completed, error)
            progress (float): Progress percentage (0-100)
            details (dict): Additional details
        """
        details = details or {}
        
        self.emit_event("crawl_progress", {
            "crawler_id": crawler_id,
            "url": url,
            "status": status,
            "progress": progress,
            "timestamp": datetime.datetime.now().isoformat(),
            **details
        })
    
    def emit_discovery(self, url: str, source: str, details: Dict = None):
        """
        Emit link discovery event.
        
        Args:
            url (str): Discovered URL
            source (str): Discovery source
            details (dict): Additional details
        """
        details = details or {}
        
        self.emit_event("discovery", {
            "url": url,
            "source": source,
            "timestamp": datetime.datetime.now().isoformat(),
            **details
        })
    
    def emit_error(self, error_type: str, message: str, details: Dict = None):
        """
        Emit error event.
        
        Args:
            error_type (str): Type of error
            message (str): Error message
            details (dict): Additional details
        """
        details = details or {}
        
        self.emit_event("error", {
            "error_type": error_type,
            "message": message,
            "timestamp": datetime.datetime.now().isoformat(),
            **details
        })
    
    def emit_system_status(self, status: str, details: Dict = None):
        """
        Emit system status event.
        
        Args:
            status (str): System status
            details (dict): Additional details
        """
        details = details or {}
        
        self.emit_event("system", {
            "status": status,
            "timestamp": datetime.datetime.now().isoformat(),
            **details
        })


    def emit_to_user(self, user_id: str, event_type: str, data: Dict, priority: str = "normal"):
        """
        Emit an event to a specific user.
        
        Args:
            user_id (str): User ID to target
            event_type (str): Event type
            data (dict): Event data
            priority (str): Message priority (low, normal, high)
        """
        # Create message
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Find websockets for this user
        target_websockets = []
        for websocket, client_info in self.clients.items():
            if client_info.get("user_id") == user_id:
                target_websockets.append(websocket)
        
        if not target_websockets:
            self.logger.debug(f"No connected clients found for user {user_id}")
            return
        
        self.logger.debug(f"Emitting event {event_type} to user {user_id} ({len(target_websockets)} connections)")
        
        # Send to each client connection for this user
        for websocket in target_websockets:
            try:
                # Get priority value
                priority_value = {
                    "low": 0,
                    "normal": 1,
                    "high": 2
                }.get(priority, 1)
                
                # Add to message queue
                self.message_queue.put((priority_value, websocket, json.dumps(message)))
            except Exception as e:
                self.logger.error(f"Error queueing message for user {user_id}: {str(e)}")
    
    def broadcast_to_room(self, room_id: str, event_type: str, data: Dict, 
                         exclude_user_id: str = None, priority: str = "normal"):
        """
        Broadcast an event to all users in a specific room.
        
        Args:
            room_id (str): Room ID to target
            event_type (str): Event type
            data (dict): Event data
            exclude_user_id (str): Optional user ID to exclude from broadcast
            priority (str): Message priority (low, normal, high)
        """
        # Create message
        message = {
            "type": event_type,
            "data": data,
            "room_id": room_id,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Find clients in this room
        target_websockets = []
        for websocket, client_info in self.clients.items():
            # Skip excluded user
            if exclude_user_id and client_info.get("user_id") == exclude_user_id:
                continue
                
            # Check if user is in this room
            client_rooms = client_info.get("rooms", [])
            if room_id in client_rooms:
                target_websockets.append(websocket)
        
        if not target_websockets:
            self.logger.debug(f"No connected clients found for room {room_id}")
            return
        
        self.logger.debug(f"Broadcasting event {event_type} to room {room_id} ({len(target_websockets)} clients)")
        
        # Convert to JSON once
        json_message = json.dumps(message)
        
        # Get priority value
        priority_value = {
            "low": 0,
            "normal": 1,
            "high": 2
        }.get(priority, 1)
        
        # Send to each client in the room
        for websocket in target_websockets:
            try:
                # Add to message queue
                self.message_queue.put((priority_value, websocket, json_message))
            except Exception as e:
                self.logger.error(f"Error queueing message for room {room_id}: {str(e)}")
    
    # Client-side methods
    def connect_client(self, server_url: str = "ws://localhost:8765", client_id: Optional[str] = None, auth_token: Optional[str] = None):
        """
        Connect to a WebSocket server as a client.
        
        Args:
            server_url: WebSocket server URL
            client_id: Client identifier (generated if not provided)
            auth_token: Authentication token (if required by server)
        
        Returns:
            True if connection process started, False otherwise
        """
        if self.client:
            self.logger.info("WebSocket client already connected")
            return False
            
        # Initialize client
        self.client = WebSocketClient(server_url, client_id)
        self.client_auth_token = auth_token
        
        # Register handlers
        self.client.register_global_handler(self._client_message_handler)
        
        # Register authentication handler
        self.client.register_handler("auth_required", self._handle_auth_required)
        
        # Connect
        self.client.start()
        self.logger.info(f"WebSocket client connecting to {server_url}")
        
        return True
    
    def _handle_auth_required(self, message_type: str, data: Dict):
        """Handle authentication request from server."""
        if not self.client or not self.client_auth_token:
            self.logger.warning("Authentication required but no token available")
            return
        
        # Send authentication token
        self.client.send_message("auth", {
            "token": self.client_auth_token
        })
    
    def generate_auth_token(self, user_id: str, channels: Optional[List[str]] = None) -> Optional[str]:
        """
        Generate an authentication token for the client.
        
        Args:
            user_id: User identifier
            channels: List of channels to access
            
        Returns:
            Authentication token or None if auth manager not available
        """
        if not self.auth_manager:
            return None
            
        token = self.auth_manager.generate_token(user_id, channels)
        self.client_auth_token = token
        return token
    
    def stop_client(self):
        """
        Disconnect the WebSocket client.
        
        Returns:
            True if disconnected, False if not connected
        """
        if not self.client:
            return False
            
        self.client.stop()
        self.client = None
        self.client_connected = False
        self.logger.info("WebSocket client disconnected")
        
        return True
    
    def register_client_handler(self, message_type: str, handler: Callable):
        """
        Register a handler for client-side messages.
        
        Args:
            message_type: Type of message to handle
            handler: Handler function
        """
        if message_type not in self.client_handlers:
            self.client_handlers[message_type] = []
            
        self.client_handlers[message_type].append(handler)
    
    def _client_message_handler(self, message_type: str, data: Dict):
        """
        Handle messages from the WebSocket server.
        
        Args:
            message_type: Message type
            data: Message data
        """
        # Update connection status
        if message_type == "connection":
            status = data.get("status")
            self.client_connected = (status == "connected")
            
        # Trigger handlers
        handlers = self.client_handlers.get(message_type, [])
        for handler in handlers:
            try:
                handler(message_type, data)
            except Exception as e:
                self.logger.error(f"Error in client handler for {message_type}: {str(e)}")
    
    def send_client_message(self, message_type: str, data: Dict = None):
        """
        Send a message to the WebSocket server.
        
        Args:
            message_type: Message type
            data: Message data
        
        Returns:
            True if sent, False if not connected
        """
        if not self.client or not self.client_connected:
            return False
            
        self.client.send_message(message_type, data or {})
        return True

# Singleton instance
_instance = None

def get_websocket_manager() -> WebSocketManager:
    """Get the singleton WebSocket manager instance."""
    global _instance
    if _instance is None:
        _instance = WebSocketManager()
    return _instance
