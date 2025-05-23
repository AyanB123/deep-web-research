"""
Query Builder UI components for the Dark Web Discovery System.
Provides a visual interface for building complex queries.
"""

import streamlit as st
import datetime
import uuid
from typing import Dict, List, Any, Optional, Callable

from query_builder import QueryBuilder, FilterGroup, FilterCondition, FilterOperator, LogicalOperator
from streamlit_components.card import render_card

class QueryBuilderUI:
    """
    UI component for building complex queries.
    Provides a visual interface for creating filter conditions.
    """
    
    def __init__(self, key_prefix: str = "query_builder"):
        """
        Initialize the query builder UI.
        
        Args:
            key_prefix: Prefix for session state keys
        """
        self.key_prefix = key_prefix
        
        # Available fields with metadata
        self.fields = {
            "url": {"label": "URL", "type": "text"},
            "title": {"label": "Title", "type": "text"},
            "content": {"label": "Content", "type": "text"},
            "status": {"label": "Status", "type": "select", "options": ["active", "inactive", "pending", "error"]},
            "discovery_date": {"label": "Discovery Date", "type": "date"},
            "last_crawled": {"label": "Last Crawled", "type": "date"},
            "category": {"label": "Category", "type": "text"},
            "is_active": {"label": "Is Active", "type": "boolean"},
            "http_status": {"label": "HTTP Status", "type": "number"}
        }
        
        # Map field types to compatible operators
        self.type_operators = {
            "text": [
                FilterOperator.EQUALS,
                FilterOperator.NOT_EQUALS,
                FilterOperator.CONTAINS,
                FilterOperator.NOT_CONTAINS,
                FilterOperator.STARTS_WITH,
                FilterOperator.ENDS_WITH,
                FilterOperator.IS_NULL,
                FilterOperator.IS_NOT_NULL,
                FilterOperator.REGEX
            ],
            "number": [
                FilterOperator.EQUALS,
                FilterOperator.NOT_EQUALS,
                FilterOperator.GREATER_THAN,
                FilterOperator.LESS_THAN,
                FilterOperator.BETWEEN,
                FilterOperator.IS_NULL,
                FilterOperator.IS_NOT_NULL
            ],
            "date": [
                FilterOperator.EQUALS,
                FilterOperator.NOT_EQUALS,
                FilterOperator.GREATER_THAN,
                FilterOperator.LESS_THAN,
                FilterOperator.BETWEEN,
                FilterOperator.IS_NULL,
                FilterOperator.IS_NOT_NULL
            ],
            "boolean": [
                FilterOperator.EQUALS,
                FilterOperator.NOT_EQUALS
            ],
            "select": [
                FilterOperator.EQUALS,
                FilterOperator.NOT_EQUALS,
                FilterOperator.IN_LIST,
                FilterOperator.NOT_IN_LIST,
                FilterOperator.IS_NULL,
                FilterOperator.IS_NOT_NULL
            ]
        }
        
        # Initialize state if needed
        self._initialize_state()
    
    def _initialize_state(self):
        """Initialize session state for the query builder."""
        # Create condition state keys
        conditions_key = f"{self.key_prefix}_conditions"
        if conditions_key not in st.session_state:
            st.session_state[conditions_key] = []
        
        # Create group state keys
        groups_key = f"{self.key_prefix}_groups"
        if groups_key not in st.session_state:
            st.session_state[groups_key] = []
        
        # Root group operator
        root_operator_key = f"{self.key_prefix}_root_operator"
        if root_operator_key not in st.session_state:
            st.session_state[root_operator_key] = LogicalOperator.AND
    
    def _get_operator_label(self, operator: FilterOperator) -> str:
        """Get a user-friendly label for an operator."""
        labels = {
            FilterOperator.EQUALS: "Equals",
            FilterOperator.NOT_EQUALS: "Not Equals",
            FilterOperator.CONTAINS: "Contains",
            FilterOperator.NOT_CONTAINS: "Does Not Contain",
            FilterOperator.STARTS_WITH: "Starts With",
            FilterOperator.ENDS_WITH: "Ends With",
            FilterOperator.GREATER_THAN: "Greater Than",
            FilterOperator.LESS_THAN: "Less Than",
            FilterOperator.BETWEEN: "Between",
            FilterOperator.IN_LIST: "In List",
            FilterOperator.NOT_IN_LIST: "Not In List",
            FilterOperator.IS_NULL: "Is Empty",
            FilterOperator.IS_NOT_NULL: "Is Not Empty",
            FilterOperator.REGEX: "Matches Pattern"
        }
        return labels.get(operator, str(operator))
    
    def _get_logical_operator_label(self, operator: LogicalOperator) -> str:
        """Get a user-friendly label for a logical operator."""
        labels = {
            LogicalOperator.AND: "AND (All Conditions Must Match)",
            LogicalOperator.OR: "OR (Any Condition Can Match)",
            LogicalOperator.NOT: "NOT (Exclude Matches)"
        }
        return labels.get(operator, str(operator))
    
    def _render_condition_input(self, condition: Dict[str, Any], index: int) -> None:
        """
        Render inputs for a filter condition.
        
        Args:
            condition: Condition data
            index: Condition index
        """
        col1, col2, col3, col4 = st.columns([3, 3, 4, 1])
        
        with col1:
            # Field selector
            field = st.selectbox(
                "Field",
                options=list(self.fields.keys()),
                format_func=lambda x: self.fields[x]["label"],
                key=f"{self.key_prefix}_condition_{index}_field",
                index=list(self.fields.keys()).index(condition["field"]) if condition["field"] in self.fields else 0
            )
            
            condition["field"] = field
            field_type = self.fields[field]["type"]
        
        with col2:
            # Operator selector based on field type
            valid_operators = self.type_operators.get(field_type, [])
            operator_options = [op.value for op in valid_operators]
            operator_labels = [self._get_operator_label(op) for op in valid_operators]
            
            operator_index = 0
            if condition["operator"] in operator_options:
                operator_index = operator_options.index(condition["operator"])
            
            operator = st.selectbox(
                "Operator",
                options=operator_options,
                format_func=lambda x: self._get_operator_label(FilterOperator(x)),
                key=f"{self.key_prefix}_condition_{index}_operator",
                index=operator_index
            )
            
            condition["operator"] = operator
        
        with col3:
            # Value input based on field type and operator
            if operator not in [FilterOperator.IS_NULL.value, FilterOperator.IS_NOT_NULL.value]:
                if field_type == "text":
                    condition["value"] = st.text_input(
                        "Value",
                        value=condition.get("value", ""),
                        key=f"{self.key_prefix}_condition_{index}_value"
                    )
                
                elif field_type == "number":
                    if operator == FilterOperator.BETWEEN.value:
                        col_a, col_b = st.columns(2)
                        with col_a:
                            condition["value"] = st.number_input(
                                "From",
                                value=float(condition.get("value", 0)),
                                key=f"{self.key_prefix}_condition_{index}_value1"
                            )
                        with col_b:
                            condition["value2"] = st.number_input(
                                "To",
                                value=float(condition.get("value2", 0)),
                                key=f"{self.key_prefix}_condition_{index}_value2"
                            )
                    else:
                        condition["value"] = st.number_input(
                            "Value",
                            value=float(condition.get("value", 0)),
                            key=f"{self.key_prefix}_condition_{index}_value"
                        )
                
                elif field_type == "date":
                    if operator == FilterOperator.BETWEEN.value:
                        col_a, col_b = st.columns(2)
                        with col_a:
                            condition["value"] = st.date_input(
                                "From",
                                value=datetime.datetime.now().date(),
                                key=f"{self.key_prefix}_condition_{index}_value1"
                            ).isoformat()
                        with col_b:
                            condition["value2"] = st.date_input(
                                "To",
                                value=datetime.datetime.now().date(),
                                key=f"{self.key_prefix}_condition_{index}_value2"
                            ).isoformat()
                    else:
                        condition["value"] = st.date_input(
                            "Value",
                            value=datetime.datetime.now().date(),
                            key=f"{self.key_prefix}_condition_{index}_value"
                        ).isoformat()
                
                elif field_type == "boolean":
                    condition["value"] = st.checkbox(
                        "Value",
                        value=bool(condition.get("value", False)),
                        key=f"{self.key_prefix}_condition_{index}_value"
                    )
                
                elif field_type == "select":
                    if operator in [FilterOperator.IN_LIST.value, FilterOperator.NOT_IN_LIST.value]:
                        options = self.fields[field].get("options", [])
                        condition["value"] = st.multiselect(
                            "Values",
                            options=options,
                            default=condition.get("value", []),
                            key=f"{self.key_prefix}_condition_{index}_value"
                        )
                    else:
                        options = self.fields[field].get("options", [])
                        condition["value"] = st.selectbox(
                            "Value",
                            options=options,
                            index=options.index(condition.get("value", options[0])) if condition.get("value") in options else 0,
                            key=f"{self.key_prefix}_condition_{index}_value"
                        )
        
        with col4:
            # Remove button
            if st.button("🗑️", key=f"{self.key_prefix}_remove_condition_{index}"):
                conditions = st.session_state[f"{self.key_prefix}_conditions"]
                if index < len(conditions):
                    conditions.pop(index)
                    st.rerun()
    
    def _render_group_operator(self) -> None:
        """Render the logical operator selector for the root group."""
        st.selectbox(
            "Match",
            options=[op.value for op in LogicalOperator],
            format_func=lambda x: self._get_logical_operator_label(LogicalOperator(x)),
            key=f"{self.key_prefix}_root_operator",
            index=[op.value for op in LogicalOperator].index(st.session_state[f"{self.key_prefix}_root_operator"])
        )
    
    def render(self) -> None:
        """Render the query builder UI."""
        with st.container():
            # Title and description
            st.markdown("### Advanced Query Builder")
            st.markdown("Build complex queries to search for onion links.")
            
            # Logical operator for root group
            self._render_group_operator()
            
            # Render conditions
            conditions = st.session_state[f"{self.key_prefix}_conditions"]
            for i, condition in enumerate(conditions):
                render_card(
                    title=f"Condition {i+1}",
                    content=lambda i=i, c=condition: self._render_condition_input(c, i),
                    border_color="#007bff"
                )
            
            # Add condition button
            if st.button("➕ Add Condition", key=f"{self.key_prefix}_add_condition"):
                # Create a new condition with defaults
                new_condition = {
                    "field": next(iter(self.fields.keys())),
                    "operator": FilterOperator.EQUALS.value,
                    "value": None
                }
                conditions.append(new_condition)
                st.rerun()
            
            # Spacer
            st.markdown("---")
    
    def build_query(self) -> QueryBuilder:
        """
        Build a query from the UI state.
        
        Returns:
            QueryBuilder object
        """
        query = QueryBuilder()
        
        # Get conditions and root operator
        conditions = st.session_state[f"{self.key_prefix}_conditions"]
        root_operator = LogicalOperator(st.session_state[f"{self.key_prefix}_root_operator"])
        
        # Set root operator
        query.filter_group.operator = root_operator
        
        # Add conditions to query
        for condition in conditions:
            field = condition["field"]
            operator = FilterOperator(condition["operator"])
            value = condition.get("value")
            value2 = condition.get("value2")
            
            query.filter(field, operator, value, value2)
        
        return query

