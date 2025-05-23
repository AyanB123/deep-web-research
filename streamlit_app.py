"""
Enhanced Streamlit application for the Dark Web Discovery System.
Provides an interactive UI with real-time updates and advanced visualizations.
Implements a modular design with separate pages for different functionality.
"""

import os
import time
import json
import uuid
import logging
import datetime
import threading
from typing import Dict, List, Any, Optional, Tuple

import streamlit as st
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components
from streamlit_javascript import st_javascript

# Import system components
from config import Config

# Import adapter for dependency injection
from app_adapter import StreamlitAdapter

# Import page modules
from streamlit_pages.dashboard import render_dashboard
from streamlit_pages.search import render_search
from streamlit_pages.visualize import render_visualize
from streamlit_pages.explore import render_explore
from streamlit_pages.settings import render_settings
from streamlit_pages.component_demo import render_component_demo
from streamlit_pages.notifications import render_notifications_page

# Import UI component library
from streamlit_components.theme import apply_theme

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(Config.DATA_DIR, "app.log")),
        logging.StreamHandler()
    ]
)

# Page configuration
st.set_page_config(
    page_title="Dark Web Discovery System",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for enhanced UI
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .status-box {
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .status-active {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .status-error {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
    .status-pending {
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
    }
    .card {
        padding: 20px;
        border-radius: 5px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        margin-bottom: 20px;
        background-color: white;
    }
    .metric-card {
        text-align: center;
        padding: 15px;
        border-radius: 5px;
        background-color: #f8f9fa;
        border: 1px solid #eaecef;
        margin: 5px;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        margin: 10px 0;
    }
    .metric-label {
        font-size: 14px;
        color: #666;
    }
    .progress-container {
        margin-top: 10px;
        margin-bottom: 20px;
    }
    .tabs-container {
        margin-top: 20px;
    }
    .section-title {
        font-size: 1.5rem;
        margin-bottom: 1rem;
        color: #1E3A8A;
    }
    .custom-tab {
        background-color: #f1f3f9;
        padding: 15px;
        border-radius: 5px;
    }
    .filter-section {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 15px;
    }
    .notification {
        position: fixed;
        top: 10px;
        right: 10px;
        padding: 10px 20px;
        border-radius: 5px;
        background-color: #4CAF50;
        color: white;
        z-index: 1000;
        animation: fadeIn 0.5s, fadeOut 0.5s 2.5s;
        animation-fill-mode: forwards;
    }
    @keyframes fadeIn {
        from {opacity: 0;}
        to {opacity: 1;}
    }
    @keyframes fadeOut {
        from {opacity: 1;}
        to {opacity: 0;}
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state for app
def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if 'initialized' not in st.session_state:
        st.session_state.initialized = False
        
    if not st.session_state.initialized:
        # Flag for adapter initialization
        st.session_state.adapter_initialized = False
        
        # Create adapter instance (will be fully initialized later)
        st.session_state.adapter = StreamlitAdapter()
        
        # Basic UI state (minimal initialization here - adapter will handle the rest)
        st.session_state.current_page = 'Dashboard'
        st.session_state.auto_refresh = True
        st.session_state.refresh_interval = 5  # seconds
        
        # Mark as initialized
        st.session_state.initialized = True
        st.session_state.db_manager = None
        
        # Crawler and components
        st.session_state.crawler = None
        st.session_state.connection_manager = None
        st.session_state.content_safety = None
        
        # WebSocket for real-time updates
        st.session_state.websocket_manager = None
        st.session_state.ws_connected = False
        
        # Visualization and export
        st.session_state.network_visualizer = None
        st.session_state.export_manager = None
        
        # Analytics
        st.session_state.content_analyzer = None
        st.session_state.trend_analyzer = None
        
        # UI state
        st.session_state.current_page = "dashboard"
        st.session_state.notifications = []
        st.session_state.search_results = []
        st.session_state.filters = {
            "category": None,
            "status": None,
            "search_query": "",
            "max_days_old": None,
            "include_blacklisted": False
        }
        
        # Crawler operations
        st.session_state.crawler_operations = {
            "active_crawls": {},
            "discovery_stats": {
                "total_discovered": 0,
                "today_discovered": 0,
                "categories": {}
            },
            "last_errors": []
        }
        
        # Auto-refresh

# Initialize system components
def initialize_system():
    """Initialize system components and connect to services."""
    # Initialize adapter (provides access to components and state)
    adapter = st.session_state.adapter
    adapter.initialize()
    
    # Apply theme from UI component library
    apply_theme(dark_mode=False)

# Set up auto-refresh for real-time updates
def setup_auto_refresh():
    """Set up auto-refresh for real-time updates."""
    adapter = st.session_state.adapter
    auto_refresh = adapter.state.get("auto_refresh", True)
    refresh_interval = adapter.state.get("refresh_interval", 5)
    
    if auto_refresh:
        st_autorefresh(interval=refresh_interval * 1000, key="data_refresh")

# Main navigation sidebar
def navigation():
    """Main navigation sidebar."""
    # Get adapter from session state
    adapter = st.session_state.adapter
    
    # Sync state from Streamlit
    adapter.sync_from_streamlit()
    
    st.sidebar.title("Dark Web Discovery System")
    
    # Main navigation
    page_names = [
        "Dashboard",
        "Search",
        "Visualize",
        "Explore",
        "Notifications",
        "Component Demo",
        "Settings"
    ]
    
    # Display navigation options
    selected_page = st.sidebar.radio("Navigation", page_names)
    adapter.update_state("current_page", selected_page)
    
    # Render the selected page
    if selected_page == "Dashboard":
        render_dashboard()
    elif selected_page == "Search":
        render_search()
    elif selected_page == "Visualize":
        render_visualize()
    elif selected_page == "Explore":
        render_explore()
    elif selected_page == "Settings":
        render_settings()
    elif selected_page == "Component Demo":
        render_component_demo()
    elif selected_page == "Notifications":
        render_notifications_page()
    else:
        st.error(f"Unknown page: {selected_page}")
    
    # System status indicator
    db_initialized = adapter.state.get("db_initialized", False)
    system_status = "Active" if db_initialized else "Initializing"
    status_class = "status-active" if db_initialized else "status-pending"
    
    st.sidebar.markdown(f"""
    <div class="status-box {status_class}">
        <strong>System Status:</strong> {system_status}
    </div>
    """, unsafe_allow_html=True)
    
    # Display active crawls
    active_crawls = adapter.state.get("crawler_operations.active_crawls", {})
    if active_crawls:
        st.sidebar.markdown("### Active Crawls")
        for crawler_id, crawl in active_crawls.items():
            st.sidebar.progress(crawl["progress"] / 100)
            # Truncate URL if needed
            url_display = crawl['url']
            if len(url_display) > 30:
                url_display = url_display[:27] + "..."
            st.sidebar.markdown(f"**{url_display}** ({crawl['status']})")
    
    # Quick actions
    st.sidebar.markdown("### Quick Actions")
    
    # Quick search
    with st.sidebar.form("quick_search_form", clear_on_submit=True):
        search_query = st.text_input("Quick Search", placeholder="Enter search terms...")
        search_submitted = st.form_submit_button("Search")
        
        if search_submitted and search_query:
            adapter.update_state("current_page", "Discover")
            adapter.update_state("last_search_query", search_query)
            st.experimental_rerun()
    
    # Quick crawl
    if adapter.state.get("db_initialized", False):
        if st.sidebar.button("Crawl Pending Links"):
            crawler = adapter.get_crawler()
            websocket_manager = adapter.get_websocket_manager()
            
            if crawler:
                # Start a background thread for crawling
                def run_crawl():
                    crawler_id = f"quick_crawl_{uuid.uuid4().hex[:8]}"
                    if websocket_manager:
                        websocket_manager.emit_crawl_progress(
                            crawler_id=crawler_id,
                            url="Batch Crawl",
                            status="starting",
                            progress=0
                        )
                    
                    try:
                        # Run batch crawl
                        crawler.batch_crawl(batch_size=10)
                        
                        # Update WebSocket with completion
                        if websocket_manager:
                            websocket_manager.emit_crawl_progress(
                                crawler_id=crawler_id,
                                url="Batch Crawl",
                                status="completed",
                                progress=100
                            )
                    except Exception as e:
                        # Update WebSocket with error
                        if websocket_manager:
                            websocket_manager.emit_crawl_progress(
                                crawler_id=crawler_id,
                                url="Batch Crawl",
                                status="error",
                                progress=0,
                                details={"error": str(e)}
                            )
                
                # Start crawl thread
                crawl_thread = threading.Thread(target=run_crawl)
                crawl_thread.daemon = True
                crawl_thread.start()
                
                # Add notification
                adapter.add_notification("Batch crawl started", "info")
    
    # Database stats
    if adapter.state.get("db_initialized", False):
        try:
            link_db = adapter.get_link_db()
            if link_db:
                stats = link_db.get_database_stats()
                st.sidebar.markdown("### Database Stats")
                st.sidebar.markdown(f"Total links: **{stats['total_links']:,}**")
                st.sidebar.markdown(f"Active links: **{stats['active_links']:,}**")
                
                # Add category breakdown
                category_counts = stats.get('category_counts', {})
                if category_counts:
                    st.sidebar.markdown("#### Categories")
                    for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                        if category:
                            st.sidebar.markdown(f"{category.title()}: **{count:,}**")
        except Exception as e:
            st.sidebar.warning(f"Error loading stats: {str(e)}")
    
    # System info at bottom
    st.sidebar.markdown("---")
    
    # Add auto-refresh toggle
    st.sidebar.markdown("### Display Settings")
    auto_refresh = adapter.state.get("auto_refresh", True)
    refresh_interval = adapter.state.get("refresh_interval", 5)
    
    auto_refresh = st.sidebar.checkbox(
        "Auto-refresh", 
        value=auto_refresh,
        help="Automatically refresh data every few seconds"
    )
    adapter.update_state("auto_refresh", auto_refresh)
    
    if auto_refresh:
        refresh_interval = st.sidebar.slider(
            "Refresh interval (seconds)",
            min_value=1,
            max_value=60,
            value=refresh_interval
        )
        adapter.update_state("refresh_interval", refresh_interval)
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"Version: {adapter.state.get('version', '1.0.0')}")
    st.sidebar.markdown("© 2025 Dark Web Discovery System")
    
    return st.session_state.current_page
