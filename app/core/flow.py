
from core.backend import ApiBackend
import logging
import json
import asyncio
import time
import threading
from datetime import datetime


class Flow():
    def __init__(self):
        self.flow_json = None
        self.devices = {}
        self.api = ApiBackend()
        self.md5 = ""
        self.creation_date = None
        self.id = None
        self.name = None
        self.flow_table = []

    


    class FlowNode():
        def __init__(self, node_id, node_type, node_name, node_data, node_function=None):
            self.node_id: int = node_id
            self.node_type = node_type
            self.node_name = node_name
            self.inputs = []
            self.outputs = []
            self.device = None
            self.node_data = node_data
            self.is_root = False
            self.is_leaf = False
            self.function = node_function

        def run(self):
            logging.info("Running node: " + self.node_name)
            self.function()

        

    class Vertex():
        def __init__(self, parent, output_nr, child, input_nr):
            self.parent = parent
            self.output_nr = output_nr
            self.child = child
            self.input_nr = input_nr
            self.vertex_data = None


    def print_flow(self) -> None:
        logging.info("Current flow:")
        logging.info("  ID: " + self.id)
        logging.info("  Name: " + self.name)
        logging.info("  Creation Date: " + self.creation_date)
        logging.info("  Hash: " + self.md5)
        logging.info("  Flow:")
        for node in self.flow_table:
            logging.info("  Node:")
            logging.info("    Node ID: " + str(node.node_id))
            logging.info("    Node Type: " + node.node_type)
            logging.info("    Node Name: " + node.node_name)
            logging.info("    Device: " + str(node.device))
            logging.info("    Data: " + str(node.node_data))
            logging.info("    Inputs:")
            for vertex in node.inputs:
                logging.info("      Parent: " + str(vertex.parent) + " Output: " + str(vertex.output_nr))
            logging.info("    Outputs:")
            for vertex in node.outputs:
                logging.info("      Child: " + str(vertex.child) + " Input: " + str(vertex.input_nr))


    def set_flow(self, flow_json) -> bool:
        logging.info("Setting flow")
        logging.info(flow_json)
        # if not flow_json:
        #     logging.error("Flow is empty, skipping update")
        #     return False
        # if flow_json.get('md5_out') == self.md5:
        #     logging.debug("Flow is the same, skipping update")
        #     return False
        # self.flow_json = flow_json.get('flow')
        # self.md5 = flow_json.get('md5_out')
        # self.creation_date = flow_json.get('creation_date')
        # self.id = flow_json.get('id')
        # self.name = flow_json.get('name')
        # self.parse_flow()
        # logging.info("Flow updated")
        # self.print_flow()
        return True

    def parse_flow(self) -> None:
        if not self.flow_json:
            logging.error("Flow JSON is empty")
            return
        self.flow_table = []

        for _, node_data in self.flow_json.items():
            node_id = node_data.get('id', -1)
            node_type = node_data.get('data', {}).get('type', 'undefined')
            node_name = node_data.get('data', {}).get('node', 'undefined')

            flow_node = self.FlowNode(int(node_id), node_type, node_name, node_data.get('data', {}))

            for input_name, input_data in node_data.get('inputs', {}).items():
                for connection in input_data.get('connections', []):
                    if not connection:
                        continue
                    parent_node_id = int(connection.get('node'))
                    parent_output_nr = connection.get('input')
                    vertex = self.Vertex(parent_node_id, parent_output_nr, node_id, input_name)
                    flow_node.inputs.append(vertex)

            for output_name, output_data in node_data.get('outputs', {}).items():
                for connection in output_data.get('connections', []):
                    if not connection:
                        continue
                    child_node_id = int(connection.get('node'))
                    child_input_nr = connection.get('output')
                    vertex = self.Vertex(node_id, output_name, child_node_id, child_input_nr)
                    flow_node.outputs.append(vertex)

            if len(flow_node.inputs) == 0:
                flow_node.is_root = True

            if len(flow_node.outputs) == 0:
                flow_node.is_leaf = True

            self.flow_table.append(flow_node)


    def execute_node(self, node) -> None:
        if not node:
            logging.error("Node is None, skipping execution")
            return
        node.function()
        for vertex in node.outputs:
            child_node = self.get_node_by_id(vertex.child)
            self.execute_node(child_node)
        
    
    def get_node_by_id(self, node_id) -> FlowNode:
        for node in self.flow_table:
            if node.node_id == node_id:
                return node
        return None


    def execute_flow(self) -> None:
        for node in self.flow_table:
            if node.is_root:
                self.execute_node(node)
        print("Flow executed")
        return


    # standard_functions = {
    #     "loop_event": self.loop_event,
    #     "clock_event": self.clock_event,
    #     "date_event": self.date_event,
    #     "sun_rise_event": self.sun_rise_event,
    #     "sun_set_event": self.sun_set_event,
    #     "the_day_is_between": self.the_day_is_between,
    #     "the_time_is_between": self.the_time_is_between,
    #     "the_day_is": self.the_day_is,
    #     "delay": self.delay,
    #     "and": self.and_operator,
    #     "or": self.or_operator,
    #     "not": self.not_operator,
    #     "message": self.message
    # }


    # def loop_event(self, unit: str, value: int) -> None:
     

    #     def timer_function():
    #         if unit == "seconds":
    #             time.sleep(value)
    #         else if unit == "minutes":
    #             time.sleep(value * 60)
    #         else if unit == "hours":
    #             time.sleep(value * 3600)
    #         else if unit == "days":
    #             time.sleep(value * 86400)
    #         else if unit == "months":
    #             time.sleep(value * 2592000)
    #         else:
    #             raise ValueError(f"Unsupported time unit: {unit}")

    #     threading.Thread(target=timer_function).start()
        