import logging
import os
import datetime
import time
import json
from typing import List, Optional, Dict, Union
from collections import deque

startup_time = time.time()

class ColoredFormatter(logging.Formatter):
    color_codes = {
        'DEBUG': '\033[94m',     # Blue
        'INFO': '\033[92m',      # Green
        'WARNING': '\033[93m',   # Yellow
        'ERROR': '\033[91m',     # Red
        'CRITICAL': '\033[95m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }

    def format(self, record):
        log_color = self.color_codes.get(record.levelname)
        reset_color = self.color_codes['RESET']
        formatted_message = super().format(record)
        return f"{log_color}{formatted_message}{reset_color}"


def setup_logging(log_level):
    log_levels = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL
    }

    level = log_levels.get(log_level.lower(), logging.INFO)

    # Create logs directory if it doesn't exist
    os.makedirs('log/logs', exist_ok=True)

    # if the number of logs exceeds 10, delete the oldest one
    logs = sorted(os.listdir('log/logs'))
    if len(logs) >= 10:
        os.remove(f'log/logs/{logs[0]}')

    # add datetime to log file name
    log_file = f"log/logs/logs_session_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

    # Configure console logging
    console_formatter = ColoredFormatter('%(asctime)s - %(levelname)s \t- %(message)s', datefmt='%H:%M:%S')
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)

    # Configure file logging
    # time since startup
    delta = datetime.timedelta(seconds=time.time() - startup_time)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s')
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    file_handler.setFormatter(file_formatter)

    # Create logger and add handlers
    logger = logging.getLogger()
    logger.setLevel(level)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)




class CloudLogger:
    MAX_LOG_LINES = 100  # Maximum number of lines to keep
    LOG_FILE = "log/logs/cloud_log.txt"  # Main log file

    def __init__(self, log_file_path: Optional[str] = None):
        """
        Initialize the file-based logger.
        
        Args:
            log_file_path: Optional custom path for the log file
        """
        self.log_file = log_file_path or self.LOG_FILE
        self.count = 0
        
        # Create log file if it doesn't exist
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', encoding='utf-8') as f:
                pass
        else:
            # Count existing lines
            with open(self.log_file, 'r', encoding='utf-8') as f:
                self.count = sum(1 for _ in f)

    def clear_log_buffer(self) -> None:
        """Clear all logs from the file."""
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                pass
            self.count = 0
        except IOError as e:
            self.logger.error(f"Error clearing log file: {e}")

    def add_log_line(self, tag: str, line: str) -> None:
        """
        Add a new log line to the file.
        
        Args:
            tag: The log tag/category
            line: The log message
        """
        try:
            now = datetime.datetime.now()
            
            # Basic time validation
            if now.year < 2016:
                self.logger.error("Time is not set - skipping log line")
                return

            timestamp = now.strftime("[%Y-%m-%d %H:%M:%S]")
            log_line = f"{timestamp} [{tag}] {line}\n"
            
            # Append the new log line
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_line)
            
            self.count += 1
            
            # If we exceed MAX_LOG_LINES, rotate the file
            if self.count > self.MAX_LOG_LINES:
                self._rotate_logs()
                
        except IOError as e:
            self.logger.error(f"Error writing to log file: {e}")

    def _rotate_logs(self) -> None:
        """
        Rotate logs keeping only the most recent MAX_LOG_LINES lines.
        """
        try:
            # Read all lines
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = deque(f, self.MAX_LOG_LINES)
            
            # Write back only the most recent lines
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            self.count = len(lines)
            
        except IOError as e:
            self.logger.error(f"Error rotating logs: {e}")

    def print_log_buffer(self) -> None:
        """Print all logs in the file."""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    print(line.rstrip())
        except IOError as e:
            self.logger.error(f"Error reading log file: {e}")

    def format_logs_to_json(self, as_dict: bool = True) -> Union[Dict, str, None]:
        """
        Format logs as JSON in the API-expected format.
        
        Args:
            as_dict: If True, returns a Python dictionary. If False, returns a JSON string.
            
        Returns:
            Dict or str: The formatted logs, or None if parsing fails
        """
        self.print_log_buffer()
        try:
            logs = []
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        # Extract parts from log line
                        # Format: [YYYY-MM-DD HH:MM:SS] [TAG] MESSAGE
                        if line.startswith('[') and '] [' in line:
                            # Split by '] [' to separate timestamp, tag, and message
                            parts = line.split('] [')
                            if len(parts) >= 2:
                                # Extract timestamp (remove leading '[')
                                timestamp = parts[0][1:]
                                # Split remaining parts and get tag and message
                                tag_message = parts[1].split('] ', 1)
                                if len(tag_message) == 2:
                                    tag = tag_message[0]
                                    message = tag_message[1]
                                    
                                    # Create log entry in expected format
                                    log_entry = {
                                        "tag": tag,
                                        "creation_date": timestamp,
                                        "message": message
                                    }
                                    logs.append(log_entry)
            
            # Create the final structure
            result = {"logs": logs}
            self.clear_log_buffer()
            # Return as dict or JSON string based on as_dict parameter
            return result if as_dict else json.dumps(result)
            
        except Exception as e:
            self.logger.error(f"Error formatting logs to JSON: {e}")
            return None

    def get_logs_for_api(self) -> Dict:
        """
        Get logs in the format ready for API submission.
        Always returns a dictionary (not a string) for API calls.
        """
        return self.format_logs_to_json(as_dict=True)
    

    def get_log_count(self) -> int:
        """Return the current number of logs in the file."""
        return self.count

    def get_recent_logs(self, num_lines: int) -> List[str]:
        """
        Get the most recent log lines.
        
        Args:
            num_lines: Number of recent lines to retrieve
            
        Returns:
            List of the most recent log lines
        """
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                # Use deque with maxlen to efficiently get last n lines
                return list(deque(f, num_lines))
        except IOError as e:
            self.logger.error(f"Error reading recent logs: {e}")
            return []

