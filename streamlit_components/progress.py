"""
Progress tracking components for the Dark Web Discovery System.
Provides real-time progress indicators with ETA calculations and cancellation support.
"""

import streamlit as st
import time
import datetime
import uuid
import json
from typing import Dict, List, Any, Optional, Callable, Union
import threading
import math

from streamlit_components.card import render_card

class ProgressTracker:
    """
    Tracks progress for long-running operations with ETA calculation.
    """
    
    def __init__(self, 
                 operation_id: Optional[str] = None, 
                 operation_type: str = "generic",
                 total_steps: int = 100, 
                 description: str = "Operation in progress",
                 cancellable: bool = False,
                 on_cancel: Optional[Callable] = None):
        """
        Initialize a progress tracker.
        
        Args:
            operation_id: Unique ID for the operation (generated if None)
            operation_type: Type of operation (e.g., "crawl", "export")
            total_steps: Total number of steps to complete
            description: Operation description
            cancellable: Whether the operation can be cancelled
            on_cancel: Function to call when cancellation is requested
        """
        self.operation_id = operation_id or str(uuid.uuid4())
        self.operation_type = operation_type
        self.total_steps = max(1, total_steps)  # Ensure at least 1 step
        self.current_step = 0
        self.description = description
        self.status = "pending"  # pending, running, completed, error, cancelled
        self.start_time = None
        self.end_time = None
        self.last_update_time = None
        self.eta = None
        self.progress_history = []  # List of (timestamp, progress) tuples
        self.history_max_size = 10  # Number of recent updates to keep for ETA
        self.error_message = None
        self.details = {}
        self.cancellable = cancellable
        self.on_cancel = on_cancel
        self.cancellation_requested = False
    
    def start(self) -> None:
        """Start the operation."""
        if self.status == "pending":
            self.status = "running"
            self.start_time = time.time()
            self.last_update_time = self.start_time
            self.progress_history = [(self.start_time, 0)]
            
            # Add to session state if not already there
            if "progress_trackers" not in st.session_state:
                st.session_state.progress_trackers = {}
            
            st.session_state.progress_trackers[self.operation_id] = self
    
    def update(self, 
               current_step: Optional[int] = None, 
               increment: Optional[int] = None,
               status: Optional[str] = None,
               description: Optional[str] = None,
               details: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Update progress.
        
        Args:
            current_step: Current step (absolute)
            increment: Step increment (relative)
            status: New status
            description: New description
            details: Additional details
            
        Returns:
            Current progress state
        """
        # Update step
        if current_step is not None:
            self.current_step = min(max(0, current_step), self.total_steps)
        elif increment is not None:
            self.current_step = min(self.current_step + increment, self.total_steps)
        
        # Update status if provided
        if status is not None:
            self.status = status
            
            # Set end time if completed or error
            if status in ["completed", "error", "cancelled"]:
                self.end_time = time.time()
        
        # Update description if provided
        if description is not None:
            self.description = description
        
        # Update details if provided
        if details is not None:
            self.details.update(details)
        
        # Record timestamp
        current_time = time.time()
        self.last_update_time = current_time
        
        # Add to progress history for ETA calculation
        self.progress_history.append((current_time, self.current_step))
        
        # Keep only recent history for ETA calculation
        if len(self.progress_history) > self.history_max_size:
            self.progress_history = self.progress_history[-self.history_max_size:]
        
        # Calculate ETA
        self._calculate_eta()
        
        # Return current state
        return self.get_state()
    
    def _calculate_eta(self) -> None:
        """Calculate estimated time to completion."""
        if self.status not in ["running", "pending"] or self.current_step >= self.total_steps:
            self.eta = None
            return
        
        if len(self.progress_history) < 2:
            self.eta = None
            return
        
        try:
            # Get oldest and newest points in history
            oldest_time, oldest_step = self.progress_history[0]
            newest_time, newest_step = self.progress_history[-1]
            
            # Calculate time elapsed and progress made
            time_elapsed = newest_time - oldest_time
            progress_made = newest_step - oldest_step
            
            # Avoid division by zero
            if progress_made <= 0:
                self.eta = None
                return
            
            # Calculate rate and remaining time
            steps_per_second = progress_made / time_elapsed
            remaining_steps = self.total_steps - newest_step
            
            # Calculate ETA
            if steps_per_second > 0:
                seconds_remaining = remaining_steps / steps_per_second
                
                # Set ETA timestamp
                self.eta = time.time() + seconds_remaining
            else:
                self.eta = None
                
        except Exception:
            self.eta = None
    
    def error(self, message: str, details: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Set error status.
        
        Args:
            message: Error message
            details: Error details
            
        Returns:
            Current progress state
        """
        self.status = "error"
        self.error_message = message
        self.end_time = time.time()
        
        if details:
            self.details.update(details)
        
        return self.get_state()
    
    def complete(self, details: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Mark as completed.
        
        Args:
            details: Completion details
            
        Returns:
            Current progress state
        """
        self.status = "completed"
        self.current_step = self.total_steps
        self.end_time = time.time()
        
        if details:
            self.details.update(details)
        
        return self.get_state()
    
    def cancel(self) -> Dict[str, Any]:
        """
        Request cancellation.
        
        Returns:
            Current progress state
        """
        if not self.cancellable or self.status not in ["pending", "running"]:
            return self.get_state()
        
        self.cancellation_requested = True
        
        # Call cancellation handler if provided
        if self.on_cancel:
            try:
                self.on_cancel(self.operation_id)
            except Exception as e:
                self.error_message = f"Error during cancellation: {str(e)}"
        
        self.status = "cancelled"
        self.end_time = time.time()
        
        return self.get_state()
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get current progress state.
        
        Returns:
            Progress state dictionary
        """
        # Calculate progress percentage
        progress_pct = 0
        if self.total_steps > 0:
            progress_pct = min(100, max(0, (self.current_step / self.total_steps) * 100))
        
        # Format ETA
        eta_str = None
        seconds_remaining = None
        
        if self.eta is not None:
            # Calculate seconds remaining
            seconds_remaining = max(0, self.eta - time.time())
            
            # Format based on time remaining
            if seconds_remaining < 60:
                eta_str = f"{int(seconds_remaining)} seconds"
            elif seconds_remaining < 3600:
                eta_str = f"{int(seconds_remaining / 60)} minutes"
            else:
                eta_str = f"{(seconds_remaining / 3600):.1f} hours"
        
        # Calculate elapsed time
        elapsed_seconds = None
        if self.start_time:
            end = self.end_time or time.time()
            elapsed_seconds = end - self.start_time
        
        # Format elapsed time
        elapsed_str = None
        if elapsed_seconds is not None:
            if elapsed_seconds < 60:
                elapsed_str = f"{int(elapsed_seconds)} seconds"
            elif elapsed_seconds < 3600:
                elapsed_str = f"{int(elapsed_seconds / 60)} minutes"
            else:
                elapsed_str = f"{(elapsed_seconds / 3600):.1f} hours"
        
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "description": self.description,
            "status": self.status,
            "progress": {
                "current": self.current_step,
                "total": self.total_steps,
                "percentage": progress_pct
            },
            "time": {
                "start": self.start_time,
                "last_update": self.last_update_time,
                "end": self.end_time,
                "elapsed_seconds": elapsed_seconds,
                "elapsed": elapsed_str,
                "eta": self.eta,
                "eta_formatted": eta_str,
                "seconds_remaining": seconds_remaining
            },
            "error": self.error_message,
            "details": self.details,
            "cancellable": self.cancellable,
            "cancellation_requested": self.cancellation_requested
        }


def render_progress_bar(
    tracker: Union[ProgressTracker, Dict], 
    key: Optional[str] = None,
    show_cancel: bool = True,
    on_cancel: Optional[Callable] = None,
    show_details: bool = True
) -> None:
    """
    Render a progress bar for a tracked operation.
    
    Args:
        tracker: Progress tracker or state dictionary
        key: Unique key for the component
        show_cancel: Whether to show cancel button
        on_cancel: Function to call when cancel is clicked
        show_details: Whether to show operation details
    """
    # Convert tracker to state if needed
    if isinstance(tracker, ProgressTracker):
        state = tracker.get_state()
    else:
        state = tracker
    
    # Generate key if not provided
    if key is None:
        key = f"progress_{state['operation_id']}_{int(time.time())}"
    
    # Get progress info
    progress_pct = state["progress"]["percentage"] / 100
    status = state["status"]
    description = state["description"]
    
    # Determine color based on status
    color_map = {
        "pending": "gray",
        "running": "blue",
        "completed": "green",
        "error": "red",
        "cancelled": "orange"
    }
    color = color_map.get(status, "blue")
    
    # Create container
    st.markdown(f"### {description}")
    
    # Show progress bar
    progress_bar = st.progress(progress_pct, text=f"{state['progress']['percentage']:.1f}%")
    
    # Show status and timing information
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Status:** {status.capitalize()}")
        if state["time"]["elapsed"]:
            st.markdown(f"**Elapsed time:** {state['time']['elapsed']}")
    
    with col2:
        if status == "running" and state["time"]["eta_formatted"]:
            st.markdown(f"**Estimated time remaining:** {state['time']['eta_formatted']}")
        
        steps_text = f"{state['progress']['current']} / {state['progress']['total']} steps"
        st.markdown(f"**Progress:** {steps_text}")
    
    # Show cancel button if operation is running and cancellable
    if show_cancel and state["cancellable"] and status in ["pending", "running"]:
        if st.button("Cancel Operation", key=f"{key}_cancel"):
            if isinstance(tracker, ProgressTracker):
                tracker.cancel()
            elif on_cancel:
                on_cancel(state["operation_id"])
    
    # Show error message if present
    if state["error"]:
        st.error(f"Error: {state['error']}")
    
    # Show details if requested
    if show_details and state["details"]:
        with st.expander("Details", expanded=False):
            # Format details for display
            for key, value in state["details"].items():
                st.markdown(f"**{key.replace('_', ' ').title()}:** {value}")


class ProgressManager:
    """
    Manages multiple progress trackers.
    Provides coordination and rendering for concurrent operations.
    """
    
    def __init__(self):
        """Initialize the progress manager."""
        # Ensure trackers are in session state
        if "progress_trackers" not in st.session_state:
            st.session_state.progress_trackers = {}
        
        # Initialize WebSocket handlers if needed
        if "websocket" in st.session_state and st.session_state.websocket:
            self._setup_websocket_handlers()
    
    def _setup_websocket_handlers(self):
        """Set up WebSocket handlers for progress updates."""
        websocket = st.session_state.websocket
        
        # Register handler for progress updates
        websocket.register_message_handler("progress_update", self._handle_progress_update)
        
        # Register handler for operation completion
        websocket.register_message_handler("operation_complete", self._handle_operation_complete)
        
        # Register handler for operation errors
        websocket.register_message_handler("operation_error", self._handle_operation_error)
    
    def _handle_progress_update(self, data):
        """Handle progress update from WebSocket."""
        operation_id = data.get("operation_id")
        if not operation_id:
            return
        
        # Get or create tracker
        tracker = self.get_tracker(operation_id)
        if not tracker:
            # Create new tracker from data
            tracker = ProgressTracker(
                operation_id=operation_id,
                operation_type=data.get("operation_type", "generic"),
                total_steps=data.get("total_steps", 100),
                description=data.get("description", "Operation in progress"),
                cancellable=data.get("cancellable", False)
            )
            self.add_tracker(tracker)
            tracker.start()
        
        # Update tracker
        tracker.update(
            current_step=data.get("current_step"),
            status=data.get("status"),
            description=data.get("description"),
            details=data.get("details")
        )
    
    def _handle_operation_complete(self, data):
        """Handle operation completion from WebSocket."""
        operation_id = data.get("operation_id")
        if not operation_id:
            return
        
        # Get tracker
        tracker = self.get_tracker(operation_id)
        if tracker:
            tracker.complete(details=data.get("details"))
    
    def _handle_operation_error(self, data):
        """Handle operation error from WebSocket."""
        operation_id = data.get("operation_id")
        if not operation_id:
            return
        
        # Get tracker
        tracker = self.get_tracker(operation_id)
        if tracker:
            tracker.error(
                message=data.get("error_message", "Unknown error"),
                details=data.get("details")
            )
    
    def add_tracker(self, tracker: ProgressTracker) -> None:
        """
        Add a progress tracker.
        
        Args:
            tracker: Progress tracker to add
        """
        st.session_state.progress_trackers[tracker.operation_id] = tracker
    
    def get_tracker(self, operation_id: str) -> Optional[ProgressTracker]:
        """
        Get a progress tracker by ID.
        
        Args:
            operation_id: Operation ID
            
        Returns:
            Progress tracker or None if not found
        """
        return st.session_state.progress_trackers.get(operation_id)
    
    def remove_tracker(self, operation_id: str) -> None:
        """
        Remove a progress tracker.
        
        Args:
            operation_id: Operation ID
        """
        if operation_id in st.session_state.progress_trackers:
            del st.session_state.progress_trackers[operation_id]
    
    def get_active_trackers(self) -> List[ProgressTracker]:
        """
        Get all active (pending or running) trackers.
        
        Returns:
            List of active trackers
        """
        return [
            tracker for tracker in st.session_state.progress_trackers.values()
            if tracker.status in ["pending", "running"]
        ]
    
    def get_recent_trackers(self, max_count: int = 5) -> List[ProgressTracker]:
        """
        Get recently updated trackers.
        
        Args:
            max_count: Maximum number of trackers to return
            
        Returns:
            List of recent trackers
        """
        # Sort by last update time
        trackers = list(st.session_state.progress_trackers.values())
        trackers.sort(key=lambda t: t.last_update_time or 0, reverse=True)
        
        return trackers[:max_count]
    
    def cancel_operation(self, operation_id: str) -> None:
        """
        Cancel an operation.
        
        Args:
            operation_id: Operation ID
        """
        tracker = self.get_tracker(operation_id)
        if tracker and tracker.cancellable:
            tracker.cancel()
            
            # If WebSocket is available, send cancellation request
            if "websocket" in st.session_state and st.session_state.websocket:
                st.session_state.websocket.send_message("cancel_operation", {
                    "operation_id": operation_id
                })
    
    def render_active_operations(self) -> None:
        """Render all active operations."""
        active_trackers = self.get_active_trackers()
        
        if not active_trackers:
            st.info("No active operations")
            return
        
        st.markdown(f"## Active Operations ({len(active_trackers)})")
        
        for tracker in active_trackers:
            with st.container():
                render_progress_bar(tracker)
                st.markdown("---")
    
    def render_recent_operations(self, max_count: int = 5) -> None:
        """
        Render recent operations.
        
        Args:
            max_count: Maximum number of operations to show
        """
        recent_trackers = self.get_recent_trackers(max_count)
        
        if not recent_trackers:
            st.info("No recent operations")
            return
        
        st.markdown(f"## Recent Operations ({len(recent_trackers)})")
        
        for tracker in recent_trackers:
            # Skip active operations if they're shown separately
            if tracker.status in ["pending", "running"]:
                continue
                
            with st.container():
                render_progress_bar(tracker)
                st.markdown("---")
    
    def render_operation_summary(self) -> None:
        """Render a summary of all operations."""
        trackers = st.session_state.progress_trackers.values()
        
        # Count by status
        counts = {
            "running": 0,
            "pending": 0,
            "completed": 0,
            "error": 0,
            "cancelled": 0
        }
        
        for tracker in trackers:
            counts[tracker.status] = counts.get(tracker.status, 0) + 1
        
        # Render summary
        st.markdown("## Operations Summary")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Active", counts["running"] + counts["pending"])
        
        with col2:
            st.metric("Completed", counts["completed"])
        
        with col3:
            st.metric("Failed", counts["error"] + counts["cancelled"])
    
    def create_tracker(self, 
                      operation_type: str = "generic",
                      total_steps: int = 100, 
                      description: str = "Operation in progress",
                      cancellable: bool = False,
                      on_cancel: Optional[Callable] = None) -> ProgressTracker:
        """
        Create a new progress tracker.
        
        Args:
            operation_type: Type of operation
            total_steps: Total number of steps
            description: Operation description
            cancellable: Whether the operation can be cancelled
            on_cancel: Function to call when cancellation is requested
            
        Returns:
            New progress tracker
        """
        tracker = ProgressTracker(
            operation_type=operation_type,
            total_steps=total_steps,
            description=description,
            cancellable=cancellable,
            on_cancel=on_cancel
        )
        
        self.add_tracker(tracker)
        return tracker


# Singleton instance
_instance = None

def get_progress_manager() -> ProgressManager:
    """Get the singleton progress manager instance."""
    global _instance
    if _instance is None:
        _instance = ProgressManager()
    return _instance
