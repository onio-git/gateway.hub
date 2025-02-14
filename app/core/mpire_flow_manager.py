import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed


class FlowManager:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.flow_tasks = {}  # Lưu các flow_id: future

    def update_flows(self, new_flows):
        for flow_dict in new_flows:
            logging.info(f"Updating flow: {flow_dict}")

    def shutdown(self):
        self.executor.shutdown(wait=False)
