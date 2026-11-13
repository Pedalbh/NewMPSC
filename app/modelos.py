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
    create_engine,
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
    origem: Mapped[str] = mapped_column(String(20), default="planilha")  # planilha | colagem
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    minuta: Mapped["Minuta | None"] = relationship(back_populates="processo", cascade="all, delete-orphan",
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


class ArquivoAutos(Base):
    """Um PDF dos autos enviado pelo usuário. Guarda-se o texto de cada página, não o arquivo."""
    __tablename__ = "arquivos_autos"
    __table_args__ = (UniqueConstraint("processo_id", "sha256"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id"), index=True)
    nome: Mapped[str] = mapped_column(String(200))
    tamanho: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    total_paginas: Mapped[int] = mapped_column(Integer)
    sem_texto: Mapped[int] = mapped_column(Integer, default=0)   # páginas digitalizadas, sem texto para ler
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


def criar_banco(url: str):
    """Motor do banco e fábrica de sessões. SQLite em memória (testes) usa uma conexão só."""
    opcoes = {}
    if url.startswith("sqlite"):
        opcoes["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            opcoes["poolclass"] = StaticPool
    motor = create_engine(url, **opcoes)
    Base.metadata.create_all(motor)
    return motor, sessionmaker(bind=motor, expire_on_commit=False)
