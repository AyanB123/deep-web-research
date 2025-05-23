"""
Advanced analytics module for the Dark Web Discovery System.
Provides content classification, entity extraction, sentiment analysis, and trend detection.
"""

import datetime
import re
import json
import logging
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Any, Optional, Set

import numpy as np
import pandas as pd
from langchain.llms import Groq, GoogleGenerativeAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from google.generativeai import GenerativeModel
import google.generativeai as genai

from config import Config

# Configure logger
def log_action(message):
    """Log actions with timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    logging.info(message)

class ContentAnalyzer:
    """
    Advanced content analysis using various NLP techniques and LLMs.
    """
    
    # Detailed content categories for classification
    CONTENT_CATEGORIES = [
        # Marketplace categories
        "drugs", "digital_goods", "counterfeit", "weapons", "hacking_services",
        "financial_services", "personal_data", "forgery", "other_illicit",
        
        # Information categories
        "news", "politics", "technology", "security", "privacy", "tutorials",
        "documentation", "research", "education", "discussion",
        
        # Communication categories
        "forum", "chat", "email", "social_network", "messaging",
        
        # Infrastructure categories
        "hosting", "vpn", "proxy", "cryptocurrency", "anonymity_tools",
        
        # Content type categories
        "text_heavy", "image_heavy", "service_oriented", "download_oriented",
        "interactive", "static"
    ]
    
    # Entity types to extract
    ENTITY_TYPES = [
        "person", "organization", "location", "product", "cryptocurrency",
        "software", "service", "file_type", "domain"
    ]
    
    def __init__(self):
        """Initialize the ContentAnalyzer with LLM for advanced processing."""
        self.initialized = False
        try:
            # Initialize LLM providers
            self.initialize_llm()
            self.initialized = True
        except Exception as e:
            log_action(f"Error initializing ContentAnalyzer: {str(e)}")
    
    def initialize_llm(self):
        """Initialize the LLM based on configuration."""
        api_key = Config.GEMINI_API_KEY
        
        if not api_key:
            log_action("Warning: No API key found for LLM. Advanced analytics will be limited.")
            return False
            
        genai.configure(api_key=api_key)
        self.gemini_model = GenerativeModel(Config.GEMINI_MODEL_NAME)
        
        # Using Groq for faster inference if available
        if Config.GROQ_API_KEY:
            try:
                self.groq_llm = Groq(api_key=Config.GROQ_API_KEY, model_name="llama3-70b-8192")
                log_action("Groq LLM initialized successfully")
            except Exception as e:
                log_action(f"Failed to initialize Groq: {str(e)}")
                self.groq_llm = None
        else:
            self.groq_llm = None
            
        # Set up the text splitter for long content
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=8000,  # Chunk size for LLM context window
            chunk_overlap=200,  # Overlap to maintain context between chunks
            separators=["\n\n", "\n", " ", ""]
        )
        
        return True
    
    def detailed_classify_content(self, content: str, url: str = "") -> Dict[str, float]:
        """
        Classify content into detailed taxonomies with confidence scores.
        
        Args:
            content (str): The text content to classify
            url (str): Optional URL for context
            
        Returns:
            dict: Category confidence scores
        """
        if not self.initialized or not content:
            return {}
            
        # Prepare the content by cleaning and truncating
        cleaned_content = self._prepare_content(content, max_length=10000)
        
        # Create classification prompt
        prompt = f"""
        Analyze the following dark web content and classify it into categories.
        URL: {url}
        
        CONTENT:
        {cleaned_content}
        
        TASK: Classify this content into these categories with confidence scores from 0.0 to 1.0:
        {', '.join(self.CONTENT_CATEGORIES)}
        
        OUTPUT FORMAT:
        {{
            "category1": score1,
            "category2": score2,
            ...
        }}
        
        Only include categories with a confidence score > 0.2. Output in valid JSON format.
        """
        
        try:
            # Use Groq if available (faster), otherwise Gemini
            if self.groq_llm:
                response = self.groq_llm.invoke(prompt)
            else:
                response = self.gemini_model.generate_content(prompt).text
                
            # Extract JSON from the response
            json_str = self._extract_json(response)
            results = json.loads(json_str)
            
            # Validate results
            classifications = {}
            for category, score in results.items():
                if category in self.CONTENT_CATEGORIES and isinstance(score, (int, float)) and 0 <= score <= 1:
                    classifications[category] = float(score)
            
            return classifications
            
        except Exception as e:
            log_action(f"Error in detailed content classification: {str(e)}")
            return {}
    
    def extract_entities(self, content: str, url: str = "") -> Dict[str, List[str]]:
        """
        Extract named entities from content.
        
        Args:
            content (str): The text content to analyze
            url (str): Optional URL for context
            
        Returns:
            dict: Dictionary of entity types mapped to lists of entities
        """
        if not self.initialized or not content:
            return {}
            
        # Prepare the content by cleaning and truncating
        cleaned_content = self._prepare_content(content, max_length=10000)
        
        # Create entity extraction prompt
        prompt = f"""
        Extract named entities from the following dark web content.
        URL: {url}
        
        CONTENT:
        {cleaned_content}
        
        TASK: Extract entities of these types: {', '.join(self.ENTITY_TYPES)}
        
        OUTPUT FORMAT:
        {{
            "entity_type1": ["entity1", "entity2", ...],
            "entity_type2": ["entity1", "entity2", ...],
            ...
        }}
        
        Only include entity types that have at least one entity. Output in valid JSON format.
        """
        
        try:
            # Use Groq if available (faster), otherwise Gemini
            if self.groq_llm:
                response = self.groq_llm.invoke(prompt)
            else:
                response = self.gemini_model.generate_content(prompt).text
                
            # Extract JSON from the response
            json_str = self._extract_json(response)
            results = json.loads(json_str)
            
            # Validate results
            entities = {}
            for entity_type, entity_list in results.items():
                if entity_type in self.ENTITY_TYPES and isinstance(entity_list, list):
                    # Deduplicate entities
                    unique_entities = list(set([str(e).strip() for e in entity_list if e]))
                    if unique_entities:
                        entities[entity_type] = unique_entities
            
            return entities
            
        except Exception as e:
            log_action(f"Error in entity extraction: {str(e)}")
            return {}
    
    def analyze_sentiment(self, content: str) -> Dict[str, float]:
        """
        Analyze sentiment in the content.
        
        Args:
            content (str): The text content to analyze
            
        Returns:
            dict: Sentiment scores (positive, negative, neutral)
        """
        if not self.initialized or not content:
            return {"positive": 0.0, "negative": 0.0, "neutral": 1.0}
            
        # Prepare the content by cleaning and truncating
        cleaned_content = self._prepare_content(content, max_length=5000)
        
        # Create sentiment analysis prompt
        prompt = f"""
        Analyze the sentiment of the following text content.
        
        CONTENT:
        {cleaned_content}
        
        TASK: Provide sentiment scores from 0.0 to 1.0 for positive, negative, and neutral sentiment.
        The sum of all scores should equal 1.0.
        
        OUTPUT FORMAT:
        {{
            "positive": score1,
            "negative": score2,
            "neutral": score3
        }}
        
        Output in valid JSON format.
        """
        
        try:
            # Use Groq if available (faster), otherwise Gemini
            if self.groq_llm:
                response = self.groq_llm.invoke(prompt)
            else:
                response = self.gemini_model.generate_content(prompt).text
                
            # Extract JSON from the response
            json_str = self._extract_json(response)
            results = json.loads(json_str)
            
            # Validate results
            sentiments = {}
            required_keys = ["positive", "negative", "neutral"]
            for key in required_keys:
                if key in results and isinstance(results[key], (int, float)) and 0 <= results[key] <= 1:
                    sentiments[key] = float(results[key])
                else:
                    sentiments[key] = 0.0
            
            # Normalize if sum is not close to 1.0
            total = sum(sentiments.values())
            if abs(total - 1.0) > 0.05:  # Allow small deviation
                for key in sentiments:
                    sentiments[key] = sentiments[key] / total if total > 0 else (1/3 if key == "neutral" else 0)
            
            return sentiments
            
        except Exception as e:
            log_action(f"Error in sentiment analysis: {str(e)}")
            return {"positive": 0.0, "negative": 0.0, "neutral": 1.0}
    
    def detect_trends(self, content_batch: List[Dict]) -> Dict[str, Any]:
        """
        Detect trends across multiple content items.
        
        Args:
            content_batch (list): List of content items with metadata
            
        Returns:
            dict: Detected trends and patterns
        """
        if not content_batch:
            return {}
            
        try:
            # Extract text content and metadata from batch
            texts = []
            dates = []
            categories = []
            entities_by_type = defaultdict(list)
            
            for item in content_batch:
                if "content" in item and item["content"]:
                    texts.append(item["content"])
                    
                    # Extract date if available
                    if "metadata" in item and "discovery_date" in item["metadata"]:
                        try:
                            date = datetime.datetime.fromisoformat(item["metadata"]["discovery_date"])
                            dates.append(date)
                        except:
                            pass
                    
                    # Extract categories if available
                    if "categories" in item:
                        for category, score in item["categories"].items():
                            if score > 0.5:  # Only consider high confidence categories
                                categories.append(category)
                    
                    # Extract entities if available
                    if "entities" in item:
                        for entity_type, entities in item["entities"].items():
                            entities_by_type[entity_type].extend(entities)
            
            # Analyze common terms and phrases
            common_terms = self._extract_common_terms(texts)
            
            # Analyze category distribution
            category_counts = Counter(categories)
            top_categories = {cat: count for cat, count in category_counts.most_common(5)}
            
            # Analyze entity frequency
            entity_frequency = {}
            for entity_type, entities in entities_by_type.items():
                entity_counts = Counter(entities)
                entity_frequency[entity_type] = {entity: count for entity, count in entity_counts.most_common(10)}
            
            # Analyze temporal patterns if dates available
            temporal_patterns = {}
            if dates:
                # Group by date
                date_counts = Counter([d.date() for d in dates])
                temporal_patterns["date_distribution"] = {str(date): count for date, count in date_counts.items()}
                
                # Calculate growth rate if multiple dates
                if len(set(date_counts.keys())) > 1:
                    sorted_dates = sorted(date_counts.keys())
                    first_date_count = date_counts[sorted_dates[0]]
                    last_date_count = date_counts[sorted_dates[-1]]
                    days_diff = (sorted_dates[-1] - sorted_dates[0]).days
                    if days_diff > 0 and first_date_count > 0:
                        growth_rate = (last_date_count - first_date_count) / first_date_count
                        temporal_patterns["growth_rate"] = growth_rate
            
            return {
                "common_terms": common_terms,
                "top_categories": top_categories,
                "entity_frequency": entity_frequency,
                "temporal_patterns": temporal_patterns,
                "sample_size": len(texts)
            }
            
        except Exception as e:
            log_action(f"Error in trend detection: {str(e)}")
            return {}
    
    def _prepare_content(self, content: str, max_length: int = 5000) -> str:
        """Clean and prepare content for analysis."""
        if not content:
            return ""
            
        # Basic cleaning
        cleaned = re.sub(r'\s+', ' ', content)  # Replace multiple spaces with single space
        cleaned = re.sub(r'[^\w\s.,;:!?()[\]{}"\'-]', '', cleaned)  # Remove special characters
        
        # Truncate if too long
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length] + "..."
            
        return cleaned
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from text response."""
        # Look for JSON pattern
        json_match = re.search(r'({[\s\S]*})', text)
        if json_match:
            json_str = json_match.group(1)
            
            # Clean up JSON string
            json_str = re.sub(r'```json', '', json_str)
            json_str = re.sub(r'```', '', json_str)
            
            return json_str.strip()
        
        # If no JSON pattern found, try to create one from key-value pairs
        pairs_pattern = r'"([^"]+)"\s*:\s*([\d.]+)'
        pairs = re.findall(pairs_pattern, text)
        
        if pairs:
            json_dict = {key: float(value) for key, value in pairs}
            return json.dumps(json_dict)
            
        # Last resort: return empty JSON
        return "{}"
    
    def _extract_common_terms(self, texts: List[str], top_n: int = 20) -> Dict[str, int]:
        """Extract common terms and phrases from a collection of texts."""
        if not texts:
            return {}
            
        # Combine texts and split into words
        combined_text = " ".join(texts).lower()
        words = re.findall(r'\b\w+\b', combined_text)
        
        # Filter out common stopwords
        stopwords = {"the", "and", "to", "of", "a", "in", "for", "is", "on", "that", "by", "this", "with", "i", "you", "it"}
        filtered_words = [word for word in words if word not in stopwords and len(word) > 2]
        
        # Count word frequencies
        word_counts = Counter(filtered_words)
        
        # Extract bigrams (two word phrases)
        bigrams = []
        for i in range(len(words) - 1):
            if words[i] not in stopwords and words[i+1] not in stopwords:
                bigrams.append(f"{words[i]} {words[i+1]}")
        
        bigram_counts = Counter(bigrams)
        
        # Combine top words and bigrams
        common_terms = {term: count for term, count in word_counts.most_common(top_n//2)}
        common_terms.update({term: count for term, count in bigram_counts.most_common(top_n//2)})
        
        return common_terms


class TrendAnalyzer:
    """
    Analyzes trends and patterns across crawled data over time.
    """
    
    def __init__(self, link_db):
        """
        Initialize the trend analyzer with database connection.
        
        Args:
            link_db: Database instance for accessing crawled data
        """
        self.link_db = link_db
        self.content_analyzer = ContentAnalyzer()
    
    def analyze_trends_by_timeframe(self, days: int = 7) -> Dict[str, Any]:
        """
        Analyze trends in crawled data for a specific timeframe.
        
        Args:
            days (int): Number of days to analyze
            
        Returns:
            dict: Trend analysis results
        """
        # Get data from the specified timeframe
        start_date = datetime.datetime.now() - datetime.timedelta(days=days)
        links = self.link_db.get_links_by_timeframe(start_date)
        
        if not links:
            return {"error": "No data available for the specified timeframe"}
        
        # Prepare data for analysis
        content_batch = []
        for link in links:
            item = {
                "url": link["url"],
                "content": link.get("content_preview", ""),
                "title": link.get("title", ""),
                "metadata": link.get("metadata", {})
            }
            
            # Add analysis data if not already present
            if "categories" not in item and item["content"]:
                item["categories"] = self.content_analyzer.detailed_classify_content(
                    item["content"], item["url"]
                )
                
            if "entities" not in item and item["content"]:
                item["entities"] = self.content_analyzer.extract_entities(
                    item["content"], item["url"]
                )
                
            content_batch.append(item)
        
        # Run trend analysis
        trends = self.content_analyzer.detect_trends(content_batch)
        
        # Add metadata
        trends["timeframe"] = {
            "days": days,
            "start_date": start_date.isoformat(),
            "end_date": datetime.datetime.now().isoformat()
        }
        
        return trends
    
    def compare_timeframes(self, period1_days: int = 7, period2_days: int = 14) -> Dict[str, Any]:
        """
        Compare trends between two different timeframes.
        
        Args:
            period1_days (int): Days for recent period
            period2_days (int): Days for comparison period
            
        Returns:
            dict: Comparison results
        """
        # Get trends for each period
        recent_trends = self.analyze_trends_by_timeframe(period1_days)
        previous_trends = self.analyze_trends_by_timeframe(period2_days)
        
        if "error" in recent_trends or "error" in previous_trends:
            return {"error": "Insufficient data for comparison"}
        
        # Compare top categories
        category_comparison = {}
        for category, count in recent_trends.get("top_categories", {}).items():
            previous_count = previous_trends.get("top_categories", {}).get(category, 0)
            if previous_count > 0:
                change_pct = ((count - previous_count) / previous_count) * 100
            else:
                change_pct = 100  # New category
            
            category_comparison[category] = {
                "recent_count": count,
                "previous_count": previous_count,
                "change_percent": change_pct
            }
        
        # Compare entity frequency
        entity_comparison = {}
        for entity_type, entities in recent_trends.get("entity_frequency", {}).items():
            previous_entities = previous_trends.get("entity_frequency", {}).get(entity_type, {})
            
            type_comparison = {}
            for entity, count in entities.items():
                previous_count = previous_entities.get(entity, 0)
                if previous_count > 0:
                    change_pct = ((count - previous_count) / previous_count) * 100
                else:
                    change_pct = 100  # New entity
                
                type_comparison[entity] = {
                    "recent_count": count,
                    "previous_count": previous_count,
                    "change_percent": change_pct
                }
            
            entity_comparison[entity_type] = type_comparison
        
        # Identify emerging terms (terms with significant growth)
        emerging_terms = {}
        for term, count in recent_trends.get("common_terms", {}).items():
            previous_count = previous_trends.get("common_terms", {}).get(term, 0)
            if previous_count > 0:
                change_pct = ((count - previous_count) / previous_count) * 100
                if change_pct > 50:  # Significant growth threshold
                    emerging_terms[term] = {
                        "recent_count": count,
                        "previous_count": previous_count,
                        "change_percent": change_pct
                    }
            elif count > 3:  # New term with multiple occurrences
                emerging_terms[term] = {
                    "recent_count": count,
                    "previous_count": 0,
                    "change_percent": 100
                }
        
        return {
            "category_comparison": category_comparison,
            "entity_comparison": entity_comparison,
            "emerging_terms": emerging_terms,
            "recent_period": {
                "days": period1_days,
                "sample_size": recent_trends.get("sample_size", 0)
            },
            "previous_period": {
                "days": period2_days,
                "sample_size": previous_trends.get("sample_size", 0)
            }
        }
