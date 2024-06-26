from pathlib import Path

import yaml

from patchwork.step import Step

_DEFAULT_INPUT_FILE = Path(__file__).parent / "config.yml"
_DEFAULT_PROMPT_JSON = Path(__file__).parent / "prompt.json"

class HelloWorld(Step):
    def __init__(self, inputs: dict):
        final_inputs = yaml.safe_load(_DEFAULT_INPUT_FILE.read_text())
                    
        if final_inputs is None:
            final_inputs = {}
        final_inputs.update(inputs)
            
        if "prompt_template_file" not in final_inputs.keys():
            final_inputs["prompt_template_file"] = _DEFAULT_PROMPT_JSON
        
        self.inputs = final_inputs

    def run(self) -> dict:
        print("Hello World!")
        
        return self.inputs
