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
    PR,
    ReadFile,
    TsMorph
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
        self.inputs["file_path"] = abs_path + "/index.tsx"
        index_file_content = ReadFile(self.inputs).run()["file_content"]
        self.inputs["prompt_value"] = {}
        prompt = f"""You are an AI assistant designed to parse JavaScript/TypeScript export statements and generate a JSON output. Your task is to analyze the contents of a file containing export statements and create a structured JSON representation of the exported types and their file paths.

Input:
1. A `base_path` string that represents the root directory for the file paths.
2. The contents of a file containing export statements.

Your task is to:
1. Parse each export statement in the file.
2. Extract the names of the exported types and the file paths they are exported from.
3. Combine the `base_path` with the relative path in the export statement to create the full file path.
4. Generate a JSON output with an "exported_types" array containing objects with "name" and "file_path" properties for each exported type.

Rules for parsing:
1. For named exports like `export {{ A, B }} from "./path/to/file"`, create an entry for each exported name.
2. For default exports like `export {{ default as Name }} from "./path/to/file"`, create an entry for the renamed default export.
3. For star exports like `export * from './lib/stack-app'`, do not create any entries (as we can't determine specific type names).
4. For direct exports like `export {{ Name }}` without a `from` clause, skip the entry (as we don't have path information).
5. Assume all files are TypeScript (.tsx) unless explicitly stated otherwise in the path.

Output format:
{{
  "exported_types": [
    {{
      "name": "ExportedTypeName",
      "file_path": "full/path/to/file.tsx"
    }}
  ]
}}

IMPORTANT: Your response must be ONLY the JSON object in the exact format shown above. Do not include any explanations, comments, or additional text. The JSON should be valid and parseable.

Example input:
base_path: "/src/components"
File contents:
```
export {{ default as StackProvider }} from "./providers/stack-provider";
export {{ useUser, useStackApp }} from "./lib/hooks";
export * from './lib/stack-app';
export {{ SignIn }} from "./components-page/sign-in";
```

Example output:
{{
  "exported_types": [
    {{
      "name": "StackProvider",
      "file_path": "/src/components/providers/stack-provider.tsx"
    }},
    {{
      "name": "useUser",
      "file_path": "/src/components/lib/hooks.tsx"
    }},
    {{
      "name": "useStackApp",
      "file_path": "/src/components/lib/hooks.tsx"
    }},
    {{
      "name": "SignIn",
      "file_path": "/src/components/components-page/sign-in.tsx"
    }}
  ]
}}

Now, parse the following file and generate the JSON output:

base_path: {abs_path}
file_content:
{index_file_content}
"""
        self.inputs["prompt_user"] = prompt
        response = SimplifiedLLMOnce(self.inputs).run()["extracted_response"]
        exported_types = response["exported_types"]

        for exported_type in exported_types:
            self.inputs["file_path"] = exported_type["file_path"]
            name = exported_type["name"]
            self.inputs["variable_name"] = name
            # print(type_information)
            # exit(0)
            content = ReadFile(self.inputs).run()["file_content"]
            if content == "":
                self.inputs["file_path"] = self.inputs["file_path"][:-1]
                content = ReadFile(self.inputs).run()["file_content"]
            type_information = TsMorph(self.inputs).run()["type_information"]
            self.inputs["prompt_user"] = f"""# Task: Extract Specific Named Exported Code Element

You are a precise code analyzer. Your task is to examine the provided code snippet and extract a specific named exported component, class, or method as a complete code snippet. Follow these steps:

1. Analyze the code to find the exported component, class, or method that matches the provided name.
2. Create a JSON object with an "export" key containing a string with the full code of the matched exported element.

## Output Format

Provide your response in the following JSON format only:

{{
  "export": 
    "string (full code snippet of the matched export)"  
}}

## Rules

1. Only include the explicitly exported component, class, or method that matches the provided name.
2. The export must be fully defined within the file.
3. Do not include re-exports or exports of items defined in other files.
4. For languages without explicit exports (e.g., Python), assume all top-level component, class, and method definitions are exported, but still only include the one matching the provided name.
5. Do not include internal or private members unless they are part of the exported element's implementation.
6. If no matching export is found, return an empty array for the "export" key.
7. Do not include any explanations or notes outside the JSON object.
8. Include the entire implementation of the matched export, not just the signature or declaration.
9. Preserve all whitespace, comments, and formatting within the exported element.
10. Do not include the language name or any other metadata.
11. Do not include exported types, interfaces, or type aliases, even if they match the name.
12. For React components, include both function components and class components if they match the name.
13. Only include functions or components that are explicitly exported (e.g., have "export" keyword in TypeScript/JavaScript) and match the provided name.

## Examples

### Example 1: TypeScript with multiple exports, looking for "UserComponent"

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

If the provided name is "UserComponent", your output should be:

{{
  "export": "export const UserComponent: React.FC<{{ user: User }}> = ({{ user }}) => {{\\n  return <div>{{user.greet()}}</div>;\\n}};"
}}

### Example 2: TypeScript with multiple exports, looking for "ProcessUser"

```typescript
export {{ User }} from './user';
export * from './constants';

export interface UserInterface {{
  id: number;
  name: string;
}}

export function ProcessUser(user: User) {{
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

If the provided name is "ProcessUser", your output should be:

{{
  "export": "export function ProcessUser(user: User) {{\\n  console.log(user.name);\\n}}"
}}

Now, analyze the following code snippet and provide the output in the specified JSON format, extracting only the export that matches the provided name:

Name to extract: {name}

Code content:
{content}
"""               
#                         response = SimplifiedLLMOnce(self.inputs).run()["extracted_response"]
#                         exports = response["exports"]
#                         # print(exports)
#                         # exit()
#                         self.inputs["prompt_user"] = f"""# Task: Filter Explicit Exports

