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
    page_title="InsightSwarm - AI Fact Checker",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        color: #1E3A8A;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        text-align: center;
        color: #64748B;
        margin-bottom: 2rem;
    }
    .verdict-true {
        background-color: #DCFCE7;
        border-left: 5px solid #16A34A;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .verdict-false {
        background-color: #FEE2E2;
        border-left: 5px solid #DC2626;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .verdict-partial {
        background-color: #FEF3C7;
        border-left: 5px solid #F59E0B;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .agent-card {
        background-color: #F8FAFC;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
        border: 1px solid #E2E8F0;
    }
    .source-verified {
        color: #16A34A;
        font-weight: bold;
    }
    .source-failed {
        color: #DC2626;
        font-weight: bold;
    }
    .metric-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 0.75rem;
        color: white;
        text-align: center;
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
    """Render page header"""
    st.markdown('<div class="main-header">🔍 InsightSwarm</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Multi-Agent AI Fact-Checking System with Source Verification</div>',
        unsafe_allow_html=True
    )


def render_sidebar():
    """Render sidebar with information"""
    with st.sidebar:
        st.header("ℹ️ How It Works")
        
        st.markdown("""
        **InsightSwarm** uses 3 AI agents to verify claims:
        
        1. **ProAgent** 📘
           - Argues the claim is TRUE
           - Finds supporting evidence
           
        2. **ConAgent** 📕
           - Argues the claim is FALSE
           - Challenges evidence
           
        3. **FactChecker** 🔍
           - Verifies all cited sources
           - Detects hallucinations
           - Weights final verdict
        
        The system runs 3 rounds of debate, then calculates a weighted verdict based on argument quality and source verification.
        """)
        
        st.divider()
        
        st.header("📊 Example Claims")
        
        example_claims = [
            "Coffee prevents cancer",
            "Exercise improves mental health",
            "The Earth is flat",
            "Vaccines cause autism",
            "AI will replace all jobs by 2030"
        ]
        
        st.markdown("**Try these:**")
        for claim in example_claims:
            if st.button(claim, key=f"example_{claim}", use_container_width=True):
                st.session_state.example_claim = claim
                st.rerun()


