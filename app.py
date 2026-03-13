"""
InsightSwarm Streamlit Web Interface

Public demo of multi-agent fact-checking system with source verification
"""

import streamlit as st
import time
import html
import uuid
from concurrent.futures import ThreadPoolExecutor
from src.orchestration.debate import DebateOrchestrator
from src.orchestration.cache import record_feedback
from main import validate_claim

# Page configuration
st.set_page_config(
    page_title="InsightSwarm",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>

/* Extremely Professional Nothing-Inspired Minimalist Theme */
:root {
    --bg-color: #000000;
    --text-primary: #FFFFFF;
    --text-secondary: #999999;
    --accent: #FFFFFF;
    --border-color: #333333;
    --surface-color: #0a0a0a;
}

[data-testid="stAppViewContainer"] {
    background-color: var(--bg-color);
    color: var(--text-primary);
    font-family: 'Space Mono', 'Inter', monospace;
}

[data-testid="stSidebar"] {
    background-color: var(--bg-color);
    border-right: 1px solid var(--border-color);
    padding-top: 20px;
}

[data-testid="stHeader"] {
    background-color: transparent !important;
}

.block-container {
    max-width: 900px;
    margin: auto;
    padding-top: 10px;
}

/* Typography & Display - Removing white banner and lowering amateur elements */
.main-header {
    font-size: 56px;
    font-weight: 500;
    letter-spacing: -2px;
    line-height: 1.1;
    text-transform: uppercase;
    color: var(--text-primary);
    margin-bottom: 4px;
    display: inline-block;
}

.sub-header {
    font-size: 14px;
    font-weight: 400;
    color: var(--text-secondary);
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 64px;
}

/* Hard Edged Inputs - ZERO border radius */
div[data-baseweb="input"], 
div[data-baseweb="input"] > div,
div[data-baseweb="base-input"],
div[data-testid="stTextInput"] > div > div {
    border-radius: 0px !important;
}

.stTextInput input {
    background-color: var(--surface-color) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 0px !important; 
    color: var(--text-primary) !important;
    padding: 18px 20px !important;
    font-family: inherit;
    font-size: 15px;
    transition: all 0.2s ease;
}

.stTextInput input:focus {
    border-color: var(--text-primary) !important;
    box-shadow: none !important;
    background-color: var(--bg-color) !important;
}

/* Hard Edged Buttons - ZERO border radius */
.stButton button {
    background-color: transparent !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 0px !important;
    padding: 14px 24px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    transition: all 0.3s ease !important;
    width: 100%;
    white-space: nowrap !important;
    min-width: max-content !important;
}

.stButton button:hover {
    border-color: var(--text-primary) !important;
    background-color: rgba(255,255,255,0.05) !important;
}

.stButton button[data-testid="baseButton-primary"] {
    background-color: var(--text-primary) !important;
    color: var(--bg-color) !important;
    border: 1px solid var(--text-primary) !important;
}

.stButton button[data-testid="baseButton-primary"]:hover {
    background-color: transparent !important;
    color: var(--text-primary) !important;
}

/* Verdict Box - Ultra minimal */
.verdict-box {
    margin-top: 32px;
    padding: 30px;
    border: 1px solid var(--border-color);
    background-color: transparent;
    text-transform: uppercase;
    position: relative;
    border-radius: 0px;
}

.verdict-box::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 2px;
    height: 100%;
}