# You are a precise code filter. Your task is to examine the provided list of exported code elements and filter out any that do not explicitly begin with the word "export". Follow these steps:

# 1. Parse the input JSON object containing the "exports" array.
# 2. For each item in the "exports" array, check if it starts with the word "export" (ignoring leading whitespace).
# 3. Create a new JSON object with an "filteredExports" key containing an array of only the items that pass this check.

# ## Input Format

# The input will be in the following JSON format:

# ```json
# {{
#   "exports": [
#     "string (full code snippet)",
#     "string (full code snippet)"
#   ]
# }}
# ```

# ## Output Format

# Provide your response in the following JSON format only:


# {{
#   "filteredExports": [
#     "string (full code snippet)",
#     "string (full code snippet)"
#   ]
# }}


# ## Rules

# 1. Only include items that explicitly begin with the word "export".
# 2. Ignore leading whitespace when checking for the "export" keyword.
# 3. Preserve the entire code snippet for items that pass the filter.
# 4. If no items pass the filter, return an empty array for the "filteredExports" key.
# 5. Do not include any explanations or notes outside the JSON object.
# 6. Preserve all whitespace, comments, and formatting within each exported element.

# ## Examples

# ### Example 1: Mixed exports

# Input:
# ```json
# {{
#   "exports": [
#     "export function hello() {{\\n  console.log('Hello');\\n}}",
#     "function notExported() {{\\n  console.log('Not exported');\\n}}",
#     "export const greeting = 'Hello, world!';",
#     "class InternalClass {{\\n  constructor() {{}}\\n}}"
#   ]
# }}
# ```

# Output:

# {{
#   "filteredExports": [
#     "export function hello() {{\\n  console.log('Hello');\\n}}",
#     "export const greeting = 'Hello, world!';"
#   ]
# }}


# ### Example 2: No explicit exports

# Input:
# ```json
# {{
#   "exports": [
#     "function notExported1() {{\\n  console.log('Not exported 1');\\n}}",
#     "const notExported2 = () => {{\\n  console.log('Not exported 2');\\n}}",
#     "class NotExportedClass {{\\n  constructor() {{}}\\n}}"
#   ]
# }}
# ```

# Output:

# {{
#   "filteredExports": []
# }}


# Now, analyze the following JSON object containing exports and provide the output in the specified JSON format, including only explicitly exported items:

