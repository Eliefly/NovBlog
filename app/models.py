from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db, login_manager

ROLES = (('admin', 'admin'),
        ('editor', 'editor'),
        ('reader', 'reader'))

class User(db.Document):
    username = db.StringField(max_length=64, required=True)
    email = db.StringField(max_length=64, required=True)
    password_hash = db.StringField(required=True)
    role = db.StringField(max_length=32, default='reader', choices=ROLES)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    # flask-login要求实现的的用户方法。因为UserMixin包含这些方法的默认实现，省去显式实现。
    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        try:
            return self.username
        except AttributeError:
            raise NotImplementedError('No `username` attribute - override `get_id`')
        

# flask-login回调函数。如果找到用户返回用会对象，否则应返回None
@login_manager.user_loader
def load_user(username):
    # return User.objects.get(username=username)
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        user = None
    return user
