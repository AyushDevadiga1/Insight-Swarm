
---

# InsightSwarm: A Multi-Agent Fact-Checking System with Adversarial Debate and Source Verification

**Soham Gawas**  
*Bharat College of Engineering, University of Mumbai*  
soham.gawas@example.edu

**Bhargav Ghawali**  
*Bharat College of Engineering, University of Mumbai*  
bhargav.ghawali@example.edu

**Mahesh Gawali**  
*Bharat College of Engineering, University of Mumbai*  
mahesh.gawali@example.edu

**Ayush Devadiga**  
*Bharat College of Engineering, University of Mumbai*  
ayush.devadiga@example.edu

Guided by: **Prof. Shital Gujar**  
Department of Computer Science and Engineering (AI & ML), Bharat College of Engineering

(Submitted on 16 Mar 2026)

## Abstract
The rapid spread of misinformation, particularly on social media and messaging platforms, poses a significant societal challenge. Existing solutions, including manual fact-checking and single large language model (LLM) systems, face limitations in scalability, source hallucination, and transparency. This paper presents InsightSwarm, a multi-agent AI fact-checking system designed to address these issues. InsightSwarm employs four specialized agents—ProAgent, ConAgent, FactChecker, and Moderator—orchestrated by LangGraph to engage in a structured, adversarial debate on a given claim. A key innovation is its anti-hallucination layer, where the FactChecker agent fetches and validates every cited source in real-time, using content matching to ensure accuracy. This process reduces source hallucination from rates observed in single-agent systems (15-30%) to under 5% in our validation tests. The system is built entirely on free-tier infrastructure, including the Groq API for primary LLM inference (Llama 3.1 70B) and Streamlit Cloud for deployment. We detail the system architecture, the weighted consensus algorithm used by the Moderator, and the implementation roadmap derived from project documentation. An evaluation using a test suite of 38 tests demonstrates 100% pass rates for core components, and validation on a set of benchmark claims indicates 75-80% agreement with professional fact-checkers. InsightSwarm provides a transparent, scalable, and cost-effective approach to automated fact-checking, with all code and documentation openly available.

## 1 Introduction
The digital information ecosystem is increasingly vulnerable to misinformation. In India, a 2023 study cited in the project's problem statement indicates that 67% of internet users share content without verification, and deepfake incidents have increased by 900% [1]. This crisis outpaces the capabilities of traditional manual fact-checking, which can take days per claim. While single large language models (LLMs) offer speed, they are prone to "hallucinating" sources, fabricating citations 15-30% of the time, and operate as "black boxes," offering little to no transparency into their reasoning.

InsightSwarm is a project developed to confront these challenges. It is a multi-agent system where four AI agents, each with a distinct role, debate a claim. This adversarial process forces a thorough examination of evidence from multiple perspectives. The core of the system is a built-in verification layer: every source cited by an agent is automatically fetched and checked for existence and content relevance. This design aims to provide a verdict that is not only fast but also verifiable and transparent.

This paper describes the architecture, methodology, and current status of InsightSwarm. It details the function of each agent, the orchestration framework, and the technical implementation choices that enable it to operate on zero-cost infrastructure. We also present the project's development roadmap and results from its validation testing.

## 2 System Architecture and Design
The architecture of InsightSwarm is modular, designed for clear separation of concerns between debate, verification, and orchestration. The complete system design is documented in the project's `InsightSwarm_Design_Document.docx` [2].

### 2.1 Agents
The system uses four specialized agents:
*   **ProAgent:** Tasked with arguing that a claim is **TRUE**. Its role is to find and present the strongest supporting evidence from retrieved sources. It is implemented with adversarial prompts to argue its assigned position forcefully, regardless of the underlying facts.
*   **ConAgent:** Tasked with arguing that a claim is **FALSE**. Its role is to challenge the evidence presented by ProAgent and find counter-evidence. This creates the core adversarial dynamic.
*   **FactChecker:** This agent is the system's anti-hallucination layer. It does not debate but performs a critical verification function. It takes all URLs cited by ProAgent and ConAgent, attempts to fetch the content, and uses fuzzy string matching to verify if the source actually supports the claim made by the agent.
*   **Moderator:** After three rounds of debate and verification, the Moderator agent synthesizes all arguments and the FactChecker's report to produce a final verdict. It uses a weighted consensus algorithm where the FactChecker's assessment has double weight, reflecting the project's priority on source integrity.

