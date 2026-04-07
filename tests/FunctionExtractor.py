import ast
from typing import List

class FunctionExtractor:

    def __init__(self, submission_path: str):
        self.submission_path = submission_path
    
    # Get a function from student submission without executing top-level code
    def get_all_functions(self):
        with open(self.submission_path) as f:
            raw = f.read()
            tree = ast.parse(raw)

            allowed_nodes = (
            ast.FunctionDef,
                # ast.Assign,
                # ast.AnnAssign,
                # ast.AugAssign,
                ast.Import,        # <-- added
                ast.ImportFrom,    # <-- added
            )

            extracted_nodes = [n for n in tree.body if isinstance(n, allowed_nodes)]
            module = ast.Module(body=extracted_nodes, type_ignores=[])

            compiled = compile(module, filename="<ast>", mode="exec")
            global_ns = {}
            exec(compiled, global_ns)
            

            return {name: global_ns[name] for name in global_ns if callable(global_ns[name])}
        



        # with open(self.submission_path) as f:
        #     raw_code = f.read()
        # tree = ast.parse(raw_code)
        # # Find the function definition
        # for node in tree.body:
        
        #     if isinstance(node, ast.FunctionDef) and node.name == func_name:
        #         try:
        #             func_code = ast.Module(body=[node], type_ignores=[])
        #         except TypeError:
        #             func_code = ast.Module([node])
        #         compiled = compile(func_code, filename="<ast>", mode="exec")
        #         local_ns = {}
        #         exec(compiled, {}, local_ns)
        #         return local_ns[func_name]
        # raise AttributeError(f"No {func_name}() function found.")