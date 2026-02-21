# InsightSwarm - Prerequisites & Setup Guide

**Complete Environment Setup for All Team Members**

*Last Updated: February 2025*  
*Estimated Time: 2-3 hours*

---

## 📋 **Table of Contents**

1. [Software Installation](#1-software-installation)
2. [Account Setup & API Keys](#2-account-setup--api-keys)
3. [Project Setup](#3-project-setup)
4. [Verify Installation](#4-verify-installation)
5. [Team Workflow Standards](#5-team-workflow-standards)
6. [Troubleshooting](#6-troubleshooting)

---

## **1. Software Installation**

### **1.1 Install Python 3.11**

**Why Python 3.11?**  
- Stable, fast, and all our libraries work with it
- Not too new (3.12 has compatibility issues)
- Not too old (3.9 missing features)

#### **For Windows:**

1. Go to: https://www.python.org/downloads/release/python-3110/
2. Scroll down to "Files"
3. Download: **Windows installer (64-bit)**
4. Run the installer
5. ⚠️ **IMPORTANT:** Check "Add Python to PATH" before clicking Install
6. Click "Install Now"
7. Wait for installation to complete

**Verify:**
```bash
# Open Command Prompt (cmd)
python --version
```
**Expected output:** `Python 3.11.x`

If you see `Python 3.9` or `Python 3.12`, you need to uninstall and reinstall 3.11.

#### **For Mac:**

1. Go to: https://www.python.org/downloads/release/python-3110/
2. Download: **macOS 64-bit universal2 installer**
3. Open the downloaded `.pkg` file
4. Follow installation steps
5. Open Terminal and verify

**Verify:**
```bash
python3 --version
```
**Expected output:** `Python 3.11.x`

#### **For Linux (Ubuntu/Debian):**

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip
```

**Verify:**
```bash
python3.11 --version
```

---

### **1.2 Install Visual Studio Code (VS Code)**

**Why VS Code?**
- Free, lightweight, best Python support
- Works on Windows, Mac, Linux
- Extensions for everything we need

#### **Download & Install:**

1. Go to: https://code.visualstudio.com/
2. Click "Download for [Your OS]"
3. Run installer
4. **Windows:** Check "Add to PATH" during installation
5. **Mac:** Drag to Applications folder
6. **Linux:** Follow instructions for your distribution

**Verify:**
```bash
code --version
```

#### **Install Essential Extensions:**

1. Open VS Code
2. Click Extensions icon (or press `Ctrl+Shift+X` / `Cmd+Shift+X`)
3. Search and install these extensions:

**Required Extensions:**
- **Python** (by Microsoft) - Python language support
- **Pylance** (by Microsoft) - Fast Python IntelliSense
- **Jupyter** (by Microsoft) - For testing code snippets
- **GitLens** (by GitKraken) - See who wrote what code
- **Error Lens** (by Alexander) - See errors inline

**Recommended Extensions:**
- **GitHub Copilot** (by GitHub) - AI code suggestions (free for students)
- **Better Comments** (by Aaron Bond) - Color-coded comments
- **indent-rainbow** (by oderwat) - See indentation levels

**How to verify extensions are installed:**
- Click Extensions icon
- You should see them in "Installed" section

---

### **1.3 Install Git**

**Why Git?**
- Version control - never lose your code
- Collaborate without overwriting each other
- Industry standard

#### **For Windows:**

1. Go to: https://git-scm.com/download/win
2. Download and run installer
3. **During installation:**
   - Select "Use Visual Studio Code as Git's default editor"
   - Keep all other defaults
4. Complete installation

**Verify:**
```bash
git --version
```

#### **For Mac:**

```bash
# Git comes with Xcode Command Line Tools
xcode-select --install
```

**Or download from:** https://git-scm.com/download/mac

**Verify:**
```bash
git --version
```

#### **For Linux:**

```bash
sudo apt install git
```

**Verify:**
```bash
git --version
```

---

### **1.4 Install Ollama (Optional - Offline Backup)**

**Why Ollama?**
- Runs LLMs locally (no internet needed)
- Backup if Groq/Gemini APIs are down
- Free, unlimited usage

**Note:** This is OPTIONAL. You can skip if you have reliable internet.

#### **For Windows/Mac/Linux:**

1. Go to: https://ollama.ai/download
2. Download for your OS
3. Run installer
4. After installation, open terminal and run:

```bash
ollama pull llama3.1:8b
```

This downloads the Llama 3.1 8B model (~5GB, takes 10-20 minutes).

**Verify:**
```bash
ollama run llama3.1:8b "Hello, how are you?"
```

You should see a response from the model.

**To stop Ollama:**
```bash
# Press Ctrl+C
```

---

## **2. Account Setup & API Keys**

### **2.1 GitHub Account**

**If you already have GitHub account:** Skip to 2.2

**If you don't have GitHub account:**

1. Go to: https://github.com/signup
2. Enter your email (use college email for student benefits)
3. Create password
4. Choose username (professional name recommended)
5. Verify email
6. Complete setup

**Student Benefits (Optional but Recommended):**

1. Go to: https://education.github.com/pack
2. Click "Get your pack"
3. Upload student ID proof
4. Get GitHub Copilot free, GitHub Pro, etc.

---

### **2.2 Groq API Key (Primary LLM)**

**Free Tier:** 14,400 requests/day (enough for 960 debates)

**Steps:**

1. Go to: https://console.groq.com
2. Click "Sign Up" or "Log In"
3. Sign up with GitHub or Google
4. After login, go to: https://console.groq.com/keys
5. Click "Create API Key"
6. Give it a name: "InsightSwarm Development"
7. **IMPORTANT:** Copy the key immediately (starts with `gsk_...`)
8. Save it in a secure place (we'll add to project later)

**Your API key looks like:** `gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

**⚠️ NEVER share this key publicly or commit to GitHub!**

---

### **2.3 Google Gemini API Key (Backup LLM)**

**Free Tier:** 1,500 requests/day

**Steps:**

1. Go to: https://ai.google.dev
2. Click "Get API key in Google AI Studio"
3. Sign in with Google account
4. Click "Get API Key"
5. Click "Create API key in new project"
6. **IMPORTANT:** Copy the key immediately
7. Save it securely

**Your API key looks like:** `AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

---

### **2.4 Brave Search API Key (Web Search)**

**Free Tier:** 2,000 queries/month

**Steps:**

1. Go to: https://brave.com/search/api/
2. Click "Get Started"
3. Sign up with email
4. Verify email
5. Go to Dashboard: https://api.search.brave.com/app/dashboard
6. Copy your API key

**Your API key looks like:** `BSAxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

---

### **2.5 Streamlit Cloud Account (Deployment)**

**Free Tier:** Unlimited public apps

**Steps:**

1. Go to: https://streamlit.io/cloud
2. Click "Sign up"
3. Sign up with GitHub (recommended - easier deployment)
4. Authorize Streamlit to access your GitHub
5. Complete profile setup

**You'll use this later for deployment - just create account for now.**

---

## **3. Project Setup**

### **3.1 Fork & Clone Repository**

**Step 1: Fork the Repository**

1. Go to: https://github.com/AyushDevadiga1/Insight-Swarm
2. Click "Fork" button (top right)
3. This creates YOUR copy of the project

**Step 2: Clone to Your Computer**

**Open Terminal/Command Prompt:**

```bash
# Navigate to where you want the project
cd Desktop  # or wherever you keep projects

# Clone YOUR fork (replace YOUR_USERNAME)
git clone https://github.com/YOUR_USERNAME/Insight-Swarm.git

# Go into the project folder
cd Insight-Swarm
```

**Verify:**
```bash
ls  # Mac/Linux
dir  # Windows
```

You should see project files.

---

### **3.2 Create Virtual Environment**

**Why virtual environment?**
- Keeps project dependencies separate
- Different projects can use different library versions
- Prevents conflicts

**Create venv:**

#### **Windows:**
```bash
python -m venv venv
```

#### **Mac/Linux:**
```bash
python3.11 -m venv venv
```

**You should see a new `venv/` folder created.**

---

### **3.3 Activate Virtual Environment**

**You need to activate venv EVERY TIME you work on the project.**

#### **Windows (Command Prompt):**
```bash
venv\Scripts\activate
```

#### **Windows (PowerShell):**
```bash
venv\Scripts\Activate.ps1
```

**If you get error:** "Execution of scripts is disabled"
```bash
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Then try activate command again.

#### **Mac/Linux:**
```bash
source venv/bin/activate
```

**You know it worked when you see:**
```bash
(venv) C:\Users\YourName\Desktop\Insight-Swarm>
```

The `(venv)` at the start means you're in the virtual environment.

**To deactivate later:**
```bash
deactivate
```

---

### **3.4 Install Python Dependencies**

**Make sure venv is activated first!** (You should see `(venv)` in terminal)

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**This will install ~50 packages. Takes 3-5 minutes.**

**Expected output:**
```
Collecting langgraph...
Collecting langchain...
Collecting streamlit...
...
Successfully installed ...
```

**If you get errors:**
- Make sure you activated venv
- Make sure you have internet connection
- Make sure Python version is 3.11

---

### **3.5 Configure API Keys (Environment Variables)**

**Create a `.env` file:**

#### **Option 1: Using Terminal**

**Mac/Linux:**
```bash
touch .env
```

**Windows (Command Prompt):**
```bash
type nul > .env
```

#### **Option 2: Using VS Code**

1. Open project in VS Code: `code .`
2. Right-click in Explorer pane
3. Click "New File"
4. Name it `.env`

**Edit `.env` file and add your API keys:**

```bash
# Groq API (Primary LLM)
GROQ_API_KEY=gsk_your_actual_key_here

# Google Gemini API (Backup LLM)
GEMINI_API_KEY=AIzaSy_your_actual_key_here

# Brave Search API
BRAVE_API_KEY=BSA_your_actual_key_here

# Optional: Ollama (if installed)
OLLAMA_BASE_URL=http://localhost:11434
```

**⚠️ Replace `your_actual_key_here` with your real API keys!**

**⚠️ NEVER commit `.env` to GitHub!**

The `.gitignore` file is already configured to ignore `.env`, but double-check:

```bash
cat .gitignore  # Mac/Linux
type .gitignore  # Windows
```

You should see `.env` in the list.

---

### **3.6 Open Project in VS Code**

```bash
code .
```

**This opens current folder in VS Code.**

**First time setup in VS Code:**

1. VS Code might ask "Do you trust the authors?" → Click "Yes"
2. Bottom right: "Select Python Interpreter" → Choose the one with `(venv)`
3. If it doesn't show, press `Ctrl+Shift+P` / `Cmd+Shift+P` and type "Python: Select Interpreter"

**Verify Python interpreter:**
- Look at bottom left of VS Code
- Should show: `Python 3.11.x ('venv': venv)`

---

## **4. Verify Installation**

### **4.1 Quick Verification Script**

Create a test file to verify everything works.

**Create file:** `test_setup.py`

```python
"""
Quick verification that your environment is set up correctly.
Run this file to check all dependencies and API keys.
"""

import sys
import os
from dotenv import load_dotenv

print("=" * 60)
print("InsightSwarm Setup Verification")
print("=" * 60)

# Check Python version
print(f"\n1. Python Version: {sys.version}")
expected_version = "3.11"
if expected_version in sys.version:
    print("   ✅ Python 3.11 detected")
else:
    print(f"   ⚠️  Warning: Expected Python {expected_version}, got {sys.version}")

# Check required packages
print("\n2. Checking Python packages...")
required_packages = [
    "langgraph",
    "langchain",
    "groq",
    "google.generativeai",
    "streamlit",
    "pytest",
    "sqlalchemy",
]

missing_packages = []
for package in required_packages:
    try:
        __import__(package)
        print(f"   ✅ {package}")
    except ImportError:
        print(f"   ❌ {package} - NOT FOUND")
        missing_packages.append(package)

if missing_packages:
    print(f"\n   ⚠️  Missing packages. Run: pip install {' '.join(missing_packages)}")

# Check environment variables
print("\n3. Checking API Keys...")
load_dotenv()

api_keys = {
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
    "BRAVE_API_KEY": os.getenv("BRAVE_API_KEY"),
}

for key_name, key_value in api_keys.items():
    if key_value and len(key_value) > 10:
        masked = key_value[:8] + "..." + key_value[-4:]
        print(f"   ✅ {key_name}: {masked}")
    else:
        print(f"   ❌ {key_name}: NOT SET")

# Test Groq API
print("\n4. Testing Groq API Connection...")
try:
    from groq import Groq
    
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=[{"role": "user", "content": "Say 'Setup successful!' and nothing else."}],
        max_tokens=10
    )
    
    print(f"   ✅ Groq API Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"   ❌ Groq API Error: {str(e)}")

# Test Gemini API
print("\n5. Testing Gemini API Connection...")
try:
    import google.generativeai as genai
    
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content("Say 'Setup successful!' and nothing else.")
    
    print(f"   ✅ Gemini API Response: {response.text.strip()}")
except Exception as e:
    print(f"   ❌ Gemini API Error: {str(e)}")

print("\n" + "=" * 60)
print("Verification Complete!")
print("=" * 60)

# Summary
all_good = (
    expected_version in sys.version and
    len(missing_packages) == 0 and
    all(v and len(v) > 10 for v in api_keys.values())
)

if all_good:
    print("\n🎉 Everything looks good! You're ready to start coding.")
else:
    print("\n⚠️  Please fix the issues above before starting development.")
    print("   Check the Troubleshooting section if you need help.")
```

**Run the verification:**

```bash
python test_setup.py
```

**Expected output:**
```
============================================================
InsightSwarm Setup Verification
============================================================

1. Python Version: 3.11.x
   ✅ Python 3.11 detected

2. Checking Python packages...
   ✅ langgraph
   ✅ langchain
   ✅ groq
   ✅ google.generativeai
   ✅ streamlit
   ✅ pytest
   ✅ sqlalchemy

3. Checking API Keys...
   ✅ GROQ_API_KEY: gsk_abc...xyz
   ✅ GEMINI_API_KEY: AIzaSy...123
   ✅ BRAVE_API_KEY: BSA_ab...xy

4. Testing Groq API Connection...
   ✅ Groq API Response: Setup successful!

5. Testing Gemini API Connection...
   ✅ Gemini API Response: Setup successful!

============================================================
Verification Complete!
============================================================

🎉 Everything looks good! You're ready to start coding.
```

**If you see all ✅ green checkmarks, you're done with setup!**

---

## **5. Team Workflow Standards**

### **5.1 Git Branching Strategy**

**Main branches:**
- `main` - Production-ready code (protected)
- `dev` - Development branch (all features merge here first)

**Feature branches:**
- `feature/agent-system` - Multi-agent orchestration
- `feature/fact-checker` - Source verification
- `feature/ui` - Streamlit interface
- `feature/testing` - Test suite

**How to create a branch:**

```bash
# Make sure you're on dev
git checkout dev

# Pull latest changes
git pull origin dev

# Create your feature branch
git checkout -b feature/your-feature-name

# Example:
git checkout -b feature/pro-agent
```

**How to push your branch:**

```bash
# Stage your changes
git add .

# Commit with meaningful message
git commit -m "Add ProAgent with adversarial prompt"

# Push to YOUR branch
git push origin feature/pro-agent
```

**Never push directly to `main`!**

---

### **5.2 Code Style Standards**

**We use Black for formatting (automatic):**

```bash
# Format all Python files
black .

# Format specific file
black src/agents/pro_agent.py
```

**We use type hints (mandatory):**

```python
# ❌ Bad - no type hints
def verify_claim(claim):
    return result

# ✅ Good - with type hints
def verify_claim(claim: str) -> Verdict:
    return result
```

**We use docstrings (mandatory for functions):**

```python
def calculate_confidence(scores: AgentScores) -> float:
    """
    Calculate weighted confidence score from agent outputs.
    
    Args:
        scores: Named tuple containing pro, con, and fact_checker scores
        
    Returns:
        Float between 0.0 and 1.0 representing confidence
        
    Example:
        >>> scores = AgentScores(pro=0.8, con=0.3, fact_checker=0.9)
        >>> calculate_confidence(scores)
        0.725
    """
    return (scores.pro + scores.con + 2 * scores.fact_checker) / 4
```

---

### **5.3 Commit Message Format**

**Use this format:**

```
<type>: <description>

[optional body]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Adding tests
- `refactor`: Code refactoring
- `style`: Code formatting (Black)

**Examples:**

```bash
# Good commit messages
git commit -m "feat: Add ProAgent with adversarial prompting"
git commit -m "fix: FactChecker now handles 404 errors gracefully"
git commit -m "test: Add unit tests for Moderator consensus algorithm"
git commit -m "docs: Update README with deployment instructions"

# Bad commit messages (don't do this)
git commit -m "changes"
git commit -m "fixed stuff"
git commit -m "asdfgh"
```

---

### **5.4 Pull Request Process**

**When you finish a feature:**

1. **Make sure tests pass:**
   ```bash
   pytest
   ```

2. **Format code:**
   ```bash
   black .
   ```

3. **Push your branch:**
   ```bash
   git push origin feature/your-feature
   ```

4. **Create Pull Request on GitHub:**
   - Go to repository on GitHub
   - Click "Pull Requests"
   - Click "New Pull Request"
   - Base: `dev` ← Compare: `feature/your-feature`
   - Write description of what you changed
   - Click "Create Pull Request"

5. **Code Review:**
   - Another team member reviews your code
   - They leave comments if changes needed
   - You make changes and push again
   - They approve

6. **Merge:**
   - Click "Merge Pull Request"
   - Delete the feature branch after merging

**Rule: Never merge your own PR without review!**

---

### **5.5 Daily Workflow**

**Every day when you start working:**

```bash
# 1. Activate virtual environment
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# 2. Pull latest changes from dev
git checkout dev
git pull origin dev

# 3. Update your feature branch
git checkout feature/your-feature
git merge dev

# 4. Install any new dependencies (if requirements.txt changed)
pip install -r requirements.txt

# 5. Start coding!
code .
```

**Every day when you finish working:**

```bash
# 1. Format your code
black .

# 2. Run tests
pytest

# 3. Stage changes
git add .

# 4. Commit
git commit -m "feat: Describe what you did today"

# 5. Push
git push origin feature/your-feature

# 6. Deactivate virtual environment
deactivate
```

---

## **6. Troubleshooting**

### **6.1 Common Errors**

#### **Error: `python: command not found` (Mac/Linux)**

**Solution:**
```bash
# Use python3 instead
python3 --version

# Or create alias (add to ~/.bashrc or ~/.zshrc)
alias python=python3
```

#### **Error: `pip: command not found`**

**Solution:**
```bash
# Windows
python -m pip --version

# Mac/Linux
python3 -m pip --version
```

#### **Error: `ModuleNotFoundError: No module named 'langgraph'`**

**Cause:** Virtual environment not activated or dependencies not installed

**Solution:**
```bash
# Make sure venv is activated (you should see (venv) in terminal)
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

#### **Error: `PermissionError` when activating venv on Windows**

**Solution:**
```bash
# Run PowerShell as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then try activating again
venv\Scripts\Activate.ps1
```

#### **Error: `API key is invalid` for Groq/Gemini**

**Solution:**
1. Check `.env` file - make sure keys are correct
2. Make sure no extra spaces around the `=` sign
3. Check if keys start with correct prefix:
   - Groq: `gsk_`
   - Gemini: `AIzaSy`
   - Brave: `BSA`
4. Try regenerating the API key from the provider's dashboard

#### **Error: `rate limit exceeded`**

**Solution:**
- Groq free tier: 14,400 requests/day, 30/minute
- If you hit limit, wait 1 minute or fallback to Gemini
- System should auto-fallback (check logs)

---

### **6.2 Platform-Specific Issues**

#### **Windows: Git Bash vs Command Prompt vs PowerShell**

**Recommendation:** Use Git Bash (comes with Git installation)

**Differences:**
- Command Prompt: `dir`, `type`, backslashes `\`
- PowerShell: `ls`, `cat`, backslashes `\`
- Git Bash: `ls`, `cat`, forward slashes `/` (Unix-style)

**Our docs use Unix-style commands. If using Command Prompt:**
- Replace `ls` with `dir`
- Replace `cat` with `type`
- Replace `/` with `\` in paths

#### **Mac: zsh vs bash**

**Modern Macs use zsh by default (fine)**

If you see `%` instead of `$`, you're using zsh. Everything still works the same.

#### **Linux: Permission denied**

**Solution:**
```bash
# Make scripts executable
chmod +x script_name.sh

# Or run with python explicitly
python3 script_name.py
```

---

### **6.3 VS Code Issues**

#### **Python extension not working**

**Solution:**
1. Press `Ctrl+Shift+P` / `Cmd+Shift+P`
2. Type "Python: Select Interpreter"
3. Choose the one with `(venv)` in path
4. Restart VS Code

#### **Linting errors everywhere**

**This is GOOD - it's catching potential bugs**

**To fix:**
```bash
# Install linting tools
pip install mypy ruff black

# Format code
black .

# Fix type errors shown by mypy
mypy src/
```

---


**Good luck! Let's build InsightSwarm! 🚀**