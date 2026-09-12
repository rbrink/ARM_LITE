from flask import Blueprint

route_database = Blueprint("database", __name__,
                           template_folder="templates",
                           static_folder="./static")