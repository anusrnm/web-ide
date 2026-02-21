import os
import shutil
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

BASE_DIR = os.path.abspath(".")

def safe_path(path):
    full = os.path.abspath(os.path.join(BASE_DIR, path))
    if not full.startswith(BASE_DIR):
        raise Exception("Invalid path")
    return full

def build_tree(root):
    tree = []
    for item in sorted(os.listdir(root)):
        path = os.path.join(root, item)
        rel = os.path.relpath(path, BASE_DIR)

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
    path = safe_path(request.json["path"])
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return jsonify({"content": f.read()})

@app.route("/save", methods=["POST"])
def save_file():
    path = safe_path(request.json["path"])
    with open(path, "w", encoding="utf-8") as f:
        f.write(request.json["content"])
    return jsonify({"status": "saved"})

@app.route("/create", methods=["POST"])
def create():
    path = safe_path(request.json["path"])
    type_ = request.json["type"]

    if type_ == "file":
        open(path, "w").close()
    else:
        os.makedirs(path, exist_ok=True)

    return jsonify({"status": "created"})

@app.route("/rename", methods=["POST"])
def rename():
    old = safe_path(request.json["old"])
    new = safe_path(request.json["new"])
    os.rename(old, new)
    return jsonify({"status": "renamed"})

@app.route("/delete", methods=["POST"])
def delete():
    path = safe_path(request.json["path"])
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)
    return jsonify({"status": "deleted"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

