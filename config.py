from flask import Flask

def configure_app(app):
    """Configure Flask application with proper settings for Thai language"""
    # Set JSON options to ensure Thai characters are handled correctly
    app.config['JSON_AS_ASCII'] = False
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
    
    # Set default character set to UTF-8
    app.config['JSON_ENSURE_ASCII'] = False
    
    # Set secret key for session management
    app.config['SECRET_KEY'] = 'anyada-salon-2025'
    
    return app