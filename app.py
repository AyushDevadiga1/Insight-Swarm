"""
InsightSwarm Streamlit Web Interface

Public demo of multi-agent fact-checking system with source verification
"""

import streamlit as st
import time
import html
from concurrent.futures import ThreadPoolExecutor
from src.orchestration.debate import DebateOrchestrator

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


def init_session_state():
    """Initialize session state variables"""
    if 'debate_run' not in st.session_state:
        st.session_state.debate_run = False
    if 'result' not in st.session_state:
        st.session_state.result = None
    if 'orchestrator' not in st.session_state:
        st.session_state.orchestrator = None
    if 'background_task' not in st.session_state:
        st.session_state.background_task = None
    if 'task_executor' not in st.session_state:
        st.session_state.task_executor = ThreadPoolExecutor(max_workers=1)


def render_header():
    st.markdown(
        """
        <div class="main-header">INSIGHTSWARM</div>
        <div class="sub-header">
        Multi-Agent Truth Verification Protocol
        </div>
        """,
        unsafe_allow_html=True
    )


def render_sidebar():
    """Render sidebar with information"""
    with st.sidebar:
        st.markdown("<h3 style='text-transform:uppercase;letter-spacing:2px;font-size:12px;color:#888;margin-bottom:16px;'>Architecture</h3>", unsafe_allow_html=True)
        
        st.markdown("""
        <div style='font-size: 13px; color: #aaa; line-height: 1.8; margin-bottom: 30px;'>
        <p style='border-left: 1px solid #333; padding-left: 12px; margin-bottom: 16px;'>
        <strong>01 ProAgent</strong><br/>
        Validates claim assumptions.<br/>
        Source aggregation.</p>
        
        <p style='border-left: 1px solid #333; padding-left: 12px; margin-bottom: 16px;'>
        <strong>02 ConAgent</strong><br/>
        Invalidates claim assumptions.<br/>
        Adversarial execution.</p>
        
        <p style='border-left: 1px solid #333; padding-left: 12px;'>
        <strong>03 FactChecker</strong><br/>
        Source verification.<br/>
        Consensus modeling.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        st.header("Example Claims")
        
        example_claims = [
            "Coffee prevents cancer",
            "Exercise improves mental health",
            "The Earth is flat",
            "Vaccines cause autism",
            "AI will replace all jobs by 2030"
        ]
        
        st.markdown("<div style='font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#666;margin-bottom:12px;'>Pre-verified queries</div>", unsafe_allow_html=True)
        for claim in example_claims:
            if st.button(claim, key=f"example_{claim}", use_container_width=True):
                st.session_state.example_claim = claim
                st.rerun()


def render_verdict(result):
    """Render verdict with styled box"""
    verdict = result.get('verdict', 'UNKNOWN')
    confidence = result.get('confidence', 0.0)
    moderator_reasoning = result.get('moderator_reasoning', '')
    
    # Determine verdict class
    verdict_class = {
        'TRUE': 'verdict-true',
        'FALSE': 'verdict-false',
        'PARTIALLY TRUE': 'verdict-partial'
    }.get(verdict, 'verdict-partial')
    
    # Escape verdict string to prevent XSS
    escaped_verdict = html.escape(verdict)
    
    st.markdown(f"""
    <div class="verdict-box {verdict_class}">
        <strong>{escaped_verdict}</strong><br>
        Confidence: {confidence:.1%}
    </div>
    """, unsafe_allow_html=True)
    
    # NEW: Display Moderator's reasoning
    if moderator_reasoning:
        st.markdown("---")
        st.subheader("🎓 Moderator's Analysis")
        
        st.markdown(f"""
        <div class="agent-card">
        <p><strong>The Moderator reviewed all arguments and evidence to reach this verdict:</strong></p>
        <p>{moderator_reasoning}</p>
        </div>
        """, unsafe_allow_html=True)


def render_verification_stats(result):
    """Render source verification statistics"""
    
    # Get verification results
    verification_results = result.get('verification_results', [])
    pro_verification = result.get('pro_verification_rate', 0.0)
    con_verification = result.get('con_verification_rate', 0.0)
    
    if not verification_results:
        return
    
    # Count statuses
    total = len(verification_results)
    verified = sum(1 for r in verification_results if r.get('status') == 'VERIFIED')
    hallucinated = total - verified
    
    st.markdown("<h3>SOURCES</h3>", unsafe_allow_html=True)
    
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
                st.markdown(f"{i}. <span class='source-verified'>{escaped_url}</span>", unsafe_allow_html=True)
            else:
                error = vr.get('error', 'Unknown error')
                # Escape error message to prevent XSS
                escaped_error = html.escape(error)
                st.markdown(f"{i}. <span class='source-failed'>{escaped_url}</span> - {escaped_error}", unsafe_allow_html=True)


def render_debate_arguments(result):
    """Render debate arguments in expandable sections"""
    
    pro_arguments = result.get('pro_arguments', [])
    con_arguments = result.get('con_arguments', [])
    pro_sources = result.get('pro_sources', [])
    con_sources = result.get('con_sources', [])
    
    st.markdown("<h3>DEBATE LOG</h3>", unsafe_allow_html=True)
    
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
                    st.markdown(f'<div class="debate-block">{escaped_pro_arg}</div>', unsafe_allow_html=True)
                    
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
                    st.markdown(f'<div class="debate-block">{escaped_con_arg}</div>', unsafe_allow_html=True)
                    
                    if i < len(con_sources) and con_sources[i]:
                        st.markdown("**Sources cited:**")
                        for j, source in enumerate(con_sources[i], 1):
                            # Escape source URLs to prevent XSS
                            escaped_source = html.escape(source)
                            st.markdown(f"{j}. {escaped_source}")


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
            st.rerun()
    
    # Process claim
    if analyze_button and claim_input:
        
        # Validation
        if len(claim_input.strip()) < 10:
            st.error("Please enter a claim with at least 10 characters.")
            return
        
        # Initialize orchestrator
        if st.session_state.orchestrator is None:
            with st.spinner("Initializing debate system..."):
                try:
                    st.session_state.orchestrator = DebateOrchestrator()
                except Exception as e:
                    st.error(f"Failed to initialize: {e}")
                    return
        
        # Run debate
        st.markdown("---")
        st.markdown("<h3 style='font-size:18px;'>ANALYZING</h3>", unsafe_allow_html=True)
        
        # Progress indicators
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Start background task on first run
            if st.session_state.background_task is None:
                st.session_state.background_task = st.session_state.task_executor.submit(
                    st.session_state.orchestrator.run,
                    claim_input
                )
                status_text.text("Connecting nodes...")
                progress_bar.progress(10)
            
            # Poll background task for completion
            task = st.session_state.background_task
            poll_interval = 0.5  # Check task every 500ms
            max_wait_time = 120  # Max 2 minutes timeout
            elapsed_time = 0
            progress = 10
            
            while not task.done() and elapsed_time < max_wait_time:
                elapsed_time += poll_interval
                
                # Update progress gradually (10% to 90%)
                if elapsed_time < max_wait_time * 0.8:
                    progress = min(90, 10 + int(80 * (elapsed_time / (max_wait_time * 0.8))))
                else:
                    progress = 90
                
                progress_bar.progress(progress)
                status_text.text(f"Processing... {elapsed_time:.1f}s")
                time.sleep(poll_interval)
            
            # Task completed or timed out
            if task.done():
                result = task.result()  # Retrieve the result from background task
                
                progress_bar.progress(75)
                status_text.text("🔍 FactChecker verifying sources...")
                time.sleep(0.5)
                
                progress_bar.progress(85)
                status_text.text("🎓 Moderator analyzing debate quality...")  # NEW
                time.sleep(0.5)
                
                progress_bar.progress(95)
                status_text.text("⚖️ Calculating final verdict...")
                time.sleep(0.2)
                
                progress_bar.progress(100)
                status_text.text("Complete.")
                time.sleep(0.3)
                
                # Store result
                st.session_state.result = result
                st.session_state.debate_run = True
                st.session_state.background_task = None  # Reset for next run
            else:
                st.error(f"Analysis timeout after {max_wait_time} seconds")
                st.session_state.background_task = None
                progress_bar.empty()
                status_text.empty()
                return
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
        except Exception as e:
            st.error(f"Analysis failed: {e}")
            progress_bar.empty()
            status_text.empty()
            st.session_state.background_task = None
            return
    
    # Display results
    if st.session_state.debate_run and st.session_state.result:
        st.markdown("---")
        
        result = st.session_state.result
        
        # Render verdict
        render_verdict(result)
        
        # Render verification stats
        render_verification_stats(result)
        
        st.markdown("---")
        
        # Render debate transcript
        render_debate_arguments(result)
        
        # Footer
        st.markdown("""
        <div class='footer'>
            <span><strong>INSIGHTSWARM</strong></span>
            <span>POWERED BY GROQ + GEMINI</span>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()