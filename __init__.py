from flask import Flask
from dotenv import load_dotenv
from .config import Config

def create_app():
    load_dotenv()
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(Config)
    from .routes import main_bp
    app.register_blueprint(main_bp)
    return app
