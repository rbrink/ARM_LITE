import json
from flask import render_template, redirect, request
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

import arm_lite.ui.utils as ui_utils
from arm_lite.models.user import User
from arm_lite.ui import app, login_manager

@app.route('/')
@app.route("/index")
@app.route("/index.html")
def home():
    authenticated = ui_utils.authenticated_state()
    
    return render_template("index.html", authenticated=authenticated)

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

@login_manager.user_loader
def load_user(user_id):
    """
    Logged in check
    :param user_id:
    :return:
    """
    try:
        return User.query.get(int(user_id))
    except SQLAlchemyError as e:
        app.logger.error("Error getting user")
        app.logger.error(f"ERROR: {e}")
        return None


@login_manager.unauthorized_handler
def unauthorized():
    """
    User isn't authorised to view the page
    :return: Page redirect
    """
    return redirect('/login')
