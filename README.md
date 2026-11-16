# NewMPSC

Aplicação web de trabalho do promotor: os processos recebidos, a minuta de cada um e a pauta de audiências num lugar só, para que o SIG fique apenas como porta de entrada e de saída.

Projeto separado do Gabinete: reaproveita, por cópia, o leitor da planilha do SIG e o gerador de .docx (`app/nucleo/ORIGEM.md`), e não altera aquele repositório.

**Estado (0.5.1):** só dados fictícios. Os autos entram em PDF e são lidos página a página. Com `NEWMPSC_MOTOR=claude`, o relatório da minuta é escrito pela API do Claude a partir dos autos, com a página de cada afirmação; fundamentação e pedido ficam com o promotor. O padrão continua sendo o motor de demonstração, sem IA. Com `NEWMPSC_SIG=simulado`, um SIG simulado mostra o envelope inteiro: a fila chega com um clique e a minuta volta como rascunho, sem arquivo (protótipo; nada chega ao SIG de verdade). A API do Claude e a integração oficial com o SIG entram trocando um adaptador em `app/portas.py`.

## Rodar no computador

```
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
python -m app.cli semente          # cria o usuário e a fila de demonstração e mostra a senha
uvicorn app.servidor:app --reload  # http://127.0.0.1:8000
```

## Ver o protótipo do envelope

```
NEWMPSC_SIG=simulado python -m app.cli criar-usuario voce@exemplo.invalid "Seu Nome"
NEWMPSC_SIG=simulado uvicorn app.servidor:app      # http://127.0.0.1:8000
```

Entre, clique em "Buscar no SIG", abra um processo, corrija a minuta e use "Enviar ao SIG". A aba "SIG simulado" mostra o que o SIG teria recebido. O plano para levar isso a promotorias de verdade está em `docs/PILOTO.md`.

## Testes

```
ruff check .
python -m playwright install chromium   # uma vez
python -m pytest
```

O teste `testes/test_navegador.py` faz a jornada inteira num navegador de verdade. `NEWMPSC_PRINTS=pasta` guarda os prints de cada tela.

## Configuração (variáveis de ambiente)

| Variável | Para quê | Padrão |
| --- | --- | --- |
| `NEWMPSC_AMBIENTE` | `desenvolvimento`, `teste` ou `producao` | `desenvolvimento` |
| `NEWMPSC_SEGREDO` | assina a sessão; obrigatório em produção (32 caracteres ou mais) | gerado a cada início |
| `NEWMPSC_BANCO` | endereço do banco (SQLAlchemy) | `sqlite:///newmpsc.db` |
| `NEWMPSC_MOTOR` | motor de minutas e fichas: `demo` ou `claude` (só com dados fictícios) | `demo` |
| `NEWMPSC_SIG` | como o SIG entra e sai: `planilha` ou `simulado` (protótipo do envelope, só com dados fictícios) | `planilha` |
| `NEWMPSC_MODELO` | modelo usado pelo motor `claude` | `claude-opus-5-5` |
| `ANTHROPIC_API_KEY` | chave da API do Claude, lida pela biblioteca; só para o motor `claude` | sem padrão |
| `NEWMPSC_DADOS_FICTICIOS` | `0` só com hospedagem e contrato institucionais | `1` |

## Servidor de teste

`docker build -t newmpsc . && docker run -p 8000:8000 -e NEWMPSC_AMBIENTE=producao -e NEWMPSC_SEGREDO=... -v newmpsc-dados:/dados newmpsc`, atrás de HTTPS. Criar usuários com `python -m app.cli criar-usuario`.

Arquitetura e decisões: `docs/ARQUITETURA.md`. Regras de trabalho: `CLAUDE.md`. Decisões à espera do titular: `docs/CARTOES.md`. Plano do piloto: `docs/PILOTO.md` (materiais da Fase 1 em `docs/piloto/`). Pedido de integração à TI: `docs/PEDIDO-TI.md`.
