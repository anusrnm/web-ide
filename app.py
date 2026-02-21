import os
import shutil
from flask import Flask, render_template, request, jsonify
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def normalize_client_path(path):
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Path must be a non-empty string")

    normalized = path.replace("\\", "/").strip().lstrip("/")
    normalized = os.path.normpath(normalized).replace("\\", "/")

    if normalized in ("", "."):
        raise ValueError("Invalid path")

    return normalized

def safe_path(path):
    rel_path = normalize_client_path(path)
    full = os.path.abspath(os.path.join(BASE_DIR, rel_path))

    try:
        common = os.path.commonpath([BASE_DIR, full])
    except ValueError as exc:
        raise ValueError("Invalid path") from exc

    if common != BASE_DIR:
        raise ValueError("Invalid path")

    return full

def get_json_payload():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object payload")
    return payload

def require_string(payload, key):
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{key}' is required")
    return value

def build_tree(root):
    tree = []
    for item in sorted(os.listdir(root)):
        path = os.path.join(root, item)
        rel = os.path.relpath(path, BASE_DIR).replace("\\", "/")

        if os.path.isdir(path):
            tree.append({
                "type": "folder",
                "name": item,
                "path": rel,
                "children": build_tree(path)
            })
        else:
            tree.append({
                "type": "file",
                "name": item,
                "path": rel
            })
    return tree

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/tree")
def tree():
    return jsonify(build_tree(BASE_DIR))

@app.route("/open", methods=["POST"])
def open_file():
    payload = get_json_payload()
    path = safe_path(require_string(payload, "path"))

    if not os.path.isfile(path):
        raise FileNotFoundError("File not found")

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return jsonify({"content": f.read()})

@app.route("/save", methods=["POST"])
def save_file():
    payload = get_json_payload()
    path = safe_path(require_string(payload, "path"))
    content = payload.get("content")

    if not isinstance(content, str):
        raise ValueError("'content' must be a string")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return jsonify({"status": "saved"})

@app.route("/create", methods=["POST"])
def create():
    payload = get_json_payload()
    path = safe_path(require_string(payload, "path"))
    type_ = require_string(payload, "type")

    if type_ not in {"file", "folder"}:
        raise ValueError("'type' must be 'file' or 'folder'")

    if type_ == "file":
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w", encoding="utf-8").close()
    else:
        os.makedirs(path, exist_ok=True)

    return jsonify({"status": "created"})

@app.route("/rename", methods=["POST"])
def rename():
    payload = get_json_payload()
    old = safe_path(require_string(payload, "old"))
    new = safe_path(require_string(payload, "new"))

    if not os.path.exists(old):
        raise FileNotFoundError("Source path not found")

    os.makedirs(os.path.dirname(new), exist_ok=True)
    os.rename(old, new)
    return jsonify({"status": "renamed"})

@app.route("/delete", methods=["POST"])
def delete():
    payload = get_json_payload()
    path = safe_path(require_string(payload, "path"))

    if not os.path.exists(path):
        raise FileNotFoundError("Path not found")

    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)
    return jsonify({"status": "deleted"})

@app.errorhandler(ValueError)
def handle_value_error(error):
    return jsonify({"error": str(error)}), 400

@app.errorhandler(FileNotFoundError)
def handle_not_found_error(error):
    return jsonify({"error": str(error)}), 404

@app.errorhandler(Exception)
def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return error
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    debug_enabled = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=debug_enabled,
    )

