# Mesa

Aplicação web de trabalho do promotor: os processos recebidos, a minuta de cada um e a pauta de audiências num lugar só, para que o SIG fique apenas como porta de entrada e de saída.

"Mesa" é nome provisório de exibição. Projeto separado do Gabinete: reaproveita, por cópia, o leitor da planilha do SIG e o gerador de .docx (`app/nucleo/ORIGEM.md`), e não altera aquele repositório.

**Estado (0.1.0):** só dados fictícios. A minuta e a ficha vêm de um motor de demonstração, sem IA. A API do Claude e a integração oficial com o SIG entram trocando um adaptador em `app/portas.py`.

## Rodar no computador

```
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
python -m app.cli semente          # cria o usuário e a fila de demonstração e mostra a senha
uvicorn app.servidor:app --reload  # http://127.0.0.1:8000
```

## Testes

```
ruff check .
python -m playwright install chromium   # uma vez
python -m pytest
```

O teste `testes/test_navegador.py` faz a jornada inteira num navegador de verdade. `MESA_PRINTS=pasta` guarda os prints de cada tela.

## Configuração (variáveis de ambiente)

| Variável | Para quê | Padrão |
| --- | --- | --- |
| `MESA_AMBIENTE` | `desenvolvimento`, `teste` ou `producao` | `desenvolvimento` |
| `MESA_SEGREDO` | assina a sessão; obrigatório em produção (32 caracteres ou mais) | gerado a cada início |
| `MESA_BANCO` | endereço do banco (SQLAlchemy) | `sqlite:///mesa.db` |
| `MESA_MOTOR` | motor de minutas e fichas | `demo` |
| `MESA_DADOS_FICTICIOS` | `0` só com hospedagem e contrato institucionais | `1` |

## Servidor de teste

`docker build -t mesa . && docker run -p 8000:8000 -e MESA_AMBIENTE=producao -e MESA_SEGREDO=... -v mesa-dados:/dados mesa`, atrás de HTTPS. Criar usuários com `python -m app.cli criar-usuario`.

Arquitetura e decisões: `docs/ARQUITETURA.md`. Regras de trabalho: `CLAUDE.md`.
