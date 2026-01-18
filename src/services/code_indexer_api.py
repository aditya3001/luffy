"""
API-based Code Indexing Service
Fetches code via GitHub/GitLab API without local repository clones
"""
import ast
import uuid
import hashlib
import re
import base64
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import logging

from src.storage.vector_db import vector_db
from src.storage.database import get_db
from src.storage.models import CodeBlock, IndexingMetadata
from src.integrations.git_api_client import GitClientFactory, AuthenticationError

# Try to import javalang for Java parsing
try:
    import javalang
    JAVALANG_AVAILABLE = True
except ImportError:
    JAVALANG_AVAILABLE = False

logger = logging.getLogger(__name__)


class APICodeIndexer:
    """
    API-based code indexer that fetches files via GitHub/GitLab API
    No local repository storage required - everything in memory
    """
    
    # Directories to exclude (build artifacts, dependencies, generated code)
    EXCLUDE_DIRS = {
        'build', 'target', 'dist', 'out',
        'node_modules', 'vendor', '.gradle', '.mvn',
        '__pycache__', '.pytest_cache', '.tox',
        'venv', 'env', '.venv', 'virtualenv',
        '.git', '.svn', '.hg',
        'generated', 'gen', 'generated-sources',
        'bin', 'obj',
        '.idea', '.vscode', '.eclipse',
        'coverage', 'htmlcov', '.coverage',
        'logs', 'tmp', 'temp',
    }
    
    # File patterns to exclude
    EXCLUDE_PATTERNS = {
        '.class', '.pyc', '.pyo', '.pyd',
        '.jar', '.war', '.ear',
        '.min.js', '.min.css',
    }
    
    def __init__(
        self,
        git_provider: str,
        repository_owner: str,
        repository_name: str,
        branch: str,
        access_token_encrypted: str,
        service_id: str
    ):
        """
        Initialize API-based code indexer
        
        Args:
            git_provider: 'github' or 'gitlab'
            repository_owner: Repository owner/organization
            repository_name: Repository name
            branch: Branch to index
            access_token_encrypted: Encrypted access token
            service_id: Service ID for isolation
        """
        # Validate provider
        if git_provider not in ['github', 'gitlab']:
            raise ValueError(
                f"Unsupported Git provider: {git_provider}. "
                f"Supported providers: github, gitlab. "
                f"Note: Bitbucket support is planned for future release."
            )
        
        self.git_provider = git_provider
        self.repository_owner = repository_owner
        self.repository_name = repository_name
        self.branch = branch
        self.service_id = service_id
        
        # Decrypt token
        # access_token = decrypt_token(access_token_encrypted)
        access_token = access_token_encrypted

        # Create Git API client
        self.git_client = GitClientFactory.create(git_provider, access_token)
        
        # For GitLab, we need project_id
        self.project_id = None
        if git_provider == 'gitlab':
            self.project_id = self.git_client.get_project_id(repository_owner, repository_name)
        
        self.commit_sha = None
    
    def _should_exclude_path(self, path: str) -> bool:
        """Check if path should be excluded from indexing"""
        path_parts = Path(path).parts
        
        # Check if any parent directory is in exclude list
        for part in path_parts:
            if part in self.EXCLUDE_DIRS:
                return True
        
        # Check file extension patterns
        for pattern in self.EXCLUDE_PATTERNS:
            if path.endswith(pattern):
                return True
        
        return False
    
    def _get_last_indexed_commit(self) -> Optional[str]:
        """Get the last indexed commit SHA from database"""
        try:
            with get_db() as db:
                metadata = db.query(IndexingMetadata).filter(
                    IndexingMetadata.service_id == self.service_id
                ).order_by(IndexingMetadata.indexed_at.desc()).first()
                
                if metadata:
                    return metadata.commit_sha
                return None
        except Exception as e:
            logger.error(f"Error getting last indexed commit: {e}")
            return None
    
    def _delete_existing_code_blocks(self) -> int:
        """
        Delete existing code blocks for this service to prevent duplicates
        
        Returns:
            Number of code blocks deleted
        """
        try:
            with get_db() as db:
                # Delete all code blocks for this service
                deleted_count = db.query(CodeBlock).filter(
                    CodeBlock.service_id == self.service_id
                ).delete()
                
                db.commit()
                logger.info(f"Deleted {deleted_count} existing code blocks for service {self.service_id}")
                return deleted_count
        except Exception as e:
            logger.error(f"Error deleting existing code blocks: {e}")
            return 0
    
    def _get_changed_files(self, old_commit: str, new_commit: str) -> List[str]:
        """
        Get list of changed files between commits
        For API mode, we'll do full indexing for simplicity
        """
        # TODO: Implement incremental indexing via API
        # For now, return empty list to trigger full indexing
        return []
    
    def index_repository(
        self,
        languages: List[str] = None,
        force_full: bool = False
    ) -> Dict[str, int]:
        """
        Index repository via API with TRUE incremental indexing support.
        
        This method:
        1. Always fetches latest commit from remote (API mode always hits remote)
        2. Checks if repository is up-to-date
        3. Uses incremental indexing (only changed files) when possible
        4. Falls back to full indexing when forced or first-time indexing
        
        Args:
            languages: List of languages to index (e.g., ['python', 'java'])
            force_full: Force full indexing even if incremental is possible
            
        Returns:
            Statistics dict with counts and mode
        """
        logger.info(f"Starting API-based code indexing for {self.repository_owner}/{self.repository_name}")
        
        # Initialize stats
        stats = {
            'files_indexed': 0,
            'code_blocks_created': 0,
            'errors': 0,
            'commit_sha': None,
            'mode': 'full'
        }
        
        try:
            # STEP 1: Get latest commit from remote (API mode always hits remote)
            logger.info("Fetching latest commit from remote...")
            if self.git_provider == 'github':
                self.commit_sha = self.git_client.get_latest_commit(
                    self.repository_owner,
                    self.repository_name,
                    self.branch
                )
            elif self.git_provider == 'gitlab':
                self.commit_sha = self.git_client.get_latest_commit(
                    self.project_id,
                    self.branch
                )
            else:
                raise ValueError(f"Unsupported provider: {self.git_provider}")
            
            logger.info(f"Latest commit: {self.commit_sha[:8]}")
            stats['commit_sha'] = self.commit_sha
            
            # STEP 2: Check if already indexed at this commit
            last_indexed_commit = self._get_last_indexed_commit()
            
            if not force_full and last_indexed_commit == self.commit_sha:
                logger.info(f"✅ Repository already indexed at commit {self.commit_sha[:8]}")
                return {
                    'status': 'up_to_date',
                    'mode': 'skip',
                    'commit_sha': self.commit_sha,
                    'files_indexed': 0,
                    'code_blocks_created': 0,
                    'errors': 0
                }
            
            # STEP 3: Determine indexing mode (full vs incremental)
            files_to_index = []
            
            if force_full or not last_indexed_commit:
                # FULL INDEXING MODE
                logger.info(f"🔄 Starting FULL indexing (force_full={force_full}, first_time={not last_indexed_commit})")
                stats['mode'] = 'full'
                
                # Delete all existing code blocks
                deleted_count = self._delete_existing_code_blocks()
                logger.info(f"Cleared {deleted_count} existing code blocks")
                
                # Get all files from repository tree
                files_to_index = self._get_all_files(languages)
                
            else:
                # INCREMENTAL INDEXING MODE
                logger.info(f"⚡ Starting INCREMENTAL indexing from {last_indexed_commit[:8]} to {self.commit_sha[:8]}")
                stats['mode'] = 'incremental'
                
                # Get changed files between commits
                changed_files = self._get_changed_files_between_commits(
                    last_indexed_commit,
                    self.commit_sha,
                    languages
                )
                
                if not changed_files:
                    logger.info("✅ No files changed, updating metadata only")
                    self._save_indexing_metadata(stats)
                    return {
                        'status': 'success',
                        'mode': 'incremental',
                        'commit_sha': self.commit_sha,
                        'files_indexed': 0,
                        'code_blocks_created': 0,
                        'errors': 0
                    }
                
                logger.info(f"Found {len(changed_files)} changed files")
                
                # Delete blocks only for changed files
                for file_path in changed_files:
                    self._delete_file_code_blocks(file_path)
                
                files_to_index = changed_files
            
            # STEP 4: Index files
            logger.info(f"Indexing {len(files_to_index)} files...")
            
            for file_path in files_to_index:
                try:
                    # Get file content from API
                    if self.git_provider == 'github':
                        content = self.git_client.get_file_content(
                            self.repository_owner,
                            self.repository_name,
                            file_path,
                            self.branch
                        )
                    elif self.git_provider == 'gitlab':
                        content = self.git_client.get_file_content(
                            self.project_id,
                            file_path,
                            self.branch
                        )
                    else:
                        raise ValueError(f"Unsupported provider: {self.git_provider}")
                    
                    # Index based on file type
                    if file_path.endswith('.py'):
                        block_ids = self._index_python_content(file_path, content)
                    elif file_path.endswith('.java'):
                        block_ids = self._index_java_content(file_path, content)
                    else:
                        continue
                    
                    stats['files_indexed'] += 1
                    stats['code_blocks_created'] += len(block_ids)
                    
                except Exception as e:
                    logger.error(f"Error indexing {file_path}: {e}")
                    stats['errors'] += 1
            
            # STEP 5: Save indexing metadata
            self._save_indexing_metadata(stats)
            
            logger.info(f"✅ Indexing complete: mode={stats['mode']}, files={stats['files_indexed']}, blocks={stats['code_blocks_created']}, errors={stats['errors']}")
            return stats
            
        except AuthenticationError as e:
            logger.error(f"Authentication failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            raise
    
    def _index_python_content(self, file_path: str, content: str) -> List[str]:
        """
        Index Python file content (in-memory)
        
        Args:
            file_path: Relative path in repository
            content: File content as string
            
        Returns:
            List of created code block IDs
        """
        block_ids = []
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    # Extract code block
                    code = ast.get_source_segment(content, node)
                    if not code:
                        continue
                    
                    # Determine type
                    if isinstance(node, ast.ClassDef):
                        block_type = 'class'
                    else:
                        block_type = 'function'
                    
                    # Extract docstring
                    docstring = ast.get_docstring(node) or ''
                    
                    # Create code block
                    block_id = self._create_code_block(
                        file_path=file_path,
                        block_type=block_type,
                        name=node.name,
                        code=code,
                        docstring=docstring,
                        language='python',
                        start_line=node.lineno,
                        end_line=node.end_lineno
                    )
                    
                    if block_id:
                        block_ids.append(block_id)
        
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error parsing Python file {file_path}: {e}")
        
        return block_ids
    
    def _index_java_content(self, file_path: str, content: str) -> List[str]:
        """
        Index Java file content (in-memory)
        
        Args:
            file_path: Relative path in repository
            content: File content as string (decoded content from API)
            
        Returns:
            List of created code block IDs
        """
        block_ids = []
        
        # Get the actual decoded content
        decoded_content = content.get('decoded_content', '') if isinstance(content, dict) else content
        lines = decoded_content.split('\n')
        
        if JAVALANG_AVAILABLE:
            try:
                tree = javalang.parse.parse(decoded_content)

                # Index methods with proper code extraction
                for path, node in tree.filter(javalang.tree.MethodDeclaration):
                    method_name = node.name
                    start_line = node.position.line if node.position else 0
                    
                    # Extract method code snippet from source
                    method_code, end_line = self._extract_java_method_code(
                        lines, start_line, method_name
                    )
                    
                    # Extract documentation
                    docstring = node.documentation or ''
                    
                    # Create code block
                    block_id = self._create_code_block(
                        file_path=file_path,
                        block_type='method',
                        name=method_name,
                        code=method_code,
                        docstring=docstring,
                        language='java',
                        start_line=start_line,
                        end_line=end_line
                    )
                    
                    if block_id:
                        block_ids.append(block_id)
                        logger.debug(f"Indexed Java method: {method_name} (lines {start_line}-{end_line})")
                
                # Index classes with proper code extraction
                for path, node in tree.filter(javalang.tree.ClassDeclaration):
                    class_name = node.name
                    start_line = node.position.line if node.position else 0
                    
                    # Extract class code snippet from source
                    class_code, end_line = self._extract_java_class_code(
                        lines, start_line, class_name
                    )
                    
                    # Extract documentation
                    docstring = node.documentation or ''
                    
                    # Create code block
                    block_id = self._create_code_block(
                        file_path=file_path,
                        block_type='class',
                        name=class_name,
                        code=class_code,
                        docstring=docstring,
                        language='java',
                        start_line=start_line,
                        end_line=end_line
                    )
                    
                    if block_id:
                        block_ids.append(block_id)
                        logger.debug(f"Indexed Java class: {class_name} (lines {start_line}-{end_line})")
            
            except Exception as e:
                logger.error(f"Error parsing Java file {file_path}: {e}")
                # Fall through to regex-based parsing
        
        # Fallback: regex-based parsing (if javalang not available or parsing failed)
        if not block_ids:
            logger.warning(f"Using regex fallback for Java file {file_path}")
            block_ids = self._index_java_regex_fallback(file_path, decoded_content, lines)
        
        return block_ids
    
    def _extract_java_method_code(self, lines: List[str], start_line: int, method_name: str) -> tuple[str, int]:
        """
        Extract method code snippet from Java source lines
        
        Args:
            lines: Source code lines
            start_line: Starting line number (1-indexed)
            method_name: Method name to find
            
        Returns:
            Tuple of (code_snippet, end_line)
        """
        try:
            # Adjust for 0-indexed list
            idx = start_line - 1
            
            # Find the method declaration line (may be before start_line due to annotations)
            while idx > 0 and '{' not in lines[idx]:
                idx -= 1
            
            method_start = idx
            
            # Find opening brace
            brace_count = 0
            found_opening = False
            
            for i in range(method_start, len(lines)):
                line = lines[i]
                
                for char in line:
                    if char == '{':
                        brace_count += 1
                        found_opening = True
                    elif char == '}':
                        brace_count -= 1
                        
                        if found_opening and brace_count == 0:
                            # Found closing brace
                            end_line = i + 1  # Convert to 1-indexed
                            code_snippet = '\n'.join(lines[method_start:end_line])
                            return code_snippet, end_line
            
            # If we couldn't find the end, return what we have
            end_line = min(method_start + 50, len(lines))  # Max 50 lines
            code_snippet = '\n'.join(lines[method_start:end_line])
            return code_snippet, end_line
            
        except Exception as e:
            logger.error(f"Error extracting Java method code for {method_name}: {e}")
            return f"// Method: {method_name}", start_line
    
    def _extract_java_class_code(self, lines: List[str], start_line: int, class_name: str) -> tuple[str, int]:
        """
        Extract class code snippet from Java source lines
        
        Args:
            lines: Source code lines
            start_line: Starting line number (1-indexed)
            class_name: Class name to find
            
        Returns:
            Tuple of (code_snippet, end_line)
        """
        try:
            # Adjust for 0-indexed list
            idx = start_line - 1
            
            # Find the class declaration line (may be before start_line due to annotations/comments)
            while idx > 0 and 'class ' + class_name not in lines[idx]:
                idx -= 1
            
            class_start = idx
            
            # Find opening brace
            brace_count = 0
            found_opening = False
            
            for i in range(class_start, len(lines)):
                line = lines[i]
                
                for char in line:
                    if char == '{':
                        brace_count += 1
                        found_opening = True
                    elif char == '}':
                        brace_count -= 1
                        
                        if found_opening and brace_count == 0:
                            # Found closing brace
                            end_line = i + 1  # Convert to 1-indexed
                            code_snippet = '\n'.join(lines[class_start:end_line])
                            return code_snippet, end_line
            
            # If we couldn't find the end, return what we have
            end_line = min(class_start + 100, len(lines))  # Max 100 lines for class
            code_snippet = '\n'.join(lines[class_start:end_line])
            return code_snippet, end_line
            
        except Exception as e:
            logger.error(f"Error extracting Java class code for {class_name}: {e}")
            return f"// Class: {class_name}", start_line
    
    def _index_java_regex_fallback(self, file_path: str, content: str, lines: List[str]) -> List[str]:
        """
        Fallback regex-based Java parsing when javalang is not available
        
        Args:
            file_path: Relative path in repository
            content: Full file content
            lines: Content split into lines
            
        Returns:
            List of created code block IDs
        """
        block_ids = []
        
        # Pattern for methods: captures modifiers, return type, method name, and parameters
        method_pattern = r'(public|private|protected)?\s*(static)?\s*(final)?\s*(\w+(?:<[^>]+>)?)\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w\s,]+)?\s*\{'
        
        for match in re.finditer(method_pattern, content):
            method_name = match.group(5)
            start_pos = match.start()
            start_line = content[:start_pos].count('\n') + 1
            
            # Extract method code using brace matching
            method_code, end_line = self._extract_code_block_by_braces(
                content, start_pos, lines, start_line
            )
            
            block_id = self._create_code_block(
                file_path=file_path,
                block_type='method',
                name=method_name,
                code=method_code,
                docstring='',
                language='java',
                start_line=start_line,
                end_line=end_line
            )
            
            if block_id:
                block_ids.append(block_id)
                logger.debug(f"Indexed Java method (regex): {method_name} (lines {start_line}-{end_line})")
        
        # Pattern for classes
        class_pattern = r'(public|private|protected)?\s*(abstract|final)?\s*class\s+(\w+)(?:\s+extends\s+\w+)?(?:\s+implements\s+[\w\s,]+)?\s*\{'
        
        for match in re.finditer(class_pattern, content):
            class_name = match.group(3)
            start_pos = match.start()
            start_line = content[:start_pos].count('\n') + 1
            
            # Extract class code using brace matching
            class_code, end_line = self._extract_code_block_by_braces(
                content, start_pos, lines, start_line
            )
            
            block_id = self._create_code_block(
                file_path=file_path,
                block_type='class',
                name=class_name,
                code=class_code,
                docstring='',
                language='java',
                start_line=start_line,
                end_line=end_line
            )
            
            if block_id:
                block_ids.append(block_id)
                logger.debug(f"Indexed Java class (regex): {class_name} (lines {start_line}-{end_line})")
        
        return block_ids
    
    def _extract_code_block_by_braces(self, content: str, start_pos: int, lines: List[str], start_line: int) -> tuple[str, int]:
        """
        Extract code block by matching braces from a starting position
        
        Args:
            content: Full file content
            start_pos: Starting position in content
            lines: Content split into lines
            start_line: Starting line number (1-indexed)
            
        Returns:
            Tuple of (code_snippet, end_line)
        """
        try:
            brace_count = 0
            found_opening = False
            
            for i in range(start_pos, len(content)):
                char = content[i]
                
                if char == '{':
                    brace_count += 1
                    found_opening = True
                elif char == '}':
                    brace_count -= 1
                    
                    if found_opening and brace_count == 0:
                        # Found closing brace
                        end_pos = i + 1
                        end_line = content[:end_pos].count('\n') + 1
                        code_snippet = content[start_pos:end_pos]
                        return code_snippet, end_line
            
            # If we couldn't find the end, return limited snippet
            end_line = min(start_line + 50, len(lines))
            code_snippet = '\n'.join(lines[start_line - 1:end_line])
            return code_snippet, end_line
            
        except Exception as e:
            logger.error(f"Error extracting code block by braces: {e}")
            return content[start_pos:start_pos + 500], start_line  # Return first 500 chars
    
    def _create_code_block(
        self,
        file_path: str,
        block_type: str,
        name: str,
        code: str,
        docstring: str,
        language: str,
        start_line: int,
        end_line: int
    ) -> Optional[str]:
        """
        Create and store code block with embedding
        
        Returns:
            Code block ID if successful, None otherwise
        """
        try:
            # Generate unique ID
            block_id = str(uuid.uuid4())
            
            # Create embedding text
            embedding_text = f"{name}\n{docstring}\n{code}"

            metadata = {
                'service_id': self.service_id,
                'type': block_type,
                'name': name,
                'language': language,
                'commit_sha': self.commit_sha,
                'start_line': start_line,
                'end_line': end_line
            }



            if self.service_id:
                metadata['service_id'] = self.service_id

                # logger.info("Inserting code block into vector db with metadata: {}, codeblock: {}", metadata, block['code_snippet'])
            vector_db.insert_code_block(block_id, embedding_text, metadata)
            logger.info("Inserted code block into vector db")

            
            # Store in PostgreSQL
            with get_db() as db:
                code_block = CodeBlock(
                    id=block_id,
                    repository="zoro",
                    version="1.0.0",
                    service_id=self.service_id,
                    file_path=file_path,
                    symbol_type=block_type,
                    symbol_name=name,
                    code_snippet=code,
                    docstring=docstring,
                    line_start=start_line,
                    line_end=end_line,
                    commit_sha=self.commit_sha
                )
                db.add(code_block)
                db.commit()
            
            return block_id
        
        except Exception as e:
            logger.error(f"Error creating code block for {name}: {e}")
            return None
    
    # Note: sync_repository() method removed - redundant in API mode
    # API mode always fetches from remote, no local repository to sync
    
    def _save_indexing_metadata(self, stats: Dict[str, Any]):
        """Save indexing metadata to database"""
        try:
            with get_db() as db:
                metadata = IndexingMetadata(
                    id=str(uuid.uuid4()),
                    repository="zoro",
                    service_id=self.service_id,
                    commit_sha=self.commit_sha,
                    files_indexed=stats.get('files_indexed', 0),
                    code_blocks_created=stats.get('code_blocks_created', 0),
                    indexing_mode='api',
                    indexed_at=datetime.utcnow()
                )
                db.add(metadata)
                db.commit()
        except Exception as e:
            logger.error(f"Error saving indexing metadata: {e}")
    
    def _get_all_files(self, languages: List[str] = None) -> List[str]:
        """
        Get all files from repository tree filtered by language
        
        Args:
            languages: List of languages to filter (e.g., ['python', 'java'])
            
        Returns:
            List of file paths to index
        """
        try:
            # Get repository tree
            if self.git_provider == 'github':
                tree = self.git_client.get_repository_tree(
                    self.repository_owner,
                    self.repository_name,
                    self.branch
                )
            elif self.git_provider == 'gitlab':
                tree = self.git_client.get_repository_tree(
                    self.project_id,
                    self.branch
                )
            else:
                raise ValueError(f"Unsupported provider: {self.git_provider}")
            
            # Filter files by language
            supported_extensions = {
                'python': ['.py'],
                'java': ['.java'],
                'javascript': ['.js'],
                'typescript': ['.ts']
            }
            
            if languages:
                extensions = []
                for lang in languages:
                    extensions.extend(supported_extensions.get(lang.lower(), []))
            else:
                # Default to Python and Java
                extensions = supported_extensions['python'] + supported_extensions['java']
            
            # Filter files
            files_to_index = []
            for item in tree['tree']:
                path = item.get('path', '')
                
                # Skip if excluded
                if self._should_exclude_path(path):
                    continue
                
                # Check extension
                if any(path.endswith(ext) for ext in extensions):
                    files_to_index.append(path)
            
            return files_to_index
            
        except Exception as e:
            logger.error(f"Error getting all files: {e}")
            return []
    
    def _get_changed_files_between_commits(
        self,
        base_commit: str,
        head_commit: str,
        languages: List[str] = None
    ) -> List[str]:
        """
        Get list of files changed between two commits using Git API
        
        Args:
            base_commit: Base commit SHA
            head_commit: Head commit SHA
            languages: List of languages to filter
            
        Returns:
            List of changed file paths
        """
        try:
            logger.info(f"Getting changed files between {base_commit[:8]} and {head_commit[:8]}")
            
            # Get commit comparison from Git API
            if self.git_provider == 'github':
                comparison = self.git_client.compare_commits(
                    self.repository_owner,
                    self.repository_name,
                    base_commit,
                    head_commit
                )
            elif self.git_provider == 'gitlab':
                comparison = self.git_client.compare_commits(
                    self.project_id,
                    base_commit,
                    head_commit
                )
            else:
                raise ValueError(f"Unsupported provider: {self.git_provider}")
            
            # Extract changed files
            changed_files = []
            
            if self.git_provider == 'github':
                # GitHub returns 'files' array with 'filename' field
                for file_info in comparison.get('files', []):
                    filename = file_info.get('filename')
                    status = file_info.get('status')  # added, modified, removed, renamed
                    
                    # Skip deleted files
                    if status == 'removed':
                        continue
                    
                    if filename:
                        changed_files.append(filename)
                        
            elif self.git_provider == 'gitlab':
                # GitLab returns 'diffs' array with 'new_path' field
                for diff in comparison.get('diffs', []):
                    new_path = diff.get('new_path')
                    deleted_file = diff.get('deleted_file', False)
                    
                    # Skip deleted files
                    if deleted_file:
                        continue
                    
                    if new_path:
                        changed_files.append(new_path)
            
            # Filter by language and exclusions
            supported_extensions = {
                'python': ['.py'],
                'java': ['.java'],
                'javascript': ['.js'],
                'typescript': ['.ts']
            }
            
            if languages:
                extensions = []
                for lang in languages:
                    extensions.extend(supported_extensions.get(lang.lower(), []))
            else:
                extensions = supported_extensions['python'] + supported_extensions['java']
            
            filtered_files = []
            for file_path in changed_files:
                # Skip if excluded
                if self._should_exclude_path(file_path):
                    continue
                
                # Check extension
                if any(file_path.endswith(ext) for ext in extensions):
                    filtered_files.append(file_path)
            
            logger.info(f"Found {len(filtered_files)} changed files (out of {len(changed_files)} total changes)")
            return filtered_files
            
        except Exception as e:
            logger.error(f"Error getting changed files: {e}")
            logger.warning("Falling back to full indexing")
            return []
    
    def _delete_file_code_blocks(self, file_path: str) -> int:
        """
        Delete existing code blocks for a specific file (for incremental updates)
        
        Args:
            file_path: Relative path to the file whose blocks should be deleted
            
        Returns:
            Number of code blocks deleted
        """
        try:
            with get_db() as db:
                # Delete code blocks for this file and service
                query = db.query(CodeBlock).filter(
                    CodeBlock.file_path == file_path
                )
                
                # Add service filter for service isolation
                if self.service_id:
                    query = query.filter(CodeBlock.service_id == self.service_id)
                
                deleted_count = query.delete()
                db.commit()
                
                if deleted_count > 0:
                    logger.debug(f"Deleted {deleted_count} existing code blocks for file {file_path}")
                
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error deleting code blocks for file {file_path}: {e}")
            return 0
