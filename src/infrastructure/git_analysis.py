"""
Git History Analysis Module for CodeProvenance.

Detects plagiarism through Git history analysis:
- Code origin detection (who wrote it first)
- Commit timeline analysis (sudden vs incremental changes)
- Cross-repo similarity (student vs student across time)
- Sudden code appearance detection (copy-paste detection)
"""

import subprocess
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class GitCommit:
    """Represents a Git commit."""
    hash: str
    author: str
    author_email: str
    date: datetime
    message: str
    files_changed: List[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0


@dataclass
class BlameEntry:
    """Represents a line-level blame entry."""
    line_number: int
    content: str
    commit_hash: str
    author: str
    author_email: str
    date: datetime
    line_hash: str  # Hash of the line content


@dataclass
class GitAnalysisResult:
    """Result of Git history analysis."""
    repository_path: str
    first_commit_date: Optional[datetime]
    total_commits: int
    total_authors: int
    author_commits: Dict[str, int] = field(default_factory=dict)
    file_authors: Dict[str, Dict[str, int]] = field(default_factory=dict)  # file -> author -> count
    suspicious_patterns: List[Dict[str, Any]] = field(default_factory=list)
    original_authorship: Dict[str, str] = field(default_factory=dict)  # file -> original author


class GitAnalyzer:
    """
    Analyzes Git history for code origin detection.
    
    Features:
    - Blame analysis for authorship attribution
    - Commit history pattern detection
    - First-commit detection
    - Suspicious pattern identification
    """
    
    def __init__(self, repo_path: str):
        """
        Initialize Git analyzer.
        
        Args:
            repo_path: Path to Git repository
        """
        self.repo_path = Path(repo_path)
        self._validate_repo()
    
    def _validate_repo(self) -> bool:
        """Validate that path is a Git repository."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _run_git_command(self, command: List[str]) -> Tuple[bool, str]:
        """Run a git command and return success status and output."""
        try:
            result = subprocess.run(
                ['git'] + command,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout
        except Exception as e:
            return False, str(e)
    
    def get_commits(self, max_count: int = 100) -> List[GitCommit]:
        """
        Get recent commits.
        
        Args:
            max_count: Maximum number of commits to retrieve
            
        Returns:
            List of GitCommit objects
        """
        success, output = self._run_git_command([
            'log',
            f'--max-count={max_count}',
            '--format=%H|%an|%ae|%aI|%s',
            '--name-only'
        ])
        
        if not success:
            return []
        
        commits = []
        current_commit = None
        
        for line in output.split('\n'):
            if not line.strip():
                continue
            
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 5:
                    current_commit = GitCommit(
                        hash=parts[0],
                        author=parts[1],
                        author_email=parts[2],
                        date=datetime.fromisoformat(parts[3].replace('Z', '+00:00')),
                        message='|'.join(parts[4:])
                    )
                    commits.append(current_commit)
            elif current_commit and line.strip():
                current_commit.files_changed.append(line.strip())
        
        return commits
    
    def get_blame(self, file_path: str) -> List[BlameEntry]:
        """
        Get blame information for a file.
        
        Args:
            file_path: Path to file (relative to repo root)
            
        Returns:
            List of BlameEntry objects
        """
        success, output = self._run_git_command([
            'blame',
            '--line-porcelain',
            file_path
        ])
        
        if not success:
            return []
        
        entries = []
        current_entry = None
        current_line = []
        line_number = 0
        
        for line in output.split('\n'):
            if line.startswith('\t'):
                # Line content
                content = line[1:]
                current_line.append(content)
                if current_entry:
                    current_entry.line_number = line_number
                    current_entry.content = content
                    current_entry.line_hash = hashlib.md5(content.encode()).hexdigest()
            elif line.startswith('author '):
                if current_entry:
                    current_entry.author = line[7:]
            elif line.startswith('author-mail '):
                if current_entry:
                    current_entry.author_email = line[12:]
            elif line.startswith('author-time '):
                if current_entry:
                    timestamp = int(line[12:])
                    current_entry.date = datetime.fromtimestamp(timestamp)
            elif line.startswith('summary '):
                if current_entry:
                    current_entry.commit_hash = line[8:]
            elif line.startswith('committer-time '):
                # New entry starting
                if current_entry and current_entry.content:
                    entries.append(current_entry)
                current_entry = BlameEntry(
                    line_number=0,
                    content='',
                    commit_hash='',
                    author='',
                    author_email='',
                    date=datetime.now(),
                    line_hash=''
                )
                line_number += 1
        
        # Don't forget the last entry
        if current_entry and current_entry.content:
            entries.append(current_entry)
        
        return entries
    
    def analyze_file_authorship(self, file_path: str) -> Dict[str, int]:
        """
        Analyze authorship of a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary of author -> line count
        """
        blame_entries = self.get_blame(file_path)
        
        author_lines = {}
        for entry in blame_entries:
            author = entry.author or 'Unknown'
            author_lines[author] = author_lines.get(author, 0) + 1
        
        return author_lines
    
    def find_original_author(self, file_path: str) -> Optional[str]:
        """
        Find the original author of a file (first person to add lines).
        
        Args:
            file_path: Path to file
            
        Returns:
            Original author name or None
        """
        blame_entries = self.get_blame(file_path)
        
        if not blame_entries:
            return None
        
        # Find the oldest commit
        oldest = min(blame_entries, key=lambda e: e.date)
        return oldest.author if oldest.author else None
    
    def detect_copied_code(
        self,
        local_code: str,
        repo_path: str
    ) -> List[Dict[str, Any]]:
        """
        Detect if code was copied from a Git repository.
        
        Args:
            local_code: Code to check
            repo_path: Path to repository to check against
            
        Returns:
            List of matches with similarity info
        """
        matches = []
        
        # Hash chunks of local code
        local_chunks = self._hash_code_chunks(local_code)
        
        # Search git log for matching content
        for chunk_hash, chunk_content in local_chunks:
            success, output = self._run_git_command([
                'log', '-S', chunk_hash[:8], '--all', '--pretty=format:%H|%an|%ae|%aI|%s'
            ])
            
            if success and output.strip():
                for line in output.strip().split('\n'):
                    if '|' in line:
                        parts = line.split('|')
                        if len(parts) >= 4:
                            matches.append({
                                'chunk_hash': chunk_hash,
                                'chunk_preview': chunk_content[:50],
                                'commit_hash': parts[0],
                                'author': parts[1],
                                'email': parts[2],
                                'date': parts[3],
                                'message': '|'.join(parts[4:]) if len(parts) > 4 else ''
                            })
        
        return matches
    
    def _hash_code_chunks(
        self,
        code: str,
        chunk_size: int = 20
    ) -> List[Tuple[str, str]]:
        """Hash consecutive line chunks of code."""
        lines = code.split('\n')
        chunks = []
        
        for i in range(len(lines) - chunk_size + 1):
            chunk = '\n'.join(lines[i:i + chunk_size])
            chunk_hash = hashlib.sha256(chunk.encode()).hexdigest()
            chunks.append((chunk_hash, chunk))
        
        return chunks
    
    def analyze_repository(self) -> GitAnalysisResult:
        """
        Perform comprehensive repository analysis.
        
        Returns:
            GitAnalysisResult with findings
        """
        # Get commit count
        success, output = self._run_git_command(['rev-list', '--count', 'HEAD'])
        total_commits = int(output.strip()) if success else 0
        
        # Get all authors
        success, output = self._run_git_command(['shortlog', '-sn', '--all'])
        author_commits = {}
        if success:
            for line in output.strip().split('\n'):
                parts = line.strip().split(None, 1)
                if len(parts) == 2:
                    author_commits[parts[1]] = int(parts[0])
        
        # Get first commit date
        success, output = self._run_git_command(['log', '--reverse', '--format=%aI', '--max-count=1'])
        first_commit = None
        if success and output.strip():
            first_commit = datetime.fromisoformat(output.strip().replace('Z', '+00:00'))
        
        # Analyze file authorship
        success, files_output = self._run_git_command(['ls-files'])
        files = []
        if success:
            files = [f for f in files_output.strip().split('\n') if f.strip()]
        
        file_authors = {}
        original_authorship = {}
        
        for file_path in files[:100]:  # Limit to 100 files
            authors = self.analyze_file_authorship(file_path)
            if authors:
                file_authors[file_path] = authors
                original = self.find_original_author(file_path)
                if original:
                    original_authorship[file_path] = original
        
        # Detect suspicious patterns
        suspicious = self._detect_suspicious_patterns(author_commits, file_authors)
        
        return GitAnalysisResult(
            repository_path=str(self.repo_path),
            first_commit_date=first_commit,
            total_commits=total_commits,
            total_authors=len(author_commits),
            author_commits=author_commits,
            file_authors=file_authors,
            suspicious_patterns=suspicious,
            original_authorship=original_authorship
        )
    
    def _detect_suspicious_patterns(
        self,
        author_commits: Dict[str, int],
        file_authors: Dict[str, Dict[str, int]]
    ) -> List[Dict[str, Any]]:
        """Detect suspicious patterns in Git history."""
        patterns = []
        
        # Single author dominates
        if author_commits:
            max_commits = max(author_commits.values())
            total = sum(author_commits.values())
            if max_commits / total > 0.8 and len(author_commits) > 1:
                dominant = max(author_commits, key=author_commits.get)
                patterns.append({
                    'type': 'single_author_dominance',
                    'description': f'Author {dominant} has {max_commits/total:.0%} of commits',
                    'author': dominant,
                    'severity': 'medium'
                })
        
        # Files with only one author (potential copy)
        for file_path, authors in file_authors.items():
            if len(authors) == 1:
                author = list(authors.keys())[0]
                patterns.append({
                    'type': 'single_author_file',
                    'description': f'File {file_path} has only one author',
                    'author': author,
                    'file': file_path,
                    'severity': 'low'
                })
        
        return patterns


class GitBlameVisualizer:
    """
    Generates visualizations of Git blame information.
    """
    
    def generate_blame_html(
        self,
        file_path: str,
        blame_entries: List[BlameEntry],
        highlighted_authors: Optional[List[str]] = None
    ) -> str:
        """
        Generate HTML visualization of blame.
        
        Args:
            file_path: File being analyzed
            blame_entries: Blame entries
            highlighted_authors: Authors to highlight
            
        Returns:
            HTML string
        """
        if highlighted_authors is None:
            highlighted_authors = []
        
        # Generate author colors
        author_colors = self._generate_author_colors(blame_entries)
        
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Git Blame Analysis</title>
    <style>
        body { font-family: 'Fira Code', monospace; font-size: 13px; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { background: #2d3748; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .file-header { background: #4a5568; padding: 10px 15px; border-radius: 4px; margin-bottom: 15px; font-family: monospace; }
        .code-container { background: #1a202c; border-radius: 8px; overflow: hidden; }
        .code-line { display: flex; margin: 0; padding: 2px 0; }
        .line-number { width: 50px; text-align: right; padding: 0 10px; color: #718096; background: #2d3748; user-select: none; }
        .line-content { flex: 1; padding: 0 10px; white-space: pre; }
        .line-content.highlighted { font-weight: bold; }
        .author-bar { width: 30px; }
        .author-legend { display: flex; gap: 15px; flex-wrap: wrap; margin-top: 20px; padding: 15px; background: #f7fafc; border-radius: 8px; }
        .legend-item { display: flex; align-items: center; gap: 8px; }
        .legend-color { width: 20px; height: 20px; border-radius: 3px; }
        .tooltip { position: relative; }
        .tooltip:hover .tooltip-text { display: block; }
        .tooltip-text { display: none; position: absolute; background: #2d3748; color: white; padding: 5px 10px; border-radius: 4px; font-size: 12px; z-index: 100; white-space: nowrap; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📜 Git Blame Analysis</h1>
        </header>
        <div class="file-header">""" + file_path + """</div>
        <div class="code-container">
"""
        
        for entry in blame_entries:
            color = author_colors.get(entry.author, '#888888')
            is_highlighted = entry.author in highlighted_authors
            
            html += f"""
            <div class="code-line">
                <div class="author-bar" style="background: {color};" title="{entry.author}"></div>
                <div class="line-number">{entry.line_number}</div>
                <div class="line-content {'highlighted' if is_highlighted else ''}">{self._escape_html(entry.content)}</div>
            </div>
"""
        
        html += """
        </div>
        <div class="author-legend">
            <strong>Authors:</strong>
"""
        
        for author, color in author_colors.items():
            html += f"""
            <div class="legend-item">
                <div class="legend-color" style="background: {color};"></div>
                <span>{author}</span>
            </div>
"""
        
        html += """
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def _generate_author_colors(self, entries: List[BlameEntry]) -> Dict[str, str]:
        """Generate consistent colors for authors."""
        authors = list(set(e.author for e in entries if e.author))
        colors = [
            '#e53e3e', '#dd6b20', '#d69e2e', '#38a169', '#319795',
            '#3182ce', '#5a67d8', '#805ad5', '#d53f8c', '#718096',
            '#00b5d8', '#76e4f7', '#68d391', '#faf089', '#f687b3'
        ]
        
        return {author: colors[i % len(colors)] for i, author in enumerate(authors)}
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
            .replace('&', '&')
            .replace('<', '<')
            .replace('>', '>')
            .replace('"', '"'))


# Convenience functions
def analyze_repository_git(repo_path: str) -> GitAnalysisResult:
    """
    Analyze a Git repository.
    
    Args:
        repo_path: Path to repository
        
    Returns:
        GitAnalysisResult
    """
    analyzer = GitAnalyzer(repo_path)
    return analyzer.analyze_repository()


def compare_blame_authorship(
    file_a: str,
    file_b: str,
    repo_path: str
) -> Dict[str, Any]:
    """
    Compare authorship between two files.
    
    Args:
        file_a: First file path
        file_b: Second file path
        repo_path: Repository path
        
    Returns:
        Comparison results
    """
    analyzer = GitAnalyzer(repo_path)
    
    authors_a = analyzer.analyze_file_authorship(file_a)
    authors_b = analyzer.analyze_file_authorship(file_b)
    
    all_authors = set(authors_a.keys()) | set(authors_b.keys())
    
    return {
        'file_a': {
            'path': file_a,
            'authors': authors_a,
            'total_lines': sum(authors_a.values())
        },
        'file_b': {
            'path': file_b,
            'authors': authors_b,
            'total_lines': sum(authors_b.values())
        },
        'common_authors': list(set(authors_a.keys()) & set(authors_b.keys())),
        'unique_to_a': list(set(authors_a.keys()) - set(authors_b.keys())),
        'unique_to_b': list(set(authors_b.keys()) - set(authors_a.keys()))
    }
