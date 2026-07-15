"""Rocket Stock Scanner — Dash application."""
from dash import Dash
import dash_bootstrap_components as dbc
from .routes import build_layout, setup_callbacks


def create_app() -> Dash:
    """Create and configure the Dash application."""
    app = Dash(
        __name__,
        title="Rocket Stock Scanner",
        suppress_callback_exceptions=True,
        external_stylesheets=[
            dbc.themes.FLATLY,
            "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css",
        ],
    )
    app.layout = build_layout()
    setup_callbacks(app)
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=8050, debug=False)
else:
    app = create_app()
