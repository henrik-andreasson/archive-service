from app import create_app, cli

# entry point for gunicorn (archive-service:app) and flask (FLASK_APP)
app = create_app()
cli.register(app)
