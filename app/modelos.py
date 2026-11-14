"""Tabelas. Cada linha de trabalho pertence a um usuário; ninguém enxerga dado de outro."""
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    bindparam,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    cargo: Mapped[str] = mapped_column(String(120), default="")
    promotoria: Mapped[str] = mapped_column(String(160), default="")
    senha_hash: Mapped[str] = mapped_column(String(255))
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Processo(Base):
    __tablename__ = "processos"
    __table_args__ = (UniqueConstraint("usuario_id", "numero"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    numero: Mapped[str] = mapped_column(String(25))
    numero_sig: Mapped[str] = mapped_column(String(30), default="")
    classe: Mapped[str] = mapped_column(String(200), default="")
    assunto: Mapped[str] = mapped_column(String(200), default="")
    vista: Mapped[str] = mapped_column(String(40), default="")
    reu_preso: Mapped[bool] = mapped_column(Boolean, default=False)
    entrada: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dv_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    grupo: Mapped[int] = mapped_column(Integer, default=3)
    situacao: Mapped[str] = mapped_column(String(20), default="a_fazer")  # a_fazer | concluido
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # conta o prazo de guarda (C1)
    origem: Mapped[str] = mapped_column(String(20), default="planilha")  # planilha | colagem
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    minuta: Mapped["Minuta | None"] = relationship(back_populates="processo", cascade="all, delete-orphan",
                                                    uselist=False)
    tarefa: Mapped["TarefaMinuta | None"] = relationship(back_populates="processo", cascade="all, delete-orphan",
                                                         uselist=False)
    autos: Mapped[list["ArquivoAutos"]] = relationship(back_populates="processo", cascade="all, delete-orphan",
                                                       order_by="ArquivoAutos.id")


class Minuta(Base):
    __tablename__ = "minutas"
    id: Mapped[int] = mapped_column(primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id"), unique=True)
    tipo: Mapped[str] = mapped_column(String(120))
    blocos: Mapped[list] = mapped_column(JSON)
    motor: Mapped[str] = mapped_column(String(40))
    editada: Mapped[bool] = mapped_column(Boolean, default=False)
    atualizada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    processo: Mapped[Processo] = relationship(back_populates="minuta")


class TarefaMinuta(Base):
    """A escrita da minuta pelo motor de IA, que demora: uma por processo, com o estado para a tela acompanhar."""
    __tablename__ = "tarefas_minuta"
    id: Mapped[int] = mapped_column(primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id"), unique=True)
    estado: Mapped[str] = mapped_column(String(20), default="escrevendo")   # escrevendo | pronta | falhou
    erro: Mapped[str] = mapped_column(String(300), default="")
    iniciada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    pontos: Mapped[list] = mapped_column(JSON, default=list)       # pontos a enfrentar: lista de conferência na tela
    vista: Mapped[bool] = mapped_column(Boolean, default=False)    # o resultado já foi mostrado ao usuário
    chave: Mapped[str] = mapped_column(String(16), default="")     # distingue esta escrita de outra do mesmo processo
    repetir: Mapped[bool] = mapped_column(Boolean, default=True)   # na falha: adianta tentar de novo sem mudar nada
    processo: Mapped[Processo] = relationship(back_populates="tarefa")


class PedidoIA(Base):
    """Registro de cada pedido ao serviço de IA: quem, qual processo, quando, qual modelo respondeu.
    Sem conteúdo. Serve à prestação de contas e aos limites de pedidos."""
    __tablename__ = "pedidos_ia"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id"), index=True)
    feito_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    modelo: Mapped[str] = mapped_column(String(60), default="")
    resultado: Mapped[str] = mapped_column(String(20), default="em curso")   # em curso | pronta | falhou
    chave: Mapped[str] = mapped_column(String(16), default="", index=True)    # a mesma da tarefa que gerou o pedido


class ArquivoAutos(Base):
    """Um PDF dos autos enviado pelo usuário. Guarda-se o texto de cada página, não o arquivo."""
    __tablename__ = "arquivos_autos"
    __table_args__ = (UniqueConstraint("processo_id", "impressao"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id"), index=True)
    nome: Mapped[str] = mapped_column(String(200))
    tamanho: Mapped[int] = mapped_column(Integer, default=0)   # sempre 0 desde a 0.4.0 (cartão C2)
    # Cartão C2: impressão com chave do servidor. Avisa arquivo repetido, mas não serve de prova fora daqui.
    impressao: Mapped[str] = mapped_column(String(64))
    total_paginas: Mapped[int] = mapped_column(Integer)
    sem_texto: Mapped[int] = mapped_column(Integer, default=0)   # páginas digitalizadas ou ilegíveis
    caracteres: Mapped[int] = mapped_column(Integer, default=0)  # para a cota; arredondado em milhares (C2)
    cita_processo: Mapped[bool] = mapped_column(Boolean, default=True)   # o número do processo aparece no texto
    enviado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    processo: Mapped[Processo] = relationship(back_populates="autos")
    paginas: Mapped[list["PaginaAutos"]] = relationship(back_populates="arquivo", cascade="all, delete-orphan",
                                                        order_by="PaginaAutos.numero")


class PaginaAutos(Base):
    __tablename__ = "paginas_autos"
    __table_args__ = (UniqueConstraint("arquivo_id", "numero"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    arquivo_id: Mapped[int] = mapped_column(ForeignKey("arquivos_autos.id"), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    texto: Mapped[str] = mapped_column(Text)
    arquivo: Mapped[ArquivoAutos] = relationship(back_populates="paginas")


class Audiencia(Base):
    __tablename__ = "audiencias"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    numero: Mapped[str] = mapped_column(String(25))
    inicio: Mapped[datetime] = mapped_column(DateTime, index=True)
    tipo: Mapped[str] = mapped_column(String(80), default="Instrução e julgamento")
    ficha: Mapped[dict] = mapped_column(JSON)
    motor: Mapped[str] = mapped_column(String(40))
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


def criar_banco(url: str, chave_impressao: bytes | None = None):
    """Motor do banco e fábrica de sessões. SQLite em memória (testes) usa uma conexão só.
    `chave_impressao` só é exigida para converter um banco antigo, que ainda guarda o `sha256` do arquivo."""
    opcoes = {}
    if url.startswith("sqlite"):
        opcoes["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            opcoes["poolclass"] = StaticPool
    motor = create_engine(url, **opcoes)
    if url.startswith("sqlite"):
        @event.listens_for(motor, "connect")
        def _apagar_de_verdade(conexao, _registro):
            conexao.execute("PRAGMA secure_delete=ON")   # texto removido não fica nas páginas livres do arquivo
    Base.metadata.create_all(motor)
    _atualizar(motor, chave_impressao)
    return motor, sessionmaker(bind=motor, expire_on_commit=False)


def _atualizar(motor, chave_impressao: bytes | None) -> None:
    """Põe em dia um banco criado por versão anterior (enquanto não há Alembic)."""
    from .autos import impressao  # aqui para não carregar a leitura de PDF junto com as tabelas
    tabelas = inspect(motor).get_table_names()
    antigas = {c["name"] for c in inspect(motor).get_columns("arquivos_autos")} \
        if "arquivos_autos" in tabelas else set()
    if "sha256" in antigas and "impressao" not in antigas and not chave_impressao:   # antes de mudar qualquer coisa
        raise RuntimeError("banco antigo: a conversão das impressões dos autos precisa da chave do servidor")
    with motor.begin() as conexao:
        colunas = {c["name"] for c in inspect(conexao).get_columns("processos")} if "processos" in tabelas else set()
        if colunas and "concluido_em" not in colunas:
            tipo = DateTime().compile(dialect=motor.dialect)
            conexao.execute(text(f"ALTER TABLE processos ADD COLUMN concluido_em {tipo}"))
            # o prazo dos já concluídos começa a contar agora
            conexao.execute(text("UPDATE processos SET concluido_em = :agora WHERE situacao = 'concluido'")
                            .bindparams(bindparam("agora", type_=DateTime)), {"agora": datetime.now()})
        colunas = {c["name"] for c in inspect(conexao).get_columns("arquivos_autos")} \
            if "arquivos_autos" in tabelas else set()
        if "sha256" in colunas and "impressao" not in colunas:
            conexao.execute(text("ALTER TABLE arquivos_autos RENAME COLUMN sha256 TO impressao"))
            linhas = conexao.execute(text("SELECT id, processo_id, impressao FROM arquivos_autos")).all()
            for id_, processo_id, antigo in linhas:
                conexao.execute(text("UPDATE arquivos_autos SET impressao = :i WHERE id = :id"),
                                {"i": impressao(antigo, chave_impressao, processo_id), "id": id_})
        if colunas:   # cartão C2: tamanho exato e caracteres exatos deixam de ficar (repetir não muda nada)
            conexao.execute(text("UPDATE arquivos_autos SET tamanho = 0, "
                                 "caracteres = ((caracteres + 999) / 1000) * 1000 WHERE tamanho <> 0"))
