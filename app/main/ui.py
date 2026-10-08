"""the web front-end, a static page calling the json api, only served when
ARCHIVE_UI is enabled"""
import os

from flask import abort, current_app, send_from_directory

from app.main import bp

UI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'ui')


@bp.route('/ui/')
def ui_index():
    return ui_file('index.html')


@bp.route('/ui/<path:name>')
def ui_file(name):
    if not current_app.config['ARCHIVE_UI']:
        abort(404)
    return send_from_directory(UI_DIR, name)
