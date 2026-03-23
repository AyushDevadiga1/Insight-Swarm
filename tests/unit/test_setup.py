#!/usr/bin/env python3
"""
Day 1 Verification Script - Check if environment is properly set up
"""

import sys
import importlib.util
from pathlib import Path


def check_python_version():
    """Check if Python 3.11+ is installed"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 11:
        print(f"✅ Python version: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ Python version: {version.major}.{version.minor} - Requires Python 3.11+")
        return False


def check_directories():
    """Check if project structure exists"""
    required_dirs = [
        "src",
        "src/agents",
        "src/llm",
        "src/orchestration",
        "src/utils",
        "tests",
        "tests/unit",
        "tests/integration",
        "data",
    ]
    
    all_exist = True
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"✅ Directory: {dir_name}/")
        else:
            print(f"❌ Directory: {dir_name}/ - NOT FOUND")
            all_exist = False
    
    return all_exist


def check_init_files():
    """Check if __init__.py files exist"""
    required_files = [
        "src/__init__.py",
        "src/agents/__init__.py",
        "src/llm/__init__.py",
        "src/orchestration/__init__.py",
        "src/utils/__init__.py",
    ]
    
    all_exist = True
    for file_name in required_files:
        file_path = Path(file_name)
        if file_path.exists():
            print(f"✅ File: {file_name}")
        else:
            print(f"❌ File: {file_name} - NOT FOUND")
            all_exist = False
    
    return all_exist


def check_packages():
    """Check if required packages are installed"""
    required_packages = [
        "langgraph",
        "groq",
        "pydantic",
        "streamlit",
        "sentence_transformers",
        "rapidfuzz",
        "requests",
        "tenacity",
        "numpy",
    ]
    
    all_installed = True
    for package in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is not None:
            print(f"✅ Package: {package}")
        else:
            print(f"❌ Package: {package} - NOT INSTALLED")
            all_installed = False
    
    return all_installed


def check_env_file():
    """Check if .env file exists"""
    env_path = Path(".env")
    if env_path.exists():
        print(f"✅ File: .env")
        return True
    else:
        print(f"⚠️  File: .env - NOT FOUND (will be needed for API keys)")
        return False


def main():
    """Run all checks"""
    print("\n" + "="*50)
    print("🔍 InsightSwarm - Environment Setup Verification")
    print("="*50 + "\n")
    
    checks = [
        ("Python Version", check_python_version),
        ("Project Directories", check_directories),
        ("Module Init Files", check_init_files),
        ("Required Packages", check_packages),
        (".env Configuration", check_env_file),
    ]
    
    results = []
    for check_name, check_func in checks:
        print(f"\n📋 Checking {check_name}:")
        print("-" * 40)
        result = check_func()
        results.append((check_name, result))
    
    # Summary
    print("\n" + "="*50)
    print("📊 SUMMARY")
    print("="*50)
    
    all_passed = all(result for _, result in results)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {check_name}")
    
    print("="*50)
    if all_passed:
        print("\n🎉 All checks passed! Environment is ready for Day 1.\n")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.\n")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
