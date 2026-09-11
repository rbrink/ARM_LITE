from flask import Blueprint, render_template

route_settings = Blueprint("settings", __name__,
                           template_folder="templates",
                           static_folder="./static")

REDIRECT_SETTINGS = "settings.settings_page"

@route_settings.route("/settings")
def settings_page():
    return render_template("settings/settings.html")