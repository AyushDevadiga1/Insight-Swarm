"""
src/config.py — Final production version. All batches applied.
"""
import logging
logger = logging.getLogger(__name__)


class AgentConfig:
    DEFAULT_TEMPERATURE  = 0.7
    DEFAULT_MAX_TOKENS   = 600
    DEFAULT_TIMEOUT      = 30
    MAX_ARGUMENT_LENGTH  = 3000  # Prevent context window overflow in 3-round debates
    MIN_ARGUMENT_LENGTH  = 50


class FactCheckerConfig:
    URL_TIMEOUT           = 10
    FUZZY_MATCH_THRESHOLD = 70
    MAX_CONTENT_LENGTH    = 2000
    PREVIEW_LENGTH        = 500
    MIN_CONTENT_LENGTH    = 10
    SEMANTIC_THRESHOLD    = 0.82   # Tightened for better integration with React UI
    URL_FETCH_RETRIES     = 2


class LLMClientConfig:
    MIN_TEMPERATURE           = 0.0
    MAX_TEMPERATURE           = 2.0
    MIN_TOKENS                = 1
    MAX_TOKENS                = 4000
    MIN_TIMEOUT               = 1
    MAX_TIMEOUT               = 300
    MAX_PROMPT_LENGTH         = 100_000
    MAX_CALLS_PER_MINUTE      = 60
    MIN_API_KEY_LENGTH        = 30
    GROQ_KEY_PREFIX           = "gsk_"
    ALLOWED_ORIGINS           = ["http://localhost:5173", "http://127.0.0.1:5173"] # Expanded for Vite
    PROVIDER_COOLDOWN_SECONDS = 90   # timed cooldown after rate-limit hit


class DebateConfig:
    NUM_ROUNDS                 = 3
    FINAL_ROUND                = 3
    ARGUMENT_WEIGHT            = 1.0
    SOURCE_VERIFICATION_WEIGHT = 2.0


class StreamlitConfig:
    THREAD_POOL_WORKERS = 1
    PAGE_TITLE          = "InsightSwarm - AI Fact Checker"
    PAGE_ICON           = "🔍"
    SIDEBAR_STATE       = "expanded"
    EXAMPLE_CLAIMS      = [
        "Coffee prevents cancer",
        "Exercise improves mental health",
        "The Earth is flat",
        "Vaccines cause autism",
        "AI will replace all jobs by 2030",
    ]
    VERDICT_CLASSES = {"TRUE":"verdict-true","FALSE":"verdict-false","PARTIALLY TRUE":"verdict-partial"}
    VERDICT_EMOJIS  = {"TRUE":"✅","FALSE":"❌","PARTIALLY TRUE":"⚠️"}


class LoggingConfig:
    LOG_LEVEL      = "INFO"
    LOG_FORMAT     = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    TEST_LOG_LEVEL = "WARNING"
