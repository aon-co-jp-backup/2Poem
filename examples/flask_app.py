from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def index():
    return jsonify({"ok": True})


@app.route("/items/<int:item_id>", methods=["GET", "DELETE"])
def item(item_id):
    return jsonify({"id": item_id})


@app.post("/users/<name>/files/<path:rest>")
def upload(name, rest):
    return "saved"
