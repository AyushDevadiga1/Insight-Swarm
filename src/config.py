"""
Configuration constants for InsightSwarm

Centralized configuration for magic numbers and settings used throughout the codebase.
This makes it easier to tune performance and behavior without editing source code.
"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('insightswarm.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# AGENT CONFIGURATION
# ============================================

class AgentConfig:
    """Configuration for debate agents (Pro, Con, FactChecker)"""
    
    # Temperature: Controls randomness in LLM responses
    # 0.0 = deterministic, 2.0 = maximum randomness
    DEFAULT_TEMPERATURE = 0.7
    
    # Max tokens per response
    DEFAULT_MAX_TOKENS = 800
    
    # Request timeout in seconds
    DEFAULT_TIMEOUT = 30
    
    # Maximum characters for argument text
    MAX_ARGUMENT_LENGTH = 5000
    
    # Minimum argument length to accept
    MIN_ARGUMENT_LENGTH = 50


# ============================================
# FACT CHECKER CONFIGURATION
# ============================================

class FactCheckerConfig:
    """Configuration for source verification"""
    
    # URL fetch timeout in seconds
    URL_TIMEOUT = 10
    
    # Fuzzy matching threshold (0-100)
    # Minimum similarity score required to consider source verified
    FUZZY_MATCH_THRESHOLD = 70
    
    # Maximum content length to analyze (characters)
    MAX_CONTENT_LENGTH = 2000
    
    # Maximum preview length in results (characters)
    PREVIEW_LENGTH = 500
    
    # Content extraction minimum length
    MIN_CONTENT_LENGTH = 10


# ============================================
# LLM CLIENT CONFIGURATION
# ============================================

class LLMClientConfig:
    """Configuration for FreeLLMClient"""
    
    # Temperature range
    MIN_TEMPERATURE = 0.0
    MAX_TEMPERATURE = 2.0
    
    # Token limits
    MIN_TOKENS = 1
    MAX_TOKENS = 4000
    
    # Timeout limits (seconds)
    MIN_TIMEOUT = 1
    MAX_TIMEOUT = 300
    
    # Prompt size limits (characters)
    MAX_PROMPT_LENGTH = 100000
    
    # Rate limiting
    MAX_CALLS_PER_MINUTE = 60  # Configurable via env var RATE_LIMIT_PER_MINUTE
    
    # API key validation
    MIN_API_KEY_LENGTH = 30
    GROQ_KEY_PREFIX = "gsk_"


# ============================================
# DEBATE ORCHESTRATION CONFIGURATION
# ============================================

class DebateConfig:
    """Configuration for debate orchestration"""
    
    # Number of rounds in debate
    NUM_ROUNDS = 3
    
    # Round at which debate ends
    FINAL_ROUND = 3
    
    # Verdict classification weights
    ARGUMENT_WEIGHT = 1.0
    SOURCE_VERIFICATION_WEIGHT = 2.0  # FactChecker gets 2x weight


# ============================================
# STREAMLIT UI CONFIGURATION
# ============================================

class StreamlitConfig:
    """Configuration for Streamlit web interface"""
    
    # ThreadPoolExecutor worker count for background tasks
    THREAD_POOL_WORKERS = 1
    
    # Default page title and icon
    PAGE_TITLE = "InsightSwarm - AI Fact Checker"
    PAGE_ICON = "🔍"
    
    # Sidebar state
    SIDEBAR_STATE = "expanded"
    
    # Example claims for users to try
    EXAMPLE_CLAIMS = [
        "Coffee prevents cancer",
        "Exercise improves mental health",
        "The Earth is flat",
        "Vaccines cause autism",
        "AI will replace all jobs by 2030"
    ]
    
    # Verdict verdicts and their display classes
    VERDICT_CLASSES = {
        'TRUE': 'verdict-true',
        'FALSE': 'verdict-false',
        'PARTIALLY TRUE': 'verdict-partial'
    }
    
    # Verdict display emojis
    VERDICT_EMOJIS = {
        'TRUE': '✅',
        'FALSE': '❌',
        'PARTIALLY TRUE': '⚠️'
    }


# ============================================
# LOGGING CONFIGURATION
# ============================================

class LoggingConfig:
    """Configuration for logging"""
    
    # Log level
    LOG_LEVEL = "INFO"
    
    # Format string
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Test log level (usually WARNING to reduce noise)
    TEST_LOG_LEVEL = "WARNING"