def render_query_preview(query_builder: QueryBuilder) -> None:
    """
    Render a preview of the query.
    
    Args:
        query_builder: Query builder object
    """
    with st.expander("Query Preview", expanded=False):
        # Build the query
        query_dict = query_builder.build()
        
        # Show as JSON
        st.json(query_dict)

def render_search_results(results: Dict[str, Any]) -> None:
    """
    Render search results.
    
    Args:
        results: Search results from SearchService
    """
    if not results:
        st.info("No results to display. Run a search to see results here.")
        return
    
    # Check for success
    if not results.get("success", False):
        st.error(f"Error: {results.get('error', 'Unknown error')}")
        return
    
    # Show result count
    total_count = results.get("total_count", 0)
    result_items = results.get("results", [])
    
    st.markdown(f"### Found {total_count:,} results")
    
    # Pagination info
    limit = results.get("limit", 10)
    offset = results.get("offset", 0)
    current_page = results.get("page", 1)
    total_pages = results.get("total_pages", 1)
    
    if total_pages > 1:
        st.markdown(f"Showing page {current_page} of {total_pages}")
    
    # Show results
    for item in result_items:
        render_card(
            title=item.get("title", "No Title"),
            subtitle=item.get("url", ""),
            content=lambda item=item: st.markdown(
                f"""
                **Status:** {item.get('status', 'Unknown')}  
                **Last Crawled:** {item.get('last_crawled', 'Never')}  
                **Discovery Date:** {item.get('discovery_date', 'Unknown')}
                
                {item.get('content', '')[:200]}...
                """
            ),
            footer=lambda item=item: st.button(
                "View Details", 
                key=f"view_{item.get('id', uuid.uuid4())}"
            ),
            border_color="#28a745" if item.get("is_active") else "#dc3545"
        )
    
    # Pagination controls
    if total_pages > 1:
        col1, col2, col3 = st.columns([1, 3, 1])
        
        with col1:
            if current_page > 1:
                st.button("◀️ Previous", key="prev_page")
        
        with col2:
            # Page selector
            page_numbers = list(range(1, total_pages + 1))
            st.select_slider(
                "Page",
                options=page_numbers,
                value=current_page,
                key="page_slider"
            )
        
        with col3:
            if current_page < total_pages:
                st.button("Next ▶️", key="next_page")

