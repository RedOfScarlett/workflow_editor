import os
import sys
import json
import traceback

def before_node_execution():
    pass

def interrupt_processing(value=True):
    pass

MAX_RESOLUTION=8192

NODE_CLASS_MAPPINGS = {
}

NODE_DISPLAY_NAME_MAPPINGS = {
}

EXTENSION_WEB_DIRS = {}

class Node_Attribute:
    def __init__(self, name, type, description):
        self.name = name
        self.type = type
        self.description = description

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

def node_constructor(self, inputs_nick_names):
    self.input_nick_names = inputs_nick_names

def create_node_class(node_class, node_info):
    node = type(node_class, (object,), {
        "__init__": node_constructor,
        "required_inputs": [Node_Attribute(name, info['type'], info['description']) for name, info in node_info["inputs"]["required"].items()],
        "optional_inputs": [Node_Attribute(name, info['type'], info['description']) for name, info in node_info["inputs"]["optional"].items()],
        "required_attributes": [Node_Attribute(name, info['type'], info['description']) for name, info in node_info["attributes"]["required"].items()],
        "optional_attributes": [Node_Attribute(name, info['type'], info['description']) for name, info in node_info["attributes"]["optional"].items()],
        "outputs": [Node_Attribute(name, info['type'], info['description']) for name, info in node_info["outputs"].items()],
        "category": node_info["category"]
    })
    return node

def load_node(node_class, node_info):
    try:
        NODE_CLASS_MAPPINGS[node_class] = create_node_class(node_class, node_info)
        NODE_DISPLAY_NAME_MAPPINGS[node_class] = node_class
    except Exception as e:
        print(traceback.format_exc())
        print(f"Cannot import module for custom nodes:", e)
        return False

def init_custom_nodes():
    test_nodes = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_nodes")
    with open(os.path.join(test_nodes, "local_nodes.json"), "r") as f:
        local_nodes = json.loads(f.read())
        for node_class, node_info in local_nodes.items():
            load_node(node_class, node_info)
