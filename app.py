from flask import Flask, render_template, request, jsonify
from translator import translate, tokenize
import io
import sys

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/run", methods=["POST"])
def run_code():
    hinglish_code = request.json["code"]

    python_code = translate(hinglish_code)
    tokens      = tokenize(hinglish_code)

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
        "python": python_code,
        "output": output,
        "tokens": tokens
    })


if __name__ == "__main__":
    app.run(debug=True)