# app/__init__.py
from flask import Flask
from .extensions import db, login_manager
from flask_migrate import Migrate


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = '874y57843hfek43rsd4r4'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:beedrill!@localhost/GSG'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    migrate = Migrate(app, db)

    app.config['UPLOAD_FOLDER'] = 'C:\Users\dbopp\Documents\Clone\WebsiteImages'    

    db.init_app(app)
    login_manager.init_app(app)
    from .models import User  

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from .routes import main_bp
    app.register_blueprint(main_bp)

# Create database tables for our data models
    with app.app_context():
        db.create_all()  

    return app
