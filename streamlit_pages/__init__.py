"""
Page manager module for the Dark Web Discovery System Streamlit app.
"""

from .dashboard import render_dashboard
from .discover import render_discover
from .visualize import render_visualize
from .export import render_export
from .settings import render_settings

# Map of page names to their render functions
PAGE_REGISTRY = {
    "Dashboard": render_dashboard,
    "Discover": render_discover,
    "Visualize": render_visualize,
    "Export": render_export,
    "Settings": render_settings
}

def get_page_names():
    """Get a list of all available page names."""
    return list(PAGE_REGISTRY.keys())

def render_page(page_name):
    """
    Render a specific page by name.
    
    Args:
        page_name: The name of the page to render
        
    Returns:
        True if page was found and rendered, False otherwise
    """
    if page_name in PAGE_REGISTRY:
        PAGE_REGISTRY[page_name]()
        return True
    
    return False
