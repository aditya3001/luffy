"""
Code indexing service.
Parses code repository, extracts functions/classes, and creates embeddings.
"""
import os
import ast
import uuid
import hashlib
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import logging
from src.config import settings
from src.storage.vector_db import vector_db
from src.storage.database import get_db
from src.storage.models import CodeBlock, IndexingMetadata

# Try to import GitPython
try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    git = None

logger = logging.getLogger(__name__)

# Try to import javalang for Java parsing
try:
    import javalang
    JAVALANG_AVAILABLE = True
except ImportError:
    JAVALANG_AVAILABLE = False
    logger.warning("javalang not installed. Java indexing will use regex-based fallback. Install with: pip install javalang")


class CodeIndexer:
    """Index code repository for RAG-based analysis"""
    
    # Directories to exclude (build artifacts, dependencies, generated code)
    EXCLUDE_DIRS = {
        'build', 'target', 'dist', 'out',  # Build outputs
        'node_modules', 'vendor', '.gradle', '.mvn',  # Dependencies
        '__pycache__', '.pytest_cache', '.tox',  # Python cache
        'venv', 'env', '.venv', 'virtualenv',  # Virtual environments
        '.git', '.svn', '.hg',  # Version control
        'generated', 'gen', 'generated-sources',  # Generated code
        'bin', 'obj',  # Binary outputs
        '.idea', '.vscode', '.eclipse',  # IDE files
        'coverage', 'htmlcov', '.coverage',  # Test coverage
        'logs', 'tmp', 'temp',  # Temporary files
    }
    
    # File patterns to exclude
    EXCLUDE_PATTERNS = {
        '.class', '.pyc', '.pyo', '.pyd',  # Compiled files
        '.jar', '.war', '.ear',  # Java archives
        '.min.js', '.min.css',  # Minified files
    }
    
    def __init__(self, repo_path: str = None, version: str = None, service_id: str = None):
        self.repo_path = Path(repo_path or settings.git_repo_path).resolve()
        self.version = version or settings.code_version
        self.service_id = service_id  # Required for service isolation
        
        # Validate that repository path exists
        if not self.repo_path.exists():
            raise ValueError(
                f"Repository path does not exist: {self.repo_path}. "
                f"Please ensure the directory exists before indexing."
            )
        
        if not self.repo_path.is_dir():
            raise ValueError(
                f"Repository path is not a directory: {self.repo_path}"
            )
        
        self.repo = None
        self.commit_sha = self._get_commit_sha()
    
    def _get_commit_sha(self) -> str:
        """
        Get current commit SHA using GitPython
        
        This is optional - if .git directory doesn't exist or GitPython fails,
        we fall back to a hash-based version. This is fine for local mode
        where the user manages the repository manually.
        """
        if GIT_AVAILABLE:
            try:
                # Check if .git directory exists
                git_dir = self.repo_path / '.git'
                if git_dir.exists():
                    self.repo = git.Repo(self.repo_path)
                    commit_sha = self.repo.head.commit.hexsha
                    logger.info(f"Got commit SHA from Git: {commit_sha[:8]}")
                    return commit_sha
                else:
                    logger.info(f"No .git directory found in {self.repo_path}, using fallback version")
            except Exception as e:
                logger.warning(f"Could not get Git commit SHA: {e}, using fallback")
        
        # Fallback to hash-based version (fine for local mode)
        fallback = hashlib.md5(self.version.encode()).hexdigest()[:8]
        logger.info(f"Using fallback commit SHA: {fallback}")
        return fallback
    
    def _should_exclude_path(self, path: Path) -> bool:
        """Check if path should be excluded from indexing"""
        # Check if any parent directory is in exclude list
        for part in path.parts:
            if part in self.EXCLUDE_DIRS:
                return True
        
        # Check file extension patterns
        for pattern in self.EXCLUDE_PATTERNS:
            if str(path).endswith(pattern):
                return True
        
        return False
    
    def _get_last_indexed_commit(self) -> Optional[str]:
        """Get the last indexed commit SHA from database"""
        try:
            with get_db() as db:
                # Filter by service_id for service isolation
                query = db.query(IndexingMetadata)
                if self.service_id:
                    query = query.filter_by(
                        service_id=self.service_id,
                        repository=str(self.repo_path.name)
                    )
                else:
                    # Fallback for backward compatibility
                    query = query.filter_by(repository=str(self.repo_path.name))
                
                metadata = query.first()
                return metadata.last_indexed_commit if metadata else None
        except Exception as e:
            logger.error(f"Error getting last indexed commit: {e}")
            return None
    
    def _update_indexing_metadata(self, stats: Dict[str, int], mode: str):
        """Update indexing metadata after successful indexing"""
        try:
            with get_db() as db:
                # Filter by service_id for service isolation
                query = db.query(IndexingMetadata)
                if self.service_id:
                    query = query.filter_by(
                        service_id=self.service_id,
                        repository=str(self.repo_path.name)
                    )
                else:
                    query = query.filter_by(repository=str(self.repo_path.name))
                
                metadata = query.first()
                
                if metadata:
                    metadata.last_indexed_commit = self.commit_sha
                    metadata.last_indexed_at = datetime.utcnow()
                    metadata.total_files_indexed = stats['total_files']
                    metadata.total_blocks_indexed = stats['total_blocks']
                    metadata.indexing_mode = mode
                    metadata.updated_at = datetime.utcnow()
                else:
                    metadata_data = {
                        'repository': str(self.repo_path.name),
                        'last_indexed_commit': self.commit_sha,
                        'last_indexed_at': datetime.utcnow(),
                        'total_files_indexed': stats['total_files'],
                        'total_blocks_indexed': stats['total_blocks'],
                        'indexing_mode': mode
                    }
                    if self.service_id:
                        metadata_data['service_id'] = self.service_id
                    
                    metadata = IndexingMetadata(**metadata_data)
                    db.add(metadata)
                
                db.commit()
                logger.info(f"Updated indexing metadata: {mode} mode, commit {self.commit_sha[:8]}")
        except Exception as e:
            logger.error(f"Error updating indexing metadata: {e}")
    
    def _get_changed_files_since_commit(self, last_commit: str, languages: List[str]) -> List[Path]:
        """Get files changed between last_commit and current HEAD, excluding build/generated files"""
        if not GIT_AVAILABLE or not self.repo:
            logger.warning("Git not available, cannot get changed files")
            return []
        
        try:
            # Get diff between commits
            diff = self.repo.commit(last_commit).diff(self.repo.head.commit)
            
            # Filter by language extensions
            extensions = []
            if 'python' in languages:
                extensions.append('.py')
            if 'java' in languages:
                extensions.append('.java')
            
            changed_files = []
            for item in diff:
                # item.a_path is the file path
                if item.a_path and any(item.a_path.endswith(ext) for ext in extensions):
                    file_path = self.repo_path / item.a_path
                    if file_path.exists() and not self._should_exclude_path(file_path):
                        changed_files.append(file_path)
            
            logger.info(f"Found {len(changed_files)} changed files since {last_commit[:8]} (after exclusions)")
            return changed_files
            
        except Exception as e:
            logger.error(f"Error getting changed files: {e}")
            return []
    
    def _get_all_files(self, languages: List[str]) -> List[Path]:
        """Get all files for specified languages, excluding build/generated directories"""
        all_files = []
        
        for lang in languages:
            if lang == 'python':
                files = self.repo_path.rglob('*.py')
            elif lang == 'java':
                files = self.repo_path.rglob('*.java')
            else:
                continue
            
            # Filter out excluded paths
            for file_path in files:
                if not self._should_exclude_path(file_path):
                    all_files.append(file_path)
        
        logger.info(f"Found {len(all_files)} source files after excluding build/generated directories")
        return all_files
    
    def index_repository(self, languages: List[str] = None, force_full: bool = False) -> Dict[str, int]:
        """
        Index repository with support for full and incremental modes.
        
        Args:
            languages: List of languages to index (default: ['python'])
            force_full: Force full indexing even if incremental is possible
        
        Returns:
            Statistics about indexing
        """
        languages = languages or ['python']
        stats = {'total_files': 0, 'total_blocks': 0, 'errors': 0, 'mode': 'full'}
        
        # Determine indexing mode
        last_commit = self._get_last_indexed_commit()
        
        if force_full or not last_commit:
            # FULL INDEXING MODE
            logger.info(f"Starting FULL indexing of repository: {self.repo_path}")
            
            # Delete all existing code blocks to prevent duplicates
            deleted_count = self._delete_all_code_blocks()
            logger.info(f"Cleared {deleted_count} existing code blocks before full re-indexing")
            
            files_to_index = self._get_all_files(languages)
            stats['mode'] = 'full'
        else:
            # Check if current commit is same as last indexed
            if last_commit == self.commit_sha:
                logger.info(f"Repository already indexed at commit {self.commit_sha[:8]}")
                return {'total_files': 0, 'total_blocks': 0, 'errors': 0, 'mode': 'skip'}
            
            # INCREMENTAL INDEXING MODE
            logger.info(f"Starting INCREMENTAL indexing from {last_commit[:8]} to {self.commit_sha[:8]}")
            files_to_index = self._get_changed_files_since_commit(last_commit, languages)
            stats['mode'] = 'incremental'
            
            # If no changed files, we're done
            if not files_to_index:
                logger.info("No files changed, updating metadata only")
                self._update_indexing_metadata(stats, 'incremental')
                return stats
        
        # Index files
        stats['total_files'] = len(files_to_index)
        
        for file_path in files_to_index:
            try:
                # For incremental mode, delete old blocks for this file first
                if stats['mode'] == 'incremental':
                    self._delete_file_code_blocks(file_path)
                
                # Determine file type and index accordingly
                if str(file_path).endswith('.py'):
                    blocks = self.index_python_file(file_path)
                    stats['total_blocks'] += len(blocks)
                elif str(file_path).endswith('.java'):
                    blocks = self.index_java_file(file_path)
                    stats['total_blocks'] += len(blocks)
            except Exception as e:
                logger.error(f"Error indexing {file_path}: {e}")
                stats['errors'] += 1
        
        # Update metadata after successful indexing
        self._update_indexing_metadata(stats, stats['mode'])
        
        logger.info(f"Indexing complete: {stats}")
        return stats
    
    def index_python_file(self, file_path: Path) -> List[str]:
        """
        Index a Python file.
        
        Returns:
            List of code block IDs
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
        except Exception as e:
            logger.error(f"Could not read {file_path}: {e}")
            return []
        
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            return []
        
        # Extract functions and classes
        code_blocks = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                block = self._extract_function(node, file_path, source_code)
                if block:
                    code_blocks.append(block)
            
            elif isinstance(node, ast.ClassDef):
                block = self._extract_class(node, file_path, source_code)
                if block:
                    code_blocks.append(block)
        
        # Store code blocks
        block_ids = []
        for block in code_blocks:
            block_id = self._store_code_block(block)
            if block_id:
                block_ids.append(block_id)
        
        logger.debug(f"Indexed {len(block_ids)} blocks from {file_path}")
        return block_ids
    
    def _extract_function(
        self,
        node: ast.FunctionDef,
        file_path: Path,
        source_code: str
    ) -> Optional[Dict[str, Any]]:
        """Extract function details"""
        try:
            # Get source code for this function
            lines = source_code.split('\n')
            start_line = node.lineno - 1
            end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 10
            
            function_code = '\n'.join(lines[start_line:end_line])
            
            # Extract docstring
            docstring = ast.get_docstring(node) or ''
            
            # Build function signature
            args = [arg.arg for arg in node.args.args]
            signature = f"{node.name}({', '.join(args)})"
            
            # Relative path from repo root
            rel_path = file_path.relative_to(self.repo_path)
            
            # Generate qualified name
            symbol_name = f"{str(rel_path).replace('/', '.').replace('.py', '')}.{node.name}"
            
            return {
                'file_path': str(rel_path),
                'symbol_name': symbol_name,
                'symbol_type': 'function',
                'line_start': node.lineno,
                'line_end': end_line + 1,
                'code_snippet': function_code,
                'docstring': docstring,
                'function_signature': signature
            }
        
        except Exception as e:
            logger.error(f"Error extracting function {node.name}: {e}")
            return None
    
    def _extract_class(
        self,
        node: ast.ClassDef,
        file_path: Path,
        source_code: str
    ) -> Optional[Dict[str, Any]]:
        """Extract class details (simplified - just the class definition)"""
        try:
            lines = source_code.split('\n')
            start_line = node.lineno - 1
            
            # For classes, just take first few lines (class definition + docstring)
            end_line = min(start_line + 20, len(lines))
            
            class_code = '\n'.join(lines[start_line:end_line])
            
            docstring = ast.get_docstring(node) or ''
            
            rel_path = file_path.relative_to(self.repo_path)
            symbol_name = f"{str(rel_path).replace('/', '.').replace('.py', '')}.{node.name}"
            
            return {
                'file_path': str(rel_path),
                'symbol_name': symbol_name,
                'symbol_type': 'class',
                'line_start': node.lineno,
                'line_end': end_line + 1,
                'code_snippet': class_code,
                'docstring': docstring,
                'function_signature': f"class {node.name}"
            }
        
        except Exception as e:
            logger.error(f"Error extracting class {node.name}: {e}")
            return None
    
    def index_java_file(self, file_path: Path) -> List[str]:
        """
        Index a Java file.
        
        Returns:
            List of code block IDs
        """
        logger.info("Indexing file in code_indexer")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
        except Exception as e:
            logger.error(f"Could not read {file_path}: {e}")
            return []
        
        if JAVALANG_AVAILABLE:
            return self._index_java_with_javalang(file_path, source_code)
        else:
            return self._index_java_with_regex(file_path, source_code)
    
    def _index_java_with_javalang(self, file_path: Path, source_code: str) -> List[str]:
        """Index Java file using javalang library"""
        logger.info("Indexing using javalang lib")
        try:
            tree = javalang.parse.parse(source_code)
        except Exception as e:
            logger.warning(f"Javalang parse error in {file_path}: {e}. Falling back to regex.")
            return self._index_java_with_regex(file_path, source_code)
        
        code_blocks = []
        lines = source_code.split('\n')
        
        # Extract package name
        package_name = ''
        if tree.package:
            package_name = tree.package.name
        
        # Extract classes
        for path, node in tree.filter(javalang.tree.ClassDeclaration):
            block = self._extract_java_class(node, file_path, lines, package_name)
            if block:
                code_blocks.append(block)
        
        # Extract methods
        for path, node in tree.filter(javalang.tree.MethodDeclaration):
            # Get parent class name
            parent_class = None
            for item in path:
                if isinstance(item, javalang.tree.ClassDeclaration):
                    parent_class = item.name
                    break
            
            block = self._extract_java_method(node, file_path, lines, package_name, parent_class)
            if block:
                code_blocks.append(block)
        
        # Store code blocks
        logger.info("Storing code blocks")
        block_ids = []
        for block in code_blocks:
            block_id = self._store_code_block(block)
            if block_id:
                block_ids.append(block_id)
        
        logger.debug(f"Indexed {len(block_ids)} blocks from {file_path}")
        return block_ids
    
    def _index_java_with_regex(self, file_path: Path, source_code: str) -> List[str]:
        """Fallback: Index Java file using regex patterns"""
        code_blocks = []
        lines = source_code.split('\n')
        
        # Extract package name
        package_match = re.search(r'^package\s+([\w.]+);', source_code, re.MULTILINE)
        package_name = package_match.group(1) if package_match else ''
        
        # Pattern for class declaration
        class_pattern = re.compile(
            r'^\s*(public|private|protected)?\s*(static)?\s*(abstract|final)?\s*class\s+(\w+)',
            re.MULTILINE
        )
        
        # Pattern for method declaration
        method_pattern = re.compile(
            r'^\s*(public|private|protected)?\s*(static)?\s*([\w<>\[\]]+)\s+(\w+)\s*\([^)]*\)',
            re.MULTILINE
        )
        
        # Find classes
        for match in class_pattern.finditer(source_code):
            class_name = match.group(4)
            start_pos = match.start()
            line_num = source_code[:start_pos].count('\n') + 1
            
            # Simplified: take next 20 lines
            end_line = min(line_num + 20, len(lines))
            code_snippet = '\n'.join(lines[line_num-1:end_line])
            
            rel_path = file_path.relative_to(self.repo_path)
            symbol_name = f"{package_name}.{class_name}" if package_name else class_name
            
            code_blocks.append({
                'file_path': str(rel_path),
                'symbol_name': symbol_name,
                'symbol_type': 'class',
                'line_start': line_num,
                'line_end': end_line,
                'code_snippet': code_snippet,
                'docstring': self._extract_java_javadoc(lines, line_num - 1),
                'function_signature': f"class {class_name}"
            })
        
        # Find methods
        for match in method_pattern.finditer(source_code):
            method_name = match.group(4)
            return_type = match.group(3)
            start_pos = match.start()
            line_num = source_code[:start_pos].count('\n') + 1
            
            # Skip if this looks like a class declaration
            if return_type in ['class', 'interface', 'enum']:
                continue
            
            # Simplified: take next 15 lines
            end_line = min(line_num + 15, len(lines))
            code_snippet = '\n'.join(lines[line_num-1:end_line])
            
            rel_path = file_path.relative_to(self.repo_path)
            # Simplified qualified name
            symbol_name = f"{package_name}.{method_name}" if package_name else method_name
            
            code_blocks.append({
                'file_path': str(rel_path),
                'symbol_name': symbol_name,
                'symbol_type': 'method',
                'line_start': line_num,
                'line_end': end_line,
                'code_snippet': code_snippet,
                'docstring': self._extract_java_javadoc(lines, line_num - 1),
                'function_signature': match.group(0)
            })
        
        # Store code blocks
        block_ids = []
        for block in code_blocks:
            block_id = self._store_code_block(block)
            if block_id:
                block_ids.append(block_id)
        
        logger.debug(f"Indexed {len(block_ids)} blocks from {file_path} (regex mode)")
        return block_ids
    
    def _extract_java_class(self, node, file_path: Path, lines: List[str], package_name: str) -> Optional[Dict[str, Any]]:
        """Extract Java class details using javalang with accurate boundary detection"""
        try:
            class_name = node.name
            
            # Get starting line number (javalang uses 1-indexed lines)
            line_num = node.position.line if node.position else 1
            
            # Find the actual end of the class by counting braces
            end_line = self._find_java_method_end(lines, line_num - 1)  # Convert to 0-indexed
            
            # Extract the complete class code
            class_code = '\n'.join(lines[line_num-1:end_line])
            
            # Extract Javadoc (look backwards from class start)
            javadoc = self._extract_java_javadoc(lines, line_num - 1)
            
            rel_path = file_path.relative_to(self.repo_path)
            symbol_name = f"{package_name}.{class_name}" if package_name else class_name
            
            return {
                'file_path': str(rel_path),
                'symbol_name': symbol_name,
                'symbol_type': 'class',
                'line_start': line_num,
                'line_end': end_line,
                'code_snippet': class_code,
                'docstring': javadoc,
                'function_signature': f"class {class_name}"
            }
        
        except Exception as e:
            logger.error(f"Error extracting Java class: {e}")
            return None
    
    def _extract_java_method(self, node, file_path: Path, lines: List[str], package_name: str, parent_class: str = None) -> Optional[Dict[str, Any]]:
        """Extract Java method details using javalang with accurate boundary detection"""
        try:
            method_name = node.name
            return_type = node.return_type.name if node.return_type else 'void'
            
            # Get starting line number (javalang uses 1-indexed lines)
            line_num = node.position.line if node.position else 1
            
            # Find the actual end of the method by counting braces
            end_line = self._find_java_method_end(lines, line_num - 1)  # Convert to 0-indexed
            
            # Extract the complete method code
            method_code = '\n'.join(lines[line_num-1:end_line])
            
            # Build parameter list
            params = []
            if node.parameters:
                for param in node.parameters:
                    param_type = param.type.name if hasattr(param.type, 'name') else str(param.type)
                    params.append(f"{param_type} {param.name}")
            
            signature = f"{return_type} {method_name}({', '.join(params)})"
            
            # Extract Javadoc (look backwards from method start)
            javadoc = self._extract_java_javadoc(lines, line_num - 1)
            
            rel_path = file_path.relative_to(self.repo_path)
            
            # Build fully qualified name
            if parent_class:
                symbol_name = f"{package_name}.{parent_class}.{method_name}" if package_name else f"{parent_class}.{method_name}"
            else:
                symbol_name = f"{package_name}.{method_name}" if package_name else method_name
            
            return {
                'file_path': str(rel_path),
                'symbol_name': symbol_name,
                'symbol_type': 'method',
                'line_start': line_num,
                'line_end': end_line,
                'code_snippet': method_code,
                'docstring': javadoc,
                'function_signature': signature
            }
        
        except Exception as e:
            logger.error(f"Error extracting Java method {node.name}: {e}")
            return None
    
    def _find_java_method_end(self, lines: List[str], start_line: int) -> int:
        """
        Find the end line of a Java method/class by counting braces.
        
        Args:
            lines: List of source code lines (0-indexed)
            start_line: Starting line number (0-indexed)
        
        Returns:
            End line number (1-indexed, exclusive - for slicing)
        """
        brace_count = 0
        found_opening_brace = False
        in_string = False
        in_char = False
        in_single_comment = False
        in_multi_comment = False
        
        for i in range(start_line, len(lines)):
            line = lines[i]
            
            # Process character by character to handle strings and comments
            j = 0
            while j < len(line):
                char = line[j]
                
                # Handle multi-line comments
                if not in_string and not in_char and not in_single_comment:
                    if j < len(line) - 1 and line[j:j+2] == '/*':
                        in_multi_comment = True
                        j += 2
                        continue
                    elif in_multi_comment and j < len(line) - 1 and line[j:j+2] == '*/':
                        in_multi_comment = False
                        j += 2
                        continue
                
                # Handle single-line comments
                if not in_string and not in_char and not in_multi_comment:
                    if j < len(line) - 1 and line[j:j+2] == '//':
                        in_single_comment = True
                        break  # Rest of line is comment
                
                # Skip if in comment
                if in_single_comment or in_multi_comment:
                    j += 1
                    continue
                
                # Handle strings
                if char == '"' and (j == 0 or line[j-1] != '\\'):
                    in_string = not in_string
                
                # Handle char literals
                elif char == "'" and (j == 0 or line[j-1] != '\\'):
                    in_char = not in_char
                
                # Count braces only if not in string or char
                elif not in_string and not in_char:
                    if char == '{':
                        brace_count += 1
                        found_opening_brace = True
                    elif char == '}':
                        brace_count -= 1
                        
                        # Found matching closing brace
                        if found_opening_brace and brace_count == 0:
                            return i + 2  # Return 1-indexed, exclusive (for slicing)
                
                j += 1
            
            # Reset single-line comment flag at end of line
            in_single_comment = False
        
        # If we didn't find the end, return a reasonable default
        # (take up to 100 lines or end of file)
        return min(start_line + 101, len(lines) + 1)
    
    def _extract_java_javadoc(self, lines: List[str], line_num: int) -> str:
        """Extract Javadoc comment above a declaration"""
        javadoc_lines = []
        
        # Look backwards for Javadoc
        i = line_num - 1
        while i >= 0 and i >= line_num - 20:  # Look up to 20 lines back
            line = lines[i].strip()
            
            if line.startswith('/**'):
                # Found start of Javadoc
                javadoc_lines.reverse()
                # Clean up Javadoc formatting
                cleaned = []
                for jline in javadoc_lines:
                    jline = jline.strip()
                    jline = re.sub(r'^/\*\*\s*', '', jline)
                    jline = re.sub(r'\s*\*/$', '', jline)
                    jline = re.sub(r'^\*\s*', '', jline)
                    if jline:
                        cleaned.append(jline)
                return ' '.join(cleaned)
            
            elif line.startswith('*') or line.startswith('*/'):
                javadoc_lines.append(line)
            
            elif line and not line.startswith('//'):
                # Hit non-comment line, stop
                break
            
            i -= 1
        
        return ''
    
    def _delete_file_code_blocks(self, file_path: Path) -> int:
        """
        Delete existing code blocks for a specific file (for incremental updates)
        
        Args:
            file_path: Path to the file whose blocks should be deleted
            
        Returns:
            Number of code blocks deleted
        """
        try:
            # Convert to relative path
            relative_path = str(file_path.relative_to(self.repo_path))
            
            with get_db() as db:
                # Delete code blocks for this file and service
                query = db.query(CodeBlock).filter(
                    CodeBlock.file_path == relative_path
                )
                
                # Add service filter if service_id is set
                if self.service_id:
                    query = query.filter(CodeBlock.service_id == self.service_id)
                
                deleted_count = query.delete()
                db.commit()
                
                logger.info(f"Deleted {deleted_count} existing code blocks for file {relative_path}")
                return deleted_count
        except Exception as e:
            logger.error(f"Error deleting code blocks for file {file_path}: {e}")
            return 0
    
    def _delete_all_code_blocks(self) -> int:
        """
        Delete all existing code blocks for this service (for full re-indexing)
        
        Returns:
            Number of code blocks deleted
        """
        try:
            with get_db() as db:
                # Delete all code blocks for this service
                query = db.query(CodeBlock)
                
                # Add service filter if service_id is set
                if self.service_id:
                    query = query.filter(CodeBlock.service_id == self.service_id)
                else:
                    # If no service_id, delete by repository name
                    query = query.filter(CodeBlock.repository == str(self.repo_path.name))
                
                deleted_count = query.delete()
                db.commit()
                
                logger.info(f"Deleted {deleted_count} existing code blocks for service {self.service_id or self.repo_path.name}")
                return deleted_count
        except Exception as e:
            logger.error(f"Error deleting all code blocks: {e}")
            return 0
    
    def _store_code_block(self, block: Dict[str, Any]) -> Optional[str]:
        """Store code block in database and vector DB"""
        try:
            # Generate unique ID
            block_id = f"{uuid.uuid4()}"
            
            # Store in vector database
            code_text = f"{block['symbol_name']}\n{block['docstring']}\n{block['code_snippet']}"
            
            metadata = {
                'repository': str(self.repo_path.name),
                'version': self.version,
                'commit_sha': self.commit_sha,
                'file_path': block['file_path'],
                'symbol_name': block['symbol_name'],
                'symbol_type': block['symbol_type'],
                'line_start': block['line_start'],
                'line_end': block['line_end']
            }
            # Add service_id to metadata for service isolation
            if self.service_id:
                metadata['service_id'] = self.service_id
            
            # logger.info("Inserting code block into vector db with metadata: {}, codeblock: {}", metadata, block['code_snippet'])
            vector_db.insert_code_block(block_id, code_text, metadata)
            logger.info("Inserted code block into vector db")

            logger.info("Inserting code block into postgres db")
            # Store in relational database
            with get_db() as db:
                code_block_data = {
                    'id': block_id,
                    'repository': str(self.repo_path.name),
                    'version': self.version,
                    'commit_sha': self.commit_sha,
                    'file_path': block['file_path'],
                    'symbol_name': block['symbol_name'],
                    'symbol_type': block['symbol_type'],
                    'line_start': block['line_start'],
                    'line_end': block['line_end'],
                    'code_snippet': block['code_snippet'],
                    'docstring': block['docstring'],
                    'function_signature': block.get('function_signature', ''),
                    'embedding_id': block_id
                }
                # Add service_id for service isolation
                if self.service_id:
                    code_block_data['service_id'] = self.service_id
                
                code_block = CodeBlock(**code_block_data)
                db.add(code_block)
            
            return block_id
        
        except Exception as e:
            logger.error(f"Error storing code block: {e}")
            return None