# {exports}
# """
            export = SimplifiedLLMOnce(self.inputs).run()['extracted_response']
            # for export in exports["exports"]:
            self.inputs["prompt_user"] = f"""# Task: Generate Concise MDX Documentation for @stackframe/stack SDK Exports

You are a technical writer. Create concise MDX documentation for a given exported type or method from the @stackframe/stack SDK, focusing solely on its interface and usage. Follow these steps:

1. Analyze the provided code snippet and type information, noting parameter types and optionality.
2. Generate brief MDX documentation explaining how to use the exported type or method.
3. Use consistent and simple language throughout.
4. Determine the appropriate file name based on the export name.
5. Create a JSON object with the file path, line numbers, and documentation content as new_code.

## Input Variables

- {{code_snippet}}: The full code of the exported type or method
- {{sdk_docs_folder}}: The base path for the documentation files
- {{type_information}}: Detailed type information obtained from tsx-morph analysis

## Output Format

Provide your response in the following JSON format only:

{{
  "file_path": "string",
  "start_line": number,
  "end_line": number,
  "new_code": "string"
}}

## Rules

1. Use kebab-case for the file name with an .mdx suffix.
2. Construct file_path by joining sdk_docs_folder and the file name.
3. Include the full MDX content in the new_code, including frontmatter.
4. Use simple language. Avoid buzzwords and complex terms.
5. Focus only on interface information: brief description, parameters, and a basic usage example.
6. Omit implementation details.
7. Document all parameters and types accurately, indicating optional parameters.
8. If the function outputs a tsx component, ignore the top level `props` argument, and instead describe the component's props in a "Props" heading.
9. Use 0 for start_line, and total lines minus 1 for end_line (zero-based indexing).
10. Always import from "@stackframe/stack" in examples.
11. Use single quotes in documentation and examples.
12. Use ```tsx for all code blocks.
13. Carefully identify and document optional parameters.
14. Show usage with and without optional parameters when applicable.
15. Do not include any additional paragraphs or sections after the example.
16. Utilize the type_information to provide accurate and detailed type descriptions.

## MDX Content Structure

1. Frontmatter with title (camelCase name of the export)
2. # Heading (export name)
3. Brief description (1-2 sentences max)
4. ## Parameters (if applicable)
5. ## Props (if applicable)
6. ## Example
7. End the documentation after the example. Do not add any concluding paragraphs or notes.

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

{{type_information}} = ```
{{
  "kind": "FunctionDeclaration",
  "name": "calculateTotalPrice",
  "parameters": [
    {{
      "name": "items",
      "type": "Item[]",
      "isOptional": false
    }},
    {{
      "name": "discountCode",
      "type": "string",
      "isOptional": true
    }}
  ],
  "returnType": "number"
}}
```

Your output should be:

{{
  "file_path": "/docs/sdk/calculate-total-price.mdx",
  "start_line": 0,
  "end_line": 22,
  "new_code": "---\\ntitle: calculateTotalPrice\\n---\\n\\n# calculateTotalPrice\\n\\nCalculates the total price of items, with an optional discount. Returns a number representing the total price.\\n\\n## Parameters\\n\\n- `items`: `Item[]` - An array of items to calculate the total price for. Each item must have a `price` property.\\n- `discountCode` (optional): `string` - A code to apply a 10% discount to the total price.\\n\\n## Example\\n\\n```tsx\\nimport {{ calculateTotalPrice }} from '@stackframe/stack';\\n\\nconst items = [\\n  {{ price: 10 }},\\n  {{ price: 20 }},\\n  {{ price: 30 }}\\n];\\n\\n// Without discount\\nconst total = calculateTotalPrice(items);\\n\\n// With discount\\nconst discountedTotal = calculateTotalPrice(items, 'DISCOUNT10');\\n```"
}}

Now, generate the MDX documentation for the following exported code snippet:

{export}

Base path for the documentation:

{sdk_path}

Type information:

{type_information}
"""
            output = SimplifiedLLMOnce(self.inputs).run()["extracted_response"]
            self.inputs.update(output) 
            modified_code_files = ModifyCodePB(self.inputs).run()
            all_docs.append(modified_code_files)
            # break

        self.inputs["modified_code_files"] = all_docs
        number = len(self.inputs["modified_code_files"])
        self.inputs["pr_title"] = "Patchwork PR for Updating SDK Docs with Claude"
        self.inputs["pr_header"] = f"This pull request from patchwork updates {number} SDK Docs"
        outputs = PR(self.inputs).run()

        return outputs
