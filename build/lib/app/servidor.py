"""Ponto de entrada do servidor: `uvicorn app.servidor:app`."""
from .main import criar_app

app = criar_app()
