"""
WebSocket authentication module for Dark Web Discovery System.
Provides secure token-based authentication for WebSocket connections.
"""

import os
import time
import uuid
import json
import hashlib
import logging
import datetime
from typing import Dict, Optional, Tuple, Any, List
import hmac
import base64

from config import Config

class WebSocketAuthManager:
    """
    Manages authentication for WebSocket connections.
    Provides token generation, validation, and access control.
    """
    
    def __init__(self, secret_key: Optional[str] = None, token_expiry: int = 3600):
        """
        Initialize the WebSocket authentication manager.
        
        Args:
            secret_key: Secret key for token signing (generated if not provided)
            token_expiry: Token expiry time in seconds (default: 1 hour)
        """
        self.logger = logging.getLogger("WebSocketAuthManager")
        
        # Use provided secret key or generate one
        if secret_key:
            self.secret_key = secret_key
        else:
            # Try to get from config or generate a new one
            self.secret_key = getattr(Config, 'WEBSOCKET_SECRET_KEY', None)
            if not self.secret_key:
                self.secret_key = self._generate_secret_key()
        
        self.token_expiry = token_expiry
        self.active_tokens = {}  # token -> (user_id, expiry, channels)
        self.channel_permissions = {}  # channel -> list of user_ids with access
    
    def _generate_secret_key(self) -> str:
        """
        Generate a secure secret key.
        
        Returns:
            Secure secret key string
        """
        # Generate a random key
        key = os.urandom(32)
        return base64.b64encode(key).decode('utf-8')
    
    def generate_token(self, user_id: str, channels: Optional[List[str]] = None) -> str:
        """
        Generate an authentication token for a user.
        
        Args:
            user_id: User identifier
            channels: List of channels the user has access to
        
        Returns:
            Authentication token
        """
        # Default channels if none provided
        if channels is None:
            channels = ["public"]
        
        # Create token payload
        now = int(time.time())
        expiry = now + self.token_expiry
        token_id = str(uuid.uuid4())
        
        payload = {
            "user_id": user_id,
            "token_id": token_id,
            "channels": channels,
            "iat": now,
            "exp": expiry
        }
        
        # Create signature
        payload_str = json.dumps(payload, sort_keys=True)
        signature = self._create_signature(payload_str)
        
        # Combine into token
        token_parts = [
            base64.b64encode(payload_str.encode('utf-8')).decode('utf-8'),
            signature
        ]
        token = ".".join(token_parts)
        
        # Store in active tokens
        self.active_tokens[token] = (user_id, expiry, channels)
        
        return token
    
    def _create_signature(self, payload: str) -> str:
        """
        Create a signature for the token payload.
        
        Args:
            payload: Token payload as string
        
        Returns:
            Signature string
        """
        # Create HMAC signature
        h = hmac.new(
            self.secret_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        )
        return base64.b64encode(h.digest()).decode('utf-8')
    
    def validate_token(self, token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate an authentication token.
        
        Args:
            token: Authentication token
        
        Returns:
            (is_valid, token_data) tuple
            token_data contains user_id, channels, etc. if valid
        """
        try:
            # Check if token is in active tokens
            if token in self.active_tokens:
                user_id, expiry, channels = self.active_tokens[token]
                
                # Check if expired
                now = int(time.time())
                if now > expiry:
                    # Remove expired token
                    del self.active_tokens[token]
                    return False, None
                
                # Token is valid
                return True, {
                    "user_id": user_id,
                    "channels": channels,
                    "exp": expiry
                }
            
            # If not in active tokens, validate manually
            token_parts = token.split(".")
            if len(token_parts) != 2:
                return False, None
            
            # Decode payload
            try:
                payload_str = base64.b64decode(token_parts[0]).decode('utf-8')
                payload = json.loads(payload_str)
            except (json.JSONDecodeError, UnicodeDecodeError, base64.binascii.Error):
                return False, None
            
            # Verify signature
            expected_signature = self._create_signature(payload_str)
            if token_parts[1] != expected_signature:
                return False, None
            
            # Check expiry
            now = int(time.time())
            if now > payload.get("exp", 0):
                return False, None
            
            # Valid token, add to active tokens
            user_id = payload.get("user_id")
            channels = payload.get("channels", ["public"])
            expiry = payload.get("exp")
            
            self.active_tokens[token] = (user_id, expiry, channels)
            
            return True, {
                "user_id": user_id,
                "channels": channels,
                "exp": expiry
            }
        
        except Exception as e:
            self.logger.error(f"Error validating token: {str(e)}")
            return False, None
    
    def revoke_token(self, token: str) -> bool:
        """
        Revoke an authentication token.
        
        Args:
            token: Authentication token
        
        Returns:
            True if token was revoked, False otherwise
        """
        if token in self.active_tokens:
            del self.active_tokens[token]
            return True
        return False
    
    def revoke_user_tokens(self, user_id: str) -> int:
        """
        Revoke all tokens for a user.
        
        Args:
            user_id: User identifier
        
        Returns:
            Number of tokens revoked
        """
        count = 0
        tokens_to_remove = []
        
        for token, (token_user_id, _, _) in self.active_tokens.items():
            if token_user_id == user_id:
                tokens_to_remove.append(token)
                count += 1
        
        for token in tokens_to_remove:
            del self.active_tokens[token]
        
        return count
    
    def set_channel_permissions(self, channel: str, allowed_users: List[str]) -> None:
        """
        Set permissions for a channel.
        
        Args:
            channel: Channel name
            allowed_users: List of user IDs allowed to access the channel
        """
        self.channel_permissions[channel] = allowed_users
    
    def can_access_channel(self, user_id: str, channel: str) -> bool:
        """
        Check if a user can access a channel.
        
        Args:
            user_id: User identifier
            channel: Channel name
        
        Returns:
            True if user can access the channel, False otherwise
        """
        # Public channel is always accessible
        if channel == "public":
            return True
        
        # Check if user is in allowed users for channel
        allowed_users = self.channel_permissions.get(channel, [])
        return user_id in allowed_users
    
    def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired tokens.
        
        Returns:
            Number of tokens removed
        """
        now = int(time.time())
        count = 0
        tokens_to_remove = []
        
        for token, (_, expiry, _) in self.active_tokens.items():
            if now > expiry:
                tokens_to_remove.append(token)
                count += 1
        
        for token in tokens_to_remove:
            del self.active_tokens[token]
        
        return count


# Singleton instance
_auth_manager = None

def get_auth_manager() -> WebSocketAuthManager:
    """Get the singleton WebSocket auth manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = WebSocketAuthManager()
    return _auth_manager
