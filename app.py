from flask import Flask, render_template, request, jsonify
from translator import translate, parse_to_ast, generate_tac
import io
import sys

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/run", methods=["POST"])
def run_code():
    hinglish_code = request.json["code"]

    # RDP: Hinglish → AST → Python
    try:
        python_code = translate(hinglish_code)
    except Exception as e:
        python_code = f"# Translation error: {e}"

    # also send the full AST for the parse-tree panel
    ast_result = parse_to_ast(hinglish_code)

    # 3AC intermediate representation
    tac_result = generate_tac(hinglish_code)

    output = ""
    try:
        old_stdout = sys.stdout
        sys.stdout = mystdout = io.StringIO()
        exec(python_code, {"__builtins__": __builtins__})
        sys.stdout = old_stdout
        output = mystdout.getvalue()
    except Exception as e:
        sys.stdout = old_stdout
        output = str(e)

    return jsonify({
        "python":    python_code,
        "output":    output,
        "ast":       ast_result.get("ast"),
        "ast_error": ast_result.get("error"),
        "tac":       tac_result.get("instructions"),
        "tac_error": tac_result.get("error"),
    })


if __name__ == "__main__":
    app.run(debug=True)