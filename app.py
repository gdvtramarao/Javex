import os
import time
import subprocess
from graphviz import Digraph
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="static")

# ---------- Lexical Analysis ----------
def lexical_analysis(code):
    start_time = time.time()
    tokens = code.split()
    token_count = {token: tokens.count(token) for token in set(tokens)}
    invalid_tokens = [
        token for token in tokens
        if not token.isalnum() and token not in ['+', '-', '*', '/', '=', '(', ')', '{', '}', ';']
    ]
    lexical_time = time.time() - start_time
    return token_count, invalid_tokens, lexical_time

# ---------- Syntax Analysis ----------
def syntax_analysis(code):
    start_time = time.time()
    stack = []
    errors = []

    for i, char in enumerate(code):
        if char in "{([":  
            stack.append((char, i))
        elif char in "})]":
            if not stack:
                errors.append(f"Unmatched closing '{char}' at position {i}")
            else:
                last_open, _ = stack.pop()
                if not ((last_open == '(' and char == ')') or
                        (last_open == '{' and char == '}') or
                        (last_open == '[' and char == ']')):
                    errors.append(f"Mismatched '{last_open}' and '{char}' at position {i}")

    if stack:
        for char, pos in stack:
            errors.append(f"Unmatched opening '{char}' at position {pos}")

    if ";" not in code:
        errors.append("Missing semicolon in the code.")

    syntax_time = time.time() - start_time
    return "Incorrect" if errors else "Correct", errors, syntax_time

# ---------- Execute Java Code ----------
def execute_java_code(java_code, file_name="Main"):
    java_file = f"{file_name}.java"
    with open(java_file, "w") as f:
        f.write(java_code)

    try:
        compile_result = subprocess.run(["javac", java_file], capture_output=True, text=True)
        if compile_result.returncode != 0:
            return "Compilation Error", compile_result.stderr

        run_result = subprocess.run(["java", file_name], capture_output=True, text=True)
        if run_result.returncode != 0:
            return "Runtime Error", run_result.stderr

        return "Execution Success", run_result.stdout
    finally:
        if os.path.exists(java_file):
            os.remove(java_file)
        if os.path.exists(f"{file_name}.class"):
            os.remove(f"{file_name}.class")

# ---------- Generate AST ----------
def generate_ast(code):
    ast = {'data': 'Root', 'children': []}
    lines = code.splitlines()
    current_node = ast
    stack = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("public class"):
            class_name = stripped.split(" ")[-1]
            class_node = {'data': f'Class: {class_name}', 'children': []}
            current_node['children'].append(class_node)
            stack.append(current_node)
            current_node = class_node

        elif stripped.startswith("public static void main"):
            main_node = {'data': 'Method: main', 'children': []}
            current_node['children'].append(main_node)
            stack.append(current_node)
            current_node = main_node

        elif "for" in stripped or "while" in stripped:
            loop_node = {'data': 'Loop', 'children': []}
            current_node['children'].append(loop_node)
            stack.append(current_node)
            current_node = loop_node

        elif stripped.startswith(("int", "String", "float", "double")):
            var_name = stripped.split()[1].replace(";", "").replace("=", "")
            var_node = {'data': f'Variable: {var_name}', 'children': []}
            current_node['children'].append(var_node)

        elif stripped.startswith("System.out.println"):
            print_node = {'data': 'Print Statement', 'children': []}
            current_node['children'].append(print_node)

        if stripped.endswith("}") and stack:
            current_node = stack.pop()

    return ast

# ---------- AST to Graphviz ----------
def ast_to_graphviz(ast):
    dot = Digraph(comment='AST')

    def add_node(node, parent=None):
        node_name = f"{node['data']}_{id(node)}"
        dot.node(node_name, node['data'])
        if parent:
            dot.edge(parent, node_name)

        for child in node.get('children', []):
            add_node(child, node_name)

    add_node(ast)
    dot.attr(dpi='300', size='10,10')
    return dot

