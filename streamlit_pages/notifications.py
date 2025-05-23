"""
Notifications page for the Dark Web Discovery System.
Displays real-time notifications and allows interaction with them.
"""

import streamlit as st
import datetime
from app_adapter import StreamlitAdapter
from notification_system import render_notification_panel


def render_notifications_page():
    """Render the notifications page."""
    st.title("Notifications")
    
    # Get adapter
    if not hasattr(st.session_state, 'adapter'):
        st.error("Application not properly initialized")
        return
        
    adapter = st.session_state.adapter
    
    # Get notification system
    notification_system = adapter.get_notification_system()
    
    # Get WebSocket component
    websocket_component = adapter.get_websocket_component()
    websocket_component.render()
    
    # Initialize WebSocket handlers
    if not getattr(st.session_state, 'notification_handlers_initialized', False):
        # Handle notifications from WebSocket
        def handle_notification(data):
            notification_type = data.get("type")
            title = data.get("title")
            message = data.get("message")
            level = data.get("level", "info")
            notification_data = data.get("data", {})
            
            # Create notification
            notification_system.send_notification(
                notification_type, title, message, level, notification_data
            )
            
        # Register handlers
        websocket_component.register_message_handler("notification", handle_notification)
        
        # Mark as initialized
        st.session_state.notification_handlers_initialized = True
    
    # Display notification stats
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Notification Statistics")
        
        unread_count = notification_system.get_unread_count()
        all_notifications = notification_system.get_notifications(include_read=True)
        unread_notifications = notification_system.get_notifications(include_read=False)
        
        st.metric("Total Notifications", len(all_notifications))
        st.metric("Unread Notifications", unread_count)
        
        # Group by type
        notification_types = {}
        for notification in all_notifications:
            notification_type = notification.get("type", "unknown")
            notification_types[notification_type] = notification_types.get(notification_type, 0) + 1
        
        # Display type breakdown
        if notification_types:
            st.subheader("Notification Types")
            for notification_type, count in notification_types.items():
                st.text(f"{notification_type}: {count}")
    
    with col2:
        st.subheader("Test Notifications")
        
        # Form for creating test notifications
        with st.form("notification_form"):
            notification_title = st.text_input("Title", "Test Notification")
            notification_message = st.text_area("Message", "This is a test notification")
            
            col1, col2 = st.columns(2)
            with col1:
                notification_type = st.selectbox(
                    "Type", 
                    ["system", "crawl_progress", "discovery", "error"]
                )
            with col2:
                notification_level = st.selectbox(
                    "Level", 
                    ["info", "success", "warning", "error"]
                )
            
            submit = st.form_submit_button("Create Notification")
            
            if submit:
                # Create notification
                notification_id = notification_system.send_notification(
                    notification_type,
                    notification_title,
                    notification_message,
                    notification_level,
                    {"source": "test", "timestamp": datetime.datetime.now().isoformat()}
                )
                
                if notification_id:
                    st.success(f"Notification created: {notification_id}")
                    
                    # Also emit via WebSocket
                    adapter.emit_event("notification", {
                        "type": notification_type,
                        "title": notification_title,
                        "message": notification_message,
                        "level": notification_level,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "source": "test"
                    })
                    
                    # Rerun to show updated notifications
                    st.rerun()
    
    # Display notifications
    st.markdown("---")
    render_notification_panel(notification_system)


if __name__ == "__main__":
    # For testing
    import sys
    import os
    
    # Add parent directory to path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Initialize adapter
    adapter = StreamlitAdapter()
    if not adapter.initialize():
        st.error("Failed to initialize adapter")
    
    # Render page
    render_notifications_page()
