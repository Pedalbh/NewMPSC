"""Montagem da aplicação: sessão, cabeçalhos de segurança, rotas e telas."""
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text
from starlette.middleware.sessions import SessionMiddleware

from . import VERSAO, autos, servicos
from .config import Config, carregar
from .modelos import Usuario, criar_banco
from .nucleo import documento
from .portas import ConexaoPlanilha, criar_motor
from .seguranca import LimiteTentativas, conferir_senha, csrf_confere, token_csrf

AQUI = Path(__file__).parent
TETO_PLANILHA = 20 * 1024 * 1024
TETO_CORPO = autos.TETO_PDF + 10 * 1024 * 1024   # maior requisição aceita de quem entrou
TETO_CORPO_ANONIMO = 64 * 1024                    # quem não entrou só envia o formulário de login
MAX_PDFS_POR_ENVIO = 10
DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro")
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
       "connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'")


class PrecisaEntrar(Exception):
    pass


def _dia_extenso(d: datetime) -> str:
    return f"{DIAS[d.weekday()]}, {d.day} de {MESES[d.month - 1]}"


def criar_app(config: Config | None = None, agora=datetime.now) -> FastAPI:
    config = config or carregar()
    motor_banco, Sessao = criar_banco(config.banco_url)
    motor = criar_motor(config.motor)
    conexao = ConexaoPlanilha()
    limite = LimiteTentativas()

    app = FastAPI(title="NewMPSC", version=VERSAO, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.Sessao, app.state.config, app.state.limite = Sessao, config, limite
    app.mount("/static", StaticFiles(directory=AQUI / "static"), name="static")
    telas = Jinja2Templates(directory=AQUI / "templates")
    telas.env.filters["data"] = lambda d: d.strftime("%d/%m/%Y") if d else "—"
    telas.env.filters["hora"] = lambda d: d.strftime("%H:%M") if d else ""
    telas.env.filters["dia_extenso"] = _dia_extenso
    telas.env.globals.update(versao=VERSAO, grupos=servicos.GRUPOS, config=config)

    @app.middleware("http")
    async def cabecalhos(request: Request, call_next):
        recusa = _corpo_recusado(request)
        if recusa:
            resposta = telas.TemplateResponse(request, "erro.html", {"codigo": recusa[0], "mensagem": recusa[1]},
                                              status_code=recusa[0], headers={"Connection": "close"})
        else:
            resposta = await call_next(request)
        resposta.headers.update({
            "Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
            "Referrer-Policy": "same-origin", "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Cross-Origin-Opener-Policy": "same-origin"})
        if not request.url.path.startswith("/static"):
            resposta.headers["Cache-Control"] = "no-store"
        if config.producao:
            resposta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return resposta

    def _corpo_recusado(request: Request) -> tuple[int, str] | None:
        """Barra a requisição grande demais antes de ler o corpo."""
        if request.method not in ("POST", "PUT", "PATCH"):
            return None
        declarado = request.headers.get("content-length", "")
        if not declarado.isdigit():
            return 411, "Envio sem tamanho declarado."
        teto = TETO_CORPO if request.session.get("uid") else TETO_CORPO_ANONIMO
        if int(declarado) > teto:
            return 413, "Envio grande demais."
        return None

    # Acrescentado depois do middleware de cabeçalhos para rodar antes dele (a sessão precisa existir em toda rota).
    app.add_middleware(SessionMiddleware, secret_key=config.segredo, session_cookie="newmpsc_sessao",
                       same_site="lax", https_only=config.producao, max_age=8 * 3600)

    # ------------------------------------------------------------------ dependências
    def banco():
        with Sessao() as db:
            yield db

    def usuario_atual(request: Request, db=Depends(banco)) -> Usuario:
        uid = request.session.get("uid")
        usuario = db.get(Usuario, uid) if uid else None
        if usuario is None:
            raise PrecisaEntrar()
        return usuario

    async def exigir_csrf(request: Request) -> None:
        recebido = request.headers.get("x-csrf-token")
        if recebido is None and request.headers.get("content-type", "").startswith(
                ("application/x-www-form-urlencoded", "multipart/form-data")):
            recebido = (await request.form()).get("csrf")
        if not csrf_confere(request.session, recebido):
            raise HTTPException(403, "Sessão expirada. Recarregue a página e tente de novo.")

    def tela(request: Request, nome: str, status: int = 200, **ctx):
        ctx.update(csrf=token_csrf(request.session), aviso=request.session.pop("aviso", None))
        return telas.TemplateResponse(request, nome, ctx, status_code=status)

    def avisar(request: Request, tipo: str, textos: str | list[str]) -> None:
        request.session["aviso"] = {"tipo": tipo, "textos": [textos] if isinstance(textos, str) else textos[:8]}

    def voltar(caminho: str) -> RedirectResponse:
        return RedirectResponse(caminho, status_code=303)

    def meu_processo(processo_id: int, usuario=Depends(usuario_atual), db=Depends(banco)):
        p = servicos.processo_do_usuario(db, usuario, processo_id)
        if p is None:
            raise HTTPException(404, "Processo não encontrado.")
        return p

    def minha_audiencia(audiencia_id: int, usuario=Depends(usuario_atual), db=Depends(banco)):
        a = servicos.audiencia_do_usuario(db, usuario, audiencia_id)
        if a is None:
            raise HTTPException(404, "Audiência não encontrada.")
        return a

    # ------------------------------------------------------------------ erros
    @app.exception_handler(PrecisaEntrar)
    async def _entrar(request: Request, exc: PrecisaEntrar):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"erro": "Sessão encerrada. Entre de novo."}, status_code=401)
        return voltar("/entrar")

    @app.exception_handler(HTTPException)
    async def _erro(request: Request, exc: HTTPException):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"erro": exc.detail}, status_code=exc.status_code)
        return telas.TemplateResponse(request, "erro.html", {"codigo": exc.status_code, "mensagem": exc.detail},
                                      status_code=exc.status_code)

    # ------------------------------------------------------------------ conta
    @app.get("/saude", include_in_schema=False)
    def saude(db=Depends(banco)):
        db.execute(text("select 1"))
        return {"estado": "ok", "versao": VERSAO}

    @app.get("/entrar", response_class=HTMLResponse)
    def entrar(request: Request):
        if request.session.get("uid"):
            return voltar("/")
        return tela(request, "entrar.html")

    @app.post("/entrar", dependencies=[Depends(exigir_csrf)])
    async def entrar_post(request: Request, db=Depends(banco)):
        dados = await request.form()
        email = str(dados.get("email") or "").strip().lower()[:254]
        senha = str(dados.get("senha") or "")[:200]
        chave = f"{request.client.host if request.client else '-'}|{email}"
        if limite.bloqueado(chave):
            return tela(request, "entrar.html", status=429, email=email,
                        erro="Muitas tentativas. Aguarde 15 minutos e tente de novo.")
        usuario = db.scalar(select(Usuario).where(Usuario.email == email))
        if not conferir_senha(usuario.senha_hash if usuario else None, senha):
            limite.registrar_falha(chave)
            return tela(request, "entrar.html", status=401, email=email, erro="E-mail ou senha incorretos.")
        limite.limpar(chave)
        request.session.clear()   # sessão nova a cada login (evita fixação de sessão)
        request.session["uid"] = usuario.id
        return voltar("/")

    @app.post("/sair", dependencies=[Depends(exigir_csrf)])
    def sair(request: Request):
        request.session.clear()
        return voltar("/entrar")

    @app.get("/configuracoes", response_class=HTMLResponse)
    def configuracoes(request: Request, usuario=Depends(usuario_atual)):
        return tela(request, "configuracoes.html", usuario=usuario, pagina="configuracoes")

    @app.post("/configuracoes", dependencies=[Depends(exigir_csrf)])
    async def configuracoes_post(request: Request, usuario=Depends(usuario_atual), db=Depends(banco)):
        dados = await request.form()
        nome = str(dados.get("nome") or "").strip()[:120]
        if not nome:
            avisar(request, "erro", "Informe o seu nome.")
            return voltar("/configuracoes")
        usuario.nome = nome
        usuario.cargo = str(dados.get("cargo") or "").strip()[:120]
        usuario.promotoria = str(dados.get("promotoria") or "").strip()[:160]
        db.merge(usuario)
        db.commit()
        avisar(request, "ok", "Dados salvos.")
        return voltar("/configuracoes")

    # ------------------------------------------------------------------ processos
    @app.get("/", response_class=HTMLResponse)
    def inicio(request: Request, ver: str = "a_fazer", usuario=Depends(usuario_atual), db=Depends(banco)):
        ver = ver if ver in ("a_fazer", "concluido") else "a_fazer"
        a_fazer = servicos.fila(db, usuario, "a_fazer")
        lista = a_fazer if ver == "a_fazer" else servicos.fila(db, usuario, "concluido")
        momento = agora()
        hoje = momento.replace(hour=0, minute=0, second=0, microsecond=0)
        saudacao = "Bom dia" if momento.hour < 12 else "Boa tarde" if momento.hour < 18 else "Boa noite"
        return tela(request, "inicio.html", usuario=usuario, pagina="processos", ver=ver, processos=lista,
                    saudacao=saudacao,
                    contagem=[sum(1 for p in a_fazer if p.grupo == g) for g in range(4)], total=len(a_fazer),
                    proximas=servicos.pauta(db, usuario, hoje, dias=7), hoje=hoje)

    @app.post("/processos/importar", dependencies=[Depends(exigir_csrf)])
    async def importar(request: Request, usuario=Depends(usuario_atual), db=Depends(banco)):
        arquivo = (await request.form()).get("planilha")
        if arquivo is None or isinstance(arquivo, str) or not arquivo.filename:
            avisar(request, "erro", "Escolha a planilha exportada do SIG.")
            return voltar("/")
        dados = await arquivo.read(TETO_PLANILHA + 1)
        try:
            res = servicos.importar_fila(db, usuario, dados, arquivo.filename[:200], conexao, motor,
                                         config.dados_ficticios)
        except conexao.Recusada as e:
            avisar(request, "erro", f"A planilha não foi lida: {e}.")
            return voltar("/")
        _resumo(request, res)
        return voltar("/")

    @app.post("/processos/colar", dependencies=[Depends(exigir_csrf)])
    async def colar(request: Request, usuario=Depends(usuario_atual), db=Depends(banco)):
        texto = str((await request.form()).get("numeros") or "")[:20000]
        _resumo(request, servicos.colar_numeros(db, usuario, texto, motor))
        return voltar("/")

    def _resumo(request: Request, res: servicos.ResultadoImportacao) -> None:
        if not res.novos and not res.atualizados:
            avisar(request, "erro", res.conferir or ["Nenhum processo encontrado."])
            return
        partes = []
        if res.novos:
            partes.append(f"{res.novos} processo(s) novo(s), com a primeira minuta pronta")
        if res.atualizados:
            partes.append(f"{res.atualizados} já estava(m) na fila")
        avisar(request, "atencao" if res.conferir else "ok", ["; ".join(partes) + "."] + res.conferir)

    @app.get("/processos/{processo_id}", response_class=HTMLResponse)
    def processo(request: Request, p=Depends(meu_processo), usuario=Depends(usuario_atual)):
        return tela(request, "processo.html", usuario=usuario, pagina="processos", p=p, minuta=p.minuta)

    @app.post("/processos/{processo_id}/autos", dependencies=[Depends(exigir_csrf)])
    async def juntar_autos(request: Request, p=Depends(meu_processo), db=Depends(banco)):
        destino = f"/processos/{p.id}#autos"
        enviados = [a for a in (await request.form()).getlist("autos") if not isinstance(a, str) and a.filename]
        if not enviados:
            avisar(request, "erro", "Escolha o PDF dos autos.")
            return voltar(destino)
        p = db.merge(p)
        lidos, textos = 0, []
        for arquivo in enviados[:MAX_PDFS_POR_ENVIO]:
            nome = arquivo.filename[:200]
            curto = nome if len(nome) <= 60 else nome[:57] + "…"   # o aviso viaja no cookie da sessão
            try:
                leitura = await run_in_threadpool(autos.ler, await arquivo.read(autos.TETO_PDF + 1))
                avisos = servicos.juntar_autos(db, p, nome, leitura, config.dados_ficticios)
            except (autos.PdfRecusado, servicos.AutosRecusados) as e:
                textos.append(f"{curto} não entrou: {e}.")
                continue
            lidos += 1
            textos.append(f"{curto}: {len(leitura.paginas)} página(s) lida(s).")
            textos += [f"{curto}: {a}." for a in avisos]
        if len(enviados) > MAX_PDFS_POR_ENVIO:
            textos.append(f"Só os {MAX_PDFS_POR_ENVIO} primeiros arquivos foram lidos; envie os demais em seguida.")
        so_leituras = lidos == len(enviados) and len(textos) == lidos
        avisar(request, "ok" if so_leituras else "atencao" if lidos else "erro", textos)
        return voltar(destino)

    @app.post("/processos/{processo_id}/autos/{arquivo_id}/remover", dependencies=[Depends(exigir_csrf)])
    def remover_autos(request: Request, arquivo_id: int, p=Depends(meu_processo), db=Depends(banco)):
        if not servicos.remover_autos(db, db.merge(p), arquivo_id):
            raise HTTPException(404, "Arquivo não encontrado.")
        avisar(request, "ok", "Arquivo removido dos autos.")
        return voltar(f"/processos/{p.id}#autos")

    @app.post("/processos/{processo_id}/situacao", dependencies=[Depends(exigir_csrf)])
    async def situacao(request: Request, p=Depends(meu_processo), db=Depends(banco)):
        nova = str((await request.form()).get("situacao") or "")
        try:
            servicos.definir_situacao(db, db.merge(p), nova)
        except ValueError as e:
            raise HTTPException(422, str(e)) from None
        avisar(request, "ok", "Processo concluído." if nova == "concluido" else "Processo devolvido à fila.")
        return voltar("/" if nova == "concluido" else f"/processos/{p.id}")

    @app.post("/processos/{processo_id}/refazer", dependencies=[Depends(exigir_csrf)])
    def refazer(request: Request, p=Depends(meu_processo), db=Depends(banco)):
        servicos.refazer_minuta(db, db.merge(p), motor)
        avisar(request, "ok", "Minuta refeita pelo motor.")
        return voltar(f"/processos/{p.id}")

    @app.put("/api/processos/{processo_id}/minuta", dependencies=[Depends(exigir_csrf)])
    async def salvar(request: Request, p=Depends(meu_processo), db=Depends(banco)):
        try:
            corpo = await request.json()
            m = servicos.salvar_minuta(db, db.merge(p), corpo.get("blocos") if isinstance(corpo, dict) else None)
        except ValueError as e:
            raise HTTPException(422, str(e)) from None
        return {"salva_em": m.atualizada_em.strftime("%H:%M"), "paragrafos": len(m.blocos)}

    def _nome_arquivo(p, extensao: str) -> str:
        return quote(f"minuta-{p.numero}.{extensao}")

    @app.get("/processos/{processo_id}/minuta.docx")
    def baixar_docx(p=Depends(meu_processo)):
        return Response(documento.docx(p.minuta.blocos), headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{_nome_arquivo(p, 'docx')}"},
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    @app.get("/processos/{processo_id}/minuta.txt")
    def baixar_texto(p=Depends(meu_processo)):
        return PlainTextResponse(documento.texto_simples(p.minuta.blocos))

    # ------------------------------------------------------------------ audiências
    @app.get("/audiencias", response_class=HTMLResponse)
    def audiencias(request: Request, usuario=Depends(usuario_atual), db=Depends(banco)):
        hoje = agora().replace(hour=0, minute=0, second=0, microsecond=0)
        dias: dict = {}
        for a in servicos.pauta(db, usuario, hoje):
            dias.setdefault(a.inicio.date(), []).append(a)
        return tela(request, "audiencias.html", usuario=usuario, pagina="audiencias", dias=dias, hoje=hoje,
                    tipos=servicos.TIPOS_AUDIENCIA)

    @app.post("/audiencias", dependencies=[Depends(exigir_csrf)])
    async def audiencias_post(request: Request, usuario=Depends(usuario_atual), db=Depends(banco)):
        d = await request.form()
        try:
            a = servicos.marcar_audiencia(db, usuario, str(d.get("numero") or ""), str(d.get("data") or ""),
                                          str(d.get("hora") or ""), str(d.get("tipo") or ""), motor)
        except ValueError as e:
            avisar(request, "erro", str(e).capitalize() + ".")
            return voltar("/audiencias")
        avisar(request, "ok", f"Audiência marcada para {a.inicio:%d/%m} às {a.inicio:%H:%M}, com a ficha pronta.")
        return voltar("/audiencias")

    @app.get("/audiencias/{audiencia_id}", response_class=HTMLResponse)
    def ficha(request: Request, a=Depends(minha_audiencia), usuario=Depends(usuario_atual)):
        return tela(request, "ficha.html", usuario=usuario, pagina="audiencias", a=a)

    @app.post("/audiencias/{audiencia_id}/remover", dependencies=[Depends(exigir_csrf)])
    def remover(request: Request, a=Depends(minha_audiencia), db=Depends(banco)):
        servicos.remover_audiencia(db, db.merge(a))
        avisar(request, "ok", "Audiência removida da pauta.")
        return voltar("/audiencias")

    return app
