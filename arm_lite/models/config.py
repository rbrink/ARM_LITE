from prettytable import PrettyTable

from arm_lite.ui import db

hidden_attribs = ("EMBY_USERID", "EMBY_PASSWORD", "EMBY_API_KEY",
                  "OMDB_KEY", "TMDB_KEY")
HIDDEN_VALUE = "<hidden>"

class Config(db.Model):
    __tablename__ = "Configuration"

    CONFIG_ID = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.job_id"))
    SKIP_TRANSCODE = db.Column(db.Boolean)
    VIDEO_TYPE = db.Column(db.String(25))
    MINLENGTH = db.Column(db.Integer)
    MAXLENGTH = db.Column(db.Integer)
    RAW_PATH = db.Column(db.String(255))
    TRANSCODE_PATH = db.Column(db.String(255))
    COMPLETED_PATH = db.Column(db.String(255))
    INSTALL_PATH = db.Column(db.String(255))
    LOGPATH = db.Column(db.String(255))
    LOGLIFE = db.Column(db.Integer)
    LOGLEVEL = db.Column(db.String(25))
    DBFILE = db.Column(db.String(255))
    WEBSERVER_IP = db.Column(db.String(25))
    WEBSERVER_PORT = db.Column(db.Integer)
    MAKEMKVCON = db.Column(db.String(255))
    RIPMETHOD = db.Column(db.String(25))
    MKV_ARGS = db.Column(db.String(25))
    DELRAWFILES = db.Column(db.Boolean)
    HB_PRESET_DVD = db.Column(db.String(256))
    HB_PRESET_BD = db.Column(db.String(256))
    DEST_EXT = db.Column(db.String(25))
    HANDBRAKE_CLI = db.Column(db.String(255))
    FFMPEG_PRE_FILE_ARGS = db.Column(db.String(512))
    FFMPEG_POST_FILE_ARGS = db.Column(db.String(512))
    FFMPEG_CLI = db.Column(db.String(256))
    USE_FFMPEG = db.Column(db.Boolean)
    CUETOOLS_PATH = db.Column(db.String(256))
    AUDIO_FORMAT = db.Column(db.String(25))
    EMBY_REFRESH = db.Column(db.Boolean)
    EMBY_SERVER = db.Column(db.String(25))
    EMBY_PORT = db.Column(db.String(6))
    EMBY_CLIENT = db.Column(db.String(25))
    EMBY_DEVICE = db.Column(db.String(50))
    EMBY_DEVICEID = db.Column(db.String(128))
    EMBY_USERNAME = db.Column(db.String(50))
    EMBY_USERID = db.Column(db.String(128))
    EMBY_PASSWORD = db.Column(db.String(128))
    EMBY_API_KEY = db.Column(db.String(64))
    OMDB_KEY = db.Column(db.String(128))
    TMDB_KEY = db.Column(db.String(128))

    def __init__(self, c, job_id):
        self.__dict__.update(c)
        self.job_id = job_id

    def __str__(self):
        """Returns a string of the object"""
        return_string = self.__class__.__name__ + ": "
        for attr, value in self.__dict__.items():
            if str(attr) in hidden_attribs and value:
                value = HIDDEN_VALUE
            return_string = return_string + "(" + str(attr) + "=" + str(value) + ") "

        return return_string

    def list_params(self):
        """Returns a string of the object"""
        return_string = self.__class__.__name__ + ": "
        for attr, value in self.__dict__.items():
            if return_string:
                return_string = return_string + "\n"
            if str(attr) in hidden_attribs and value:
                value = HIDDEN_VALUE
            return_string = return_string + str(attr) + ":" + str(value)

        return return_string

    def pretty_table(self):
        """Returns a string of the PrettyTable"""
        pretty_table = PrettyTable()
        pretty_table.field_names = ["Config", "Value"]
        pretty_table._max_width = {"Config": 20, "Value": 30}
        for attr, value in self.__dict__.items():
            if str(attr) in hidden_attribs and value:
                value = HIDDEN_VALUE
            pretty_table.add_row([str(attr), str(value)])
        return str(pretty_table.get_string())

    def get_d(self):
        """
        Return a dict of class - exclude any sensitive info
        :return: dict containing all attribs from class
        """
        return_dict = {}
        for key, value in self.__dict__.items():
            if str(key) not in hidden_attribs:
                return_dict[str(key)] = str(value)
        return return_dict