# ---------- Code Summary + Suggestions ----------
def analyze_code_summary(code):
    summary = []
    suggestions = []

    if "class " in code:
        class_name = code.split("class ")[1].split("{")[0].strip()
        summary.append(f"This code defines a class named '{class_name}'.")

    if "public static void main" in code:
        summary.append("This program contains a main method, which is the entry point of the program.")

    methods = []
    for line in code.splitlines():
        if line.strip().startswith("public") and "(" in line and ")" in line and "class" not in line:
            method_name = line.split("(")[0].split()[-1]
            methods.append(method_name)
    if methods:
        summary.append(f"The program defines the following methods: {', '.join(methods)}.")

    variables = []
    for line in code.splitlines():
        line = line.strip()
        if line.startswith(("int ", "String ", "float ", "double ")):
            var_def = line.split()[1].replace(";", "").replace("=", "")
            variables.append(var_def)
    if variables:
        summary.append(f"The program declares the following variables: {', '.join(variables)}.")

    if "for" in code or "while" in code:
        summary.append("The program uses loops to iterate over data.")
    if "if" in code:
        summary.append("The program uses conditional statements (e.g., 'if' statements) for decision-making.")
    if "System.out.println" in code:
        summary.append("The program contains print statements to display the output.")

    # Suggestions
    if any("for" in line and "{" in line for line in code.splitlines()):
        suggestions.append("Consider refactoring to reduce excessive nesting.")
        suggestions.append("Consider using enhanced for-loop syntax where possible for better readability.")
    if "+" in code and "System.out.println" in code:
        suggestions.append("Avoid using '+' for string concatenation inside loops. Use StringBuilder for better performance.")
    if "try" not in code and "catch" not in code:
        suggestions.append("Add proper exception handling with meaningful error messages.")
    suggestions.append("Consider breaking large methods into smaller, more manageable ones.")

    return summary, suggestions

# ---------- Time Complexity Estimation ----------
def estimate_time_complexity(code):
    loops = code.count("for") + code.count("while")
    if loops == 0:
        return "O(1)"
    elif loops == 1:
        return "O(n)"
    else:
        return f"O(n^{loops}) where {loops} is the number of nested loops"

# ---------- Flask Routes ----------
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/compile_and_run", methods=["POST"])
def compile_and_run():
    data = request.json
    java_code = data.get("code", "")

    # Lexical Analysis
    token_count, invalid_tokens, lexical_time = lexical_analysis(java_code)

    # Syntax Analysis
    syntax_result, syntax_errors, syntax_time = syntax_analysis(java_code)

    # Execution
    if syntax_result == "Correct":
        execution_status, execution_output = execute_java_code(java_code)
    else:
        execution_status, execution_output = "Incorrect Syntax", "\n".join(syntax_errors)

    # AST
    ast = generate_ast(java_code)
    dot = ast_to_graphviz(ast)
    # ✅ Generate unique filename (without .png)
    filename = f"ast_{int(time.time())}"
    filepath = os.path.join("static", filename)
    # ✅ Graphviz will add .png automatically
    dot.render(filepath, format="png", cleanup=True)
    # Later when returning response, make sure:
    # "ast_image": filename + ".png"


    # Summary + Suggestions + Complexity
    summary, suggestions = analyze_code_summary(java_code)
    complexity = estimate_time_complexity(java_code)

    # Render AST and prepare filename
    output_path = dot.render(filepath, format="png", cleanup=True)
    ast_filename = os.path.basename(output_path)   # e.g. "ast_1756712118.png"
    return jsonify({
        "execution_status": execution_status,
        "execution_output": execution_output,
        "lexical": token_count,
        "invalid_tokens": invalid_tokens,
        "lexical_time": round(lexical_time, 4),
        "syntax_result": syntax_result,
        "syntax_errors": syntax_errors,
        "syntax_time": round(syntax_time, 4),
        "time_complexity": complexity,
        "summary": summary,
        "suggestions": suggestions,
        "ast_image": ast_filename
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