def render_verdict(result):
    """Render verdict with styled box"""
    verdict = result.get('verdict', 'UNKNOWN')
    confidence = result.get('confidence', 0.0)
    
    # Determine verdict class
    verdict_class = {
        'TRUE': 'verdict-true',
        'FALSE': 'verdict-false',
        'PARTIALLY TRUE': 'verdict-partial'
    }.get(verdict, 'verdict-partial')
    
    # Verdict emoji
    verdict_emoji = {
        'TRUE': '✅',
        'FALSE': '❌',
        'PARTIALLY TRUE': '⚠️'
    }.get(verdict, '❓')
    
    # Escape verdict string to prevent XSS
    escaped_verdict = html.escape(verdict)
    
    st.markdown(f"""
    <div class="{verdict_class}">
        <h2>{verdict_emoji} Verdict: {escaped_verdict}</h2>
        <h3>Confidence: {confidence:.1%}</h3>
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
    
    st.header("🔍 Source Verification Results")
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Sources", total)
    with col2:
        st.metric("✅ Verified", verified, f"{(verified/total*100):.0f}%")
    with col3:
        st.metric("❌ Failed", hallucinated, f"{(hallucinated/total*100):.0f}%")
    with col4:
        avg_verification = (pro_verification + con_verification) / 2
        st.metric("Avg. Rate", f"{avg_verification:.1%}")
    
    # Detailed results
    with st.expander("📋 Detailed Verification Results", expanded=False):
        for i, vr in enumerate(verification_results, 1):
            status = vr.get('status', 'UNKNOWN')
            url = vr.get('url', 'Unknown URL')
            # Escape URL to prevent XSS
            escaped_url = html.escape(url)
            
            if status == 'VERIFIED':
                st.markdown(f"{i}. <span class='source-verified'>✅ {escaped_url}</span>", unsafe_allow_html=True)
            else:
                error = vr.get('error', 'Unknown error')
                # Escape error message to prevent XSS
                escaped_error = html.escape(error)
                st.markdown(f"{i}. <span class='source-failed'>❌ {escaped_url}</span> - {escaped_error}", unsafe_allow_html=True)


def render_debate_arguments(result):
    """Render debate arguments in expandable sections"""
    
    pro_arguments = result.get('pro_arguments', [])
    con_arguments = result.get('con_arguments', [])
    pro_sources = result.get('pro_sources', [])
    con_sources = result.get('con_sources', [])
    
    st.header("💬 Debate Transcript")
    
    # Create tabs for each round
    num_rounds = min(len(pro_arguments), len(con_arguments))
    
    if num_rounds > 0:
        tabs = st.tabs([f"Round {i+1}" for i in range(num_rounds)])
        
        for i, tab in enumerate(tabs):
            with tab:
                col1, col2 = st.columns(2)
                
                # ProAgent column
                with col1:
                    st.markdown("### 📘 ProAgent (Argues TRUE)")
                    # Escape argument content to prevent XSS
                    escaped_pro_arg = html.escape(pro_arguments[i])
                    st.markdown(f'<div class="agent-card">{escaped_pro_arg}</div>', unsafe_allow_html=True)
                    
                    if i < len(pro_sources) and pro_sources[i]:
                        st.markdown("**Sources cited:**")
                        for j, source in enumerate(pro_sources[i], 1):
                            # Escape source URLs to prevent XSS
                            escaped_source = html.escape(source)
                            st.markdown(f"{j}. {escaped_source}")
                
                # ConAgent column
                with col2:
                    st.markdown("### 📕 ConAgent (Argues FALSE)")
                    # Escape argument content to prevent XSS
                    escaped_con_arg = html.escape(con_arguments[i])
                    st.markdown(f'<div class="agent-card">{escaped_con_arg}</div>', unsafe_allow_html=True)
                    
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
        "Enter a claim to fact-check:",
        value=st.session_state.get('example_claim', ''),
        placeholder="e.g., Coffee prevents cancer",
        help="Enter any factual claim you want to verify"
    )
    
    col1, col2, col3 = st.columns([1, 1, 4])
    
    with col1:
        analyze_button = st.button("🔍 Analyze Claim", type="primary", use_container_width=True)
    
    with col2:
        if st.button("🔄 Clear", use_container_width=True):
            st.session_state.debate_run = False
            st.session_state.result = None
            st.session_state.example_claim = ''
            st.rerun()
    
    # Process claim
    if analyze_button and claim_input:
        
        # Validation
        if len(claim_input.strip()) < 10:
            st.error("⚠️ Please enter a claim with at least 10 characters.")
            return
        
        # Initialize orchestrator
        if st.session_state.orchestrator is None:
            with st.spinner("🔧 Initializing debate system..."):
                try:
                    st.session_state.orchestrator = DebateOrchestrator()
                except Exception as e:
                    st.error(f"❌ Failed to initialize: {e}")
                    return
        
        # Run debate
        st.markdown("---")
        st.header("⏳ Running Analysis...")
        
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
                status_text.text("🤖 ProAgent and ConAgent debating...")
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
                status_text.text(f"🤖 Analyzing claim... ({elapsed_time:.1f}s)")
                time.sleep(poll_interval)
            
            # Task completed or timed out
            if task.done():
                result = task.result()  # Retrieve the result from background task
                
                progress_bar.progress(95)
                status_text.text("🔍 Finalizing results...")
                time.sleep(0.2)
                
                progress_bar.progress(100)
                status_text.text("✅ Analysis complete!")
                time.sleep(0.3)
                
                # Store result
                st.session_state.result = result
                st.session_state.debate_run = True
                st.session_state.background_task = None  # Reset for next run
            else:
                st.error(f"❌ Analysis timeout after {max_wait_time} seconds")
                st.session_state.background_task = None
                progress_bar.empty()
                status_text.empty()
                return
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
        except Exception as e:
            st.error(f"❌ Analysis failed: {e}")
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
        st.markdown("---")
        st.markdown("""
        <div style='text-align: center; color: #64748B; padding: 2rem;'>
            <p>Built with InsightSwarm - Multi-Agent Fact-Checking System</p>
            <p>Powered by Groq (Llama 3.1) and Google Gemini</p>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()