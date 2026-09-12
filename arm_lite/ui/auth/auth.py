import bcrypt
from flask import Blueprint, render_template, redirect, flash, \
    request, session
from flask_login import login_required, current_user, \
    login_user, logout_user
from sqlite3 import OperationalError

import arm_lite.ui.utils as utils
from arm_lite.ui import app, db, login_manager
from arm_lite.models.user import User
from arm_lite.ui.forms import SetupForm, PasswordReset, AdminSetupForm

route_auth = Blueprint("auth", __name__,
                       template_folder="templates",
                       static_folder="./static")

@route_auth.route("/setup-admin", methods=["GET", "POST"])
def setup_admin():
    """Create the first admin user when the database is empty."""
    if User.query.first() is not None:
        if current_user.is_authenticated:
            return redirect('/index')
        return redirect('/login')

    form = AdminSetupForm()
    if form.validate_on_submit():
        admin_email = form.username.data.strip()
        admin_password = form.password.data.strip().encode('utf-8')

        if User.query.filter_by(email=admin_email).first():
            flash("An admin account with that email already exists.", "warning")
            return render_template('setup_admin.html', form=form)

        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(admin_password, salt)
        admin = User(email=admin_email, password=hashed_password, hashed=salt)

        try:
            db.session.add(admin)
            db.session.commit()
            flash("Admin account created. Please log in.", "success")
            return redirect('/login')
        except Exception as error:
            db.session.rollback()
            app.logger.error(f"Error creating admin user: {error}")
            flash(str(error), "danger")

    return render_template('setup_admin.html', form=form)

@route_auth.route("/login", methods=["GET", "POST"])
def login():
    return_redirect = None
    # if a user is logged in
    if current_user.is_authenticated:
        return_redirect = redirect('/index')

    admin = User.query.first()
    if admin is None:
        flash("No admin account exists yet. Create the initial admin user.", "warning")
        return redirect('/setup-admin')

    form = SetupForm()
    if form.validate_on_submit():
        login_username = form.username.data.strip()
        login_password = form.password.data.strip().encode('utf-8')
        app.logger.debug("user= " + str(admin))
        password = admin.password
        login_hashed = bcrypt.hashpw(login_password, admin.hash)

        if login_hashed == password and login_username == admin.email:
            login_user(admin)
            app.logger.debug("user was logged in - redirecting")
            return_redirect = redirect('/index')
        else:
            flash("Something isn't right", "danger")

    # If nothing has gone wrong, give them the login page
    if request.method == 'GET' or return_redirect is None:
        return_redirect = render_template('login.html', form=form)

    return return_redirect

@route_auth.route("/logout")
def logout():
    """
    Log user out
    :return:
    """
    logout_user()
    flash("logged out", "success")
    return redirect('/')

@route_auth.route('/update_password', methods=['GET', 'POST'])
@login_required
def update_password():
    """
    updating the password for the admin account
    """
    # get current user
    user = User.query.first()
    session["page_title"] = "Update Admin Password"

    # After a login for is submitted
    form = PasswordReset()

    if form.validate_on_submit():
        # Get form values
        username = form.username.data.strip()
        new_password = form.new_password.data.strip().encode('utf-8')
        old_password = form.old_password.data.strip().encode('utf-8')

        # Get current password and dehash
        user = User.query.filter_by(email=username).first()
        current_password = user.password
        hashed = user.hash
        login_hashed = bcrypt.hashpw(old_password, hashed)

        # If user entered correct password
        if login_hashed == current_password:
            hashed_password = bcrypt.hashpw(new_password, hashed)
            user.password = hashed_password
            user.hash = hashed
            try:
                db.session.commit()
                flash("Password successfully updated", "success")
                app.logger.info("Password successfully updated")
                return redirect("logout")
            except Exception as error:
                flash(str(error), "danger")
                app.logger.error(f"Error in updating password: {error}")
        else:
            flash("Current password does not match", "danger")
            app.logger.error("Current password does not match")

    return render_template('update_password.html', user=user.email, form=form)


@login_manager.user_loader
def load_user(user_id):
    """
    Logged in check
    :param user_id:
    :return:
    """
    try:
        return User.query.get(int(user_id))
    except OperationalError as e:
        app.logger.error("Error getting user")
        app.logger.error(f"ERROR: {e}")
        return None


@login_manager.unauthorized_handler
def unauthorized():
    """
    User isn't authorised to view the requested page
    :return: redirect to login page
    """
    return redirect('/login')
