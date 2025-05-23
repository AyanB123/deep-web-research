"""
Notification system for the Dark Web Discovery System.
Provides real-time notifications for events using WebSockets.
"""

import logging
import datetime
import uuid
from typing import Dict, List, Any, Optional, Callable
import streamlit as st

from app_adapter import StreamlitAdapter

class NotificationSystem:
    """
    Notification system for real-time updates and alerts.
    Uses WebSocket for delivery and maintains a history of notifications.
    """
    
    def __init__(self, adapter: Optional[StreamlitAdapter] = None):
        """
        Initialize the notification system.
        
        Args:
            adapter: StreamlitAdapter instance for component access
        """
        self.adapter = adapter
        self.logger = logging.getLogger("NotificationSystem")
        self.notification_handlers = {}
        
        # Initialize notification store in state
        if self.adapter:
            if not self.adapter.state.get("notifications"):
                self.adapter.update_state("notifications", {
                    "unread_count": 0,
                    "notifications": [],
                    "max_notifications": 50
                })
    
    def register_notification_handler(self, notification_type: str, handler: Callable):
        """
        Register a handler for a specific notification type.
        
        Args:
            notification_type: Type of notification to handle
            handler: Handler function that takes notification data
        """
        if notification_type not in self.notification_handlers:
            self.notification_handlers[notification_type] = []
        
        self.notification_handlers[notification_type].append(handler)
    
    def send_notification(self, 
                         notification_type: str, 
                         title: str, 
                         message: str, 
                         level: str = "info", 
                         data: Optional[Dict] = None):
        """
        Send a notification to the user.
        
        Args:
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            level: Notification level (info, warning, error, success)
            data: Additional notification data
        
        Returns:
            Notification ID
        """
        # Create notification
        notification_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().isoformat()
        
        notification = {
            "id": notification_id,
            "type": notification_type,
            "title": title,
            "message": message,
            "level": level,
            "timestamp": timestamp,
            "read": False,
            "data": data or {}
        }
        
        # Add to state if adapter available
        if self.adapter:
            notifications_state = self.adapter.state.get("notifications", {})
            notifications_list = notifications_state.get("notifications", [])
            
            # Add to beginning of list
            notifications_list.insert(0, notification)
            
            # Limit size
            max_notifications = notifications_state.get("max_notifications", 50)
            if len(notifications_list) > max_notifications:
                notifications_list = notifications_list[:max_notifications]
            
            # Update unread count
            unread_count = notifications_state.get("unread_count", 0) + 1
            
            # Update state
            self.adapter.update_state("notifications", {
                "unread_count": unread_count,
                "notifications": notifications_list,
                "max_notifications": max_notifications
            })
        
        # Send via WebSocket if available
        if self.adapter:
            websocket_manager = self.adapter.get_websocket_manager()
            if websocket_manager:
                websocket_manager.emit_event("notification", notification)
        
        # Trigger handlers
        handlers = self.notification_handlers.get(notification_type, [])
        for handler in handlers:
            try:
                handler(notification)
            except Exception as e:
                self.logger.error(f"Error in notification handler: {str(e)}")
        
        return notification_id
    
    def mark_as_read(self, notification_id: str):
        """
        Mark a notification as read.
        
        Args:
            notification_id: Notification ID
        
        Returns:
            True if marked as read, False otherwise
        """
        if not self.adapter:
            return False
        
        notifications_state = self.adapter.state.get("notifications", {})
        notifications_list = notifications_state.get("notifications", [])
        
        # Find notification
        for notification in notifications_list:
            if notification.get("id") == notification_id and not notification.get("read"):
                notification["read"] = True
                
                # Update unread count
                unread_count = notifications_state.get("unread_count", 0)
                if unread_count > 0:
                    unread_count -= 1
                
                # Update state
                self.adapter.update_state("notifications", {
                    "unread_count": unread_count,
                    "notifications": notifications_list,
                    "max_notifications": notifications_state.get("max_notifications", 50)
                })
                
                return True
        
        return False
    
    def mark_all_as_read(self):
        """
        Mark all notifications as read.
        
        Returns:
            Number of notifications marked as read
        """
        if not self.adapter:
            return 0
        
        notifications_state = self.adapter.state.get("notifications", {})
        notifications_list = notifications_state.get("notifications", [])
        
        # Count unread
        unread_count = 0
        for notification in notifications_list:
            if not notification.get("read"):
                notification["read"] = True
                unread_count += 1
        
        # Update state if any were marked as read
        if unread_count > 0:
            self.adapter.update_state("notifications", {
                "unread_count": 0,
                "notifications": notifications_list,
                "max_notifications": notifications_state.get("max_notifications", 50)
            })
        
        return unread_count
    
    def clear_notifications(self):
        """
        Clear all notifications.
        
        Returns:
            Number of notifications cleared
        """
        if not self.adapter:
            return 0
        
        notifications_state = self.adapter.state.get("notifications", {})
        notifications_list = notifications_state.get("notifications", [])
        
        count = len(notifications_list)
        
        # Clear notifications
        if count > 0:
            self.adapter.update_state("notifications", {
                "unread_count": 0,
                "notifications": [],
                "max_notifications": notifications_state.get("max_notifications", 50)
            })
        
        return count
    
    def get_unread_count(self):
        """
        Get the number of unread notifications.
        
        Returns:
            Unread count
        """
        if not self.adapter:
            return 0
        
        notifications_state = self.adapter.state.get("notifications", {})
        return notifications_state.get("unread_count", 0)
    
    def get_notifications(self, limit: int = 10, include_read: bool = True):
        """
        Get recent notifications.
        
        Args:
            limit: Maximum number of notifications to return
            include_read: Whether to include read notifications
        
        Returns:
            List of notifications
        """
        if not self.adapter:
            return []
        
        notifications_state = self.adapter.state.get("notifications", {})
        notifications_list = notifications_state.get("notifications", [])
        
        # Filter read if needed
        if not include_read:
            notifications_list = [n for n in notifications_list if not n.get("read")]
        
        # Limit results
        return notifications_list[:limit]


