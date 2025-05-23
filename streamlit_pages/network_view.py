"""
Network visualization page for the Dark Web Discovery System.
Provides interactive network exploration and analysis.
"""

import streamlit as st
import os
import datetime
import networkx as nx
from typing import Dict, List, Any, Optional

from network_visualization import NetworkVisualizer, create_visualizations_for_streamlit
from streamlit_components.network_graph import render_network_graph
from streamlit_components.card import render_card
from database.link_database import get_link_database
from config import Config

def load_network_visualizer():
    """Load the network visualizer with database connection."""
    if "network_visualizer" not in st.session_state:
        # Get database connection
        link_db = get_link_database()
        
        # Create output directory if needed
        output_dir = os.path.join(Config.DATA_DIR, "visualizations")
        os.makedirs(output_dir, exist_ok=True)
        
        # Create visualizer
        st.session_state.network_visualizer = NetworkVisualizer(link_db, output_dir)
    
    return st.session_state.network_visualizer

def handle_node_select(node_id, node_data):
    """Handle node selection from the network graph."""
    # Store selected node details
    st.session_state.selected_node = {
        "id": node_id,
        "data": node_data,
        "selected_at": datetime.datetime.now().isoformat()
    }
    
    # You could add more logic here, like loading additional data

def render_visualization_tabs():
    """Render tabs for different visualization types."""
    # Create tabs
    tabs = st.tabs([
        "Network Graph", 
        "Domain Hierarchy", 
        "Category Distribution", 
        "Safety Distribution",
        "Discovery Timeline"
    ])
    
    # Load visualizer
    visualizer = load_network_visualizer()
    
    # Network Graph tab
    with tabs[0]:
        render_network_graph(
            network_visualizer=visualizer,
            title="Interactive Network Graph",
            key="main_network_graph",
            height=700,
            with_controls=True,
            with_sidebar=True,
            with_selection=True,
            with_details=True,
            on_node_select=handle_node_select
        )
    
    # Domain Hierarchy tab
    with tabs[1]:
        st.markdown("## Domain Hierarchy")
        st.markdown("Hierarchical view of domains and their pages.")
        
        # Get or create the visualization
        if "domain_hierarchy_graph" not in st.session_state:
            with st.spinner("Creating domain hierarchy visualization..."):
                G = visualizer.build_network_graph()
                fig = visualizer.create_domain_hierarchy_visualization(G)
                st.session_state.domain_hierarchy_graph = fig
        
        # Display the visualization
        st.plotly_chart(st.session_state.domain_hierarchy_graph, use_container_width=True)
    
    # Category Distribution tab
    with tabs[2]:
        st.markdown("## Category Distribution")
        st.markdown("Distribution of links by category.")
        
        # Get or create the visualization
        if "category_distribution_graph" not in st.session_state:
            with st.spinner("Creating category distribution visualization..."):
                G = visualizer.build_network_graph()
                fig = visualizer.create_category_distribution(G)
                st.session_state.category_distribution_graph = fig
        
        # Display the visualization
        st.plotly_chart(st.session_state.category_distribution_graph, use_container_width=True)
    
    # Safety Distribution tab
    with tabs[3]:
        st.markdown("## Safety Distribution")
        st.markdown("Distribution of links by safety level.")
        
        # Get or create the visualization
        if "safety_distribution_graph" not in st.session_state:
            with st.spinner("Creating safety distribution visualization..."):
                G = visualizer.build_network_graph()
                fig = visualizer.create_safety_distribution(G)
                st.session_state.safety_distribution_graph = fig
        
        # Display the visualization
        st.plotly_chart(st.session_state.safety_distribution_graph, use_container_width=True)
    
    # Discovery Timeline tab
    with tabs[4]:
        st.markdown("## Discovery Timeline")
        st.markdown("Timeline of link discoveries by category.")
        
        # Get or create the visualization
        if "discovery_timeline_graph" not in st.session_state:
            with st.spinner("Creating discovery timeline visualization..."):
                G = visualizer.build_network_graph()
                fig = visualizer.create_discovery_timeline(G)
                st.session_state.discovery_timeline_graph = fig
        
        # Display the visualization
        st.plotly_chart(st.session_state.discovery_timeline_graph, use_container_width=True)

def render_network_view():
    """Render the network visualization page."""
    st.title("Network Visualization")
    
    # Description
    st.markdown("""
    Explore discovered sites as an interactive network graph. 
    Visualize connections between sites, analyze link patterns, and identify clusters.
    
    Use the controls in the sidebar to filter and customize the visualization.
    """)
    
    # Check if WebSocket is available
    if "websocket" in st.session_state and st.session_state.websocket:
        st.info("Real-time updates are enabled. New discoveries will be added to the graph automatically.")
    
    # Render visualization tabs
    render_visualization_tabs()
    
    # Advanced options
    with st.expander("Advanced Export Options", expanded=False):
        st.markdown("### Export Graph")
        
        col1, col2 = st.columns(2)
        
        with col1:
            export_format = st.selectbox(
                "Export Format",
                ["GraphML", "JSON", "CSV", "GEXF"],
                index=0
            )
        
        with col2:
            filename = st.text_input(
                "Filename",
                value="network_export"
            )
        
        if st.button("Export Graph"):
            visualizer = load_network_visualizer()
            G = visualizer.build_network_graph()
            
            if export_format == "GraphML":
                output_path = visualizer.export_graph_to_graphml(G, f"{filename}.graphml")
                st.success(f"Graph exported to {output_path}")
            elif export_format == "JSON":
                # Add JSON export functionality
                st.warning("JSON export not implemented yet")
            elif export_format == "CSV":
                # Add CSV export functionality
                st.warning("CSV export not implemented yet")
            elif export_format == "GEXF":
                # Add GEXF export functionality
                st.warning("GEXF export not implemented yet")
    
    # Footer
    st.markdown("---")
    st.markdown("Powered by the Dark Web Discovery System Network Visualization Engine")

# Main function to run the page
if __name__ == "__main__":
    render_network_view()
