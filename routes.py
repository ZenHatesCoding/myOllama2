from flask import render_template
from api import register_api_routes


def register_routes(app):
    register_api_routes(app)

    @app.route('/')
    def index():
        return render_template('index.html')
