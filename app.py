from flask import Flask
from config import Config
from extensions import db

from routes.admin import admin_bp

from routes.main import main_bp
from routes.booking import booking_bp
from routes.payment import payment_bp

from routes.setup import setup_bp
from routes.sms_test import sms_test_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(setup_bp)
    app.register_blueprint(sms_test_bp)
    app.register_blueprint(admin_bp)
    with app.app_context():
        db.create_all()

    return app

app = create_app()
application = app
