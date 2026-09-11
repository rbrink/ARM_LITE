import json
from flask import render_template, request
from werkzeug.exceptions import HTTPException

from arm_lite.ui import app

@app.route('/')
@app.route("/index")
@app.route("/index.html")
def home():
    return render_template("index.html")

@app.route("/error")
def was_error(error):
    return render_template("error.html", title="error", error=error)

@app.errorhandler(Exception)
def handle_exception(sent_error):
    """
    Exception handler - This breaks all the normal debug functions \n
    :param sent_error: error
    :return: error page
    """
    # pass through HTTP errors
    if isinstance(sent_error, HTTPException):
        return sent_error

    app.logger.debug(f"Error: {sent_error}", exc_info=sent_error)
    if request.path.startswith('/json') or request.args.get('json'):
        app.logger.debug(f"{request.path} - {sent_error}")
        return_json = {
            'path': request.path,
            'Error': str(sent_error)
        }
        return app.response_class(response=json.dumps(return_json, indent=4, sort_keys=True),
                                  status=200,
                                  mimetype="application/json")

    return render_template("error.html", error=sent_error), 500
