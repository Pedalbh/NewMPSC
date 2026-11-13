# Imagem do servidor. Roda como usuário sem privilégio; o banco e o segredo vêm do ambiente.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY pyproject.toml ./
COPY app ./app
COPY dados_ficticios ./dados_ficticios
RUN pip install --no-cache-dir . && useradd --system --home /srv newmpsc && mkdir /dados && chown newmpsc /dados
USER newmpsc
ENV NEWMPSC_BANCO=sqlite:////dados/newmpsc.db
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/saude')"
CMD ["uvicorn", "app.servidor:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
