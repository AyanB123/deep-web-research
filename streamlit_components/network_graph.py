"""
Network graph visualization component for Streamlit.
Provides interactive network visualization with real-time updates.
"""

import streamlit as st
import networkx as nx
import plotly.graph_objects as go
import time
import datetime
import json
import os
from typing import Dict, List, Any, Optional, Callable, Union

from network_visualization import NetworkVisualizer
from streamlit_components.card import render_card

# Check if streamlit-plotly-events is installed
try:
    from streamlit_plotly_events import plotly_events
    PLOTLY_EVENTS_AVAILABLE = True
except ImportError:
    PLOTLY_EVENTS_AVAILABLE = False
    st.warning("Package 'streamlit-plotly-events' not installed. Node selection will be disabled.")

class NetworkGraphComponent:
    """
    Interactive network graph component for Streamlit.
    Provides real-time updates, filtering, and node selection.
    """
    
    def __init__(self, 
                 network_visualizer: NetworkVisualizer,
                 title: str = "Network Graph",
                 key: str = "network_graph",
                 height: int = 600,
                 with_controls: bool = True,
                 with_sidebar: bool = False,
                 with_selection: bool = True,
                 with_details: bool = True,
                 on_node_select: Optional[Callable] = None):
        """
        Initialize the network graph component.
        
        Args:
            network_visualizer: NetworkVisualizer instance
            title: Component title
            key: Component key prefix
            height: Graph height in pixels
            with_controls: Whether to show controls
            with_sidebar: Whether to place controls in sidebar
            with_selection: Whether to enable node selection
            with_details: Whether to show node details
            on_node_select: Function to call when a node is selected
        """
        self.visualizer = network_visualizer
        self.title = title
        self.key_prefix = key
        self.height = height
        self.with_controls = with_controls
        self.with_sidebar = with_sidebar
        self.with_selection = with_selection and PLOTLY_EVENTS_AVAILABLE
        self.with_details = with_details
        self.on_node_select = on_node_select
        
        # State management
        if f"{self.key_prefix}_graph" not in st.session_state:
            st.session_state[f"{self.key_prefix}_graph"] = None
        
        if f"{self.key_prefix}_selected_node" not in st.session_state:
            st.session_state[f"{self.key_prefix}_selected_node"] = None
            
        if f"{self.key_prefix}_filters" not in st.session_state:
            st.session_state[f"{self.key_prefix}_filters"] = {
                "category": None,
                "status": None,
                "search_query": None,
                "include_blacklisted": False,
                "max_days_old": None,
                "layout_type": "force_directed",
                "color_by": "category",
                "max_nodes": 100
            }
            
        # Setup WebSocket handlers for real-time updates if available
        if "websocket" in st.session_state and st.session_state.websocket:
            self._setup_websocket_handlers()
    
    def _setup_websocket_handlers(self):
        """Set up WebSocket handlers for real-time updates."""
        websocket = st.session_state.websocket
        
        # Register handler for new links
        websocket.register_message_handler("new_link", self._handle_new_link)
        
        # Register handler for link updates
        websocket.register_message_handler("link_update", self._handle_link_update)
        
        # Register handler for graph reset
        websocket.register_message_handler("reset_graph", self._handle_reset_graph)
    
    def _handle_new_link(self, data):
        """Handle new link event from WebSocket."""
        # Mark graph as needing update
        st.session_state[f"{self.key_prefix}_graph_needs_update"] = True
        
        # If auto-update is enabled, update the graph
        if st.session_state.get(f"{self.key_prefix}_auto_update", False):
            st.experimental_rerun()
    
    def _handle_link_update(self, data):
        """Handle link update event from WebSocket."""
        # Mark graph as needing update
        st.session_state[f"{self.key_prefix}_graph_needs_update"] = True
        
        # If auto-update is enabled, update the graph
        if st.session_state.get(f"{self.key_prefix}_auto_update", False):
            st.experimental_rerun()
    
    def _handle_reset_graph(self, data):
        """Handle graph reset event from WebSocket."""
        # Clear graph
        st.session_state[f"{self.key_prefix}_graph"] = None
        
        # Mark graph as needing update
        st.session_state[f"{self.key_prefix}_graph_needs_update"] = True
        
        # Always update on reset
        st.experimental_rerun()
    
    def _build_graph(self):
        """Build the graph using the current filters with progressive loading."""
        filters = st.session_state[f"{self.key_prefix}_filters"]
        
        # Get the network graph with progressive loading enabled
        with st.spinner("Loading network data..."):
            # First phase: Get basic graph structure with limited nodes for quick rendering
            G = self.visualizer.build_network_graph(
                category_filter=filters["category"],
                status_filter=filters["status"],
                search_query=filters["search_query"],
                include_blacklisted=filters["include_blacklisted"],
                max_days_old=filters["max_days_old"],
                max_nodes=filters["max_nodes"]
            )
            
            # Store the graph
            st.session_state[f"{self.key_prefix}_graph"] = G
            
            # Set loading phase
            st.session_state[f"{self.key_prefix}_loading_phase"] = "basic"
            
            # Clear needs update flag
            st.session_state[f"{self.key_prefix}_graph_needs_update"] = False
            
            # Start background loading of additional data if needed
            if G.number_of_nodes() >= filters["max_nodes"] - 10:  # Close to max nodes limit
                st.session_state[f"{self.key_prefix}_full_loading_needed"] = True
            else:
                st.session_state[f"{self.key_prefix}_full_loading_needed"] = False
        
        return G
        
    def _load_additional_data(self):
        """Load additional graph data in the background."""
        if not st.session_state.get(f"{self.key_prefix}_full_loading_needed", False):
            return
        
        # Get filters
        filters = st.session_state[f"{self.key_prefix}_filters"]
        
        # Check if we're already in advanced loading phase
        if st.session_state.get(f"{self.key_prefix}_loading_phase") == "advanced":
            return
            
        # Set loading phase
        st.session_state[f"{self.key_prefix}_loading_phase"] = "advanced"
        
        # Get existing graph
        G = st.session_state.get(f"{self.key_prefix}_graph")
        if G is None:
            return
            
        with st.spinner("Loading additional network data..."):
            # Load additional nodes and edges
            G_extended = self.visualizer.build_network_graph(
                category_filter=filters["category"],
                status_filter=filters["status"],
                search_query=filters["search_query"],
                include_blacklisted=filters["include_blacklisted"],
                max_days_old=filters["max_days_old"],
                max_nodes=filters["max_nodes"] * 2,  # Double the nodes
                base_graph=G  # Use existing graph as base
            )
            
            # Store the extended graph
            st.session_state[f"{self.key_prefix}_graph"] = G_extended
            st.session_state[f"{self.key_prefix}_loading_phase"] = "complete"
            
            # Trigger rerun to update visualization
            if st.session_state.get(f"{self.key_prefix}_auto_update", False):
                st.experimental_rerun()
    
    def _render_controls(self, container):
        """Render filter controls."""
        filters = st.session_state[f"{self.key_prefix}_filters"]
        
        # Create columns for compact layout
        col1, col2 = container.columns(2)
        
        with col1:
            # Category filter
            category = st.selectbox(
                "Category",
                [None, "directory", "search_engine", "marketplace", "forum", "blog", "service", "social", "other"],
                index=0,
                key=f"{self.key_prefix}_category"
            )
            filters["category"] = category
            
            # Status filter
            status = st.selectbox(
                "Status",
                [None, "active", "error", "pending", "blacklisted", "clearnet_fallback"],
                index=0,
                key=f"{self.key_prefix}_status"
            )
            filters["status"] = status
            
            # Search query
            search_query = st.text_input(
                "Search Query",
                value="",
                key=f"{self.key_prefix}_search_query"
            )
            filters["search_query"] = search_query if search_query else None
        
        with col2:
            # Include blacklisted
            include_blacklisted = st.checkbox(
                "Include Blacklisted",
                value=filters["include_blacklisted"],
                key=f"{self.key_prefix}_include_blacklisted"
            )
            filters["include_blacklisted"] = include_blacklisted
            
            # Max days old
            max_days_old = st.number_input(
                "Max Days Old",
                min_value=0,
                value=filters.get("max_days_old", 0) or 0,
                step=1,
                key=f"{self.key_prefix}_max_days_old"
            )
            filters["max_days_old"] = max_days_old if max_days_old > 0 else None
            
            # Max nodes
            max_nodes = st.slider(
                "Max Nodes",
                min_value=10,
                max_value=500,
                value=filters["max_nodes"],
                step=10,
                key=f"{self.key_prefix}_max_nodes"
            )
            filters["max_nodes"] = max_nodes
        
        # Create another row of columns
        col1, col2 = container.columns(2)
        
        with col1:
            # Layout type
            layout_type = st.selectbox(
                "Layout",
                ["force_directed", "circular", "random", "spring", "spectral"],
                index=0,
                key=f"{self.key_prefix}_layout_type"
            )
            filters["layout_type"] = layout_type
        
        with col2:
            # Color by
            color_by = st.selectbox(
                "Color By",
                ["category", "status", "safety", "domain"],
                index=0,
                key=f"{self.key_prefix}_color_by"
            )
            filters["color_by"] = color_by
        
        # Auto-update toggle
        auto_update = st.checkbox(
            "Auto-update",
            value=st.session_state.get(f"{self.key_prefix}_auto_update", True),
            key=f"{self.key_prefix}_auto_update"
        )
        st.session_state[f"{self.key_prefix}_auto_update"] = auto_update
        
        # Update button
        if st.button("Update Graph", key=f"{self.key_prefix}_update"):
            st.session_state[f"{self.key_prefix}_graph"] = None
            st.session_state[f"{self.key_prefix}_graph_needs_update"] = True
            st.experimental_rerun()
    
    def _render_details(self, container, node_id):
        """Render node details."""
        G = st.session_state[f"{self.key_prefix}_graph"]
        
        if G is None or node_id not in G.nodes:
            container.info("No node selected")
            return
        
        # Get node data
        node_data = G.nodes[node_id]
        
        # Format node data
        details = {
            "URL": node_id,
            "Category": node_data.get("category", "unknown"),
            "Status": node_data.get("status", "unknown"),
            "Safety Level": node_data.get("safety_level", "unknown"),
            "Title": node_data.get("title", "Unknown"),
            "Domain": node_data.get("domain", "unknown"),
            "Discovery Date": node_data.get("discovery_date", "unknown"),
            "Last Checked": node_data.get("last_checked", "unknown")
        }
        
        # Show metadata if available
        metadata = node_data.get("metadata", {})
        if metadata:
            details["Metadata"] = json.dumps(metadata, indent=2)
        
        # Create card with node details
        render_card(
            title=f"Node Details: {node_data.get('title', node_id)}",
            content=[f"**{k}:** {v}" for k, v in details.items()],
            container=container
        )
        
        # Show connected nodes
        neighbors = list(G.neighbors(node_id))
        if neighbors:
            container.markdown("### Connected Nodes")
            
            # Create columns for compact layout
            cols = container.columns(2)
            
            for i, neighbor in enumerate(neighbors[:10]):  # Limit to 10 neighbors
                col_idx = i % 2
                neighbor_data = G.nodes[neighbor]
                
                cols[col_idx].markdown(f"**{neighbor_data.get('title', neighbor)}**")
                cols[col_idx].markdown(f"_{neighbor}_")
                cols[col_idx].markdown(f"Category: {neighbor_data.get('category', 'unknown')}")
                cols[col_idx].markdown("---")
            
            if len(neighbors) > 10:
                container.info(f"Showing 10 of {len(neighbors)} connected nodes")
    
    def _render_graph(self, container):
        """Render the network graph with progressive loading support."""
        # Get the graph
        G = st.session_state.get(f"{self.key_prefix}_graph")
        
        # Check if we need to build the graph
        if G is None or st.session_state.get(f"{self.key_prefix}_graph_needs_update", False):
            with st.spinner("Building network graph..."):
                G = self._build_graph()
        
        if G is None or G.number_of_nodes() == 0:
            container.warning("No nodes to display with current filters")
            return
        
        # Show graph stats
        stats_col1, stats_col2, stats_col3, stats_col4 = container.columns(4)
        stats_col1.metric("Nodes", G.number_of_nodes())
        stats_col2.metric("Edges", G.number_of_edges())
        stats_col3.metric("Connected Components", nx.number_connected_components(G.to_undirected()))
        
        # Show loading status
        loading_phase = st.session_state.get(f"{self.key_prefix}_loading_phase", "complete")
        if loading_phase == "basic":
            stats_col4.info("Basic view loaded. Loading more data...")
            # Trigger additional data loading in background
            if st.session_state.get(f"{self.key_prefix}_full_loading_needed", False):
                self._load_additional_data()
        elif loading_phase == "advanced":
            stats_col4.info("Advanced view loading...")
        else:
            stats_col4.success("Complete view loaded")
        
        # Get visualization options
        filters = st.session_state[f"{self.key_prefix}_filters"]
        
        # Create the graph visualization with appropriate level of detail
        level_of_detail = "high" if loading_phase == "complete" else "medium"
        
        # Apply level-of-detail rendering based on graph size
        node_size = 10 if G.number_of_nodes() > 100 else 15
        show_labels = G.number_of_nodes() <= 50 or loading_phase == "complete"
        
        fig = self.visualizer.create_plotly_graph(
            G,
            color_by=filters["color_by"],
            layout_type=filters["layout_type"],
            node_size=node_size,
            show_labels=show_labels
        )
        
        # Update layout
        fig.update_layout(
            height=self.height,
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255,255,255,0.8)"
            ),
            hoverlabel=dict(
                bgcolor="white",
                font_size=12
            )
        )
        
        # Display the graph
        if self.with_selection and PLOTLY_EVENTS_AVAILABLE:
            # Use plotly_events for node selection
            selected_points = plotly_events(
                fig,
                click_event=True,
                hover_event=False,
                select_event=False,
                override_height=self.height,
                key=f"{self.key_prefix}_plotly_events"
            )
            
            # Handle selection
            if selected_points:
                node_index = selected_points[0].get("pointIndex", None)
                if node_index is not None:
                    # Get the node ID from the graph
                    node_ids = list(G.nodes())
                    if 0 <= node_index < len(node_ids):
                        selected_node = node_ids[node_index]
                        st.session_state[f"{self.key_prefix}_selected_node"] = selected_node
                        
                        # Call selection callback if provided
                        if self.on_node_select:
                            self.on_node_select(selected_node, G.nodes[selected_node])
        else:
            # Use regular plotly for display only
            st.plotly_chart(fig, use_container_width=True)
    
    def render(self):
        """Render the network graph component."""
        st.markdown(f"## {self.title}")
        
        # Determine where to place controls
        if self.with_controls:
            if self.with_sidebar:
                controls_container = st.sidebar
                st.sidebar.markdown(f"### {self.title} Controls")
                self._render_controls(controls_container)
                
                # Main container for graph and details
                graph_container = st
            else:
                # Create expander for controls
                controls_container = st.expander("Graph Controls", expanded=False)
                self._render_controls(controls_container)
                
                # Main container for graph
                graph_container = st
        else:
            # No controls, just use main container
            graph_container = st
        
        # Create columns for graph and details if needed
        if self.with_details:
            graph_col, details_col = graph_container.columns([2, 1])
            self._render_graph(graph_col)
            
            # Get selected node
            selected_node = st.session_state.get(f"{self.key_prefix}_selected_node")
            self._render_details(details_col, selected_node)
        else:
            # Just render the graph
            self._render_graph(graph_container)


def render_network_graph(
    network_visualizer: NetworkVisualizer,
    title: str = "Network Graph",
    key: str = "network_graph",
    height: int = 600,
    with_controls: bool = True,
    with_sidebar: bool = False,
    with_selection: bool = True,
    with_details: bool = True,
    on_node_select: Optional[Callable] = None
):
    """
    Render a network graph component.
    
    Args:
        network_visualizer: NetworkVisualizer instance
        title: Component title
        key: Component key prefix
        height: Graph height in pixels
        with_controls: Whether to show controls
        with_sidebar: Whether to place controls in sidebar
        with_selection: Whether to enable node selection
        with_details: Whether to show node details
        on_node_select: Function to call when a node is selected
    """
    component = NetworkGraphComponent(
        network_visualizer=network_visualizer,
        title=title,
        key=key,
        height=height,
        with_controls=with_controls,
        with_sidebar=with_sidebar,
        with_selection=with_selection,
        with_details=with_details,
        on_node_select=on_node_select
    )
    
    component.render()
