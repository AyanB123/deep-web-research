from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import BaseTool
from langchain.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph
from typing import TypedDict, List, Dict, Any, Optional
from config import Config
from crawler import TorCrawler  # Keep for backwards compatibility
from enhanced_crawler import EnhancedTorCrawler
from onion_database import OnionLinkDatabase
from knowledge_base import KnowledgeBase
from utils import log_action
from seed_data import seed_initial_directories

class AgentState(TypedDict):
    query: str
    plan: List[str]
    crawled_data: List[dict]
    report: str
    chat_history: List[dict]
    discovery_stats: Optional[Dict[str, Any]]

class TorSearchTool(BaseTool):
    name: str = "tor_search"
    description: str = "Crawls the dark web for content based on query terms, with comprehensive discovery capabilities."
    
    def __init__(self):
        super().__init__()
        self.link_db = OnionLinkDatabase()
        self.discovery_mode = Config.DISCOVERY_MODE
        
        # Seed the database if it's empty
        stats = self.link_db.get_statistics()
        if stats["total_links"] == 0:
            log_action("Initializing onion link database with seed data...")
            seed_initial_directories(self.link_db)
    
    def _run(self, query: str):
        log_action(f"Running dark web search for: {query}")
        crawler = EnhancedTorCrawler(self.link_db)
        
        # Use our comprehensive discovery process
        discovery_stats = crawler.deep_discovery_run(query)
        
        # Gather the most relevant results for the query
        results = []
        
        # First check if we have any direct search engine results
        search_results = self.link_db.search_links(query, limit=10)
        if search_results:
            log_action(f"Found {len(search_results)} direct matches for query in database")
            for result in search_results:
                # Crawl each search result to get current content
                data = crawler.crawl_onion(result["url"], max_depth=1, store_in_db=True)
                if data["content"]:
                    results.append(data)
        
        # If we don't have enough results, get from related categories
        if len(results) < 5:
            # Try to determine relevant categories based on the query
            categories = self._determine_categories(query)
            for category in categories:
                category_links = self.link_db.get_links_by_category(category, limit=5)
                for link in category_links:
                    # Skip if we already have this result
                    if any(r["url"] == link["url"] for r in results):
                        continue
                        
                    # Crawl each category result
                    data = crawler.crawl_onion(link["url"], max_depth=1, store_in_db=True)
                    if data["content"]:
                        results.append(data)
                        
                    # Stop if we have enough results
                    if len(results) >= 5:
                        break
                        
                if len(results) >= 5:
                    break
        
        # If we still don't have enough results, get from recently active sites
        if len(results) < 5:
            active_links = self.link_db.get_links_by_status("active", limit=10)
            for link in active_links:
                # Skip if we already have this result
                if any(r["url"] == link["url"] for r in results):
                    continue
                    
                # Crawl each active link
                data = crawler.crawl_onion(link["url"], max_depth=1, store_in_db=True)
                if data["content"]:
                    results.append(data)
                    
                # Stop if we have enough results
                if len(results) >= 5:
                    break
        
        # Clean up and return results
        crawler.close()
        
        # Add discovery stats to the results
        final_result = {
            "results": results,
            "discovery_stats": discovery_stats,
            "database_stats": self.link_db.get_statistics()
        }
        
        return final_result
    
    def _determine_categories(self, query):
        """Determine relevant categories based on the query."""
        query_lower = query.lower()
        categories = []
        
        # Simple keyword matching for categories
        if any(term in query_lower for term in ["market", "buy", "sell", "product", "store"]):
            categories.append("marketplace")
            
        if any(term in query_lower for term in ["forum", "discuss", "community", "board"]):
            categories.append("forum")
            
        if any(term in query_lower for term in ["news", "article", "report", "journalism"]):
            categories.append("news")
            
        if any(term in query_lower for term in ["service", "host", "email", "vpn"]):
            categories.append("services")
            
        if any(term in query_lower for term in ["bitcoin", "crypto", "currency", "finance", "money"]):
            categories.append("financial")
            
        if any(term in query_lower for term in ["social", "network", "connect", "friend"]):
            categories.append("social")
            
        # If no categories matched, use some defaults
        if not categories:
            categories = ["forum", "marketplace", "news"]
            
        return categories

