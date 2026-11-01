from flask import Flask, request
from html import escape
import os
import subprocess

app = Flask(__name__)

folder = os.path.dirname(os.path.abspath(__file__))
exe = os.path.join(folder, "buspass.exe")
index = os.path.join(folder, "index.html")


# starts the C program with the given arguments and returns its output
def run(*args):
    result = subprocess.run([exe] + list(args), capture_output=True, text=True)
    out = result.stdout + result.stderr
    if out == "":
        out = "No output from program"
    # result page: white box with the output and a Go Back link
    return '<div class="result-area"><pre>' + escape(out) + '</pre><a class="back-link" href="/">Go Back</a></div>'


# shows the page again with the result on top
def page(result):
    html = open(index, encoding="utf-8").read()
    return html.replace("{{result}}", result)


@app.route("/")
def home():
    return page("")


@app.route("/register", methods=["POST"])
def register():
    f = request.form
    out = run("register", f.get("name", ""), f.get("age", ""), f.get("college", ""),
              f.get("course", ""), f.get("year", ""), f.get("mobile", ""),
              f.get("source", ""), f.get("destination", ""))
    return page(out)


@app.route("/search", methods=["POST"])
def search():
    return page(run("search", request.form.get("query", "")))


@app.route("/renew", methods=["POST"])
def renew():
    return page(run("renew", request.form.get("id", ""), request.form.get("months", "")))


@app.route("/cancel", methods=["POST"])
def cancel():
    return page(run("cancel", request.form.get("id", "")))


if __name__ == "__main__":
    app.run(debug=True)
