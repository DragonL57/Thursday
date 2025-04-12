"""
Enhanced file system operations module.

This module provides comprehensive file system capabilities with a focus on power and flexibility:
- Reading from and writing to files in various formats
- Searching for files based on names, patterns, or content
- Creating and organizing directory structures
- Compressing and archiving files (zip, tar)
- Analyzing file contents and extracting relevant information
- Converting between different file formats
"""

import os
import shutil
import glob
import json
import csv
import yaml
import zipfile
import tarfile
import datetime
import re
import mimetypes
import chardet
from typing import List, Dict, Any, Union, Optional, Tuple, Iterator, BinaryIO
from pydantic import BaseModel, Field
from pathlib import Path

from .formatting import tool_message_print, tool_report_print
from gem import format_size

# Define models for input data
class FileData(BaseModel):
    """Model for file data with path and content."""
    file_path: str = Field(..., description="Path of the file, can be folder/folder2/filename.txt too")
    content: str = Field(..., description="Content of the file")

class FileOperation(BaseModel):
    """Model for file operations with source and destination paths."""
    source_path: str = Field(..., description="Source file/directory path")
    dest_path: str = Field(..., description="Destination file/directory path")

class FileSearchCriteria(BaseModel):
    """Model for file search criteria."""
    pattern: str = Field(None, description="Glob pattern to match filenames (e.g., '*.py', 'data_*.csv')")
    path: str = Field(".", description="Directory to search in (defaults to current directory)")
    recursive: bool = Field(False, description="Whether to search recursively in subdirectories")
    include_hidden: bool = Field(False, description="Whether to include hidden files")
    content_match: str = Field(None, description="Text pattern to match in file contents")
    case_sensitive: bool = Field(False, description="Whether content matching is case-sensitive")
    max_size: int = Field(None, description="Maximum file size in bytes")
    min_size: int = Field(None, description="Minimum file size in bytes")
    file_types: List[str] = Field(None, description="List of file extensions to include (e.g., ['.txt', '.md'])")

class FileSystemNavigator:
    """
    Class for navigating and gathering information about the file system structure.
    """
    
    @staticmethod
    def get_current_directory() -> str:
        """
        Get the current working directory.

        Returns:
            str: The absolute path of the current working directory.
        """
        tool_message_print("get_current_directory", [])
        tool_message_print("get_current_directory", [], is_output=True)
        
        try:
            return os.getcwd()
        except Exception as e:
            tool_report_print("Error getting current directory:", str(e), is_error=True)
            return f"Error getting current directory: {e}"
    
    @staticmethod
    def list_directory(path: str = ".", recursive: bool = False, 
                      files_only: bool = False, dirs_only: bool = False) -> List[Dict]:
        """
        Returns a list of contents of a directory with detailed information about each item.

        Args:
            path: The path to the directory.
            recursive: Whether to list contents recursively.
            files_only: Whether to list only files.
            dirs_only: Whether to list only directories.

        Returns:
            list: A list of dictionaries containing information about each item.
        """
        tool_message_print("list_directory", [("path", path), ("recursive", str(recursive)), 
                                           ("files_only", str(files_only)), ("dirs_only", str(dirs_only))])
        
        tool_message_print("list_directory", [("path", path), ("recursive", str(recursive)), 
                                           ("files_only", str(files_only)), ("dirs_only", str(dirs_only))], is_output=True)
        items = []
        
        try:
            def get_item_info(item_path: str) -> Dict:
                """Get detailed info about a file system item."""
                is_dir = os.path.isdir(item_path)
                
                info = {
                    'name': os.path.basename(item_path),
                    'path': item_path,
                    'is_dir': is_dir,
                    'size': 'N/A' if is_dir else format_size(os.path.getsize(item_path)),
                }
                
                # Add modification and creation times
                try:
                    info['modified'] = datetime.datetime.fromtimestamp(
                        os.path.getmtime(item_path)).isoformat()
                    info['created'] = datetime.datetime.fromtimestamp(
                        os.path.getctime(item_path)).isoformat()
                except Exception:
                    info['modified'] = 'Unknown'
                    info['created'] = 'Unknown'
                
                # Add file type for files
                if not is_dir:
                    mime_type, _ = mimetypes.guess_type(item_path)
                    info['type'] = mime_type or 'application/octet-stream'
                
                return info

            if recursive:
                for dirpath, dirnames, filenames in os.walk(path):
                    if not files_only:
                        for dirname in dirnames:
                            items.append(get_item_info(os.path.join(dirpath, dirname)))
                    if not dirs_only:
                        for filename in filenames:
                            items.append(get_item_info(os.path.join(dirpath, filename)))
            else:
                with os.scandir(path) as it:
                    for entry in it:
                        if files_only and entry.is_file():
                            items.append(get_item_info(entry.path))
                        elif dirs_only and entry.is_dir():
                            items.append(get_item_info(entry.path))
                        elif not files_only and not dirs_only:
                            items.append(get_item_info(entry.path))
            
            return items
        except Exception as e:
            tool_report_print("Error listing directory:", str(e), is_error=True)
            return [{"error": str(e)}]
    
    @staticmethod
    def get_file_metadata(filepath: str) -> Dict:
        """
        Get comprehensive metadata of a file.

        Args:
          filepath: The path to the file.

        Returns:
            dict: A dictionary containing file metadata.
        """
        tool_message_print("get_file_metadata", [("filepath", filepath)])
        tool_message_print("get_file_metadata", [("filepath", filepath)], is_output=True)
        
        try:
            stats = os.stat(filepath)
            metadata = {
                'path': filepath,
                'name': os.path.basename(filepath),
                'size': format_size(stats.st_size),
                'size_bytes': stats.st_size,
                'is_dir': os.path.isdir(filepath),
                'creation_time': stats.st_ctime,
                'modification_time': stats.st_mtime,
                'access_time': stats.st_atime,
                'creation_time_readable': datetime.datetime.fromtimestamp(stats.st_ctime).isoformat(),
                'modification_time_readable': datetime.datetime.fromtimestamp(stats.st_mtime).isoformat(),
                'access_time_readable': datetime.datetime.fromtimestamp(stats.st_atime).isoformat(),
            }
            
            # Add file-specific data for non-directories
            if not os.path.isdir(filepath):
                mime_type, encoding = mimetypes.guess_type(filepath)
                metadata.update({
                    'mime_type': mime_type or 'application/octet-stream',
                    'encoding': encoding,
                    'extension': os.path.splitext(filepath)[1],
                })
                
                # For text files, detect encoding
                if mime_type and mime_type.startswith('text/') or filepath.endswith(('.py', '.js', '.ts', '.html', '.css', '.json', '.md')):
                    try:
                        with open(filepath, 'rb') as f:
                            raw_data = f.read(4096)  # Read first 4KB to detect encoding
                            encoding_info = chardet.detect(raw_data)
                            metadata['detected_encoding'] = encoding_info
                    except Exception:
                        pass
            
            return metadata
        except Exception as e:
            tool_report_print("Error getting file metadata:", str(e), is_error=True)
            return {"error": str(e)}
    
    @staticmethod
    def get_directory_size(path: str) -> Dict:
        """
        Get the size of the specified directory.

        Args:
          path: The path to the directory.

        Returns:
            dict: Directory size information.
        """
        tool_message_print("get_directory_size", [("path", path)])
        tool_message_print("get_directory_size", [("path", path)], is_output=True)
        
        try:
            total_size = 0
            file_count = 0
            dir_count = 0
            
            for dirpath, dirnames, filenames in os.walk(path):
                dir_count += len(dirnames)
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.isfile(fp):
                        file_size = os.path.getsize(fp)
                        total_size += file_size
                        file_count += 1

            return {
                'path': path,
                'total_size_bytes': total_size,
                'total_size_human': format_size(total_size),
                'file_count': file_count,
                'directory_count': dir_count,
                'total_items': file_count + dir_count
            }
        except Exception as e:
            tool_report_print("Error getting directory size:", str(e), is_error=True)
            return {"error": str(e)}

