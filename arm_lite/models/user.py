from flask_login import UserMixin

from arm_lite.ui import db

class User(db.Model, UserMixin):
    __tablename__ = "Users"

    user_id = db.Column(db.Integer, index=True, primary_key=True)
    email = db.Column(db.String(64))
    password = db.Column(db.String(128))
    hash = db.Column(db.String(256))

    def __init__(self, email=None, password=None, hashed=None):
        self.email = email
        self.password = password
        self.hash = hashed

    def __repr__(self):
        """Return user's name"""
        return f"<User {self.email}>"

    def __str__(self):
        """Return string of object"""
        return self.__class__.__name__ + ": " + self.email

    def get_id(self):
        """Return user's id"""
        return self.user_id