def render_saved_searches(searches: List[Dict[str, Any]], on_select: Callable[[str], None]) -> None:
    """
    Render saved searches.
    
    Args:
        searches: List of saved searches
        on_select: Callback when a search is selected
    """
    if not searches:
        st.info("No saved searches. Save a search to see it here.")
        return
    
    # Show as a table
    st.markdown("### Saved Searches")
    
    for search in searches:
        col1, col2 = st.columns([4, 1])
        
        with col1:
            st.markdown(f"**{search['name']}**")
            if search.get("description"):
                st.markdown(f"_{search['description']}_")
            
            created = search.get("created", "")
            if created:
                st.markdown(f"Created: {created}")
        
        with col2:
            if st.button("Load", key=f"load_{search['name']}"):
                on_select(search["name"])

def render_search_templates(templates: List[Dict[str, Any]], on_select: Callable[[str, Dict[str, Any]], None]) -> None:
    """
    Render search templates.
    
    Args:
        templates: List of search templates
        on_select: Callback when a template is selected with parameters
    """
    if not templates:
        st.info("No search templates available.")
        return
    
    st.markdown("### Search Templates")
    
    # Template selector
    template_names = [t["name"] for t in templates]
    selected_template = st.selectbox("Select Template", template_names)
    
    # Find selected template
    template = next((t for t in templates if t["name"] == selected_template), None)
    if not template:
        return
    
    # Show description
    if template.get("description"):
        st.markdown(f"_{template['description']}_")
    
    # Parameter inputs
    parameters = {}
    if template.get("parameters"):
        st.markdown("#### Parameters")
        
        for param_name, param_info in template["parameters"].items():
            param_type = param_info.get("type", "string")
            default_value = param_info.get("default")
            description = param_info.get("description", "")
            
            # Input based on type
            if param_type == "string" or param_type == "text":
                parameters[param_name] = st.text_input(
                    param_info.get("name", param_name),
                    value=default_value or "",
                    help=description
                )
            
            elif param_type == "number":
                parameters[param_name] = st.number_input(
                    param_info.get("name", param_name),
                    value=float(default_value or 0),
                    help=description
                )
            
            elif param_type == "date":
                parameters[param_name] = st.date_input(
                    param_info.get("name", param_name),
                    value=default_value or datetime.datetime.now().date(),
                    help=description
                ).isoformat()
            
            elif param_type == "boolean":
                parameters[param_name] = st.checkbox(
                    param_info.get("name", param_name),
                    value=bool(default_value),
                    help=description
                )
    
    # Use template button
    if st.button("Use Template", key=f"use_template_{selected_template}"):
        on_select(selected_template, parameters)
