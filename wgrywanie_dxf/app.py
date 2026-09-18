# -*- coding: utf-8 -*-
"""Aplikacja: wgrywanie DXF (Sheet Parts) do LANTEKA przez PowerSync.

Uruchomienie lokalne:   python app.py
                        http://127.0.0.1:5059/dxf/
"""
from flask import Flask, redirect, url_for

from config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["DATA_DIR"].mkdir(parents=True, exist_ok=True)

    from modules.dxf import bp as dxf_bp
    app.register_blueprint(dxf_bp)

    @app.route("/")
    def index():
        return redirect(url_for("dxf.start"))

    return app


app = create_app()

if __name__ == "__main__":
    import os
    app.run(host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "5059")),
            debug=bool(os.getenv("DEBUG")))