class ResearchAgent:
    def __init__(self, model_name=Config.DEFAULT_MODEL):
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=Config.GEMINI_API_KEY,
            temperature=Config.TEMPERATURE,
            max_output_tokens=Config.MAX_TOKENS
        )
        self.kb = KnowledgeBase()
        self.tools = [TorSearchTool()]
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a deep research agent specializing in dark web analysis. 
            Your capabilities include:
            1. Discovering onion sites through directories and search engines
            2. Crawling and categorizing dark web content
            3. Storing discovered links in a structured database
            4. Generating insightful reports based on collected data
            
            Break down research queries into sub-tasks, use your tools to gather data, 
            and generate detailed markdown reports with insights. Always prioritize ethical 
            research and avoid promoting illegal activities.
            
            When analyzing dark web content, focus on patterns, trends, and insights rather
            than sensitive or explicit details. Your goal is to provide value through analysis,
            not raw exposure of potentially harmful content."""),
            ("human", "{query}")
        ])

    def planner_node(self, state: AgentState):
        log_action("Generating research plan")
        prompt = self.prompt.format(query=state["query"])
        plan = self.llm.invoke(prompt).content.split("\n")
        return {"plan": [p.strip() for p in plan if p.strip()]}

    def crawler_node(self, state: AgentState):
        log_action("Executing crawler with enhanced discovery")
        data = []
        discovery_stats = {}
        
        for sub_task in state["plan"]:
            for tool in self.tools:
                result = tool._run(sub_task)
                
                # Store results in data list
                if "results" in result:
                    data.extend(result["results"])
                else:
                    # Handle legacy format
                    data.append(result)
                
                # Track discovery statistics
                if "discovery_stats" in result:
                    discovery_stats = result["discovery_stats"]
        
        # Store crawled data in knowledge base
        self.kb.store_data(data)
        
        return {
            "crawled_data": data,
            "discovery_stats": discovery_stats
        }

    def analyzer_node(self, state: AgentState):
        log_action("Analyzing crawled data with enhanced context")
        
        # Get relevant context from knowledge base
        context = self.kb.retrieve_data(state["query"])
        
        # Prepare discovery stats summary if available
        discovery_summary = ""
        if state.get("discovery_stats"):
            stats = state["discovery_stats"]
            discovery_summary = f"""
            ## Discovery Statistics:
            - Directories crawled: {stats.get('directories_crawled', 0)}
            - Search engines queried: {stats.get('search_engines_queried', 0)}
            - Sites crawled: {stats.get('sites_crawled', 0)}
            - New links discovered: {stats.get('new_links_discovered', 0)}
            """
        
        # Construct enhanced prompt with discovery context
        prompt = f"""
        Analyze the following dark web research data for the query: {state['query']}
        
        Crawled data:
        {state['crawled_data']}
        
        {discovery_summary}
        
        Context from knowledge base:
        {context}
        
        Focus your analysis on identifying patterns, key insights, and relevant findings.
        Organize your analysis into sections covering different aspects of the research question.
        Include specific examples from the data where relevant.
        """
        
        analysis = self.llm.invoke(prompt).content
        return {"report": analysis}

    def report_node(self, state: AgentState):
        log_action("Generating final report")
        prompt = f"Generate a detailed markdown report from:\n{state['report']}"
        report = self.llm.invoke(prompt).content
        return {"report": report}

    def build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("planner", self.planner_node)
        graph.add_node("crawler", self.crawler_node)
        graph.add_node("analyzer", self.analyzer_node)
        graph.add_node("report_generator", self.report_node)
        graph.add_edge("planner", "crawler")
        graph.add_edge("crawler", "analyzer")
        graph.add_edge("analyzer", "report_generator")
        graph.set_entry_point("planner")
        return graph.compile()
