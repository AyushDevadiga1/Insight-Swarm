"""
Source verification utilities for FactChecker

Verifies URLs cited by agents:
- Checks if URL is accessible
- Extracts text content
- Validates content matches agent's claim
"""

import logging
import requests
from typing import Dict, Optional, Tuple
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SourceVerification:
    """Result of source verification"""
    
    def __init__(
        self,
        url: str,
        status: str,
        content_preview: Optional[str] = None,
        similarity_score: Optional[float] = None,
        error: Optional[str] = None
    ):
        self.url = url
        self.status = status  # VERIFIED, NOT_FOUND, INVALID_URL, TIMEOUT, CONTENT_MISMATCH
        self.content_preview = content_preview
        self.similarity_score = similarity_score
        self.error = error
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'url': self.url,
            'status': self.status,
            'content_preview': self.content_preview,
            'similarity_score': self.similarity_score,
            'error': self.error
        }
    
    def is_verified(self) -> bool:
        """Check if source was successfully verified"""
        return self.status == "VERIFIED"


class SourceVerifier:
    """
    Verifies sources cited by debate agents
    
    Checks:
    1. URL is valid format
    2. URL is accessible (HTTP 200)
    3. Content can be extracted
    4. (Optional) Content matches claim
    
    Can be used as a context manager for automatic cleanup:
        with SourceVerifier() as verifier:
            result = verifier.verify_url(url)
    """
    
    # Configuration constants
    SIMILARITY_THRESHOLD = 30  # Minimum similarity score (%) for content match
    
    def __init__(self, timeout: int = 10, similarity_threshold: int = None):
        """
        Initialize verifier
        
        Args:
            timeout: HTTP request timeout in seconds
            similarity_threshold: Minimum similarity score (%) for content match. Defaults to class constant.
        """
        self.timeout = timeout
        self.similarity_threshold = similarity_threshold if similarity_threshold is not None else self.SIMILARITY_THRESHOLD
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'InsightSwarm-FactChecker/1.0'
        })
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session"""
        self.close()
        return False
    
    def close(self):
        """Close the requests session"""
        if self.session:
            try:
                self.session.close()
            except Exception as e:
                logger.warning(f"Error closing session: {e}")
    
    def verify_url(self, url: str, expected_content: Optional[str] = None) -> SourceVerification:
        """
        Verify a single URL
        
        Args:
            url: URL to verify
            expected_content: Optional text that should appear in source
            
        Returns:
            SourceVerification result
        """
        logger.info(f"Verifying source: {url}")
        
        # Step 1: Validate URL format
        if not self._is_valid_url(url):
            logger.warning(f"Invalid URL format: {url}")
            return SourceVerification(
                url=url,
                status="INVALID_URL",
                error="Invalid URL format"
            )
        
        # Step 2: Fetch URL
        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            
            if response.status_code != 200:
                logger.warning(f"URL returned {response.status_code}: {url}")
                return SourceVerification(
                    url=url,
                    status="NOT_FOUND",
                    error=f"HTTP {response.status_code}"
                )
            
            # Step 3: Extract content
            content = self._extract_text(response.text)
            
            if not content:
                logger.warning(f"No content extracted from: {url}")
                return SourceVerification(
                    url=url,
                    status="NOT_FOUND",
                    error="No text content found"
                )
            
            content_preview = content[:500]  # First 500 chars
            
            # Step 4: Optional content matching
            similarity_score = None
            status = "VERIFIED"
            
            if expected_content:
                similarity_score = self._calculate_similarity(expected_content, content)
                
                if similarity_score < self.similarity_threshold:
                    status = "CONTENT_MISMATCH"
                    logger.warning(f"Content mismatch ({similarity_score}%) for {url}")
            
            logger.info(f"✅ Verified: {url} (similarity: {similarity_score}%)")
            
            return SourceVerification(
                url=url,
                status=status,
                content_preview=content_preview,
                similarity_score=similarity_score
            )
        
        except requests.Timeout:
            logger.warning(f"Timeout fetching: {url}")
            return SourceVerification(
                url=url,
                status="TIMEOUT",
                error="Request timeout"
            )
        
        except requests.RequestException as e:
            logger.warning(f"Request failed for {url}: {e}")
            return SourceVerification(
                url=url,
                status="NOT_FOUND",
                error=str(e)
            )
        
        except Exception as e:
            logger.error(f"Unexpected error verifying {url}: {e}")
            return SourceVerification(
                url=url,
                status="ERROR",
                error=str(e)
            )
    
    def _is_valid_url(self, url: str) -> bool:
        """
        Check if URL has valid format
        
        Args:
            url: URL to check
            
        Returns:
            True if valid format
        """
        try:
            result = urlparse(url)
            return all([result.scheme in ['http', 'https'], result.netloc])
        except:
            return False
    
    def _extract_text(self, html: str) -> str:
        """
        Extract readable text from HTML
        
        Args:
            html: HTML content
            
        Returns:
            Extracted text
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(['script', 'style', 'nav', 'footer', 'header']):
                script.decompose()
            
            # Get text
            text = soup.get_text(separator=' ', strip=True)
            
            # Clean up whitespace
            lines = [line.strip() for line in text.splitlines()]
            text = ' '.join(line for line in lines if line)
            
            return text
        
        except Exception as e:
            logger.error(f"Failed to extract text: {e}")
            return ""
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts
        
        Uses fuzzy string matching to handle:
        - Different wording
        - Typos
        - Word order variations
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score (0-100)
        """
        # Normalize texts
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        # Use partial ratio (finds best matching substring)
        score = fuzz.partial_ratio(text1, text2)
        
        return score


# ============================================
# TESTING CODE
# ============================================

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*70)
    print("SourceVerifier Test")
    print("="*70)
    
    verifier = SourceVerifier(timeout=10)
    
    # Test URLs
    test_cases = [
        ("https://www.cancer.gov/", "cancer research prevention"),
        ("https://www.wikipedia.org/", "encyclopedia"),
        ("https://this-url-does-not-exist-12345.com/", None),
        ("not-a-valid-url", None)
    ]
    
    for url, expected in test_cases:
        print(f"\nTesting: {url}")
        result = verifier.verify_url(url, expected)
        print(f"  Status: {result.status}")
        if result.similarity_score:
            print(f"  Similarity: {result.similarity_score}%")
        if result.error:
            print(f"  Error: {result.error}")
        if result.content_preview:
            print(f"  Preview: {result.content_preview[:100]}...")
    
    print("\n" + "="*70)
    print("✅ Test complete!")
    print("="*70 + "\n")