class FileSearcher:
    """
    Class for advanced file searching capabilities.
    """
    
    @staticmethod
    def find_files(criteria: FileSearchCriteria) -> List[Dict]:
        """
        Advanced file search with multiple criteria.

        Args:
            criteria: FileSearchCriteria object containing search parameters

        Returns:
            List of dictionaries with file information
        """
        tool_message_print("find_files", [
            ("pattern", criteria.pattern),
            ("path", criteria.path),
            ("recursive", str(criteria.recursive)), 
            ("content_match", criteria.content_match or "None")
        ])
        
        tool_message_print("find_files", [], is_output=True)
        
        try:
            if not os.path.isdir(criteria.path):
                tool_report_print("Error:", f"Directory '{criteria.path}' not found.", is_error=True)
                return [{"error": f"Directory '{criteria.path}' not found."}]
            
            # Prepare the pattern
            pattern = criteria.pattern or '*'
            full_pattern = os.path.join(criteria.path, pattern)
            
            # Get initial matches based on filename pattern
            matches = glob.glob(full_pattern, recursive=criteria.recursive, include_hidden=criteria.include_hidden)
            
            result_files = []
            
            # Filter matches based on additional criteria
            for file_path in matches:
                # Skip directories if we're checking content
                if os.path.isdir(file_path) and criteria.content_match:
                    continue
                    
                try:
                    # Check file size constraints if specified
                    if criteria.min_size is not None or criteria.max_size is not None:
                        file_size = os.path.getsize(file_path)
                        if criteria.min_size is not None and file_size < criteria.min_size:
                            continue
                        if criteria.max_size is not None and file_size > criteria.max_size:
                            continue
                    
                    # Check file extension if specified
                    if criteria.file_types:
                        file_ext = os.path.splitext(file_path)[1].lower()
                        if file_ext not in criteria.file_types and f".{file_ext}" not in criteria.file_types:
                            continue
                    
                    # Check file content if specified
                    if criteria.content_match and os.path.isfile(file_path):
                        try:
                            # Try to read file as text
                            with open(file_path, 'r', errors='ignore') as f:
                                content = f.read()
                                
                            if criteria.case_sensitive:
                                if criteria.content_match not in content:
                                    continue
                            else:
                                if criteria.content_match.lower() not in content.lower():
                                    continue
                        except UnicodeDecodeError:
                            # Skip binary files when content matching
                            continue
                    
                    # If we get here, all criteria are satisfied
                    file_info = {
                        'path': file_path,
                        'name': os.path.basename(file_path),
                        'is_dir': os.path.isdir(file_path),
                        'size': format_size(os.path.getsize(file_path)) if os.path.isfile(file_path) else 'N/A'
                    }
                    result_files.append(file_info)
                    
                except Exception as e:
                    # Skip files with access issues
                    tool_report_print(f"Skipping {file_path}: {str(e)}", is_error=True)
                    continue
            
            if not result_files:
                tool_report_print("Status:", "No files found matching the criteria.")
                return []
            
            tool_report_print("Status:", f"Found {len(result_files)} matching files")
            return result_files
            
        except Exception as e:
            tool_report_print("Error during file search:", str(e), is_error=True)
            return [{"error": str(e)}]
    
    @staticmethod
    def grep_in_files(pattern: str, file_pattern: str = "*", 
                     directory: str = ".", recursive: bool = False, 
                     case_sensitive: bool = False, use_regex: bool = False) -> List[Dict]:
        """
        Search for pattern in file contents (similar to grep).
        
        Args:
            pattern: Text pattern to search for
            file_pattern: File pattern to limit search
            directory: Directory to search in
            recursive: Whether to search recursively
            case_sensitive: Whether to match case sensitively
            use_regex: Whether to treat pattern as regex
            
        Returns:
            List of dictionaries with matching results
        """
        tool_message_print("grep_in_files", [
            ("pattern", pattern),
            ("file_pattern", file_pattern),
            ("directory", directory),
            ("recursive", str(recursive)),
            ("case_sensitive", str(case_sensitive)),
            ("use_regex", str(use_regex))
        ])
        
        tool_message_print("grep_in_files", [], is_output=True)
        
        try:
            # Prepare for matches
            results = []
            
            # Prepare the pattern
            if use_regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                compiled_pattern = re.compile(pattern, flags)
            else:
                if not case_sensitive:
                    pattern = pattern.lower()
            
            # Get file list using find_files
            criteria = FileSearchCriteria(
                pattern=file_pattern,
                path=directory,
                recursive=recursive
            )
            files = [f['path'] for f in FileSearcher.find_files(criteria) if not f.get('is_dir', False)]
            
            # Search through each file
            for file_path in files:
                try:
                    with open(file_path, 'r', errors='ignore') as f:
                        for line_number, line in enumerate(f, 1):
                            match_found = False
                            
                            if use_regex:
                                match_found = bool(compiled_pattern.search(line))
                            else:
                                line_to_check = line if case_sensitive else line.lower()
                                match_found = pattern in line_to_check
                            
                            if match_found:
                                results.append({
                                    'file': file_path,
                                    'line_number': line_number,
                                    'line': line.rstrip('\n'),
                                    'match': pattern
                                })
                except UnicodeDecodeError:
                    # Skip binary files
                    continue
                except Exception as e:
                    tool_report_print(f"Error reading {file_path}: {str(e)}", is_error=True)
            
            tool_report_print("Status:", f"Found {len(results)} matches in {len(set(r['file'] for r in results))} files")
            return results
            
        except Exception as e:
            tool_report_print("Error during grep search:", str(e), is_error=True)
            return [{"error": str(e)}]

