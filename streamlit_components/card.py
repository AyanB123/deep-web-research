"""
Card components for the UI component library.
Provides consistent card layouts for displaying content.
"""

import streamlit as st
from typing import Dict, List, Any, Optional, Callable
from streamlit_components.theme import get_css_classes

def render_card(
    title: str,
    content: Optional[Callable] = None,
    subtitle: Optional[str] = None,
    footer: Optional[Callable] = None,
    key: Optional[str] = None,
    is_expanded: bool = True,
    on_click: Optional[Callable] = None,
    border_color: Optional[str] = None
) -> None:
    """
    Render a card with title, content, and footer.
    
    Args:
        title: Card title
        content: Function to render card content (takes no args)
        subtitle: Optional subtitle
        footer: Function to render card footer (takes no args)
        key: Unique key for the card
        is_expanded: Whether the card is expanded by default
        on_click: Function to call when card is clicked
        border_color: Optional border color
    """
    # Generate unique key if not provided
    if key is None:
        import uuid
        key = f"card_{str(uuid.uuid4())[:8]}"
    
    # Get CSS classes
    css_classes = get_css_classes()
    
    # Custom border style
    border_style = ""
    if border_color:
        border_style = f"border-left: 4px solid {border_color};"
    
    # Render card container
    st.markdown(
        f"""
        <div class="{css_classes['card']}" style="{border_style}" id="{key}">
        """, 
        unsafe_allow_html=True
    )
    
    # Render title
    st.markdown(
        f"""
        <div class="{css_classes['card_title']}">{title}</div>
        """, 
        unsafe_allow_html=True
    )
    
    # Render subtitle if provided
    if subtitle:
        st.markdown(
            f"""
            <div class="{css_classes['card_subtitle']}">{subtitle}</div>
            """, 
            unsafe_allow_html=True
        )
    
    # Render content
    if content:
        content()
    
    # Render footer
    if footer:
        st.markdown("<hr style='margin: 0.5rem 0'>", unsafe_allow_html=True)
        footer()
    
    # Close card container
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Add click handler if provided
    if on_click:
        st.markdown(
            f"""
            <script>
                document.getElementById("{key}").addEventListener("click", function() {{
                    // Send message to Streamlit
                    window.parent.postMessage({{
                        type: "card_click",
                        key: "{key}"
                    }}, "*");
                }});
            </script>
            """,
            unsafe_allow_html=True
        )


def render_stat_card(
    title: str,
    value: Any,
    subtitle: Optional[str] = None,
    delta: Optional[float] = None,
    delta_description: Optional[str] = None,
    is_currency: bool = False,
    is_percentage: bool = False,
    key: Optional[str] = None,
    color: Optional[str] = None
) -> None:
    """
    Render a card with a statistic/metric value.
    
    Args:
        title: Metric title
        value: Metric value
        subtitle: Optional subtitle
        delta: Optional change value (positive or negative)
        delta_description: Optional description for delta
        is_currency: Whether the value is a currency
        is_percentage: Whether the value is a percentage
        key: Unique key for the card
        color: Optional color for the value
    """
    # Format value
    formatted_value = value
    if is_currency:
        try:
            formatted_value = f"${float(value):,.2f}"
        except (ValueError, TypeError):
            pass
    elif is_percentage:
        try:
            formatted_value = f"{float(value):.1f}%"
        except (ValueError, TypeError):
            pass
    
    # Define content renderer
    def render_content():
        # Get CSS classes
        css_classes = get_css_classes()
        
        # Value style
        value_style = ""
        if color:
            value_style = f"color: {color};"
        
        # Render value
        st.markdown(
            f"""
            <div class="{css_classes['metric_value']}" style="{value_style}">{formatted_value}</div>
            """, 
            unsafe_allow_html=True
        )
        
        # Render delta if provided
        if delta is not None:
            # Determine class
            delta_class = css_classes['metric_change_positive'] if delta >= 0 else css_classes['metric_change_negative']
            
            # Format delta
            delta_prefix = "+" if delta > 0 else ""
            formatted_delta = f"{delta_prefix}{delta:.1f}%" if is_percentage else f"{delta_prefix}{delta}"
            
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
    
    # Render card with content
    render_card(title, render_content, subtitle, key=key, border_color=color)


def render_link_card(
    title: str,
    url: str,
    description: Optional[str] = None,
    icon: Optional[str] = None,
    open_in_new_tab: bool = True,
    key: Optional[str] = None
) -> None:
    """
    Render a card with a link.
    
    Args:
        title: Link title
        url: URL to link to
        description: Optional description
        icon: Optional icon (emoji or URL)
        open_in_new_tab: Whether to open link in new tab
        key: Unique key for the card
    """
    # Define content renderer
    def render_content():
        # Icon display
        icon_html = ""
        if icon:
            if icon.startswith(("http://", "https://")):
                # URL icon
                icon_html = f'<img src="{icon}" style="height: 24px; margin-right: 0.5rem; vertical-align: middle;">'
            else:
                # Emoji or text icon
                icon_html = f'<span style="margin-right: 0.5rem; font-size: 1.2rem;">{icon}</span>'
        
        # Target attribute
        target = '_blank' if open_in_new_tab else '_self'
        
        # Render link
        st.markdown(
            f"""
            <a href="{url}" target="{target}" style="text-decoration: none; color: inherit;">
                <div style="display: flex; align-items: center;">
                    {icon_html}<span>{url}</span>
                </div>
            </a>
            """, 
            unsafe_allow_html=True
        )
        
        # Render description if provided
        if description:
            st.markdown(
                f"""
                <div style="margin-top: 0.5rem; font-size: 0.9rem; color: #666;">{description}</div>
                """, 
                unsafe_allow_html=True
            )
    
    # Render card with content
    render_card(title, render_content, key=key)
