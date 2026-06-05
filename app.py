"""
Disease Portal Application Factory.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

from flask import Flask, render_template
from models import db
from routes import main_bp
from config import Config

# On restricted/institutional networks an SSL-inspection proxy can break cert
# verification for some hosts (e.g. Open Targets, UMLS), so the app runs with
# EXTERNAL_API_VERIFY_SSL=false. Silence the noisy per-request urllib3 warning
# and note it once at startup instead. (In production/cloud, set it back to true.)
if not Config.EXTERNAL_API_VERIFY_SSL:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print("[startup] SSL verification is OFF (EXTERNAL_API_VERIFY_SSL=false). "
          "Required on this network; set it to true in production.")


def create_app(config_class=Config):
    """
    Application factory function.
    
    Args:
        config_class: Configuration class to use
        
    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    
    # Register blueprints
    app.register_blueprint(main_bp)

    # Friendly error pages. In production (debug off) these replace the bare
    # Werkzeug 404/500. In local debug mode Flask still shows the interactive
    # debugger for 500s, which is the desired dev behaviour.
    @app.errorhandler(404)
    def _not_found(error):
        return render_template(
            'error.html', code=404, title='Page not found',
            message="That page doesn't exist or has moved."
        ), 404

    @app.errorhandler(500)
    def _server_error(error):
        return render_template(
            'error.html', code=500, title='Something went wrong',
            message='An unexpected error occurred while processing your request. Please try again.'
        ), 500

    return app


# Create the application instance
app = create_app()


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