class FileReader:
    """
    Class for reading file content with various formats.
    """
    
    @staticmethod
    def read_text(filepath: str, encoding: str = 'utf-8') -> str:
        """
        Read content from a text file.

        Args:
            filepath: The path to the file
            encoding: File encoding (default: utf-8)

        Returns:
            str: The content of the file as a string
        """
        tool_message_print("read_text", [("filepath", filepath), ("encoding", encoding)])
        tool_message_print("read_text", [("filepath", filepath), ("encoding", encoding)], is_output=True)
        
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
                return content
        except UnicodeDecodeError:
            # Try to detect encoding if specified encoding fails
            try:
                with open(filepath, 'rb') as f:
                    raw_data = f.read()
                    encoding_result = chardet.detect(raw_data)
                    detected_encoding = encoding_result['encoding']
                    
                    tool_report_print("Warning:", f"Encoding detection suggests {detected_encoding}")
                    
                    with open(filepath, 'r', encoding=detected_encoding) as f:
                        return f.read()
            except Exception as e:
                tool_report_print("Error detecting encoding:", str(e), is_error=True)
                return f"Error: Could not detect proper encoding for {filepath}"
        except Exception as e:
            tool_report_print("Error reading file:", str(e), is_error=True)
            return f"Error reading file: {e}"
    
    @staticmethod
    def read_binary(filepath: str) -> Dict:
        """
        Read binary content from a file providing information about it.

        Args:
            filepath: The path to the file

        Returns:
            Dict: Information about the binary file
        """
        tool_message_print("read_binary", [("filepath", filepath)])
        tool_message_print("read_binary", [("filepath", filepath)], is_output=True)
        
        try:
            with open(filepath, 'rb') as f:
                # Read the first 256 bytes for header inspection
                header = f.read(256)
                
                # Get file size
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                
            mime_type, _ = mimetypes.guess_type(filepath)
            
            # Create binary file information
            info = {
                'path': filepath,
                'size': format_size(file_size),
                'size_bytes': file_size,
                'mime_type': mime_type or 'application/octet-stream',
                'header_hex': header.hex()[:100] + ('...' if len(header) > 50 else ''),
                'is_text': False,
                'file_type': mime_type or 'Unknown'
            }
            
            # Try to determine if it might be text despite being opened as binary
            try:
                encoding_result = chardet.detect(header)
                if encoding_result['confidence'] > 0.9:
                    info['possible_encoding'] = encoding_result['encoding']
                    info['encoding_confidence'] = encoding_result['confidence']
                    info['is_text'] = True
            except:
                pass
                
            return info
        except Exception as e:
            tool_report_print("Error reading binary file:", str(e), is_error=True)
            return {"error": str(e)}
    
    @staticmethod
    def read_lines(filepath: str, start_line: int = 1, end_line: Optional[int] = None, 
                  encoding: str = 'utf-8') -> str:
        """
        Read a range of lines from a file (inclusive).

        Args:
            filepath: The path to the file
            start_line: First line to read (1-indexed)
            end_line: Last line to read (if None, reads to the end)
            encoding: File encoding

        Returns:
            str: Content of the specified lines
        """
        tool_message_print("read_lines", [
            ("filepath", filepath), 
            ("start_line", str(start_line)), 
            ("end_line", str(end_line) if end_line else "end")
        ])
        tool_message_print("read_lines", [], is_output=True)
        
        try:
            with open(filepath, "r", encoding=encoding) as file:
                if end_line is not None:
                    # Read specific lines
                    lines = []
                    for i, line in enumerate(file, 1):
                        if i < start_line:
                            continue
                        if end_line is not None and i > end_line:
                            break
                        lines.append(line)
                    content = "".join(lines)
                else:
                    # Skip to start_line and read the rest of the file
                    for i in range(start_line - 1):
                        file.readline()
                    content = file.read()
                
                return content
        except UnicodeDecodeError:
            return f"Error: File {filepath} appears to be binary or uses a different encoding."
        except FileNotFoundError:
            return f"Error: File {filepath} not found."
        except Exception as e:
            tool_report_print("Error reading file:", str(e), is_error=True)
            return f"Error reading file: {e}"
    
    @staticmethod
    def read_structured_file(filepath: str) -> Dict:
        """
        Read a structured file (JSON, YAML, CSV) and return its content.

        Args:
            filepath: Path to the file

        Returns:
            Dict with parsed content or error
        """
        tool_message_print("read_structured_file", [("filepath", filepath)])
        tool_message_print("read_structured_file", [("filepath", filepath)], is_output=True)
        
        ext = os.path.splitext(filepath)[1].lower()
        
        try:
            if ext == '.json':
                with open(filepath, 'r', encoding='utf-8') as f:
                    return {'format': 'json', 'data': json.load(f)}
            
            elif ext in ('.yaml', '.yml'):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return {'format': 'yaml', 'data': yaml.safe_load(f)}
            
            elif ext == '.csv':
                with open(filepath, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    return {'format': 'csv', 'headers': reader.fieldnames, 'rows': rows}
            
            else:
                return {'error': f"Unsupported file format: {ext}"}
                
        except json.JSONDecodeError as e:
            return {'format': 'json', 'error': f"Invalid JSON: {str(e)}"}
        except yaml.YAMLError as e:
            return {'format': 'yaml', 'error': f"Invalid YAML: {str(e)}"}
        except Exception as e:
            tool_report_print("Error reading structured file:", str(e), is_error=True)
            return {'error': str(e)}

class FileWriter:
    """
    Class for writing content to files with various formats.
    """
    
    @staticmethod
    def write_text(filepath: str, content: str, encoding: str = 'utf-8') -> Dict:
        """
        Write text content to a file.

        Args:
            filepath: Path to the file
            content: Text content to write
            encoding: File encoding

        Returns:
            Dict with status information
        """
        tool_message_print("write_text", [("filepath", filepath)])
        tool_message_print("write_text", [("filepath", filepath)], is_output=True)
        
        try:
            # Create directories if they don't exist
            dir_path = os.path.dirname(filepath)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
                
            with open(filepath, 'w', encoding=encoding) as f:
                f.write(content)
            
            tool_report_print("Status:", f"Successfully wrote {len(content)} characters to {filepath}")
            return {
                'success': True,
                'path': filepath,
                'bytes_written': len(content.encode(encoding)),
                'chars_written': len(content)
            }
        except Exception as e:
            tool_report_print("Error writing file:", str(e), is_error=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def write_multiple(files_data: List[FileData]) -> Dict:
        """
        Write content to multiple files, supports nested directory file creation.
        
        Args:
          files_data: A list of FileData objects containing file paths and content

        Returns:
          Dict with summary of operations
        """
        tool_message_print("write_multiple", [("count", str(len(files_data)))])
        tool_message_print("write_multiple", [("count", str(len(files_data)))], is_output=True)
        
        results = {'success': 0, 'failed': 0, 'details': {}}
        
        for file_data in files_data:
            try:
                nested_dirs = os.path.dirname(file_data.file_path)
                if nested_dirs:
                    os.makedirs(nested_dirs, exist_ok=True)

                with open(file_data.file_path, 'w', encoding="utf-8") as f:
                    f.write(file_data.content)
                tool_report_print("Created ✅:", file_data.file_path)
                results['details'][file_data.file_path] = {
                    'success': True,
                    'bytes_written': len(file_data.content.encode('utf-8')),
                    'chars_written': len(file_data.content)
                }
                results['success'] += 1
            except Exception as e:
                tool_report_print("❌", file_data.file_path, is_error=True)
                tool_report_print("Error writing file:", str(e), is_error=True)
                results['details'][file_data.file_path] = {
                    'success': False,
                    'error': str(e)
                }
                results['failed'] += 1

        tool_report_print("Summary:", f"Wrote {results['success']}/{len(files_data)} files successfully")
        return results
    
    @staticmethod
    def write_structured_file(filepath: str, data: Any, format_type: str) -> Dict:
        """
        Write data to a structured file format (JSON, YAML, CSV).

        Args:
            filepath: Path to the file
            data: Data to write
            format_type: Format type ('json', 'yaml', 'csv')

        Returns:
            Dict with status information
        """
        tool_message_print("write_structured_file", [("filepath", filepath), ("format", format_type)])
        tool_message_print("write_structured_file", [("filepath", filepath), ("format", format_type)], is_output=True)
        
        try:
            # Create directories if they don't exist
            dir_path = os.path.dirname(filepath)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            if format_type.lower() == 'json':
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
            elif format_type.lower() in ('yaml', 'yml'):
                with open(filepath, 'w', encoding='utf-8') as f:
                    yaml.safe_dump(data, f)
                
            elif format_type.lower() == 'csv':
                if not isinstance(data, list) or not data:
                    return {
                        'success': False,
                        'error': "CSV data must be a non-empty list of dictionaries"
                    }
                    
                with open(filepath, 'w', encoding='utf-8', newline='') as f:
                    fieldnames = data[0].keys()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(data)
            
            else:
                return {
                    'success': False,
                    'error': f"Unsupported format: {format_type}"
                }
                
            tool_report_print("Status:", f"Successfully wrote data to {filepath}")
            return {
                'success': True,
                'path': filepath,
                'format': format_type
            }
            
        except Exception as e:
            tool_report_print("Error writing structured file:", str(e), is_error=True)
            return {
                'success': False,
                'error': str(e)
            }

class FileManager:
    """
    Class for file operations like copying, moving, and organizing files.
    """
    
    @staticmethod
    def copy(operations: Union[FileOperation, List[FileOperation]]) -> Dict:
        """
        Copy files or directories from source to destination.

        Args:
            operations: Single FileOperation or list of operations

        Returns:
            Dict with operation results
        """
        if not isinstance(operations, list):
            operations = [operations]
            
        tool_message_print("copy", [("operations", str(len(operations)))])
        tool_message_print("copy", [], is_output=True)
        
        results = {'success': 0, 'failed': 0, 'details': {}}
        
        for op in operations:
            try:
                # Check if source exists
                if not os.path.exists(op.source_path):
                    raise FileNotFoundError(f"Source path not found: {op.source_path}")
                
                # Create parent directories if needed
                dest_dir = os.path.dirname(op.dest_path)
                if dest_dir:
                    os.makedirs(dest_dir, exist_ok=True)
                
                # Perform copy
                if os.path.isdir(op.source_path):
                    shutil.copytree(op.source_path, op.dest_path)
                    item_type = "directory"
                else:
                    shutil.copy2(op.source_path, op.dest_path)
                    item_type = "file"
                
                tool_report_print("Copied ✅:", f"{item_type} {op.source_path} to {op.dest_path}")
                results['details'][op.source_path] = {
                    'success': True,
                    'destination': op.dest_path,
                    'type': item_type
                }
                results['success'] += 1
                
            except Exception as e:
                tool_report_print("❌", f"Failed to copy {op.source_path}", is_error=True)
                tool_report_print("Error:", str(e), is_error=True)
                results['details'][op.source_path] = {
                    'success': False,
                    'destination': op.dest_path,
                    'error': str(e)
                }
                results['failed'] += 1
                
        tool_report_print("Summary:", f"Copied {results['success']}/{len(operations)} items successfully")
        return results
    
    @staticmethod
    def move(operations: Union[FileOperation, List[FileOperation]]) -> Dict:
        """
        Move files or directories from source to destination.

        Args:
            operations: Single FileOperation or list of operations

        Returns:
            Dict with operation results
        """
        if not isinstance(operations, list):
            operations = [operations]
            
        tool_message_print("move", [("operations", str(len(operations)))])
        tool_message_print("move", [], is_output=True)
        
        results = {'success': 0, 'failed': 0, 'details': {}}
        
        for op in operations:
            try:
                # Check if source exists
                if not os.path.exists(op.source_path):
                    raise FileNotFoundError(f"Source path not found: {op.source_path}")
                
                # Create parent directories if needed
                dest_dir = os.path.dirname(op.dest_path)
                if dest_dir:
                    os.makedirs(dest_dir, exist_ok=True)
                
                # Perform move
                item_type = "directory" if os.path.isdir(op.source_path) else "file"
                shutil.move(op.source_path, op.dest_path)
                
                tool_report_print("Moved ✅:", f"{item_type} {op.source_path} to {op.dest_path}")
                results['details'][op.source_path] = {
                    'success': True,
                    'destination': op.dest_path,
                    'type': item_type
                }
                results['success'] += 1
                
            except Exception as e:
                tool_report_print("❌", f"Failed to move {op.source_path}", is_error=True)
                tool_report_print("Error:", str(e), is_error=True)
                results['details'][op.source_path] = {
                    'success': False,
                    'destination': op.dest_path,
                    'error': str(e)
                }
                results['failed'] += 1
                
        tool_report_print("Summary:", f"Moved {results['success']}/{len(operations)} items successfully")
        return results
    
    @staticmethod
    def create_directory(paths: Union[str, List[str]]) -> Dict:
        """
        Create one or multiple directories.

        Args:
            paths: Single path or list of paths to create

        Returns:
            Dict with operation results
        """
        if isinstance(paths, str):
            paths = [paths]
            
        tool_message_print("create_directory", [("paths", str(paths))])
        tool_message_print("create_directory", [], is_output=True)
        
        results = {'success': 0, 'failed': 0, 'details': {}}
        
        for path in paths:
            try:
                os.makedirs(path, exist_ok=True)
                tool_report_print("Created ✅:", path)
                results['details'][path] = {
                    'success': True,
                }
                results['success'] += 1
            except Exception as e:
                tool_report_print("❌", f"Failed to create directory {path}", is_error=True)
                tool_report_print("Error:", str(e), is_error=True)
                results['details'][path] = {
                    'success': False,
                    'error': str(e)
                }
                results['failed'] += 1
                
        tool_report_print("Summary:", f"Created {results['success']}/{len(paths)} directories successfully")
        return results
    
    @staticmethod
    def delete(paths: Union[str, List[str]], recursive: bool = False) -> Dict:
        """
        Delete files or directories.

        Args:
            paths: Single path or list of paths to delete
            recursive: Whether to recursively delete directories

        Returns:
            Dict with operation results
        """
        if isinstance(paths, str):
            paths = [paths]
            
        tool_message_print("delete", [("paths", str(paths)), ("recursive", str(recursive))])
        tool_message_print("delete", [], is_output=True)
        
        results = {'success': 0, 'failed': 0, 'details': {}}
        
        for path in paths:
            try:
                if os.path.isdir(path):
                    if recursive:
                        shutil.rmtree(path)
                        item_type = "directory (recursive)"
                    else:
                        os.rmdir(path)
                        item_type = "directory"
                else:
                    os.remove(path)
                    item_type = "file"
                    
                tool_report_print("Deleted ✅:", f"{item_type} {path}")
                results['details'][path] = {
                    'success': True,
                    'type': item_type
                }
                results['success'] += 1
                
            except IsADirectoryError:
                tool_report_print("❌", f"Cannot delete directory {path} without recursive=True", is_error=True)
                results['details'][path] = {
                    'success': False,
                    'error': "Directory not empty and recursive not enabled"
                }
                results['failed'] += 1
                
            except Exception as e:
                tool_report_print("❌", f"Failed to delete {path}", is_error=True)
                tool_report_print("Error:", str(e), is_error=True)
                results['details'][path] = {
                    'success': False,
                    'error': str(e)
                }
                results['failed'] += 1
                
        tool_report_print("Summary:", f"Deleted {results['success']}/{len(paths)} items successfully")
        return results

class FileArchiver:
    """
    Class for compressing and extracting archive files.
    """
    
    @staticmethod
    def create_zip(zip_file: str, files: List[str], compress_level: int = 6) -> Dict:
        """
        Create a ZIP archive from files.

        Args:
            zip_file: Path to the output ZIP file
            files: List of files or directories to include
            compress_level: Compression level (0-9)

        Returns:
            Dict with operation results
        """
        tool_message_print("create_zip", [
            ("zip_file", zip_file), 
            ("files", str(len(files))),
            ("compress_level", str(compress_level))
        ])
        tool_message_print("create_zip", [], is_output=True)
        
        try:
            # Create parent directories if needed
            zip_dir = os.path.dirname(zip_file)
            if zip_dir:
                os.makedirs(zip_dir, exist_ok=True)
            
            added_files = []
            skipped_files = []
            
            with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED, compresslevel=compress_level) as zipf:
                for path in files:
                    if os.path.isdir(path):
                        # For directories, add all files recursively
                        for root, _, filenames in os.walk(path):
                            for filename in filenames:
                                file_to_add = os.path.join(root, filename)
                                try:
                                    # Store with relative path
                                    arcname = os.path.relpath(file_to_add, os.path.dirname(path))
                                    zipf.write(file_to_add, arcname=arcname)
                                    added_files.append(file_to_add)
                                except Exception as e:
                                    tool_report_print("❌", f"Skipping {file_to_add}: {str(e)}", is_error=True)
                                    skipped_files.append({
                                        'file': file_to_add,
                                        'error': str(e)
                                    })
                    else:
                        # For individual files
                        try:
                            arcname = os.path.basename(path)
                            zipf.write(path, arcname=arcname)
                            added_files.append(path)
                        except Exception as e:
                            tool_report_print("❌", f"Skipping {path}: {str(e)}", is_error=True)
                            skipped_files.append({
                                'file': path,
                                'error': str(e)
                            })
                            
            # Get compressed size
            compressed_size = os.path.getsize(zip_file)
            
            tool_report_print("Created ✅:", f"ZIP file {zip_file} with {len(added_files)} files")
            return {
                'success': True,
                'zip_file': zip_file,
                'size': format_size(compressed_size),
                'size_bytes': compressed_size,
                'files_added': len(added_files),
                'files_skipped': len(skipped_files),
                'skipped_details': skipped_files if skipped_files else None
            }
            
        except Exception as e:
            tool_report_print("Error creating ZIP file:", str(e), is_error=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def extract_archive(archive_path: str, extract_path: str = None, specific_files: List[str] = None) -> Dict:
        """
        Extract a ZIP or TAR archive.

        Args:
            archive_path: Path to the archive file
            extract_path: Path to extract to (defaults to same directory)
            specific_files: List of specific files to extract (optional)

        Returns:
            Dict with operation results
        """
        tool_message_print("extract_archive", [
            ("archive_path", archive_path), 
            ("extract_path", extract_path or "same directory")
        ])
        tool_message_print("extract_archive", [], is_output=True)
        
        try:
            if not extract_path:
                extract_path = os.path.dirname(archive_path)
            
            # Create extraction directory if needed
            os.makedirs(extract_path, exist_ok=True)
            
            # Detect archive type
            if archive_path.endswith(('.zip')):
                with zipfile.ZipFile(archive_path, 'r') as archive:
                    # List contents
                    contents = archive.namelist()
                    
                    if specific_files:
                        # Extract only specified files
                        to_extract = [f for f in contents if f in specific_files]
                        archive.extractall(path=extract_path, members=to_extract)
                        extracted_count = len(to_extract)
                    else:
                        # Extract all files
                        archive.extractall(path=extract_path)
                        extracted_count = len(contents)
                    
                    tool_report_print("Extracted ✅:", f"{extracted_count} files from ZIP archive to {extract_path}")
                    return {
                        'success': True,
                        'archive_type': 'zip',
                        'extract_path': extract_path,
                        'files_extracted': extracted_count,
                        'all_contents': contents
                    }
                    
            elif archive_path.endswith(('.tar', '.tar.gz', '.tgz')):
                mode = 'r:gz' if archive_path.endswith(('.tar.gz', '.tgz')) else 'r'
                
                with tarfile.open(archive_path, mode) as archive:
                    # List contents
                    contents = archive.getnames()
                    
                    if specific_files:
                        # Extract only specified files
                        to_extract = [f for f in contents if f in specific_files]
                        for member in to_extract:
                            archive.extract(member, path=extract_path)
                        extracted_count = len(to_extract)
                    else:
                        # Extract all files
                        archive.extractall(path=extract_path)
                        extracted_count = len(contents)
                    
                    tool_report_print("Extracted ✅:", f"{extracted_count} files from TAR archive to {extract_path}")
                    return {
                        'success': True,
                        'archive_type': 'tar',
                        'extract_path': extract_path,
                        'files_extracted': extracted_count,
                        'all_contents': contents
                    }
            else:
                return {
                    'success': False,
                    'error': f"Unsupported archive format: {os.path.basename(archive_path)}"
                }
                
        except Exception as e:
            tool_report_print("Error extracting archive:", str(e), is_error=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def list_archive_contents(archive_path: str) -> Dict:
        """
        List contents of an archive without extracting.

        Args:
            archive_path: Path to the archive file

        Returns:
            Dict with archive contents information
        """
        tool_message_print("list_archive_contents", [("archive_path", archive_path)])
        tool_message_print("list_archive_contents", [], is_output=True)
        
        try:
            if archive_path.endswith(('.zip')):
                with zipfile.ZipFile(archive_path, 'r') as archive:
                    info_list = archive.infolist()
                    total_size = sum(info.file_size for info in info_list)
                    compressed_size = sum(info.compress_size for info in info_list)
                    
                    contents = []
                    for info in info_list:
                        contents.append({
                            'filename': info.filename,
                            'size': format_size(info.file_size),
                            'size_bytes': info.file_size,
                            'compressed_size': format_size(info.compress_size),
                            'compressed_bytes': info.compress_size,
                            'is_dir': info.filename.endswith('/'),
                            'date_time': f"{info.date_time[0]}-{info.date_time[1]:02d}-{info.date_time[2]:02d} {info.date_time[3]:02d}:{info.date_time[4]:02d}:{info.date_time[5]:02d}"
                        })
                    
                    tool_report_print("Status:", f"Listed {len(contents)} files from ZIP archive")
                    return {
                        'success': True,
                        'archive_type': 'zip',
                        'file_count': len(contents),
                        'total_size': format_size(total_size),
                        'compressed_size': format_size(compressed_size),
                        'compression_ratio': f"{(1 - compressed_size/total_size) * 100:.1f}%" if total_size else "0%",
                        'contents': contents
                    }
                    
            elif archive_path.endswith(('.tar', '.tar.gz', '.tgz')):
                mode = 'r:gz' if archive_path.endswith(('.tar.gz', '.tgz')) else 'r'
                
                with tarfile.open(archive_path, mode) as archive:
                    contents = []
                    total_size = 0
                    
                    for member in archive.getmembers():
                        contents.append({
                            'filename': member.name,
                            'size': format_size(member.size),
                            'size_bytes': member.size,
                            'is_dir': member.isdir(),
                            'type': 'directory' if member.isdir() else 'file',
                            'mode': member.mode,
                            'modified': datetime.datetime.fromtimestamp(member.mtime).isoformat()
                        })
                        total_size += member.size
                    
                    tool_report_print("Status:", f"Listed {len(contents)} files from TAR archive")
                    return {
                        'success': True,
                        'archive_type': 'tar',
                        'file_count': len(contents),
                        'total_size': format_size(total_size),
                        'contents': contents
                    }
            else:
                return {
                    'success': False,
                    'error': f"Unsupported archive format: {os.path.basename(archive_path)}"
                }
                
        except Exception as e:
            tool_report_print("Error reading archive contents:", str(e), is_error=True)
            return {
                'success': False,
                'error': str(e)
            }

class FileConverter:
    """
    Class for converting between different file formats.
    """
    
    @staticmethod
    def convert_to_json(input_path: str, output_path: str = None) -> Dict:
        """
        Convert various formats to JSON.

        Args:
            input_path: Path to input file (CSV, YAML, etc.)
            output_path: Path to output JSON file (optional)

        Returns:
            Dict with conversion results
        """
        tool_message_print("convert_to_json", [
            ("input_path", input_path), 
            ("output_path", output_path or "auto-generated")
        ])
        tool_message_print("convert_to_json", [], is_output=True)
        
        try:
            ext = os.path.splitext(input_path)[1].lower()
            
            # Set default output path if not provided
            if not output_path:
                output_path = os.path.splitext(input_path)[0] + '.json'
            
            # Create output directory if needed
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Convert based on input format
            if ext in ('.csv'):
                with open(input_path, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.DictReader(f)
                    data = list(reader)
                    
            elif ext in ('.yaml', '.yml'):
                with open(input_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    
            else:
                return {
                    'success': False,
                    'error': f"Unsupported input format: {ext}"
                }
                
            # Write JSON output
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            tool_report_print("Converted ✅:", f"{os.path.basename(input_path)} to JSON")
            return {
                'success': True,
                'input_format': ext.lstrip('.'),
                'output_format': 'json',
                'input_path': input_path,
                'output_path': output_path
            }
                
        except Exception as e:
            tool_report_print("Error converting to JSON:", str(e), is_error=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def convert_from_json(input_path: str, output_format: str, output_path: str = None) -> Dict:
        """
        Convert JSON to other formats.

        Args:
            input_path: Path to input JSON file
            output_format: Target format ('csv', 'yaml')
            output_path: Path to output file (optional)

        Returns:
            Dict with conversion results
        """
        tool_message_print("convert_from_json", [
            ("input_path", input_path), 
            ("output_format", output_format),
            ("output_path", output_path or "auto-generated")
        ])
        tool_message_print("convert_from_json", [], is_output=True)
        
        try:
            # Set default output path if not provided
            if not output_path:
                output_path = os.path.splitext(input_path)[0] + '.' + output_format.lower()
            
            # Create output directory if needed
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Read input JSON
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Convert to target format
            if output_format.lower() == 'csv':
                if not isinstance(data, list) or not data or not isinstance(data[0], dict):
                    return {
                        'success': False,
                        'error': "JSON data must be a list of objects for CSV conversion"
                    }
                    
                with open(output_path, 'w', encoding='utf-8', newline='') as f:
                    fieldnames = data[0].keys()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(data)
                    
            elif output_format.lower() in ('yaml', 'yml'):
                with open(output_path, 'w', encoding='utf-8') as f:
                    yaml.safe_dump(data, f)
                    
            else:
                return {
                    'success': False,
                    'error': f"Unsupported output format: {output_format}"
                }
                
            tool_report_print("Converted ✅:", f"JSON to {output_format}")
            return {
                'success': True,
                'input_format': 'json',
                'output_format': output_format.lower(),
                'input_path': input_path,
                'output_path': output_path
            }
                
        except Exception as e:
            tool_report_print("Error converting from JSON:", str(e), is_error=True)
            return {
                'success': False,
                'error': str(e)
            }

# Create a unified interface for all file system operations
class FileSys:
    """Unified interface for all file system operations."""
    
    # File system information
    navigator = FileSystemNavigator()
    
    # File content operations
    reader = FileReader()
    writer = FileWriter()
    
    # File management
    manager = FileManager()
    
    # Search and find
    searcher = FileSearcher()
    
    # Archive operations
    archiver = FileArchiver()
    
    # Format conversion
    converter = FileConverter()