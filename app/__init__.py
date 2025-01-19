from flask import Flask
from .config import Config
from .extensions import db, login_manager

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # Import and register blueprints
    from .routes.auth import auth
    from .routes.dashboard import dashboard
    app.register_blueprint(auth)
    app.register_blueprint(dashboard)
    
    # Import models
    from .models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    return app 