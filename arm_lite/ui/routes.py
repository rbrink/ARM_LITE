from flask import render_template

from arm_lite.ui import app

@app.route('/')
@app.route("/index")
@app.route("/index.html")
def home():
    return render_template("index.html")