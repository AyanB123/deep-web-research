"""
Status components for the UI component library.
Provides status indicators and progress bars.
"""

import streamlit as st
from typing import Dict, List, Any, Optional, Union
from streamlit_components.theme import get_css_classes, get_theme_colors

def render_status_indicator(
    status: str,
    label: Optional[str] = None,
    tooltip: Optional[str] = None,
    size: str = "medium"  # "small", "medium", "large"
) -> None:
    """
    Render a status indicator with optional label.
    
    Args:
        status: Status type ("success", "warning", "error", "info")
        label: Optional status label
        tooltip: Optional tooltip on hover
        size: Size of the indicator
    """
    # Get CSS classes
    css_classes = get_css_classes()
    
    # Determine status class
    status_class = css_classes.get(f"status_{status.lower()}", css_classes["status_info"])
    
    # Determine size in pixels
    sizes = {
        "small": "8px",
        "medium": "12px",
        "large": "16px"
    }
    pixel_size = sizes.get(size, sizes["medium"])
    
    # Build indicator HTML
    indicator_html = f"""
    <div style="display: flex; align-items: center;">
        <div class="{status_class}" style="width: {pixel_size}; height: {pixel_size};"
        title="{tooltip if tooltip else ''}"></div>
    """
    
    # Add label if provided
    if label:
        indicator_html += f"""
        <span style="margin-left: 0.5rem;">{label}</span>
        """
    
    # Close container
    indicator_html += "</div>"
    
    # Render indicator
    st.markdown(indicator_html, unsafe_allow_html=True)


def render_progress(
    value: float,
    label: Optional[str] = None,
    description: Optional[str] = None,
    min_value: float = 0.0,
    max_value: float = 100.0,
    color: Optional[str] = None,
    height: str = "8px",
    show_percentage: bool = True,
    animate: bool = False
) -> None:
    """
    Render a custom progress bar.
    
    Args:
        value: Current progress value
        label: Optional label above progress bar
        description: Optional description below progress bar
        min_value: Minimum value (default: 0)
        max_value: Maximum value (default: 100)
        color: Progress bar color (default: primary color)
        height: Height of the progress bar
        show_percentage: Whether to show percentage value
        animate: Whether to add animation
    """
    # Get CSS classes and theme
    css_classes = get_css_classes()
    theme = get_theme_colors()
    
    # Calculate percentage
    total_range = max_value - min_value
    if total_range <= 0:
        percentage = 0
    else:
        percentage = ((value - min_value) / total_range) * 100
        percentage = max(0, min(100, percentage))
    
    # Determine color
    if color is None:
        # Use color based on percentage
        if percentage < 25:
            color = theme["error"]
        elif percentage < 50:
            color = theme["warning"]
        elif percentage < 75:
            color = theme["info"]
        else:
            color = theme["success"]
    
    # Animation CSS
    animation_css = ""
    if animate:
        animation_css = """
        @keyframes progress-animation {
            0% { opacity: 0.6; }
            50% { opacity: 1; }
            100% { opacity: 0.6; }
        }
        """
        animation_style = "animation: progress-animation 2s infinite;"
    else:
        animation_style = ""
    
    # Render label if provided
    if label:
        if show_percentage:
            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                    <div>{label}</div>
                    <div>{percentage:.1f}%</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            st.markdown(f"<div style='margin-bottom: 0.25rem;'>{label}</div>", unsafe_allow_html=True)
    elif show_percentage:
        st.markdown(
            f"<div style='text-align: right; margin-bottom: 0.25rem;'>{percentage:.1f}%</div>",
            unsafe_allow_html=True
        )
    
    # Render progress bar
    st.markdown(
        f"""
        <style>
        {animation_css}
        </style>
        
        <div class="{css_classes['progress_container']}">
            <div class="{css_classes['progress_bar']}" style="width: {percentage}%; 
            background-color: {color}; height: {height}; {animation_style}"></div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Render description if provided
    if description:
        st.markdown(
            f"<div class='{css_classes['progress_label']}'>{description}</div>",
            unsafe_allow_html=True
        )


def render_status_timeline(
    steps: List[Dict[str, Any]],
    current_step: int,
    show_time: bool = True
) -> None:
    """
    Render a timeline of status steps.
    
    Args:
        steps: List of step dictionaries, each with:
            - label: Step label
            - status: Step status ("success", "warning", "error", "info", "pending")
            - description (optional): Step description
            - time (optional): Time for the step
        current_step: Index of the current step (0-based)
        show_time: Whether to show time for each step
    """
    theme = get_theme_colors()
    
    # Status colors
    status_colors = {
        "success": theme["success"],
        "warning": theme["warning"],
        "error": theme["error"],
        "info": theme["info"],
        "pending": theme["disabled"]
    }
    
    # Render timeline
    st.markdown(
        """
        <div style="margin: 1rem 0;">
        """,
        unsafe_allow_html=True
    )
    
    for i, step in enumerate(steps):
        # Get step details
        label = step.get("label", f"Step {i+1}")
        status = step.get("status", "pending")
        description = step.get("description", "")
        time = step.get("time", "")
        
        # Determine color
        color = status_colors.get(status.lower(), status_colors["pending"])
        
        # Determine if completed, current, or pending
        if i < current_step:
            # Completed step
            icon = "✓"
            text_color = theme["success"]
            line_color = theme["success"]
            line_style = "solid"
        elif i == current_step:
            # Current step
            icon = "•"
            text_color = color
            line_color = color
            line_style = "solid"
        else:
            # Pending step
            icon = "○"
            text_color = theme["disabled"]
            line_color = theme["disabled"]
            line_style = "dashed"
        
        # Render step
        st.markdown(
            f"""
            <div style="display: flex; margin-bottom: 1rem;">
                <!-- Timeline indicator -->
                <div style="display: flex; flex-direction: column; align-items: center; margin-right: 1rem;">
                    <div style="width: 24px; height: 24px; border-radius: 50%; background-color: {color if i <= current_step else 'white'}; 
                    border: 2px solid {color}; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">
                        {icon}
                    </div>
                    {'' if i == len(steps) - 1 else f'<div style="width: 2px; background-color: {line_color}; height: 100%; margin-top: 0.25rem; border-left: 2px {line_style} {line_color};"></div>'}
                </div>
                
                <!-- Step content -->
                <div style="flex: 1;">
                    <div style="display: flex; justify-content: space-between;">
                        <div style="font-weight: 500; color: {text_color};">{label}</div>
                        {f'<div style="color: {theme["text_secondary"]}; font-size: 0.8rem;">{time}</div>' if show_time and time else ''}
                    </div>
                    {f'<div style="color: {theme["text_secondary"]}; font-size: 0.9rem; margin-top: 0.25rem;">{description}</div>' if description else ''}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Close container
    st.markdown("</div>", unsafe_allow_html=True)
