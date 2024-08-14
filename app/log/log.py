import logging
import os
import datetime
import time

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
