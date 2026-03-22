from .conversations import conversations_bp
from .documents import documents_bp
from .images import images_bp

def register_api_routes(app):
    app.register_blueprint(conversations_bp, url_prefix='/api/conversations')
    app.register_blueprint(documents_bp, url_prefix='/api/documents')
    app.register_blueprint(images_bp, url_prefix='/api/images')
