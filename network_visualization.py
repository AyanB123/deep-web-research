"""
Advanced network visualization for the Dark Web Discovery System.
Provides interactive network graphs with clustering and filtering.
"""

import os
import json
import math
import datetime
import logging
import tempfile
import random
from typing import Dict, List, Any, Optional, Tuple, Set, Union

import networkx as nx
import pandas as pd
from pyvis.network import Network
import community as community_louvain
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import matplotlib.colors as mcolors
import matplotlib.cm as cm
import numpy as np

from config import Config

# Configure logger
def log_action(message):
    """Log actions with timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    logging.info(message)


class NetworkVisualizer:
    """
    Advanced network visualization with interactive features.
    Provides different visualization types and export options.
    """
    
    # Color schemes for different node types
    COLOR_SCHEMES = {
        "category": {
            "directory": "#ff9900",
            "search_engine": "#3366cc",
            "marketplace": "#dc3912",
            "forum": "#109618",
            "blog": "#990099",
            "service": "#0099c6",
            "social": "#dd4477",
            "other": "#66aa00",
            "unknown": "#b82e2e"
        },
        "status": {
            "active": "#109618",
            "error": "#dc3912",
            "pending": "#ff9900",
            "blacklisted": "#b82e2e",
            "clearnet_fallback": "#3366cc",
            "unknown": "#666666"
        },
        "safety": {
            "safe": "#109618",
            "caution": "#ff9900",
            "unsafe": "#dc3912",
            "unknown": "#666666"
        }
    }
    
    def __init__(self, link_db, output_dir: Optional[str] = None):
        """
        Initialize the network visualizer.
        
        Args:
            link_db: Database instance for accessing link data
            output_dir (str): Directory for saving visualizations
        """
        self.link_db = link_db
        self.output_dir = output_dir or os.path.join(Config.DATA_DIR, "visualizations")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Graph building options
        self.include_content_nodes = False
        self.include_metadata_nodes = False
        self.max_nodes = 500  # Limit for performance
    
    def build_network_graph(self, 
                           category_filter: Optional[str] = None,
                           status_filter: Optional[str] = None,
                           search_query: Optional[str] = None,
                           include_blacklisted: bool = False,
                           max_days_old: Optional[int] = None,
                           max_nodes: int = 500,
                           base_graph: Optional[nx.Graph] = None) -> nx.Graph:
        """
        Build a NetworkX graph from the database.
        
        Args:
            category_filter (str): Filter by category
            status_filter (str): Filter by status
            search_query (str): Filter by search query
            include_blacklisted (bool): Whether to include blacklisted sites
            max_days_old (int): Maximum age in days
            
        Returns:
            nx.Graph: NetworkX graph
        """
        # Start with base graph if provided, otherwise create new graph
        if base_graph is not None:
            G = base_graph.copy()
            existing_nodes = set(G.nodes())
            log_action(f"Building on existing graph with {len(existing_nodes)} nodes")
        else:
            G = nx.DiGraph()
            existing_nodes = set()
        
        # Get links from database with filters
        links = self.link_db.get_links_with_filters(
            category=category_filter,
            status=status_filter,
            search_query=search_query,
            include_blacklisted=include_blacklisted,
            max_days_old=max_days_old
        )
        
        # Prioritize links not already in the graph
        new_links = [link for link in links if link["url"] not in existing_nodes]
        existing_links = [link for link in links if link["url"] in existing_nodes]
        
        # Calculate how many more nodes we can add
        remaining_capacity = max_nodes - len(existing_nodes)
        
        # If we're over capacity, limit the new links
        if len(new_links) > remaining_capacity and remaining_capacity > 0:
            log_action(f"Limiting progressive loading to {remaining_capacity} new nodes from {len(new_links)} available")
            new_links = new_links[:remaining_capacity]
        
        # If we have no capacity, just return the existing graph
        if remaining_capacity <= 0 and base_graph is not None:
            return G
        
        # Combine new and existing links for processing
        # Process existing links first to ensure they're updated
        links_to_process = existing_links + new_links
        
        # Add nodes for each link
        nodes_added = set(existing_nodes)  # Start with existing nodes
        for link in links_to_process:
            url = link["url"]
            if url not in nodes_added:
                # Extract domain
                domain = self._extract_domain(url)
                
                # Node attributes
                node_attrs = {
                    "url": url,
                    "title": link.get("title", ""),
                    "category": link.get("category", "unknown"),
                    "status": link.get("status", "unknown"),
                    "domain": domain,
                    "last_checked": link.get("last_checked", ""),
                    "discovery_date": link.get("discovery_date", ""),
                    "discovery_source": link.get("discovery_source", ""),
                    "is_seed": link.get("is_seed", False)
                }
                
                # Add safety data if available in metadata
                metadata = link.get("metadata", {})
                if "safety_score" in metadata:
                    node_attrs["safety_score"] = metadata["safety_score"]
                    if metadata["safety_score"] < 3:
                        node_attrs["safety_level"] = "safe"
                    elif metadata["safety_score"] < 7:
                        node_attrs["safety_level"] = "caution"
                    else:
                        node_attrs["safety_level"] = "unsafe"
                else:
                    node_attrs["safety_level"] = "unknown"
                
                # Add node
                G.add_node(url, **node_attrs)
                nodes_added.add(url)
        
        # Add edges based on discovery sources
        for link in links:
            url = link["url"]
            discovery_source = link.get("discovery_source", "")
            
            # Skip if no discovery source
            if not discovery_source:
                continue
            
            # Handle different discovery source formats
            if discovery_source.startswith("search:"):
                # Format is "search:engine_name"
                engine_name = discovery_source.split(":", 1)[1]
                
                # Find matching search engine node
                for node in G.nodes():
                    if G.nodes[node].get("category") == "search_engine" and engine_name in G.nodes[node].get("title", ""):
                        G.add_edge(node, url, type="search_result")
                        break
            
            elif "://" in discovery_source:
                # Discovery source is a URL
                if discovery_source in G.nodes():
                    G.add_edge(discovery_source, url, type="discovered_by")
            
            elif discovery_source == "seed":
                # Seed link, no edge needed
                pass
            
            elif discovery_source == "manual":
                # Manually added, no edge needed
                pass
            
            else:
                # Other discovery source, add as attribute
                G.nodes[url]["other_source"] = discovery_source
        
        # Add domain clustering
        self._add_domain_clustering(G)
        
        return G
    
    def _add_domain_clustering(self, G: nx.Graph):
        """Add domain-based clustering to the graph."""
        # Group nodes by domain
        domain_groups = {}
        for node in G.nodes():
            domain = G.nodes[node].get("domain", "")
            if domain:
                if domain not in domain_groups:
                    domain_groups[domain] = []
                domain_groups[domain].append(node)
        
        # Add domain group attribute
        for domain, nodes in domain_groups.items():
            for node in nodes:
                G.nodes[node]["domain_group"] = domain
                G.nodes[node]["domain_group_size"] = len(nodes)
    
    def create_interactive_graph(self, G: nx.Graph, 
                               color_by: str = "category",
                               height: str = "800px",
                               width: str = "100%",
                               filename: Optional[str] = None) -> str:
        """
        Create an interactive HTML visualization using PyVis.
        
        Args:
            G (nx.Graph): NetworkX graph
            color_by (str): Node coloring scheme (category, status, safety)
            height (str): Height of the visualization
            width (str): Width of the visualization
            filename (str): Output filename
            
        Returns:
            str: Path to the saved HTML file
        """
        # Get color scheme
        color_scheme = self.COLOR_SCHEMES.get(color_by, self.COLOR_SCHEMES["category"])
        
        # Create PyVis network
        net = Network(height=height, width=width, directed=True, notebook=False)
        
        # Get node communities for alternative coloring
        communities = community_louvain.best_partition(G.to_undirected())
        
        # Add nodes with proper attributes
        for node in G.nodes():
            node_data = G.nodes[node]
            
            # Determine node color
            if color_by == "community":
                # Color by community
                community_id = communities.get(node, 0)
                color = self._get_color_from_palette(community_id, len(set(communities.values())))
            else:
                # Color by attribute
                attribute_value = node_data.get(color_by, "unknown")
                color = color_scheme.get(attribute_value, color_scheme["unknown"])
            
            # Determine node size based on connectivity and importance
            size = 25  # Default size
            if node_data.get("is_seed", False):
                size = 35  # Larger for seed nodes
            elif node_data.get("category") == "search_engine":
                size = 30  # Larger for search engines
            elif node_data.get("domain_group_size", 0) > 5:
                size = 28  # Larger for domains with many pages
            
            # Create node title (tooltip)
            title = f"<b>{node_data.get('title', node)}</b><br>"
            title += f"URL: {node}<br>"
            title += f"Category: {node_data.get('category', 'unknown')}<br>"
            title += f"Status: {node_data.get('status', 'unknown')}<br>"
            
            if "safety_level" in node_data:
                title += f"Safety: {node_data.get('safety_level', 'unknown')}<br>"
            
            if "last_checked" in node_data and node_data["last_checked"]:
                title += f"Last Checked: {node_data['last_checked']}<br>"
            
            # Add node to network
            net.add_node(
                node, 
                label=node_data.get("title", node)[:20] + "..." if len(node_data.get("title", node)) > 20 else node_data.get("title", node),
                title=title,
                color=color,
                size=size,
                borderWidth=2,
                borderWidthSelected=3,
                font={"size": 12}
            )
        
        # Add edges
        for source, target, edge_data in G.edges(data=True):
            edge_type = edge_data.get("type", "link")
            
            # Determine edge color and width
            edge_color = "#666666"  # Default
            edge_width = 1  # Default
            
            if edge_type == "search_result":
                edge_color = "#3366cc"
                edge_width = 2
            elif edge_type == "discovered_by":
                edge_color = "#109618"
                edge_width = 1.5
            
            # Add edge to network
            net.add_edge(
                source, 
                target, 
                color=edge_color,
                width=edge_width,
                title=edge_type
            )
        
        # Set physics options for better layout
        net.set_options("""
        {
          "physics": {
            "forceAtlas2Based": {
              "gravitationalConstant": -50,
              "centralGravity": 0.01,
              "springLength": 100,
              "springConstant": 0.08
            },
            "maxVelocity": 50,
            "solver": "forceAtlas2Based",
            "timestep": 0.5,
            "stabilization": {
              "enabled": true,
              "iterations": 500,
              "updateInterval": 25
            }
          },
          "interaction": {
            "navigationButtons": true,
            "keyboard": true
          }
        }
        """)
        
        # Generate output filename if not provided
        if not filename:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"network_graph_{timestamp}.html"
        
        # Save to file
        output_path = os.path.join(self.output_dir, filename)
        net.save_graph(output_path)
        
        return output_path
    
    def create_plotly_graph(self, G: nx.Graph, 
                          color_by: str = "category",
                          layout_type: str = "force_directed",
                          node_size: int = 15,
                          show_labels: bool = True,
                          filename: Optional[str] = None) -> str:
        """
        Create an interactive Plotly graph for embedding in Streamlit.
        
        Args:
            G (nx.Graph): NetworkX graph
            color_by (str): Node coloring scheme
            layout_type (str): Graph layout algorithm
            filename (str): Output filename
            
        Returns:
            str: Path to the saved HTML file (or JSON for Streamlit)
        """
        # Get positions for nodes
        if layout_type == "force_directed":
            pos = nx.spring_layout(G, seed=42)
        elif layout_type == "circular":
            pos = nx.circular_layout(G)
        elif layout_type == "kamada_kawai":
            pos = nx.kamada_kawai_layout(G)
        else:
            pos = nx.spring_layout(G, seed=42)
        
        # Get color scheme
        color_scheme = self.COLOR_SCHEMES.get(color_by, self.COLOR_SCHEMES["category"])
        
        # Prepare node trace
        node_x = []
        node_y = []
        node_text = []
        node_colors = []
        node_sizes = []
        
        for node in G.nodes():
            node_data = G.nodes[node]
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            
            # Node tooltip
            text = f"<b>{node_data.get('title', node)}</b><br>"
            text += f"URL: {node}<br>"
            text += f"Category: {node_data.get('category', 'unknown')}<br>"
            text += f"Status: {node_data.get('status', 'unknown')}<br>"
            
            if "safety_level" in node_data:
                text += f"Safety: {node_data.get('safety_level', 'unknown')}<br>"
            
            node_text.append(text)
            
            # Node color
            attribute_value = node_data.get(color_by, "unknown")
            color = color_scheme.get(attribute_value, color_scheme["unknown"])
            node_colors.append(color)
            
            # Node size - adjusted based on parameter
            base_size = node_size  # Use parameter as base size
            if node_data.get("is_seed", False):
                size = base_size * 1.3  # Larger for seed nodes
            elif node_data.get("category") == "search_engine":
                size = base_size * 1.2  # Larger for search engines
            elif node_data.get("domain_group_size", 0) > 5:
                size = base_size * 1.1  # Larger for domains with many pages
            else:
                size = base_size
            
            node_sizes.append(size)
        
        # Create node trace with level-of-detail adjustments
        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode='markers+text' if show_labels else 'markers',
            hoverinfo='text',
            text=node_text,
            marker=dict(
                color=node_colors,
                size=node_sizes,
                line=dict(width=1, color='#888'),
                opacity=0.8
            )
        )
        
        # Add node labels if enabled
        if show_labels:
            # Prepare node labels
            label_trace = go.Scatter(
                x=node_x,
                y=node_y,
                mode='text',
                text=[G.nodes[node].get('title', node) for node in G.nodes()],
                textposition="top center",
                textfont=dict(size=8 if len(G.nodes()) > 50 else 10),
                hoverinfo='none'
            )
        
        # Prepare edge traces
        edge_traces = []
        
        for source, target, edge_data in G.edges(data=True):
            edge_type = edge_data.get("type", "link")
            
            # Determine edge color
            edge_color = "#aaaaaa"  # Default
            
            if edge_type == "search_result":
                edge_color = "#3366cc"
            elif edge_type == "discovered_by":
                edge_color = "#109618"
            
            # Edge coordinates
            x0, y0 = pos[source]
            x1, y1 = pos[target]
            
            # Create edge trace
            edge_trace = go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode='lines',
                line=dict(width=1, color=edge_color),
                hoverinfo='none'
            )
            
            edge_traces.append(edge_trace)
        
        # Create figure with all traces
        traces = [node_trace]
        
        # Add edge traces
        traces.extend(edge_traces)
        
        # Add label trace if enabled
        if show_labels and 'label_trace' in locals():
            traces.append(label_trace)
        
        # Create figure
        fig = go.Figure(
            data=traces,
            layout=go.Layout(
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20, l=5, r=5, t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                title=dict(
                    text=f"Network Graph ({G.number_of_nodes()} nodes, {G.number_of_edges()} edges)",
                    font=dict(size=16)
                )
            )
        )
        
        # Add legend for the color scheme
        if color_by in self.COLOR_SCHEMES:
            # Create a separate trace for each category with visibility='legendonly'
            for category, color in color_scheme.items():
                fig.add_trace(go.Scatter(
                    x=[None],
                    y=[None],
                    mode='markers',
                    marker=dict(size=10, color=color),
                    name=category.capitalize(),
                    legendgroup=category
                ))
            
            fig.update_layout(showlegend=True)
        
        # Save to file if filename provided
        if filename:
            output_path = os.path.join(self.output_dir, filename)
            fig.write_html(output_path)
            return output_path
        
        # Return figure for Streamlit
        return fig
    
    def export_graph_to_graphml(self, G: nx.Graph, filename: Optional[str] = None) -> str:
        """
        Export graph to GraphML format for use in external tools.
        
        Args:
            G (nx.Graph): NetworkX graph
            filename (str): Output filename
            
        Returns:
            str: Path to the saved GraphML file
        """
        if not filename:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"network_graph_{timestamp}.graphml"
        
        output_path = os.path.join(self.output_dir, filename)
        nx.write_graphml(G, output_path)
        
        return output_path
    
    def create_domain_hierarchy_visualization(self, G: nx.Graph, 
                                           filename: Optional[str] = None) -> str:
        """
        Create hierarchical visualization of domains and their pages.
        
        Args:
            G (nx.Graph): NetworkX graph
            filename (str): Output filename
            
        Returns:
            str: Path to the saved HTML file
        """
        # Group nodes by domain
        domain_groups = {}
        for node in G.nodes():
            domain = G.nodes[node].get("domain", "")
            if domain:
                if domain not in domain_groups:
                    domain_groups[domain] = []
                domain_groups[domain].append(node)
        
        # Create hierarchy visualization
        fig = go.Figure()
        
        # Sort domains by number of pages
        sorted_domains = sorted(domain_groups.items(), key=lambda x: len(x[1]), reverse=True)
        
        # Limit to top 30 domains for readability
        if len(sorted_domains) > 30:
            sorted_domains = sorted_domains[:30]
        
        # Add bar for each domain
        domains = [domain for domain, _ in sorted_domains]
        page_counts = [len(pages) for _, pages in sorted_domains]
        
        fig.add_trace(go.Bar(
            x=domains,
            y=page_counts,
            text=page_counts,
            textposition='auto',
            marker_color='rgba(50, 171, 96, 0.7)'
        ))
        
        fig.update_layout(
            title='Top Domains by Number of Pages',
            xaxis=dict(
                title='Domain',
                tickangle=-45
            ),
            yaxis=dict(
                title='Number of Pages'
            ),
            margin=dict(l=50, r=50, t=50, b=100),
            height=600
        )
        
        # Save to file if filename provided
        if filename:
            output_path = os.path.join(self.output_dir, filename)
            fig.write_html(output_path)
            return output_path
        
        # Return figure for Streamlit
        return fig
    
    def create_category_distribution(self, G: nx.Graph,
                                   filename: Optional[str] = None) -> str:
        """
        Create visualization of category distribution.
        
        Args:
            G (nx.Graph): NetworkX graph
            filename (str): Output filename
            
        Returns:
            str: Path to the saved HTML file
        """
        # Count categories
        categories = {}
        for node in G.nodes():
            category = G.nodes[node].get("category", "unknown")
            if category not in categories:
                categories[category] = 0
            categories[category] += 1
        
        # Create pie chart
        fig = go.Figure(data=[go.Pie(
            labels=list(categories.keys()),
            values=list(categories.values()),
            hole=.3,
            marker=dict(
                colors=[self.COLOR_SCHEMES["category"].get(cat, "#666666") for cat in categories.keys()]
            )
        )])
        
        fig.update_layout(
            title='Content Category Distribution',
            height=500
        )
        
        # Save to file if filename provided
        if filename:
            output_path = os.path.join(self.output_dir, filename)
            fig.write_html(output_path)
            return output_path
        
        # Return figure for Streamlit
        return fig
    
    def create_safety_distribution(self, G: nx.Graph,
                                 filename: Optional[str] = None) -> str:
        """
        Create visualization of safety level distribution.
        
        Args:
            G (nx.Graph): NetworkX graph
            filename (str): Output filename
            
        Returns:
            str: Path to the saved HTML file
        """
        # Count safety levels
        safety_levels = {}
        for node in G.nodes():
            safety = G.nodes[node].get("safety_level", "unknown")
            if safety not in safety_levels:
                safety_levels[safety] = 0
            safety_levels[safety] += 1
        
        # Create pie chart
        fig = go.Figure(data=[go.Pie(
            labels=list(safety_levels.keys()),
            values=list(safety_levels.values()),
            hole=.3,
            marker=dict(
                colors=[self.COLOR_SCHEMES["safety"].get(level, "#666666") for level in safety_levels.keys()]
            )
        )])
        
        fig.update_layout(
            title='Content Safety Distribution',
            height=500
        )
        
        # Save to file if filename provided
        if filename:
            output_path = os.path.join(self.output_dir, filename)
            fig.write_html(output_path)
            return output_path
        
        # Return figure for Streamlit
        return fig
    
    def create_discovery_timeline(self, G: nx.Graph,
                                filename: Optional[str] = None) -> str:
        """
        Create timeline visualization of link discoveries.
        
        Args:
            G (nx.Graph): NetworkX graph
            filename (str): Output filename
            
        Returns:
            str: Path to the saved HTML file
        """
        # Extract discovery dates
        dates = []
        categories = []
        
        for node in G.nodes():
            discovery_date = G.nodes[node].get("discovery_date", "")
            if discovery_date:
                try:
                    date = datetime.datetime.fromisoformat(discovery_date)
                    dates.append(date)
                    categories.append(G.nodes[node].get("category", "unknown"))
                except (ValueError, TypeError):
                    continue
        
        # Create dataframe
        if not dates:
            # Return empty figure if no dates
            fig = go.Figure()
            fig.update_layout(
                title='No discovery date data available',
                height=500
            )
        else:
            df = pd.DataFrame({
                'date': dates,
                'category': categories
            })
            
            # Group by date and category
            df['date_only'] = df['date'].dt.date
            grouped = df.groupby(['date_only', 'category']).size().reset_index(name='count')
            
            # Create line chart
            fig = px.line(
                grouped, 
                x='date_only', 
                y='count', 
                color='category',
                labels={'date_only': 'Date', 'count': 'Discovered Links', 'category': 'Category'},
                color_discrete_map={cat: self.COLOR_SCHEMES["category"].get(cat, "#666666") for cat in grouped['category'].unique()}
            )
            
            fig.update_layout(
                title='Link Discovery Timeline by Category',
                height=500,
                legend_title_text='Category'
            )
        
        # Save to file if filename provided
        if filename:
            output_path = os.path.join(self.output_dir, filename)
            fig.write_html(output_path)
            return output_path
        
        # Return figure for Streamlit
        return fig
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        # Remove protocol
        domain = url.split("://", 1)[-1]
        
        # Remove path
        domain = domain.split("/", 1)[0]
        
        return domain
    
    def _get_color_from_palette(self, index: int, total: int) -> str:
        """Get color from a palette based on index."""
        cmap = cm.get_cmap('viridis', total)
        rgba = cmap(index / total)
        return f"rgba({int(rgba[0]*255)}, {int(rgba[1]*255)}, {int(rgba[2]*255)}, 0.8)"


def create_visualizations_for_streamlit(link_db, output_dir: Optional[str] = None):
    """
    Create a set of visualizations for Streamlit dashboard.
    
    Args:
        link_db: Database instance
        output_dir (str): Output directory
        
    Returns:
        dict: Paths to visualization files
    """
    visualizer = NetworkVisualizer(link_db, output_dir)
    
    # Create base graph
    G = visualizer.build_network_graph()
    
    # Create visualizations
    interactive_graph = visualizer.create_interactive_graph(
        G, color_by="category", filename="interactive_network.html"
    )
    
    plotly_graph = visualizer.create_plotly_graph(
        G, color_by="category", filename="plotly_network.html"
    )
    
    domain_hierarchy = visualizer.create_domain_hierarchy_visualization(
        G, filename="domain_hierarchy.html"
    )
    
    category_distribution = visualizer.create_category_distribution(
        G, filename="category_distribution.html"
    )
    
    safety_distribution = visualizer.create_safety_distribution(
        G, filename="safety_distribution.html"
    )
    
    discovery_timeline = visualizer.create_discovery_timeline(
        G, filename="discovery_timeline.html"
    )
    
    # Export to GraphML
    graphml_export = visualizer.export_graph_to_graphml(G, filename="network_export.graphml")
    
    return {
        "interactive_graph": interactive_graph,
        "plotly_graph": plotly_graph,
        "domain_hierarchy": domain_hierarchy,
        "category_distribution": category_distribution,
        "safety_distribution": safety_distribution,
        "discovery_timeline": discovery_timeline,
        "graphml_export": graphml_export
    }