def create_notification_system(adapter: Optional[StreamlitAdapter] = None):
    """
    Create a notification system instance.
    
    Args:
        adapter: StreamlitAdapter instance
    
    Returns:
        NotificationSystem instance
    """
    if not adapter and hasattr(st.session_state, 'adapter'):
        adapter = st.session_state.adapter
    
    return NotificationSystem(adapter)


def render_notification_badge(notification_system: NotificationSystem):
    """
    Render a notification badge.
    
    Args:
        notification_system: NotificationSystem instance
    """
    unread_count = notification_system.get_unread_count()
    
    if unread_count > 0:
        st.markdown(
            f"""
            <div style="position: relative; display: inline-block;">
                <span style="position: absolute; top: -10px; right: -10px; 
                    background-color: red; color: white; border-radius: 50%; 
                    width: 20px; height: 20px; display: flex; align-items: center; 
                    justify-content: center; font-size: 12px;">
                    {unread_count}
                </span>
                <span style="font-size: 24px;">🔔</span>
            </div>
            """, 
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <div style="position: relative; display: inline-block;">
                <span style="font-size: 24px;">🔔</span>
            </div>
            """, 
            unsafe_allow_html=True
        )


def render_notification_panel(notification_system: NotificationSystem):
    """
    Render a notification panel.
    
    Args:
        notification_system: NotificationSystem instance
    """
    notifications = notification_system.get_notifications(limit=10)
    
    st.subheader("Notifications")
    
    if not notifications:
        st.info("No notifications")
        return
    
    # Actions
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Mark All as Read"):
            count = notification_system.mark_all_as_read()
            if count > 0:
                st.success(f"Marked {count} notifications as read")
                st.rerun()
    
    with col2:
        if st.button("Clear All"):
            count = notification_system.clear_notifications()
            if count > 0:
                st.success(f"Cleared {count} notifications")
                st.rerun()
    
    # Display notifications
    for notification in notifications:
        # Determine color based on level
        level = notification.get("level", "info")
        color = {
            "info": "blue",
            "success": "green",
            "warning": "orange",
            "error": "red"
        }.get(level, "gray")
        
        # Format timestamp
        timestamp = notification.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.datetime.fromisoformat(timestamp)
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                pass
        
        # Mark as read when expanded
        notification_id = notification.get("id", "")
        is_read = notification.get("read", False)
        
        with st.expander(
            f"{notification.get('title')} - {timestamp}" + 
            (" 🆕" if not is_read else "")
        ):
            st.markdown(f"<p style='color: {color};'>{notification.get('message', '')}</p>", 
                      unsafe_allow_html=True)
            
            # Show details if available
            data = notification.get("data", {})
            if data and isinstance(data, dict):
                with st.expander("Details"):
                    for key, value in data.items():
                        st.text(f"{key}: {value}")
            
            # Mark as read if needed
            if not is_read and notification_id:
                notification_system.mark_as_read(notification_id)