### 2.2 Orchestration with LangGraph
The workflow is orchestrated as a state machine using LangGraph [3]. The process begins with a user's claim and proceeds through a defined graph of nodes:
1.  **Source Retrieval:** The system fetches relevant context using the Wikipedia API and the Brave Search API to ground the debate in real-world information.
2.  **Multi-Agent Debate:** The graph manages a three-round exchange between ProAgent and ConAgent. After the initial arguments, FactChecker validates the cited sources.
3.  **Verdict Calculation:** The results are passed to the Moderator node, which calculates the final verdict and confidence score.
4.  **Output:** The final state, containing the verdict, confidence, and full debate transcript, is returned to the user interface.

### 2.3 Technology Stack
A core objective of InsightSwarm is to build a production-grade system without incurring costs. The technology stack, detailed in the `InsightSwarm_Project_Plan.pdf` [4], reflects this:
*   **Primary LLM:** Groq API (Llama 3.1 70B) - chosen for its generous free tier and low latency.
*   **Backup LLM:** Google Gemini 1.5 Flash - provides a free fallback option.
*   **Orchestration:** LangGraph - an open-source library for building stateful, multi-agent applications.
*   **Frontend:** Streamlit - used to build a web interface quickly, deployable for free on Streamlit Cloud.
*   **Data Sources:** Wikipedia API and Brave Search API (2,000 free queries/month).
*   **Verification:** Python libraries (requests, BeautifulSoup4) for fetching and parsing web content, and `fuzzywuzzy` for string matching.
*   **Database:** SQLite for storing debate history.

## 3 Methodology: Debate and Verification
The methodology of InsightSwarm is built around two key processes: adversarial debate to explore a claim and source verification to ground it in reality.

### 3.1 Adversarial Debate Protocol
For each claim, the system initiates a structured debate of three rounds.
*   **Round 1:** ProAgent constructs an initial argument in favor of the claim, citing 2-3 sources. ConAgent then constructs a counter-argument, challenging the ProAgent's points and presenting its own evidence.
*   **Round 2 (Rebuttal):** Before Round 2 begins, the FactChecker verifies all sources from Round 1. The results are fed back to the agents. ProAgent and ConAgent then generate rebuttals, aiming to strengthen their positions while addressing the other's points and incorporating the verification feedback.
*   **Round 3 (Synthesis):** In the final round, agents provide a concluding summary, integrating the key points and evidence from the previous rounds.

### 3.2 Source Verification and Anti-Hallucination
The FactChecker is the core of the system's anti-hallucination mechanism. Its process is documented in the project's "Verification Report" and codebase [5].
1.  **Source Extraction:** It parses the outputs of ProAgent and ConAgent to extract every cited URL.
2.  **Content Fetching:** It attempts to fetch the content from each URL. Timeouts, 404 errors, and other failures are logged.
3.  **Content Validation:** For successfully fetched pages, the agent performs a two-step check:
    *   It extracts the main textual content.
    *   It compares this content against the agent's claim about that source using fuzzy string matching. If the similarity score is below a defined threshold (e.g., 70%), the source is marked as unverified, even if the URL is valid. This catches cases where an agent misrepresents a source's findings.
4.  **Weighted Voting:** The verification results are passed to the Moderator. A low verification rate for an agent's sources significantly reduces the weight of that agent's arguments in the final verdict, as the FactChecker's input is weighted double.

## 4 Implementation and Evaluation
InsightSwarm has been developed following an 8-week roadmap, with progress tracked in the project's GitHub repository [6] and detailed in the `InsightSwarm_Project_Plan.pdf` [4].

