# -*- coding: utf-8 -*-
from flask import Flask, jsonify
app = Flask(__name__)

@app.route("/old/<int:n>")
def old(n):
    try:
        print "handling", n
    except Exception, e:
        raise ValueError, "bad"
    return jsonify({"n": n})
