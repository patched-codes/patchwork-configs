import yaml
import os
import fnmatch
import json

from pathlib import Path
from patchwork.logger import logger
from patchwork.step import Step
from patchwork.steps import (
    SimplifiedLLMOnce,
    ModifyCodePB,
    PR
)

_DEFAULT_INPUT_FILE = Path(__file__).parent / "config.yml"

class UpdateSDKDocs(Step):
    def __init__(self, inputs: dict):
        final_inputs = yaml.safe_load(_DEFAULT_INPUT_FILE.read_text())
                    
        if final_inputs is None:
            final_inputs = {}
        final_inputs.update(inputs)
        
        self.inputs = final_inputs

    def run(self) -> dict:
        # Get the absolute path of the folder
        abs_path = os.path.abspath(self.inputs["sdk_src_folder"])
        sdk_path = os.path.abspath(self.inputs["sdk_docs_folder"])
        responses = {}
        all_docs = []
        # Check if the folder exists
        if not os.path.exists(abs_path):
            print(f"The folder '{self.inputs["sdk_src_folder"]}' does not exist.")
            return
        
        # Convert the file pattern string to a list
        file_patterns = [pattern.strip() for pattern in self.inputs["filter"].split(',')]
        
        # Walk through the directory tree
        for root, dirs, files in os.walk(abs_path):
            for filename in files:
                if any(fnmatch.fnmatch(filename, pattern) for pattern in file_patterns):
                    file_path = os.path.join(root, filename)
                    logger.debug(f"Processing file: {file_path}")
                    with open(file_path, 'r') as file:
                        content = file.read()
                        self.inputs["prompt_value"] = {}
                        self.inputs["prompt_user"] = f"""# Task: Extract Full Exported Code Elements (Components, Classes, and Methods)

You are a precise code analyzer. Your task is to examine the provided code snippet and extract all fully defined exported components, classes, and methods as a list of complete code snippets. Follow these steps:

1. Analyze the code to find all exported components, classes, and methods that are fully defined within the file.
2. Create a JSON object with an "exports" key containing an array of the full code of each exported element.

## Output Format

Provide your response in the following JSON format only:

```json
{{
  "exports": [
    "string (full code snippet)",
    "string (full code snippet)"
  ]
}}
```

## Rules

1. Only include explicitly exported components, classes, and methods that are fully defined within the file.
2. Do not include re-exports or exports of items defined in other files.
3. For languages without explicit exports (e.g., Python), assume all top-level component, class, and method definitions are exported, but still only include fully defined items.
4. Do not include internal or private members unless they are part of the exported element's implementation.
5. If no exports are found, return an empty array for the "exports" key.
6. Do not include any explanations or notes outside the JSON object.
7. For each export, include the entire implementation, not just the signature or declaration.
8. Preserve all whitespace, comments, and formatting within each exported element.
9. Do not include the language name or any other metadata.
10. Do not include exported types, interfaces, or type aliases.
11. For React components, include both function components and class components.
12. Only include functions or components that are explicitly exported (e.g., have "export" keyword in TypeScript/JavaScript).

## Examples

### Example 1: TypeScript with fully defined exports

```typescript
export class User {{
  constructor(public name: string) {{}}

  greet(): string {{
    return `Hello, ${{this.name}}!`;
  }}
}}

export function createUser(name: string): User {{
  return new User(name);
}}

export const UserComponent: React.FC<{{ user: User }}> = ({{ user }}) => {{
  return <div>{{user.greet()}}</div>;
}};

export type UserType = {{
  id: number;
  name: string;
}};
```

Your output should be:

```json
{{
  "exports": [
    "export class User {{\\n  constructor(public name: string) {{}}\\n\\n  greet(): string {{\\n    return `Hello, ${{this.name}}!`;\\n  }}\\n}}",
    "export function createUser(name: string): User {{\\n  return new User(name);\\n}}",
    "export const UserComponent: React.FC<{{ user: User }}> = ({{ user }}) => {{\\n  return <div>{{user.greet()}}</div>;\\n}};"
  ]
}}
```

### Example 2: TypeScript with re-exports, types, and non-exported functions

```typescript
export {{ User }} from './user';
export * from './constants';

export interface UserInterface {{
  id: number;
  name: string;
}}

export function processUser(user: User) {{
  console.log(user.name);
}}

function helperFunction(data: any) {{
  // This function is not exported
  return data.toString();
}}

export class UserManager {{
  private users: User[] = [];

  addUser(user: User) {{
    this.users.push(user);
  }}
}}

const InternalComponent = () => {{
  // This component is not exported
  return <div>Internal</div>;
}};
```

Your output should be:

```json
{{
  "exports": [
    "export function processUser(user: User) {{\\n  console.log(user.name);\\n}}",
    "export class UserManager {{\\n  private users: User[] = [];\\n\\n  addUser(user: User) {{\\n    this.users.push(user);\\n  }}\\n}}"
  ]
}}
```

Now, analyze the following code snippet and provide the output in the specified JSON format:

{content}
"""
                        response = SimplifiedLLMOnce(self.inputs).run()["extracted_response"]
                        for export in response["exports"]:
                            self.inputs["prompt_user"] = f"""# Task: Generate Interface-focused MDX Documentation for @stackframe/stack SDK Exports

You are a technical writer. Your task is to create clear and simple MDX documentation for a given exported type or method from the @stackframe/stack SDK, focusing only on its interface and usage. Follow these steps:

1. Analyze the provided code snippet.
2. Generate concise MDX documentation that explains how to use the exported type or method, without any implementation details.
3. Use consistent and simple language throughout the documentation.
4. Determine the appropriate file name based on the export name.
5. Create a JSON object with the file path, line numbers, and documentation content as a patch.

## Input Variables

- {{code_snippet}}: The full code of the exported type or method
- {{sdk_docs_folder}}: The base path for the documentation files

## Output Format

Provide your response in the following JSON format only:

```json
{{
  "file_path": "string",
  "start_line": number,
  "end_line": number,
  "patch": "string"
}}
```

## Rules

1. The file name should be the kebab-case version of the exported type or method name, with an .mdx suffix.
2. The file_path should be constructed by joining the sdk_docs_folder and the file name.
3. The patch should contain the full content of the MDX file, including frontmatter.
4. Use simple and consistent language. Avoid buzzwords and complex terms.
5. Include only interface-related information: brief description, parameters, return value, and a basic usage example.
6. Do not include any implementation details or explain how the function works internally.
7. Ensure all parameters and types are accurately documented.
8. start_line should always be 0, and end_line should be the total number of lines in the generated MDX content minus 1 (zero-based indexing).
9. Do not include any explanations or notes outside the JSON object.
10. Always use "@stackframe/stack" as the import source in examples and explanations.
11. Use single quotes consistently throughout the documentation and examples.
12. Avoid using console.log in examples unless absolutely necessary to demonstrate the function's output.

## MDX Content Guidelines

1. Start with a frontmatter section containing a title (the original camelCase name of the export).
2. Provide a brief, clear description of what the export does, focusing on its purpose, not its implementation.
3. For functions or methods:
   - List parameters with their types and a simple description.
   - Describe the return value and its type within the main description, not as a separate section.
4. For classes or types:
   - List properties with their types and a simple description.
   - Briefly describe any methods, focusing on what they do, not how they do it.
5. Include one basic example of how to use the export, always importing from "@stackframe/stack".
6. Use appropriate MDX and Markdown formatting for headings, code blocks, and lists.
7. Do not include sections for notes, explanations, or conclusions.
8. Do not mention any internal workings, algorithms, or implementation specifics.

## Example

For this input:

{{code_snippet}} = ```
export function calculateTotalPrice(items: Item[], discountCode?: string): number {{
  let total = items.reduce((sum, item) => sum + item.price, 0);
  if (discountCode) {{
    total *= 0.9; // 10% discount
  }}
  return total;
}}
```

{{sdk_docs_folder}} = "/docs/sdk"

Your output should be:

```json
{{
  "file_path": "/docs/sdk/calculate-total-price.mdx",
  "start_line": 0,
  "end_line": 18,
  "patch": "---\\ntitle: calculateTotalPrice\\n---\\n\\n# calculateTotalPrice\\n\\nCalculates the total price of items, with an optional discount. Returns a number representing the total price of all items, with discount applied if a discount code was provided.\\n\\n## Parameters\\n\\n- `items`: `Item[]` - An array of items to calculate the total price for. Each item must have a `price` property.\\n- `discountCode`: `string` (optional) - A code to apply a discount to the total price.\\n\\n## Example\\n\\n```typescript\\nimport {{ calculateTotalPrice }} from '@stackframe/stack';\\n\\nconst items = [\\n  {{ price: 10 }},\\n  {{ price: 20 }},\\n  {{ price: 30 }}\\n];\\n\\nconst total = calculateTotalPrice(items);\\n// total is 60\\n\\nconst discountedTotal = calculateTotalPrice(items, 'DISCOUNT10');\\n// discountedTotal is 54\\n```"
}}
```

Now, generate the MDX documentation for the following exported code snippet:

{export}

Base path for the documentation:

{sdk_path}
"""
                            output = SimplifiedLLMOnce(self.inputs).run()["extracted_response"]
                            self.inputs.update(output) 
                            modified_code_files = ModifyCodePB(self.inputs).run()
                            all_docs.append(modified_code_files)

        self.inputs["modified_code_files"] = all_docs
        number = len(self.inputs["modified_code_files"])
        self.inputs["pr_title"] = "Patchwork PR for Updating SDK Docs"
        self.inputs["pr_header"] = f"This pull request from patchwork updates {number} SDK Docs"
        outputs = PR(self.inputs).run()

        return outputs