### 4.1 Implementation Status
Based on the repository's commit history and status, the following core features are implemented:
*   Multi-agent framework with ProAgent, ConAgent, FactChecker, and Moderator.
*   LangGraph orchestration for a 3-round debate.
*   Source verification module using BeautifulSoup and fuzzy string matching.
*   Weighted consensus algorithm for final verdict calculation.
*   Comprehensive test suite with 38 tests passing.
*   A functional Streamlit web interface and a CLI interface.
*   Deployment to Streamlit Cloud (https://insightswarm.streamlit.app).

### 4.2 Evaluation Metrics
The project defines several success metrics in its Product Requirements Document (PRD) [1] and Project Plan [4]. Based on the latest tests and validation scripts (e.g., `validate_day3.py`), the system's performance against these targets is as follows:

| Metric | Target (from PRD) | Current Status (from Repo) |
| :--- | :--- | :--- |
| Fact-checking Accuracy | 75%+ agreement with pros | **78%** (on internal test set) |
| Source Hallucination Rate | Under 5% | **< 2%** (in FactChecker validation) |
| End-to-end Response Time | Under 60 seconds | **~45-60 seconds** (in testing) |
| Source Verification | 100% of cited sources checked | **Yes** (core function) |
| Unit/Integration Test Pass | 100% | **38/38 tests passing** |
| User Satisfaction | 80%+ positive feedback | Data being collected |

### 4.3 Current Development and Future Enhancements
The project is under active development. The repository's "In Development" and "Planned" sections outline the next steps:
*   **In Development:** REST API endpoints, advanced analytics.
*   **Planned (Future Enhancements):** Real-time optimization for sub-60 second claims, multilingual support, and image/video fact-checking.

## 5 Conclusion
InsightSwarm presents a practical and novel approach to automated fact-checking. By combining a multi-agent adversarial debate with a dedicated, real-time source verification layer, the system directly tackles the critical issues of hallucination and lack of transparency found in single-LLM solutions. Its implementation on entirely free infrastructure demonstrates that such systems can be both powerful and sustainable. The open-source release of the code, along with comprehensive documentation and planning materials, provides a foundation for future research and development in multi-agent systems for misinformation detection. The next phases of the project will focus on expanding its capabilities to new media types and languages.

## Acknowledgments
The authors acknowledge the support and guidance of Prof. Shital Gujar from the Department of Computer Science and Engineering (AI & ML) at Bharat College of Engineering. We also thank the providers of the free infrastructure that made this project possible: Groq, Google (Gemini), Brave Software, and Streamlit.

## References
[1] InsightSwarm Team. (2025). *Product Requirements Document: InsightSwarm*. Bharat College of Engineering. [Online]. Available: https://github.com/AyushDevadiga1/Insight-Swarm/blob/main/planning/InsightSwarm_PRD.docx
[2] A. Devadiga, et al. (2025). *System Design Document: InsightSwarm*. Bharat College of Engineering. [Online]. Available: https://github.com/AyushDevadiga1/Insight-Swarm/blob/main/planning/InsightSwarm_Design_Document.docx
[3] LangChain. (2024). *LangGraph Documentation*. [Online]. Available: https://python.langchain.com/docs/langgraph
[4] InsightSwarm Team. (2026). *InsightSwarm Project Plan*. Bharat College of Engineering. [Online]. Available: https://github.com/AyushDevadiga1/Insight-Swarm/blob/main/planning/InsightSwarm_Project_Plan.pdf
[5] InsightSwarm Repository. (2026). *Verification Report (Day 3 FactChecker Implementation)*. [Online]. Available: https://github.com/AyushDevadiga1/Insight-Swarm/tree/main/progress
[6] A. Devadiga, et al. (2026). *Insight-Swarm GitHub Repository*. [Online]. Available: https://github.com/AyushDevadiga1/Insight-Swarm

