"""
Advanced Search page for the Dark Web Discovery System.
Provides a powerful search interface with visual query building.
"""

import streamlit as st
import sqlite3
import datetime
import json
from typing import Dict, List, Any, Optional

from query_builder import QueryBuilder, FilterGroup, FilterCondition, FilterOperator, LogicalOperator
from search_service import SearchService, SearchTemplateRegistry
from streamlit_components.query_builder_ui import (
    QueryBuilderUI, 
    render_query_preview, 
    render_search_results,
    render_saved_searches,
    render_search_templates
)
from streamlit_components.layout import create_layout_columns
from streamlit_components.card import render_card
from streamlit_websocket_component import StreamlitWebSocketComponent
from websocket_auth import WebSocketAuthManager

# Initialize page
st.set_page_config(
    page_title="Advanced Search - Dark Web Discovery",
    page_icon="🔍",
    layout="wide"
)

# Initialize session state for search
if "search_results" not in st.session_state:
    st.session_state.search_results = None

if "websocket" not in st.session_state:
    st.session_state.websocket = None

if "db_connection" not in st.session_state:
    # Create database connection
    # In a real app, this would be handled by a connection pool or service
    st.session_state.db_connection = sqlite3.connect("onion_links.db", check_same_thread=False)

# Get or initialize services
def get_search_service():
    """Get or initialize search service"""
    if "search_service" not in st.session_state:
        st.session_state.search_service = SearchService(st.session_state.db_connection)
    return st.session_state.search_service

def get_template_registry():
    """Get or initialize template registry"""
    if "template_registry" not in st.session_state:
        st.session_state.template_registry = SearchTemplateRegistry()
    return st.session_state.template_registry

def get_websocket_auth():
    """Get or initialize WebSocket auth manager"""
    if "websocket_auth" not in st.session_state:
        st.session_state.websocket_auth = WebSocketAuthManager()
    return st.session_state.websocket_auth

# Initialize WebSocket for real-time updates if not already initialized
def initialize_websocket():
    """Initialize WebSocket connection for real-time updates"""
    if st.session_state.websocket is None:
        # Generate a user ID for this session
        if "user_id" not in st.session_state:
            st.session_state.user_id = f"user_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Get auth manager and generate token
        auth_manager = get_websocket_auth()
        token = auth_manager.generate_token(
            user_id=st.session_state.user_id,
            channels=["search_updates", "notifications"]
        )
        
        # Initialize WebSocket component
        st.session_state.websocket = StreamlitWebSocketComponent(
            websocket_url="ws://localhost:8765",
            user_id=st.session_state.user_id,
            channels=["search_updates", "notifications"],
            auth_token=token,
            on_message=handle_websocket_message
        )

def handle_websocket_message(message: Dict[str, Any]) -> None:
    """Handle incoming WebSocket messages"""
    message_type = message.get("type")
    
    if message_type == "search_update":
        # Update search results if this is a search update
        st.session_state.search_results = message.get("data")
        st.rerun()
    
    elif message_type == "notification":
        # Handle notification
        st.toast(message.get("message", "New notification"), icon="🔔")

# Main search function
def perform_search(query_builder: QueryBuilder) -> None:
    """
    Perform a search using the query builder.
    
    Args:
        query_builder: Query builder object
    """
    search_service = get_search_service()
    results = search_service.search(query_builder)
    
    # Store results in session state
    st.session_state.search_results = results
    
    # Notify via WebSocket that search is complete
    if st.session_state.websocket:
        st.session_state.websocket.send({
            "type": "search_complete",
            "query": query_builder.build(),
            "timestamp": datetime.datetime.now().isoformat()
        })

def save_current_search(name: str, description: str, query_builder: QueryBuilder) -> bool:
    """
    Save the current search.
    
    Args:
        name: Search name
        description: Search description
        query_builder: Query builder object
        
    Returns:
        True if saved successfully
    """
    search_service = get_search_service()
    return search_service.save_search(name, query_builder, description)

def load_saved_search(name: str) -> None:
    """
    Load a saved search.
    
    Args:
        name: Search name
    """
    search_service = get_search_service()
    query_builder = search_service.get_saved_search(name)
    
    if query_builder:
        # Store in session state for the UI to use
        st.session_state.loaded_query = query_builder
        st.rerun()

def use_search_template(template_name: str, parameters: Dict[str, Any]) -> None:
    """
    Use a search template.
    
    Args:
        template_name: Template name
        parameters: Template parameters
    """
    template_registry = get_template_registry()
    template = template_registry.get_template(template_name)
    
    if template:
        query_builder = template.build_query(parameters)
        
        # Store in session state for the UI to use
        st.session_state.loaded_query = query_builder
        st.rerun()

# Initialize WebSocket
initialize_websocket()

# Main UI
st.title("🔍 Advanced Search")
st.markdown("""
    Build complex search queries to find specific onion links in the database.
    Use the visual query builder to create conditions, or choose from saved searches and templates.
""")

# Create tabs for different search methods
tab1, tab2, tab3 = st.tabs(["Query Builder", "Saved Searches", "Templates"])

with tab1:
    # Initialize query builder UI
    query_builder_ui = QueryBuilderUI(key_prefix="main_query_builder")
    
    # Check if we have a loaded query to display
    if "loaded_query" in st.session_state:
        # TODO: Transfer the loaded query to the UI
        # This would require adding a method to set the UI state from a query
        # For now, just show a message
        st.success("Loaded query from saved search or template")
        st.session_state.pop("loaded_query")
    
    # Render the query builder UI
    query_builder_ui.render()
    
    # Build the query and show preview
    query = query_builder_ui.build_query()
    render_query_preview(query)
    
    # Search button
    if st.button("🔍 Search", type="primary"):
        perform_search(query)
    
    # Save search form
    with st.expander("Save this search"):
        search_name = st.text_input("Search Name")
        search_description = st.text_area("Description")
        
        if st.button("Save Search"):
            if search_name:
                if save_current_search(search_name, search_description, query):
                    st.success(f"Search '{search_name}' saved successfully!")
                else:
                    st.error(f"Search with name '{search_name}' already exists.")
            else:
                st.error("Please provide a search name.")

with tab2:
    # Get saved searches
    search_service = get_search_service()
    saved_searches = search_service.list_saved_searches()
    
    # Render saved searches with load callback
    render_saved_searches(saved_searches, load_saved_search)

with tab3:
    # Get templates
    template_registry = get_template_registry()
    templates = template_registry.list_templates()
    
    # Render templates with use callback
    render_search_templates(templates, use_search_template)

# Show search results if available
st.markdown("---")
if st.session_state.search_results:
    render_search_results(st.session_state.search_results)
else:
    st.info("Use the query builder above to search for onion links.")

# Footer
st.markdown("---")
st.markdown("Dark Web Discovery System - Advanced Search")
