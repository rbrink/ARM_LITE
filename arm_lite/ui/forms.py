from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, \
    IntegerField, BooleanField, PasswordField, Form, FieldList, FormField, HiddenField
from wtforms.validators import DataRequired, Optional

class SetupForm(FlaskForm):
    """"
    ARM User Login form.
    This form is used on:
      - /login

    Fields:
        username (StringField): The user's username (required).
        password (PasswordField): The user's password (required).
        submit (SubmitField): Button to submit the login form.
    """
    username = StringField('username', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])
    submit = SubmitField('Submit')

class AdminSetupForm(FlaskForm):
    """Form used to create the first admin account when the DB is empty."""
    username = StringField('username', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])
    submit = SubmitField('Submit')

class PasswordReset(FlaskForm):
    """
    Password reset form.
    This form is used on:
      - /update_password (for authenticated users to change their password)

    Fields:
        username (StringField): The user's username (required).
        old_password (PasswordField): The user's current password (required).
        new_password (PasswordField): The new password to set (required).
        submit (SubmitField): Button to submit the form.
    """
    username = StringField('username', validators=[DataRequired()])
    old_password = PasswordField('password', validators=[DataRequired()])
    new_password = PasswordField('password', validators=[DataRequired()])
    submit = SubmitField('Submit')

class GeneralSettingsForm(FlaskForm):
    SKIP_TRANSCODE = BooleanField("Skip Transcoding: ")
    VIDEO_TYPE = SelectField("Video Type: ", choices=[("Auto", "auto"), ("Movie", "movie"), ("Series", "series")])
    DATE_FORMAT = StringField("Date Format:", validators=[DataRequired()])
    AUTO_EJECT = BooleanField("Auto Eject Disc: ")
    DELRAWFILES = BooleanField("Delete After Trancode: ")
    submit = SubmitField("Submit")

class SystemInfoDrives(FlaskForm):
    """
    SystemInformation Form, to update system drive name (nickname) and description
      - /systeminfo
      - /settings
    """
    id = IntegerField('Drive ID', validators=[DataRequired()])
    name = StringField('Name', validators=[DataRequired()])
    description = StringField('Description', validators=[Optional()])
    drive_mode = SelectField('Drive Mode',
                             validators=[DataRequired()],
                             choices=[
                                 ('auto', 'Auto'),
                                 ('manual', 'Manual')
                             ],
                             )
    submit = SubmitField('Submit')