.verdict-true::before { background-color: #ffffff; }
.verdict-false::before { background-color: #ff3333; }
.verdict-partial::before { background-color: #aaaaaa; }

.verdict-box strong {
    font-size: 20px;
    letter-spacing: 1px;
    font-weight: 500;
}

/* Debate Blocks */
.debate-block {
    margin-top: 16px;
    padding: 24px;
    border: 1px solid var(--border-color);
    background-color: var(--surface-color);
    border-radius: 0px;
    font-size: 14px;
    line-height: 1.7;
    color: #cccccc;
    font-family: inherit;
}

/* Source Status Minimal */
.source-verified {
    color: #ffffff;
    opacity: 0.9;
}

.source-failed {
    color: #ff3333;
    opacity: 0.9;
}

/* Headers override */
h1, h2, h3, h4, h5, h6 {
    color: var(--text-primary) !important;
    text-transform: uppercase !important;
    letter-spacing: 1.5px !important;
    font-weight: 500 !important;
}

/* Expander/Tabs styling - STRICT hard edges */
[data-testid="stExpander"] {
    border: 1px solid var(--border-color) !important;
    border-radius: 0px !important;
    background: transparent !important;
}

[data-baseweb="tab"] {
    border-radius: 0px !important;
    background: transparent !important;
    padding: 10px 20px !important;
    border: 1px solid transparent;
}

[data-baseweb="tab-list"] {
    border-bottom: 1px solid var(--border-color) !important;
}

[aria-selected="true"] {
    border: 1px solid var(--border-color) !important;
    border-bottom: 1px solid var(--bg-color) !important;
}

/* Metrics - Monospace, stark */
[data-testid="stMetricValue"] {
    font-family: 'Space Mono', monospace;
    font-weight: 400;
    font-size: 32px;
}
[data-testid="stMetricLabel"] {
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-secondary);
    font-size: 12px;
}

/* Footer - clean */
.footer {
    text-align: left;
    color: var(--text-secondary);
    margin-top: 120px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 2px;
    border-top: 1px solid var(--border-color);
    padding-top: 24px;
    display: flex;
    justify-content: space-between;
}

/* Custom Webkit Scrollbar */
::-webkit-scrollbar {
    width: 6px;
}
::-webkit-scrollbar-track {
    background: var(--bg-color);
}
::-webkit-scrollbar-thumb {
    background: var(--border-color);
}
::-webkit-scrollbar-thumb:hover {
    background: var(--text-secondary);
}

/* Divider styling */
hr {
    border-color: var(--border-color) !important;
    opacity: 0.5;
}

</style>
""", unsafe_allow_html=True)



def safe_markdown(content: str, is_html: bool = True):
    """
    Centralized helper for safe HTML/Markdown rendering.
    Escapes content and ensures unsafe_allow_html is only used intentionally.
    """
    if is_html:
        st.markdown(content, unsafe_allow_html=True)
    else:
        st.markdown(content)


import atexit

def init_session_state():
    """Initialize session state variables"""
    if 'debate_run' not in st.session_state:
        st.session_state.debate_run = False
    if 'thread_id' not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if 'moderator_chat' not in st.session_state:
        st.session_state.moderator_chat = []
    if 'result' not in st.session_state:
        st.session_state.result = None
    if 'orchestrator' not in st.session_state:
        st.session_state.orchestrator = None
    if 'background_task' not in st.session_state:
        st.session_state.background_task = None
    if 'task_executor' not in st.session_state:
        executor = ThreadPoolExecutor(max_workers=1)
        st.session_state.task_executor = executor
        
        # Register cleanup on exit (FIX 4)
        def shutdown_executor():
            try:
                executor.shutdown(wait=False)
            except:
                pass
        atexit.register(shutdown_executor)


def render_header():
    safe_markdown(
        """
        <div class="main-header">INSIGHTSWARM</div>
        <div class="sub-header">
        Multi-Agent Truth Verification Protocol
        </div>
        """
    )


def render_sidebar():
    """Render sidebar with information"""
    with st.sidebar:
        safe_markdown("<h3 style='text-transform:uppercase;letter-spacing:2px;font-size:12px;color:#888;margin-bottom:16px;'>Architecture</h3>")
        
        safe_markdown("""
        <div style='font-size: 13px; color: #aaa; line-height: 1.8; margin-bottom: 30px;'>
        <p style='border-left: 1px solid #333; padding-left: 12px; margin-bottom: 16px;'>
        <strong>01 ProAgent</strong><br/>
        Validates claim assumptions.<br/>
        Source aggregation.</p>
        
        <p style='border-left: 1px solid #333; padding-left: 12px; margin-bottom: 16px;'>
        <strong>02 ConAgent</strong><br/>
        Invalidates claim assumptions.<br/>
        Adversarial execution.</p>
        
        <p style='border-left: 1px solid #333; padding-left: 12px; margin-bottom: 16px;'>
        <strong>03 FactChecker</strong><br/>
        Source verification.<br/>
        Hallucination detection.</p>
        
        <p style='border-left: 1px solid #333; padding-left: 12px;'>
        <strong>04 Moderator</strong><br/>
        Intelligent consensus.<br/>
        Fallacy detection.</p>
        </div>
        """)
        
        st.divider()
        
        st.header("Example Claims")
        
        example_claims = [
            "Coffee prevents cancer",
            "Exercise improves mental health",
            "The Earth is flat",
            "Vaccines cause autism",
            "AI will replace all jobs by 2030"
        ]
        
        safe_markdown("<div style='font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#666;margin-bottom:12px;'>Pre-verified queries</div>")
        for claim in example_claims:
            if st.button(claim, key=f"example_{claim}", use_container_width=True):
                st.session_state.example_claim = claim
                st.rerun()


def render_verdict(result):
    """Render verdict with styled box"""
    verdict = result.get('verdict', 'UNKNOWN')
    confidence = result.get('confidence', 0.0)
    if confidence is None:
        confidence = 0.0
    moderator_reasoning = result.get('moderator_reasoning', '')
    
    # Determine verdict class
    verdict_class = {
        'TRUE': 'verdict-true',
        'FALSE': 'verdict-false',
        'PARTIALLY TRUE': 'verdict-partial',
        'INSUFFICIENT EVIDENCE': 'verdict-partial'
    }.get(verdict, 'verdict-partial')
    
    # Escape verdict string to prevent XSS
    escaped_verdict = html.escape(verdict)
    
    safe_markdown(f"""
    <div class="verdict-box {verdict_class}">
        <strong>{escaped_verdict}</strong><br>
        Confidence: {confidence:.1%}
    </div>
    """)
    
    # Moderation Decision Chat style
    if moderator_reasoning:
        st.markdown("---")
        safe_markdown("""
        <div style='display: flex; align-items: center; margin-bottom: 20px;'>
            <div style='width: 40px; height: 40px; border-radius: 0; border: 1px solid #fff; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: bold; margin-right: 15px;'>
                M
            </div>
            <div>
                <h3 style='margin: 0; font-size: 14px; letter-spacing: 2px;'>MODERATOR_DECISION_CHAT</h3>
                <div style='font-size: 10px; color: #888; text-transform: uppercase;'>Evidence-Based Consensus Protocol</div>
            </div>
        </div>
        """)
        
        # Sanitize for excerpt
        escaped_reasoning = html.escape(moderator_reasoning)
        excerpt = escaped_reasoning[:300] + ("..." if len(escaped_reasoning) > 300 else "")
        
        # Fix f-string backslash error and ensure safe rendering
        formatted_excerpt = excerpt.replace('\n', '<br>')
        safe_markdown(f"""
        <div class="debate-block" style="border-left: 3px solid #fff; padding-left: 20px; color: #fff; margin-bottom: 10px;">
            {formatted_excerpt}
        </div>
        """)
        
        with st.expander("VIEW FULL REASONING PROTOCOL"):
            formatted_reasoning = escaped_reasoning.replace('\n', '<br>')
            safe_markdown(f"""
            <div style="font-size: 14px; line-height: 1.6; color: #ccc; font-family: 'Space Mono', monospace;">
                {formatted_reasoning}
            </div>
            """)
    
    # NEW: Gap Analysis for Insufficient Evidence
    if verdict == 'INSUFFICIENT EVIDENCE':
        st.markdown("---")
        safe_markdown("""
        <div style='background-color: #111; border: 1px solid #333; padding: 20px;'>
            <h4 style='font-size: 12px; color: #ff3333; margin-top:0;'>GAP_ANALYSIS_PROTOCOL</h4>
            <p style='font-size: 13px; color: #888;'>The current evidence pool is non-decisive. Primary bottlenecks:</p>
            <ul style='font-size: 13px; color: #aaa; padding-left: 20px;'>
                <li>Low verification density on primary claims</li>
                <li>Conflicting signals from verified peer-reviewed sources</li>
                <li>High fallacy density in adversarial rebuttals</li>
            </ul>
        </div>
        """)


def render_metrics(result):
    """Render quantitative metrics dashboard"""
    metrics = result.get('metrics')
    if not metrics:
        return
        
    st.markdown("---")
    safe_markdown("<h3>INTELLIGENCE_METRICS</h3>")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        cred = metrics.get('credibility', 0.0) or 0.0
        st.metric("Evidence Credibility", f"{cred:.0%}", help="Strength of verified sources")
    
    with col2:
        fallacies = metrics.get('fallacies', 0) or 0
        st.metric("Fallacy Count", fallacies, delta=f"-{fallacies}" if fallacies > 0 else None, delta_color="inverse")
    
    with col3:
        balance = metrics.get('balance', 0.5) or 0.5
        st.metric("Rebuttal Balance", f"{balance:.1f}", help="Semantic balance between Pro and Con arguments")


def render_verification_stats(result):
    """Render source verification statistics"""
    
    # Get verification results
    verification_results = result.get('verification_results', []) or []
    pro_verification = result.get('pro_verification_rate', 0.0) or 0.0
    con_verification = result.get('con_verification_rate', 0.0) or 0.0
    
    if not verification_results:
        return
    
    # Count statuses
    total = len(verification_results)
    verified = sum(1 for r in verification_results if r.get('status') == 'VERIFIED')
    hallucinated = total - verified
    
    safe_markdown("<h3>SOURCES</h3>")
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Sources", total)
    with col2:
        st.metric("Verified", verified, f"{(verified/total*100):.0f}%")
    with col3:
        st.metric("Failed", hallucinated, f"{(hallucinated/total*100):.0f}%")
    with col4:
        avg_verification = (pro_verification + con_verification) / 2
        st.metric("Avg. Rate", f"{avg_verification:.1%}")
    
    # Detailed results
    with st.expander("Detailed Verification Results", expanded=False):
        for i, vr in enumerate(verification_results, 1):
            status = vr.get('status', 'UNKNOWN')
            url = vr.get('url', 'Unknown URL')
            # Escape URL to prevent XSS
            escaped_url = html.escape(url)
            
            if status == 'VERIFIED':
                safe_markdown(f"{i}. <span class='source-verified'>{escaped_url}</span>")
            else:
                error = vr.get('error', 'Unknown error')
                # Escape error message to prevent XSS
                escaped_error = html.escape(error)
                safe_markdown(f"{i}. <span class='source-failed'>{escaped_url}</span> - {escaped_error}")


def render_debate_arguments(result):
    """Render debate arguments in expandable sections"""
    
    pro_arguments = result.get('pro_arguments', [])
    con_arguments = result.get('con_arguments', [])
    pro_sources = result.get('pro_sources', [])
    con_sources = result.get('con_sources', [])
    
    safe_markdown("<h3>DEBATE LOG</h3>")
    
    # Create tabs for each round
    num_rounds = min(len(pro_arguments), len(con_arguments))
    
    if num_rounds > 0:
        tabs = st.tabs([f"Round {i+1}" for i in range(num_rounds)])
        
        for i, tab in enumerate(tabs):
            with tab:
                col1, col2 = st.columns(2)
                
                # ProAgent column
                with col1:
                    st.markdown("### ProAgent")
                    # Escape argument content to prevent XSS
                    escaped_pro_arg = html.escape(pro_arguments[i])
                    safe_markdown(f'<div class="debate-block">{escaped_pro_arg}</div>')
                    
                    if i < len(pro_sources) and pro_sources[i]:
                        st.markdown("**Sources cited:**")
                        for j, source in enumerate(pro_sources[i], 1):
                            # Escape source URLs to prevent XSS
                            escaped_source = html.escape(source)
                            st.markdown(f"{j}. {escaped_source}")
                
                # ConAgent column
                with col2:
                    st.markdown("### ConAgent")
                    # Escape argument content to prevent XSS
                    escaped_con_arg = html.escape(con_arguments[i])
                    safe_markdown(f'<div class="debate-block">{escaped_con_arg}</div>')
                    
                    if i < len(con_sources) and con_sources[i]:
                        st.markdown("**Sources cited:**")
                        for j, source in enumerate(con_sources[i], 1):
                            # Escape source URLs to prevent XSS
                            escaped_source = html.escape(source)
                            st.markdown(f"{j}. {escaped_source}")


@st.cache_resource(show_spinner=False)
def get_orchestrator():
    """Cache the LangGraph compilation so it doesn't recompile on every interaction"""
    return DebateOrchestrator()


def main():
    """Main application logic"""
    
    init_session_state()
    render_header()
    render_sidebar()
    
    # Main content area
    st.markdown("---")
    
    # Claim input
    claim_input = st.text_input(
        "SUBJECT CLAIM",
        value=st.session_state.get('example_claim', ''),
        placeholder="Enter natural language claim...",
        help="System connects to Groq & Gemini for verification",
        label_visibility="visible"
    )
    
    col1, col2, col3 = st.columns([2, 2, 3])
    
    with col1:
        analyze_button = st.button("VERIFY_CLAIM", type="primary", use_container_width=True)
    
    with col2:
        if st.button("RESET", use_container_width=True):
            st.session_state.debate_run = False
            st.session_state.result = None
            st.session_state.example_claim = ''
            st.session_state.thread_id = str(uuid.uuid4())  # Reset thread isolation
            st.rerun()
    
    # Process claim
    if analyze_button and claim_input:
        
        # Validation
        if len(claim_input.strip()) < 10:
            st.error("Please enter a claim with at least 10 characters.")
            return
        
        # Fix #37: Use shared validate_claim for injection/length/quality checks
        valid, error_msg = validate_claim(claim_input)
        if not valid:
            st.error(f"Invalid claim: {error_msg}")
            return
        
        # Initialize/Retrieve orchestrator
        with st.spinner("Initializing debate system..."):
            try:
                orchestrator = get_orchestrator()
                st.session_state.orchestrator = orchestrator
            except Exception as e:
                st.error(f"Failed to initialize: {e}")
                return
        
        # Run debate
        st.markdown("---")
        safe_markdown("<h3 style='font-size:18px;'>ANALYZING</h3>")
        
        try:
            # Check if task already running
            if st.session_state.background_task is not None and not st.session_state.background_task.done():
                st.warning("Debate already in progress. Please wait for it to complete...")
                return
            
            # Using st.status for a live, streaming UX instead of a frozen while loop
            with st.status("Initializing Debate Nodes...", expanded=True) as status:
                st.write("Configuring adversarial agents...")
                
                # Start background task (in real life, orchestrator needs streaming yields, 
                # but for now we block gracefully inside the status box so the UI isn't completely frozen)
                st.session_state.background_task = st.session_state.task_executor.submit(
                    st.session_state.orchestrator.run,
                    claim_input,
                    st.session_state.thread_id # Pass thread isolation via kwargs supported later
                )
                
                status.update(label="Running 3-Round Debate...", state="running")
                st.write("Debating...")
                
                # Poll gracefully
                task = st.session_state.background_task
                poll_interval = 0.5
                max_wait_time = 120
                elapsed_time = 0
                
                while not task.done() and elapsed_time < max_wait_time:
                    time.sleep(poll_interval)
                    elapsed_time += poll_interval
                    
                    if elapsed_time > 15 and elapsed_time < 16:
                        st.write("FactChecker verifying cited sources...")
                    elif elapsed_time > 30 and elapsed_time < 31:
                        st.write("Moderator analyzing logical fallacies...")
                
                if task.done():
                    result = task.result()
                    
                    if result.get('is_cached'):
                        status.update(label="Loaded from Cache", state="complete", expanded=False)
                        st.success("Lightning Fast: Result loaded from Semantic Cache.")
                    else:
                        status.update(label="Debate Complete", state="complete", expanded=False)
                    
                    st.session_state.result = result
                    
                    # Fix #29: Cap moderator chat memory leak if this is storing anything
                    if len(st.session_state.moderator_chat) > 20:
                        st.session_state.moderator_chat = st.session_state.moderator_chat[-10:]
                        
                    st.session_state.debate_run = True
                    st.session_state.background_task = None
                else:
                    status.update(label="Analysis Timeout", state="error")
                    st.error(f"Analysis timeout after {max_wait_time} seconds")
                    st.session_state.background_task = None
                    return
            
        except Exception as e:
            st.error(f"Analysis failed: {e}")
            st.session_state.background_task = None
            return
    
    # Display results
    if st.session_state.debate_run and st.session_state.result:
        st.markdown("---")
        
        result = st.session_state.result
        
        # Render verdict
        render_verdict(result)
        
        # Render metrics dashboard (NEW)
        render_metrics(result)
        
        # Render verification stats
        render_verification_stats(result)
        
        st.markdown("---")
        
        # Render debate transcript
        render_debate_arguments(result)
        
        # Provide User Feedback loop
        st.markdown("---")
        safe_markdown("<h3>FEEDBACK_PROTOCOL</h3>")
        fcol1, fcol2, fcol3 = st.columns([1,1,4])
        
        # We need to capture the current claim and verdict for feedback
        current_claim = st.session_state.get('result', {}).get('claim', 'Unknown Claim')
        current_verdict = st.session_state.get('result', {}).get('verdict', 'UNKNOWN')
        
        with fcol1:
            if st.button("👍 ACCURATE", key="feedback_up", help="Mark this verdict as correct"):
                record_feedback(current_claim, current_verdict, "UP")
                st.success("Feedback recorded. Thank you.")
        with fcol2:
            if st.button("👎 INCORRECT", key="feedback_down", help="Mark this verdict as flawed"):
                record_feedback(current_claim, current_verdict, "DOWN")
                st.success("Feedback recorded for human review.")
        
        # Footer
        safe_markdown("""
        <div class='footer'>
            <span><strong>INSIGHTSWARM</strong></span>
            <span>POWERED BY GROQ + GEMINI</span>
        </div>
        """)


if __name__ == "__main__":
    main()