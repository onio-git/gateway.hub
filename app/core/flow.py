
from core.backend import ApiBackend
import logging
import json


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
        def __init__(self, node_id, node_type, node_name, node_data):
            self.node_id: int = node_id
            self.node_type = node_type
            self.node_name = node_name
            self.inputs = []
            self.outputs = []
            self.device = None
            self.node_data = node_data
            self.is_root = False
            self.is_leaf = False

        def function(self):
            print("node " + str(self.node_id) + ": " + self.node_name + " executed. Next: " + str([vertex.child for vertex in self.outputs]))

    class Vertex():
        def __init__(self, parent, output_nr, child, input_nr):
            self.parent = parent
            self.output_nr = output_nr
            self.child = child
            self.input_nr = input_nr
            self.vertex_data = None


    def print_flow(self) -> None:
        print("Current flow:")
        print("  ID: " + self.id)
        print("  Name: " + self.name)
        print("  Creation Date: " + self.creation_date)
        print("  Hash: " + self.md5)
        print("  Flow:")
        for node in self.flow_table:
            print("  Node:")
            print("    Node ID: " + str(node.node_id))
            print("    Node Type: " + node.node_type)
            print("    Node Name: " + node.node_name)
            print("    Device: " + str(node.device))
            print("    Data: " + str(node.node_data))
            print("    Inputs:")
            for vertex in node.inputs:
                print("      Parent: " + str(vertex.parent) + " Output: " + str(vertex.output_nr))
            print("    Outputs:")
            for vertex in node.outputs:
                print("      Child: " + str(vertex.child) + " Input: " + str(vertex.input_nr))


    def set_flow(self, flow_json) -> bool:
        if not flow_json:
            logging.error("Flow is empty, skipping update")
            return False
        if flow_json.get('md5_out') == self.md5:
            logging.debug("Flow is the same, skipping update")
            return False
        self.flow_json = flow_json.get('flow')
        self.md5 = flow_json.get('md5_out')
        self.creation_date = flow_json.get('creation_date')
        self.id = flow_json.get('id')
        self.name = flow_json.get('name')
        self.parse_flow()
        logging.info("Flow updated")
        self.print_flow()
        self.execute_flow()
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