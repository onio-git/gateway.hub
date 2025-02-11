from flowpipe import Graph, Node
import threading
import importlib


def load_plugin(module_path, function_name):
    """Dynamic plugin loader."""
    module = importlib.import_module(module_path)
    return getattr(module, function_name)


@Node(outputs=["success"])
def EventNode(event_name, node_meta):
    """Trigger an event to start the workflow."""
    print(f"Waiting for event: {event_name} with metadata: {node_meta}")
    plugin_module = node_meta.get("plugin_module")
    plugin_function = node_meta.get("plugin_function")

    if not plugin_module or not plugin_function:
        raise ValueError("Missing plugin_module or plugin_function in metadata")

    # Load plugin and execute
    plugin = load_plugin(plugin_module, plugin_function)
    event_data = plugin(event_name, node_meta)
    print(f"Event triggered: {event_data}")
    return {"success": event_data}


@Node(outputs=["success", "unsuccess", "fail"])
def NodeCondition(event, node_meta):
    """Condition node with three outputs: success, unsuccess, and fail."""
    print(f"Evaluating condition for event: {event} with metadata: {node_meta}")
    try:
        if event and event.get("event_name") == "button_pressed":
            print("Condition met: Success")
            return {"success": event, "unsuccess": None, "fail": None}
        else:
            print("Condition not met: Unsuccess")
            return {"success": None, "unsuccess": event, "fail": None}
    except Exception as e:
        print(f"Error in NodeCondition: {e}")
        return {"success": None, "unsuccess": None, "fail": event}


@Node(outputs=["success", "unsuccess", "fail"])
def ActionNode(previous_data, node_meta):
    """Action node to perform an action."""
    # print(f"Performing action for previous data: {previous_data} with metadata: {node_meta}")
    plugin_module = node_meta.get("plugin_module")
    plugin_function = node_meta.get("plugin_function")

    if not plugin_module or not plugin_function:
        raise ValueError("Missing plugin_module or plugin_function in metadata")

    # Load plugin and execute
    plugin = load_plugin(plugin_module, plugin_function)
    result = plugin(previous_data, node_meta)
    # print(f"Plugin {plugin_module}.{plugin_function} executed with result: {result}")
    return {"success": result}


def convert_drawflow_to_config(drawflow):
    nodes = {}
    connections = []

    for node_id, node_data in drawflow["drawflow"]["Home"]["data"].items():
        node_metadata = node_data.get("metadata", {})
        node_metadata["id"] = node_id

        # Lưu thông tin node
        nodes[node_id] = {
            "type": node_data["type"],
            "name": node_data["name"],
            "metadata": node_metadata
        }

        # Lưu thông tin kết nối
        for output_name, output_data in node_data.get("outputs", {}).items():
            for connection in output_data.get("connections", []):
                connections.append({
                    "source": node_id,
                    "source_output": output_name,
                    "target": connection["node"],
                    "target_input": connection["output"]
                })

    return {"nodes": nodes, "connections": connections}


class ConfigurableWorkflow:
    """Workflow that builds its graph from a JSON configuration."""

    def __init__(self, drawflow_config):
        self.graph = Graph()

        config = convert_drawflow_to_config(drawflow_config)
        self.nodes = {}

        # Create nodes based on config
        for node_id, node_data in config["nodes"].items():
            node_metadata = node_data["metadata"]

            if node_data["type"] == "Event":
                self.nodes[node_id] = EventNode(name=node_data["name"], graph=self.graph, node_meta=node_metadata)
            elif node_data["type"] == "Condition":
                self.nodes[node_id] = NodeCondition(name=node_data["name"], graph=self.graph, node_meta=node_metadata)
            elif node_data["type"] == "Action":
                self.nodes[node_id] = ActionNode(name=node_data["name"], graph=self.graph, node_meta=node_metadata)

        # Connect nodes based on config
        for connection in config["connections"]:
            source_id = connection["source"]
            target_id = connection["target"]
            source_output = connection["source_output"]
            target_input = connection["target_input"]

            print(f"Connecting {source_id}.{source_output} to {target_id}.{target_input}")

            if source_id in self.nodes and target_id in self.nodes:
                self.nodes[source_id].outputs[source_output].connect(self.nodes[target_id].inputs[target_input])
            else:
                print(f"Error: Node {source_id} or {target_id} is not defined in the configuration.")

    def evaluate(self):
        """Evaluate the graph."""
        print("Starting Workflow Execution:")
        self.graph.evaluate()

    def evaluate_loop(self, auto_restart=True, max_iterations=None):
        """Evaluate the graph and restart when finished."""
        iteration = 0
        while auto_restart:
            iteration += 1
            print(f"\n--- Starting Workflow Iteration {iteration} ---")
            self.graph.evaluate()
            print(f"--- Workflow Iteration {iteration} Completed ---")

            # Kiểm tra nếu đạt đến số vòng lặp tối đa
            if max_iterations and iteration >= max_iterations:
                print("Reached maximum iterations. Stopping workflow.")
                break
            time.sleep(1)

    def run_events(self):
        """Run all event nodes in parallel."""
        threads = []
        for node_id, node in self.nodes.items():
            # print(node)
            if "Event" in node.name:  # Chỉ chạy các node Event
                t = threading.Thread(target=node.evaluate)
                print("start")
                t.start()
                threads.append(t)

        for t in threads:
            t.join()  # Chờ tất cả các sự kiện hoàn thành
