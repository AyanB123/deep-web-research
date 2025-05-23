"""
Layout components for the UI component library.
Provides consistent layout elements for streamlit apps.
"""

import streamlit as st
from typing import Dict, List, Any, Optional, Callable, Tuple, Union

def create_layout_columns(ratios: List[int] = None) -> List:
    """
    Create columns with specified width ratios.
    
    Args:
        ratios: List of relative width ratios (e.g., [1, 2, 1] for 25%, 50%, 25%)
                If None, equal width columns are created
    
    Returns:
        List of column objects
    """
    if not ratios:
        # Default to 3 equal columns
        ratios = [1, 1, 1]
    
    # Create columns based on ratios
    columns = st.columns(ratios)
    return columns

def create_sidebar_section(title: str, content_func: Callable, expanded: bool = True) -> None:
    """
    Create a collapsible section in the sidebar.
    
    Args:
        title: Section title
        content_func: Function to render section content
        expanded: Whether the section is expanded by default
    """
    with st.sidebar.expander(title, expanded=expanded):
        content_func()

def create_tabs(tab_titles: List[str]) -> List:
    """
    Create tabs with specified titles.
    
    Args:
        tab_titles: List of tab titles
    
    Returns:
        List of tab objects
    """
    return st.tabs(tab_titles)

def create_grid(items: List[Any], columns: int = 3, render_func: Callable = None) -> None:
    """
    Create a responsive grid layout for displaying items.
    
    Args:
        items: List of items to display
        columns: Number of columns in the grid
        render_func: Function to render each item (takes item as argument)
    """
    # Create rows based on number of items and columns
    rows = (len(items) + columns - 1) // columns
    
    for row in range(rows):
        # Create columns for this row
        cols = st.columns(columns)
        
        for col in range(columns):
            idx = row * columns + col
            if idx < len(items):
                with cols[col]:
                    if render_func:
                        render_func(items[idx])
                    else:
                        st.write(items[idx])

def create_two_column_layout(
    left_content: Callable, 
    right_content: Callable,
    left_width: int = 1,
    right_width: int = 1
) -> None:
    """
    Create a two-column layout with specified content.
    
    Args:
        left_content: Function to render left column content
        right_content: Function to render right column content
        left_width: Relative width of left column
        right_width: Relative width of right column
    """
    col1, col2 = st.columns([left_width, right_width])
    
    with col1:
        left_content()
    
    with col2:
        right_content()

def create_container(
    content_func: Callable,
    border: bool = False,
    padding: str = "1rem",
    background_color: Optional[str] = None,
    border_color: Optional[str] = None,
    border_radius: str = "0.5rem",
    margin: str = "0 0 1rem 0"
) -> None:
    """
    Create a styled container for content.
    
    Args:
        content_func: Function to render container content
        border: Whether to add a border
        padding: CSS padding value
        background_color: Optional background color
        border_color: Optional border color
        border_radius: CSS border radius value
        margin: CSS margin value
    """
    # Build style
    style = f"padding: {padding}; border-radius: {border_radius}; margin: {margin};"
    
    if border:
        style += f" border: 1px solid {border_color or '#ddd'};"
    
    if background_color:
        style += f" background-color: {background_color};"
    
    # Create container with style
    container_html = f"<div style='{style}'>"
    st.markdown(container_html, unsafe_allow_html=True)
    
    # Render content
    content_func()
    
    # Close container
    st.markdown("</div>", unsafe_allow_html=True)

def create_divider(margin: str = "1rem 0") -> None:
    """
    Create a horizontal divider.
    
    Args:
        margin: CSS margin value
    """
    st.markdown(f"<hr style='margin: {margin}; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)

def create_responsive_sidebar(content_func: Callable, min_width: int = 768) -> None:
    """
    Create a responsive sidebar that converts to a hamburger menu on small screens.
    
    Args:
        content_func: Function to render sidebar content
        min_width: Minimum width in pixels for desktop layout
    """
    # Add custom CSS for responsive sidebar
    st.markdown(
        f"""
        <style>
        @media (max-width: {min_width}px) {{
            .sidebar .sidebar-content {{
                position: absolute;
                top: 0;
                left: 0;
                transform: translateX(-100%);
                transition: transform 0.3s ease-in-out;
                z-index: 1000;
                background: white;
                height: 100vh;
                box-shadow: 2px 0 5px rgba(0,0,0,0.1);
            }}
            
            .sidebar.open .sidebar-content {{
                transform: translateX(0);
            }}
            
            .hamburger-menu {{
                display: block;
                position: fixed;
                top: 1rem;
                left: 1rem;
                z-index: 1001;
                background: white;
                border-radius: 4px;
                padding: 0.5rem;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
        }}
        
        @media (min-width: {min_width + 1}px) {{
            .hamburger-menu {{
                display: none;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True
    )
    
    # Add hamburger menu button
    st.markdown(
        """
        <div class="hamburger-menu" onclick="toggleSidebar()">
            <svg width="24" height="24" viewBox="0 0 24 24">
                <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"></path>
            </svg>
        </div>
        
        <script>
        function toggleSidebar() {
            const sidebar = document.querySelector('.sidebar');
            sidebar.classList.toggle('open');
        }
        </script>
        """,
        unsafe_allow_html=True
    )
    
    # Render sidebar content
    with st.sidebar:
        content_func()
