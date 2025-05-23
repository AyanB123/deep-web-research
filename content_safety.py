"""
Content safety module for filtering and classifying potentially inappropriate content.
Uses Gemini AI to detect and filter NSFW content, violence, illegal activity, etc.
"""

import json
from langchain_google_genai import ChatGoogleGenerativeAI
from config import Config
from utils import log_action

class ContentSafetyClassifier:
    """
    Classifies and filters content for safety concerns using Gemini AI.
    """
    
    def __init__(self, model_name=None):
        """
        Initialize the content safety classifier.
        
        Args:
            model_name (str, optional): Gemini model to use. Defaults to Config.DEFAULT_MODEL.
        """
        self.model_name = model_name or Config.DEFAULT_MODEL
        self.model = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=Config.GEMINI_API_KEY,
            temperature=0.1  # Low temperature for more deterministic results
        )
        
    def classify_content(self, content, url=""):
        """
        Classify content for safety concerns.
        
        Args:
            content (str): Text content to classify
            url (str, optional): Source URL for context
            
        Returns:
            dict: Classification results with categories and confidence scores
        """
        if not content:
            return self._default_safe_scores()
        
        # Truncate content to reasonable length
        truncated_content = content[:5000]
        
        prompt = f"""
        Analyze the following content from a dark web site and classify it into these safety categories:
        1. NSFW (pornographic or explicit sexual content)
        2. Violence (graphic violence, gore, or abuse)
        3. Illegal activity (specific instructions for illegal activities)
        4. Hate speech (content promoting hatred or discrimination)
        5. Harassment (targeted harassment or bullying)
        6. Self-harm (content promoting self-harm)
        7. Child exploitation (any content related to child exploitation)
        
        For each category, provide a score from 0-10 where:
        0 = definitely not present
        10 = definitely present
        
        Content from {url}:
        {truncated_content}
        
        Return only a JSON object with the category scores, nothing else.
        Example: {{"NSFW": 0, "Violence": 2, "Illegal activity": 1, "Hate speech": 0, "Harassment": 0, "Self-harm": 0, "Child exploitation": 0}}
        """
        
        try:
            response = self.model.invoke(prompt).content.strip()
            
            # Extract JSON from response
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].strip()
                
            # Parse JSON response
            scores = json.loads(json_str)
            return scores
        except Exception as e:
            log_action(f"Error classifying content safety: {str(e)}")
            return self._default_safe_scores(error=str(e))
    
    def _default_safe_scores(self, error=None):
        """
        Return default safe scores when classification fails.
        
        Args:
            error (str, optional): Error message if any
            
        Returns:
            dict: Default safety scores
        """
        scores = {
            "NSFW": 0, 
            "Violence": 0, 
            "Illegal activity": 0,
            "Hate speech": 0, 
            "Harassment": 0, 
            "Self-harm": 0, 
            "Child exploitation": 0
        }
        
        if error:
            scores["error"] = error
            
        return scores
    
    def is_safe_content(self, content, url="", threshold=None):
        """
        Check if content is safe based on classification.
        
        Args:
            content (str): Text content to check
            url (str, optional): Source URL for context
            threshold (int, optional): Score threshold for unsafe content (0-10)
            
        Returns:
            tuple: (is_safe, categories_exceeding_threshold)
        """
        if threshold is None:
            threshold = Config.SAFETY_THRESHOLD
            
        scores = self.classify_content(content, url)
        
        # Remove error key if present
        if "error" in scores:
            scores.pop("error")
            
        # Check which categories exceed the threshold
        unsafe_categories = {k: v for k, v in scores.items() if v >= threshold}
        
        return (len(unsafe_categories) == 0, unsafe_categories)
    
    def get_filtered_content(self, content, url="", threshold=None):
        """
        Get filtered version of content if unsafe.
        
        Args:
            content (str): Original content
            url (str, optional): Source URL for context
            threshold (int, optional): Score threshold for unsafe content (0-10)
            
        Returns:
            tuple: (filtered_content, was_filtered, filter_reason, safety_scores)
        """
        if not content:
            return (content, False, None, self._default_safe_scores())
            
        is_safe, unsafe_categories = self.is_safe_content(content, url, threshold)
        
        if is_safe:
            return (content, False, None, self._default_safe_scores())
            
        # Generate a sanitized version
        filter_reason = ", ".join(unsafe_categories.keys())
        
        # Create a redacted summary that excludes the unsafe content
        summary_prompt = f"""
        The following content has been identified to contain problematic material related to: {filter_reason}.
        
        Create a very brief, sanitized summary that describes the general topic without including ANY of the problematic content.
        Keep the summary under 100 words and make sure it's appropriate for all audiences.
        
        Original content from {url}:
        {content[:1000]}
        """
        
        try:
            summary = self.model.invoke(summary_prompt).content.strip()
            filtered_content = f"[Content filtered due to safety concerns: {filter_reason}]\n\nSanitized summary: {summary}"
        except Exception as e:
            log_action(f"Error creating sanitized summary: {str(e)}")
            filtered_content = f"[Content filtered due to safety concerns: {filter_reason}]"
        
        return (filtered_content, True, filter_reason, unsafe_categories)
