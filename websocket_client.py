"""
WebSocket client implementation for the Dark Web Discovery System.
Handles WebSocket connections, message handling, and reconnection logic.
"""

import json
import logging
import threading
import time
import queue
import os
import pickle
import random
from typing import Dict, List, Any, Optional, Callable, Union
import websocket
import uuid
from dataclasses import dataclass

@dataclass
class QueuedMessage:
    """A message queued for sending."""
    type: str
    data: Dict[str, Any]
    timestamp: float
    priority: int = 0  # Higher priority messages are sent first
    attempts: int = 0  # Number of send attempts
    id: str = None  # Unique message ID
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for sending."""
        return {
            "type": self.type,
            "data": self.data,
            "id": self.id
        }
    
    def increment_attempt(self):
        """Increment the send attempt counter."""
        self.attempts += 1

class WebSocketClient:
    """
    WebSocket client for real-time communication with the WebSocket server.
    Handles connection management, message queuing, and event handling.
    """
    
    def __init__(self, server_url: str = "ws://localhost:8765", client_id: Optional[str] = None, 
                 persistent_queue: bool = True, storage_dir: Optional[str] = None):
        """
        Initialize the WebSocket client.
        
        Args:
            server_url: URL of the WebSocket server
            client_id: Unique client identifier (generated if not provided)
            persistent_queue: Whether to persist messages during disconnection
            storage_dir: Directory for persistent message storage
        """
        self.server_url = server_url
        self.client_id = client_id or str(uuid.uuid4())
        self.ws = None
        self.connected = False
        
        # Reconnection settings
        self.reconnect_interval = 2  # seconds
        self.max_reconnect_interval = 60  # seconds
        self.reconnect_decay = 1.5  # exponential backoff factor
        self.max_reconnect_attempts = 10  # 0 for unlimited
        self.reconnect_attempts = 0
        self.last_reconnect_time = 0
        
        # Message queue settings
        self.persistent_queue = persistent_queue
        self.storage_dir = storage_dir or os.path.join(os.path.dirname(__file__), "queue_storage")
        self.max_queue_size = 1000  # Maximum number of messages to queue
        self.max_retry_attempts = 5  # Maximum number of retry attempts per message
        self.priority_queue = queue.PriorityQueue()  # (priority, timestamp, message)
        self.event_handlers = {}
        self.global_handlers = []
        self.running = False
        self.connection_status = "disconnected"  # disconnected, connecting, connected
        self.offline_mode = False  # True when offline and not attempting to reconnect
        
        # Configure logger
        self.logger = logging.getLogger("WebSocketClient")
        
        # Message acknowledgment timeout (seconds)
        self.ack_timeout = 30
        
        # Connection thread
        self.connection_thread = None
        self.processing_thread = None
        self.queue_persistence_thread = None
        
        # Message tracking
        self.sent_messages = {}  # Track sent messages waiting for acknowledgment
        self.received_message_ids = set()  # Track received message IDs to prevent duplicates
        self.last_activity_time = 0  # Last time a message was sent or received
        
        # Subscribed topics
        self.subscribed_topics = set(["system"])
        
        # Create storage directory if needed
        if self.persistent_queue and not os.path.exists(self.storage_dir):
            try:
                os.makedirs(self.storage_dir)
                self.logger.info(f"Created message storage directory: {self.storage_dir}")
            except Exception as e:
                self.logger.error(f"Failed to create storage directory: {str(e)}")
                self.persistent_queue = False
        
        # Load any persisted messages
        self._load_persisted_messages()
    
    def _load_persisted_messages(self):
        """
        Load persisted messages from storage.
        """
        if not self.persistent_queue:
            return
            
        try:
            queue_file = os.path.join(self.storage_dir, f"queue_{self.client_id}.pickle")
            if os.path.exists(queue_file):
                with open(queue_file, 'rb') as f:
                    messages = pickle.load(f)
                    
                # Add messages to queue
                for msg in messages:
                    self._queue_message(msg.type, msg.data, msg.priority, msg.id)
                    
                self.logger.info(f"Loaded {len(messages)} persisted messages")
                
                # Delete the file after loading
                os.remove(queue_file)
        except Exception as e:
            self.logger.error(f"Error loading persisted messages: {str(e)}")
    
    def _persist_messages(self):
        """
        Persist queued messages to storage.
        """
        if not self.persistent_queue or self.priority_queue.empty():
            return
            
        try:
            # Get all messages from queue
            messages = []
            temp_queue = queue.PriorityQueue()
            
            while not self.priority_queue.empty():
                priority, timestamp, msg = self.priority_queue.get()
                messages.append(msg)
                temp_queue.put((priority, timestamp, msg))
            
            # Restore queue
            self.priority_queue = temp_queue
            
            # Save messages
            queue_file = os.path.join(self.storage_dir, f"queue_{self.client_id}.pickle")
            with open(queue_file, 'wb') as f:
                pickle.dump(messages, f)
                
            self.logger.info(f"Persisted {len(messages)} messages")
        except Exception as e:
            self.logger.error(f"Error persisting messages: {str(e)}")
    
    def start(self):
        """
        Start the WebSocket client.
        """
        if self.running:
            return
            
        self.running = True
        self.offline_mode = False
        self.reconnect_attempts = 0
        
        # Start connection thread
        self.connection_thread = threading.Thread(target=self._connection_loop)
        self.connection_thread.daemon = True
        self.connection_thread.start()
        
        # Start message processing thread
        self.processing_thread = threading.Thread(target=self._message_processing_loop)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
        # Start queue persistence thread if enabled
        if self.persistent_queue:
            self.queue_persistence_thread = threading.Thread(target=self._queue_persistence_loop)
            self.queue_persistence_thread.daemon = True
            self.queue_persistence_thread.start()
        
        self.logger.info("WebSocket client started")
    
    def stop(self):
        """
        Stop the WebSocket client.
        """
        self.running = False
        
        if self.ws:
            self.ws.close()
        
        # Persist any remaining messages
        if self.persistent_queue:
            self._persist_messages()
            
        self.logger.info("WebSocket client stopped")
    
    def _queue_persistence_loop(self):
        """
        Periodically persist queued messages to storage.
        """
        persist_interval = 30  # seconds
        
        while self.running:
            try:
                # Persist messages
                if not self.connected and not self.priority_queue.empty():
                    self._persist_messages()
                
                # Wait for next persistence cycle
                time.sleep(persist_interval)
            except Exception as e:
                self.logger.error(f"Error in queue persistence loop: {str(e)}")
                time.sleep(5)  # Wait a bit on error before retrying
    
    def _connection_loop(self):
        """
        Main connection loop. Handles connection and reconnection.
        """
        reconnect_interval = self.reconnect_interval
        self.connection_status = "disconnected"
        
        while self.running:
            # Check if we've reached max reconnection attempts
            if self.max_reconnect_attempts > 0 and self.reconnect_attempts >= self.max_reconnect_attempts:
                self.logger.warning(f"Maximum reconnection attempts ({self.max_reconnect_attempts}) reached")
                self.offline_mode = True
                
                # Notify handlers of offline mode
                self._notify_handlers("connection", {
                    "status": "offline", 
                    "reason": "max_attempts_reached"
                })
                
                # Persist messages and wait for manual reconnection
                if self.persistent_queue:
                    self._persist_messages()
                
                # Wait until running is set to False or offline mode is disabled
                while self.running and self.offline_mode:
                    time.sleep(1)
                
                # Reset reconnection attempts if offline mode was disabled
                if not self.offline_mode:
                    self.reconnect_attempts = 0
                    reconnect_interval = self.reconnect_interval
                
                continue
            
            try:
                # Update connection status
                self.connection_status = "connecting"
                self._notify_handlers("connection", {"status": "connecting"})
                
                # Try to connect
                self.logger.info(f"Connecting to WebSocket server at {self.server_url} (attempt {self.reconnect_attempts + 1})")
                self.ws = websocket.WebSocketApp(
                    self.server_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                
                # Start WebSocket connection in a separate thread
                ws_thread = threading.Thread(target=self.ws.run_forever)
                ws_thread.daemon = True
                ws_thread.start()
                
                # Wait for the thread to finish
                connection_timeout = 10  # seconds to wait for successful connection
                start_time = time.time()
                
                while self.running and ws_thread.is_alive():
                    # Check if we've connected successfully
                    if self.connected:
                        # Reset reconnect interval and attempts on successful connection
                        reconnect_interval = self.reconnect_interval
                        self.reconnect_attempts = 0
                    
                    # Check for connection timeout
                    if not self.connected and time.time() - start_time > connection_timeout:
                        self.logger.warning("Connection attempt timed out")
                        self.ws.close()
                        break
                    
                    time.sleep(0.1)
                
                # If we've connected successfully, continue
                if self.connected:
                    continue
                    
            except Exception as e:
                self.logger.error(f"Error in WebSocket connection: {str(e)}")
            
            # If we're still running, increment attempt counter and wait before reconnecting
            if self.running:
                self.reconnect_attempts += 1
                self.connection_status = "disconnected"
                
                # Calculate next reconnect interval with jitter to prevent thundering herd
                jitter = 0.1 * reconnect_interval * (2 * random.random() - 1)  # ±10% jitter
                next_interval = reconnect_interval + jitter
                
                self.logger.info(f"Reconnecting in {next_interval:.1f} seconds (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts or 'unlimited'})")
                self.last_reconnect_time = time.time()
                
                # Notify handlers of reconnection status
                self._notify_handlers("connection", {
                    "status": "reconnecting",
                    "attempt": self.reconnect_attempts,
                    "next_attempt": next_interval
                })
                
                time.sleep(next_interval)
                
                # Exponential backoff with max limit
                reconnect_interval = min(
                    reconnect_interval * self.reconnect_decay,
                    self.max_reconnect_interval
                )
        Args:
            ws: WebSocket instance
        """
        self.connected = True
        self.logger.info("WebSocket connection opened")
        
        # Subscribe to topics
        self._subscribe(list(self.subscribed_topics))
        
        # Request history
        self._request_history("all")
        
        # Notify handlers
        self._notify_handlers("connection", {"status": "connected"})
    
    def _on_message(self, ws, message):
        """
        Called when a message is received.
        
        Args:
            ws: WebSocket instance
            message: Received message
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")
            message_data = data.get("data", {})
            
            # Process the message
            self._notify_handlers(message_type, message_data)
            
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON received")
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
    
    def _on_error(self, ws, error):
        """
        Called when an error occurs.
        
        Args:
            ws: WebSocket instance
            error: Error information
        """
        self.logger.error(f"WebSocket error: {str(error)}")
        self._notify_handlers("error", {"message": str(error)})
    
    def _on_close(self, ws, close_status_code, close_msg):
        """
        Called when the connection is closed.
        
        Args:
            ws: WebSocket instance
            close_status_code: Status code
            close_msg: Close message
        """
        self.connected = False
        self.logger.info(f"WebSocket connection closed: {close_msg} (code: {close_status_code})")
        self._notify_handlers("connection", {"status": "disconnected"})
    
    def _requeue_message(self, message: QueuedMessage, priority: int):
        """
        Requeue a message after a failed send attempt.
        
        Args:
            message: Message to requeue
            priority: Message priority
        """
        if self.running:
            # Use original timestamp to maintain order among same-priority messages
            self.priority_queue.put((priority, message.timestamp, message))
    
    def _queue_message(self, message_type: str, data: Dict[str, Any], priority: int = 0, message_id: str = None) -> str:
        """
        Queue a message for sending.
        
        Args:
            message_type: Type of message
            data: Message data
            priority: Message priority (higher numbers = higher priority)
            message_id: Optional message ID (generated if None)
            
        Returns:
            Message ID
        """
        # Create message object
        message = QueuedMessage(
            type=message_type,
            data=data,
            timestamp=time.time(),
            priority=priority,
            id=message_id
        )
        
        # Check queue size limit
        if self.priority_queue.qsize() >= self.max_queue_size:
            self.logger.warning(f"Message queue full ({self.max_queue_size} messages), dropping oldest message")
            
            # Get all messages from queue
            messages = []
            temp_queue = queue.PriorityQueue()
            
            while not self.priority_queue.empty():
                p, ts, msg = self.priority_queue.get()
                messages.append((p, ts, msg))
            
            # Sort by priority and timestamp (ascending)
            messages.sort()
            
            # Remove the oldest, lowest priority message
            messages.pop(0)
            
            # Rebuild queue
            for item in messages:
                temp_queue.put(item)
            
            self.priority_queue = temp_queue
        
        # Add to queue
        self.priority_queue.put((priority, message.timestamp, message))
        
        # If connected, trigger processing
        if self.connected and self.processing_thread and self.processing_thread.is_alive():
            # Wake up processing thread
            pass  # No explicit wake-up needed due to short sleep time
        
        return message.id
    
    def _message_processing_loop(self):
        """
        Message processing loop. Processes queued messages.
        """
        retry_delay = 1.0  # Initial delay between retries in seconds
        max_retry_delay = 10.0  # Maximum delay between retries
        
        while self.running:
            try:
                # Process messages if connected
                if self.connected and not self.priority_queue.empty():
                    # Get the next message (highest priority first, then oldest)
                    priority, timestamp, message = self.priority_queue.get(block=False)
                    
                    # Check if we should retry this message
                    if message.attempts >= self.max_retry_attempts:
                        self.logger.warning(f"Discarding message {message.id} after {message.attempts} failed attempts")
                        continue
                    
                    # Send the message
                    success = self._send_message(message)
                    
                    # If sending failed, requeue with exponential backoff
                    if not success:
                        message.increment_attempt()
                        
                        # Calculate backoff delay
                        backoff_delay = min(retry_delay * (2 ** (message.attempts - 1)), max_retry_delay)
                        
                        # Add jitter to prevent thundering herd
                        jitter = 0.1 * backoff_delay * (2 * random.random() - 1)  # ±10% jitter
                        requeue_delay = backoff_delay + jitter
                        
                        self.logger.info(f"Requeuing message {message.id} after {message.attempts} attempts, next try in {requeue_delay:.1f}s")
                        
                        # Schedule requeue after delay
                        threading.Timer(requeue_delay, lambda: self._requeue_message(message, priority)).start()
                
                # Check for acknowledgment timeouts
                current_time = time.time()
                timed_out_messages = []
                
                for msg_id, info in self.sent_messages.items():
                    if current_time - info["sent_at"] > self.ack_timeout:
                        timed_out_messages.append(msg_id)
                        
                        # Requeue the message
                        message = info["message"]
                        message.increment_attempt()
                        
                        if message.attempts < self.max_retry_attempts:
                            self.logger.warning(f"Message {msg_id} timed out waiting for acknowledgment, requeuing (attempt {message.attempts})")
                            self._requeue_message(message, 0)  # Default priority
                        else:
                            self.logger.error(f"Message {msg_id} failed after {message.attempts} attempts, giving up")
                
                # Remove timed out messages from tracking
                for msg_id in timed_out_messages:
                    self.sent_messages.pop(msg_id, None)
                
                # Don't busy-wait
                time.sleep(0.05)
            except queue.Empty:
                # Queue is empty, wait a bit longer
                time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Error in message processing loop: {str(e)}")
                time.sleep(1)  # Wait a bit on error
    
    def _on_open(self, ws):
        """
        Called when the WebSocket connection is opened.
        
        Args:
            ws: WebSocket instance
        """
        self.connected = True
        self.connection_status = "connected"
        self.reconnect_attempts = 0  # Reset reconnect attempts on successful connection
        self.last_activity_time = time.time()
        
        self.logger.info("WebSocket connection established")
        
        # Notify handlers of connection
        self._notify_handlers("connection", {"status": "connected"})
        
        # Subscribe to topics
        if self.subscribed_topics:
            self._subscribe(self.subscribed_topics)
    
    def _on_message(self, ws, message):
        """
        Called when a message is received.
        
        Args:
            ws: WebSocket instance
            message: Received message
        """
        try:
            # Parse message
            data = json.loads(message)
            message_type = data.get("type")
            message_data = data.get("data", {})
            message_id = data.get("id")
            
            # Update activity time
            self.last_activity_time = time.time()
            
            # Check for duplicate message
            if message_id and message_id in self.received_message_ids:
                self.logger.debug(f"Ignoring duplicate message: {message_id}")
                return
            
            # Add to received messages
            if message_id:
                self.received_message_ids.add(message_id)
                
                # Limit size of received IDs set
                if len(self.received_message_ids) > 1000:
                    # Remove oldest IDs (approximate since we don't track order)
                    self.received_message_ids = set(list(self.received_message_ids)[-500:])
            
            # Handle acknowledgment
            if message_type == "ack" and "message_id" in message_data:
                ack_msg_id = message_data["message_id"]
                if ack_msg_id in self.sent_messages:
                    self.sent_messages.pop(ack_msg_id)
                    self.logger.debug(f"Received acknowledgment for message {ack_msg_id}")
            
            # Notify handlers
            self._notify_handlers(message_type, message_data)
            
        except json.JSONDecodeError:
            self.logger.error(f"Error parsing message: {message}")
        except Exception as e:
            self.logger.error(f"Error handling message: {str(e)}")
    
    def _on_error(self, ws, error):
        """
        Called when an error occurs.
        
        Args:
            ws: WebSocket instance
            error: Error information
        """
        self.logger.error(f"WebSocket error: {str(error)}")
        self._notify_handlers("error", {"error": str(error)})
    
    def _on_close(self, ws, close_status_code, close_msg):
        """
        Called when the connection is closed.
        
        Args:
            ws: WebSocket instance
            close_status_code: Status code
            close_msg: Close message
        """
        self.connected = False
        self.connection_status = "disconnected"
        self.logger.info(f"WebSocket connection closed: {close_msg} (code: {close_status_code})")
        self._notify_handlers("connection", {"status": "disconnected"})
    
    def _send_message(self, message: QueuedMessage) -> bool:
        """
        Send a message to the server.
        
        Args:
            message: Message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.connected or not self.ws:
            return False
            
        try:
            # Convert to JSON
            msg_dict = message.to_dict()
            json_message = json.dumps(msg_dict)
            
            # Track when it was sent
            self.last_activity_time = time.time()
            
            # Send the message
            self.ws.send(json_message)
            
            # Track sent message for acknowledgment
            self.sent_messages[message.id] = {
                "message": message,
                "sent_at": self.last_activity_time
            }
            
            return True
        except Exception as e:
            self.logger.error(f"Error sending message {message.id}: {str(e)}")
            return False
    
    def _subscribe(self, topics):
        """
        Subscribe to topics.
        
        Args:
            topics: List of topics to subscribe to
        """
        self.subscribed_topics.update(topics)
        
        self._send_message({
            "type": "subscribe",
            "data": {
                "client_id": self.client_id,
                "topics": list(self.subscribed_topics)
            }
        })
    
    def _request_history(self, history_type, count=10):
        """
        Request message history.
        
        Args:
            history_type: Type of history to request
            count: Number of messages to request
        """
        self._send_message({
            "type": "request_history",
            "data": {
                "history_type": history_type,
                "count": count
            }
        })
    
    def send_ping(self):
        """
        Send a ping message to keep the connection alive.
        """
        self._send_message({
            "type": "ping",
            "data": {
                "timestamp": time.time()
            }
        })
    
    def register_handler(self, message_type, handler):
        """
        Register a handler for a specific message type.
        
        Args:
            message_type: Type of message to handle
            handler: Handler function
        """
        if message_type not in self.event_handlers:
            self.event_handlers[message_type] = []
            
        self.event_handlers[message_type].append(handler)
    
    def register_global_handler(self, handler):
        """
        Register a handler for all message types.
        
        Args:
            handler: Handler function
        """
        self.global_handlers.append(handler)
    
    def _notify_handlers(self, message_type, data):
        """
        Notify handlers about a message.
        
        Args:
            message_type: Type of message
            data: Message data
        """
        # Call specific handlers
        handlers = self.event_handlers.get(message_type, [])
        for handler in handlers:
            try:
                handler(message_type, data)
            except Exception as e:
                self.logger.error(f"Error in handler for {message_type}: {str(e)}")
        
        # Call global handlers
        for handler in self.global_handlers:
            try:
                handler(message_type, data)
            except Exception as e:
                self.logger.error(f"Error in global handler for {message_type}: {str(e)}")
    
    def subscribe(self, topics):
        """
        Subscribe to topics.
        
        Args:
            topics: List of topics to subscribe to
        """
        if isinstance(topics, str):
            topics = [topics]
            
        self._subscribe(topics)
    
    def send_message(self, message_type, data=None, priority: int = 0) -> str:
        """
        Send a message to the server.
        
        Args:
            message_type: Type of message
            data: Message data
            priority: Message priority (higher values = higher priority)
            
        Returns:
            Message ID
        """
        # Queue the message
        return self._queue_message(message_type, data or {}, priority)
