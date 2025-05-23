"""
Theme management for the UI component library.
Provides consistent styling across components.
"""

import streamlit as st
from typing import Dict, Tuple, Any, Optional

# Default theme colors
DEFAULT_THEME = {
    # Primary colors
    "primary": "#1E88E5",
    "primary_light": "#90CAF9",
    "primary_dark": "#0D47A1",
    
    # Secondary colors
    "secondary": "#26A69A",
    "secondary_light": "#B2DFDB",
    "secondary_dark": "#00796B",
    
    # Accent colors
    "accent": "#FF5722",
    "accent_light": "#FFAB91",
    "accent_dark": "#BF360C",
    
    # Status colors
    "success": "#4CAF50",
    "warning": "#FFC107",
    "error": "#F44336",
    "info": "#2196F3",
    
    # Neutral colors
    "background": "#FFFFFF",
    "surface": "#F5F5F5",
    "border": "#DDDDDD",
    "text": "#212121",
    "text_secondary": "#757575",
    "disabled": "#9E9E9E",
    
    # Dark mode colors
    "dark_background": "#121212",
    "dark_surface": "#1E1E1E",
    "dark_border": "#333333",
    "dark_text": "#FFFFFF",
    "dark_text_secondary": "#AAAAAA",
}

# Current theme storage
if "ui_theme" not in st.session_state:
    st.session_state.ui_theme = DEFAULT_THEME.copy()

def get_theme_colors() -> Dict[str, str]:
    """
    Get the current theme colors.
    
    Returns:
        Dict of color names and hex values
    """
    return st.session_state.ui_theme.copy()

def set_theme_colors(theme: Dict[str, str]) -> None:
    """
    Set the theme colors.
    
    Args:
        theme: Dict of color names and hex values
    """
    st.session_state.ui_theme.update(theme)

def apply_theme(dark_mode: bool = False) -> None:
    """
    Apply the theme to the current page.
    
    Args:
        dark_mode: Whether to use dark mode
    """
    theme = get_theme_colors()
    
    # Determine background and text colors
    background = theme["dark_background"] if dark_mode else theme["background"]
    surface = theme["dark_surface"] if dark_mode else theme["surface"]
    text = theme["dark_text"] if dark_mode else theme["text"]
    text_secondary = theme["dark_text_secondary"] if dark_mode else theme["text_secondary"]
    
    # Apply CSS
    st.markdown(
        f"""
        <style>
        /* Base styles */
        .reportview-container .main .block-container {{
            padding-top: 1rem;
            padding-bottom: 1rem;
        }}
        
        /* Text styles */
        body {{
            color: {text};
            background-color: {background};
        }}
        
        h1, h2, h3, h4, h5, h6 {{
            color: {text};
        }}
        
        .css-hxt7ib {{
            padding-top: 2rem;
        }}
        
        /* Widget styling */
        .stButton>button {{
            background-color: {theme["primary"]};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 0.5rem 1rem;
        }}
        
        .stButton>button:hover {{
            background-color: {theme["primary_dark"]};
        }}
        
        /* Card styling */
        .card {{
            background-color: {surface};
            border-radius: 4px;
            padding: 1rem;
            margin-bottom: 1rem;
            border: 1px solid {theme["border"] if not dark_mode else theme["dark_border"]};
        }}
        
        .card-title {{
            color: {theme["primary"]};
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}
        
        .card-subtitle {{
            color: {text_secondary};
            font-size: 0.9rem;
            margin-bottom: 0.5rem;
        }}
        
        /* Metric styling */
        .metric-container {{
            text-align: center;
            padding: 0.5rem;
        }}
        
        .metric-value {{
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }}
        
        .metric-label {{
            color: {text_secondary};
            font-size: 0.9rem;
        }}
        
        .metric-change-positive {{
            color: {theme["success"]};
            font-size: 0.9rem;
        }}
        
        .metric-change-negative {{
            color: {theme["error"]};
            font-size: 0.9rem;
        }}
        
        /* Status indicator */
        .status-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 0.5rem;
        }}
        
        .status-success {{
            background-color: {theme["success"]};
        }}
        
        .status-warning {{
            background-color: {theme["warning"]};
        }}
        
        .status-error {{
            background-color: {theme["error"]};
        }}
        
        .status-info {{
            background-color: {theme["info"]};
        }}
        
        /* Progress bar styling */
        .custom-progress-container {{
            width: 100%;
            background-color: {theme["border"] if not dark_mode else theme["dark_border"]};
            border-radius: 4px;
            margin: 0.5rem 0;
        }}
        
        .custom-progress-bar {{
            height: 8px;
            border-radius: 4px;
        }}
        
        .custom-progress-label {{
            font-size: 0.8rem;
            color: {text_secondary};
            margin-top: 0.25rem;
        }}
        </style>
        """, 
        unsafe_allow_html=True
    )

def get_css_classes(dark_mode: bool = False) -> Dict[str, str]:
    """
    Get CSS classes for components.
    
    Args:
        dark_mode: Whether to use dark mode
    
    Returns:
        Dict of component names and CSS classes
    """
    theme = get_theme_colors()
    
    return {
        "card": "card",
        "card_title": "card-title",
        "card_subtitle": "card-subtitle",
        "metric_container": "metric-container",
        "metric_value": "metric-value",
        "metric_label": "metric-label",
        "metric_change_positive": "metric-change-positive",
        "metric_change_negative": "metric-change-negative",
        "status_indicator": "status-indicator",
        "status_success": "status-indicator status-success",
        "status_warning": "status-indicator status-warning",
        "status_error": "status-indicator status-error",
        "status_info": "status-indicator status-info",
        "progress_container": "custom-progress-container",
        "progress_bar": "custom-progress-bar",
        "progress_label": "custom-progress-label",
    }
