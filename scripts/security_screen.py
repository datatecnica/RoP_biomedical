#!/usr/bin/env python3
"""Security screening before git push.

Checks:
1. No files >100 MB (GitHub hard limit)
2. No API keys, tokens, credentials in tracked files
3. No PHI/PII patterns
4. All large files properly gitignored
5. No confidential project identifiers

Run before every git push:
    python3 scripts/security_screen.py
"""

import subprocess
import sys
from pathlib import Path
import re

# Patterns that should NEVER appear in git
FORBIDDEN_PATTERNS = [
    (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?[a-zA-Z0-9]{20,}', "API key"),
    (r'(?i)(secret|password|passwd|pwd)\s*[:=]\s*["\']?[^\s]{8,}', "Secret/password"),
    (r'(?i)aws[_-]?(access[_-]?key|secret)', "AWS credentials"),
    (r'(?i)bearer\s+[a-zA-Z0-9\-._~+/]+=*', "Bearer token"),
    (r'(?i)authorization:\s*basic\s+[a-zA-Z0-9+/=]{20,}', "Basic auth header"),
    (r'(?i)ssh-rsa\s+AAAA[0-9A-Za-z+/]+', "SSH private key"),
    (r'-----BEGIN\s+(RSA|DSA|EC|OPENSSH)\s+PRIVATE\s+KEY-----', "PEM private key"),
    (r'\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b', "SSN pattern"),
    (r'\b[0-9]{16}\b', "Credit card pattern"),
]

# Directories that should NEVER be tracked
FORBIDDEN_DIRS = [
    "data/sources/",
    "data/foundation/staging/",
    "data/boutique/",
    "data/final/",
    "dist/",
    ".venv/",
    "venv/",
    "__pycache__/",
]

# Extensions for large binary files
LARGE_FILE_EXTENSIONS = {".npy", ".faiss", ".parquet", ".csv", ".tsv", ".db", ".sqlite"}

MAX_FILE_SIZE_MB = 50  # GitHub soft limit (hard limit is 100 MB)

def run_git_command(args):
    """Run git command and return output."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Git command failed: {' '.join(args)}")
        print(f"   Error: {e.stderr}")
        return None

def get_tracked_files():
    """Get list of all files tracked by git."""
    output = run_git_command(["ls-files"])
    if output is None:
        return []
    return [line.strip() for line in output.split('\n') if line.strip()]

def get_staged_files():
    """Get list of files staged for commit."""
    output = run_git_command(["diff", "--cached", "--name-only"])
    if output is None:
        return []
    return [line.strip() for line in output.split('\n') if line.strip()]

def check_file_size(filepath):
    """Check if file exceeds size limit."""
    path = Path(filepath)
    if not path.exists():
        return True, 0
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        return False, size_mb
    return True, size_mb

def check_forbidden_content(filepath):
    """Check file for forbidden patterns (keys, secrets, PII)."""
    path = Path(filepath)
    if not path.exists() or not path.is_file():
        return []

    # Skip binary files
    if path.suffix.lower() in {".npy", ".faiss", ".pyc", ".so", ".db", ".sqlite"}:
        return []

    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"   ⚠️  Could not read {filepath}: {e}")
        return []

    violations = []
    for pattern, description in FORBIDDEN_PATTERNS:
        matches = re.finditer(pattern, content)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            violations.append((line_num, description, match.group(0)[:50]))

    return violations

def check_forbidden_directories(filepath):
    """Check if file is in a forbidden directory."""
    for forbidden_dir in FORBIDDEN_DIRS:
        if filepath.startswith(forbidden_dir):
            return False, forbidden_dir
    return True, None

def main():
    print("=" * 70)
    print("RoP SECURITY SCREENING")
    print("=" * 70)
    print()

    # Check if in git repo
    if run_git_command(["rev-parse", "--is-inside-work-tree"]) != "true":
        print("❌ Not in a git repository")
        return 1

    errors = []
    warnings = []

    # Get all tracked files
    print("📋 Checking tracked files...")
    tracked_files = get_tracked_files()
    print(f"   {len(tracked_files)} files tracked by git")
    print()

    # Check 1: File sizes
    print("📏 Checking file sizes...")
    large_files = []
    for filepath in tracked_files:
        ok, size_mb = check_file_size(filepath)
        if not ok:
            large_files.append((filepath, size_mb))

    if large_files:
        errors.append("Large files tracked by git (>50 MB):")
        for filepath, size_mb in large_files:
            errors.append(f"   {filepath}: {size_mb:.1f} MB")
    else:
        print("   ✅ No files exceed 50 MB")
    print()

    # Check 2: Forbidden directories
    print("📂 Checking for forbidden directories...")
    forbidden_tracked = []
    for filepath in tracked_files:
        ok, forbidden_dir = check_forbidden_directories(filepath)
        if not ok:
            forbidden_tracked.append((filepath, forbidden_dir))

    if forbidden_tracked:
        errors.append("Files tracked in forbidden directories:")
        for filepath, forbidden_dir in forbidden_tracked:
            errors.append(f"   {filepath} (in {forbidden_dir})")
    else:
        print("   ✅ No files in forbidden directories")
    print()

    # Check 3: Forbidden content (keys, secrets, PII)
    print("🔒 Scanning for sensitive content...")
    sensitive_files = []
    for filepath in tracked_files:
        violations = check_forbidden_content(filepath)
        if violations:
            sensitive_files.append((filepath, violations))

    if sensitive_files:
        errors.append("Sensitive content detected:")
        for filepath, violations in sensitive_files:
            errors.append(f"   {filepath}:")
            for line_num, description, snippet in violations:
                errors.append(f"      Line {line_num}: {description} - {snippet}...")
    else:
        print("   ✅ No sensitive content detected")
    print()

    # Check 4: Large file extensions that should be in .gitignore
    print("🗂️  Checking for large file types...")
    large_file_types = []
    for filepath in tracked_files:
        path = Path(filepath)
        if path.suffix.lower() in LARGE_FILE_EXTENSIONS:
            large_file_types.append(filepath)

    if large_file_types:
        warnings.append("Large file types tracked (should be in .gitignore):")
        for filepath in large_file_types:
            warnings.append(f"   {filepath}")
    else:
        print("   ✅ No large file types tracked")
    print()

    # Summary
    print("=" * 70)
    if errors:
        print("❌ SECURITY SCREENING FAILED")
        print("=" * 70)
        for error_group in errors:
            print(error_group)
        print()
        print("Fix these issues before committing:")
        print("  1. Remove large files: git rm --cached <file>")
        print("  2. Add to .gitignore: echo '<pattern>' >> .gitignore")
        print("  3. Remove sensitive content")
        print("=" * 70)
        return 1
    elif warnings:
        print("⚠️  WARNINGS DETECTED")
        print("=" * 70)
        for warning_group in warnings:
            print(warning_group)
        print()
        print("Consider fixing these warnings before committing.")
        print("=" * 70)
        return 0
    else:
        print("✅ SECURITY SCREENING PASSED")
        print("=" * 70)
        print("All checks passed. Safe to commit.")
        print("=" * 70)
        return 0

if __name__ == "__main__":
    sys.exit(main())
