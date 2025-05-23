"""
Metric components for the UI component library.
Provides consistent metrics display for statistics and KPIs.
"""

import streamlit as st
from typing import Dict, List, Any, Optional, Union, Tuple
from streamlit_components.theme import get_css_classes, get_theme_colors

def render_metric(
    label: str,
    value: Any,
    delta: Optional[Union[float, int]] = None,
    delta_description: Optional[str] = None,
    prefix: Optional[str] = None,
    suffix: Optional[str] = None,
    color: Optional[str] = None,
    help_text: Optional[str] = None,
    size: str = "medium"  # "small", "medium", "large"
) -> None:
    """
    Render a metric with label, value, and optional delta.
    
    Args:
        label: Metric label
        value: Metric value
        delta: Optional delta value (change)
        delta_description: Optional description for delta
        prefix: Optional prefix for value (e.g., "$")
        suffix: Optional suffix for value (e.g., "%")
        color: Optional color for value
        help_text: Optional help text shown on hover
        size: Size of the metric (small, medium, large)
    """
    # Get CSS classes
    css_classes = get_css_classes()
    
    # Format value
    formatted_value = str(value)
    if prefix:
        formatted_value = f"{prefix}{formatted_value}"
    if suffix:
        formatted_value = f"{formatted_value}{suffix}"
    
    # Determine font sizes based on size
    value_sizes = {
        "small": "1.4rem",
        "medium": "1.8rem",
        "large": "2.2rem"
    }
    label_sizes = {
        "small": "0.8rem",
        "medium": "0.9rem",
        "large": "1rem"
    }
    value_size = value_sizes.get(size, value_sizes["medium"])
    label_size = label_sizes.get(size, label_sizes["medium"])
    
    # Value style
    value_style = f"font-size: {value_size};"
    if color:
        value_style += f"color: {color};"
    
    # Container
    st.markdown(
        f"""
        <div class="{css_classes['metric_container']}">
        """, 
        unsafe_allow_html=True
    )
    
    # Value
    st.markdown(
        f"""
        <div class="{css_classes['metric_value']}" style="{value_style}"
        title="{help_text if help_text else ''}">{formatted_value}</div>
        """, 
        unsafe_allow_html=True
    )
    
    # Delta if provided
    if delta is not None:
        # Determine class
        delta_class = css_classes['metric_change_positive'] if delta >= 0 else css_classes['metric_change_negative']
        
        # Format delta
        delta_prefix = "+" if delta > 0 else ""
        formatted_delta = f"{delta_prefix}{delta}"
        
        # Add description if provided
        if delta_description:
            formatted_delta = f"{formatted_delta} {delta_description}"
        
        # Render delta
        st.markdown(
            f"""
            <div class="{delta_class}">{formatted_delta}</div>
            """, 
            unsafe_allow_html=True
        )
    
    # Label
    st.markdown(
        f"""
        <div class="{css_classes['metric_label']}" style="font-size: {label_size};">{label}</div>
        """, 
        unsafe_allow_html=True
    )
    
    # Close container
    st.markdown("</div>", unsafe_allow_html=True)


def render_metric_group(
    metrics: List[Dict[str, Any]],
    columns: Optional[int] = None
) -> None:
    """
    Render a group of metrics in columns.
    
    Args:
        metrics: List of metric dictionaries, each with:
            - label: Metric label
            - value: Metric value
            - delta (optional): Delta value
            - delta_description (optional): Description for delta
            - prefix (optional): Value prefix
            - suffix (optional): Value suffix
            - color (optional): Value color
            - help_text (optional): Help text on hover
            - size (optional): Size of metric
        columns: Number of columns (auto-calculated if None)
    """
    # Determine number of columns if not provided
    if columns is None:
        if len(metrics) <= 2:
            columns = len(metrics)
        elif len(metrics) <= 4:
            columns = 2
        else:
            columns = 3
    
    # Create columns
    cols = st.columns(columns)
    
    # Render metrics
    for i, metric in enumerate(metrics):
        with cols[i % columns]:
            render_metric(
                label=metric.get("label", ""),
                value=metric.get("value", ""),
                delta=metric.get("delta"),
                delta_description=metric.get("delta_description"),
                prefix=metric.get("prefix"),
                suffix=metric.get("suffix"),
                color=metric.get("color"),
                help_text=metric.get("help_text"),
                size=metric.get("size", "medium")
            )


def render_value_comparison(
    title: str,
    value1: Any,
    value2: Any,
    label1: str,
    label2: str,
    is_percentage: bool = False,
    color1: Optional[str] = None,
    color2: Optional[str] = None,
    description: Optional[str] = None
) -> None:
    """
    Render a comparison between two values with a horizontal bar.
    
    Args:
        title: Comparison title
        value1: First value
        value2: Second value
        label1: Label for first value
        label2: Label for second value
        is_percentage: Whether values are percentages
        color1: Color for first value
        color2: Color for second value
        description: Optional description
    """
    theme = get_theme_colors()
    
    # Default colors
    if color1 is None:
        color1 = theme["primary"]
    if color2 is None:
        color2 = theme["secondary"]
    
    # Convert values to float
    try:
        float_value1 = float(value1)
        float_value2 = float(value2)
        total = float_value1 + float_value2
    except (ValueError, TypeError):
        st.error(f"Cannot compare non-numeric values: {value1} and {value2}")
        return
    
    # Calculate percentages for bar
    if total > 0:
        percent1 = (float_value1 / total) * 100
        percent2 = (float_value2 / total) * 100
    else:
        percent1 = 50
        percent2 = 50
    
    # Format values
    if is_percentage:
        formatted_value1 = f"{float_value1:.1f}%"
        formatted_value2 = f"{float_value2:.1f}%"
    else:
        formatted_value1 = f"{float_value1:,.0f}"
        formatted_value2 = f"{float_value2:,.0f}"
    
    # Render component
    st.markdown(f"**{title}**")
    
    if description:
        st.markdown(f"<small>{description}</small>", unsafe_allow_html=True)
    
    # Render bar
    st.markdown(
        f"""
        <div style="margin: 0.5rem 0;">
            <div style="display: flex; height: 24px; border-radius: 4px; overflow: hidden;">
                <div style="width: {percent1}%; background-color: {color1}; display: flex; align-items: center; justify-content: center;">
                    <span style="color: white; font-size: 0.8rem; white-space: nowrap; padding: 0 0.5rem;">
                        {formatted_value1}
                    </span>
                </div>
                <div style="width: {percent2}%; background-color: {color2}; display: flex; align-items: center; justify-content: center;">
                    <span style="color: white; font-size: 0.8rem; white-space: nowrap; padding: 0 0.5rem;">
                        {formatted_value2}
                    </span>
                </div>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 0.25rem;">
                <div style="font-size: 0.8rem; color: {color1};">{label1}</div>
                <div style="font-size: 0.8rem; color: {color2};">{label2}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
