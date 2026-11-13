# Arquitetura

## Ideia
O usuário trabalha no NewMPSC; o SIG fica como porta de entrada (planilha exportada) e de saída (minuta em .docx ou texto). Quando houver integração oficial, troca-se o adaptador, não a aplicação.

```
navegador ── HTTPS ── servidor (FastAPI)
                        ├─ app/main.py       rotas, sessão, cabeçalhos de segurança
                        ├─ app/servicos.py   regras: fila, minuta, pauta (sempre por usuário)
                        ├─ app/portas.py     Motor (IA) e Conexão (SIG): pontos de troca
                        ├─ app/nucleo/       leitor da planilha do SIG, folha e .docx
                        └─ app/modelos.py    banco (SQLAlchemy; SQLite hoje, Postgres depois)
```

## Portas
| Porta | Hoje | Depois |
| --- | --- | --- |
| Motor | `MotorDemo`: esqueleto marcado, sem IA | adaptador da API do Claude (direta ou via Bedrock), com os especialistas e a verificação de fontes |
| Conexão | `ConexaoPlanilha`: planilha do SIG entra, .docx sai | API do SIG ou MNI do eproc, se o MPSC abrir |

## Segurança (referência: OWASP ASVS)
- Senha com Argon2id, mínimo de 12 caracteres; resposta igual para e-mail inexistente e senha errada.
- Sessão em cookie assinado, `HttpOnly`, `SameSite=Lax`, `Secure` em produção, 8 horas; renovada no login.
- Token CSRF em todo POST e PUT. Limite de 5 tentativas de login por 15 minutos.
- CSP sem `unsafe-inline`; `X-Frame-Options: DENY`; `no-store` nas páginas; HSTS em produção.
- Entrada validada no servidor (tetos de tamanho, estilos em lista fechada); saída escapada pelo Jinja.
- Isolamento por usuário em toda consulta, com teste.

## Decisões
- **13/11/2026 – Projeto separado do Gabinete** (titular). A aplicação web não muda a estrutura do Gabinete; reuso por cópia.
- **13/11/2026 – Páginas feitas no servidor**, com pouco JavaScript: menos peças, carregamento rápido, CSP estrita.
- **13/11/2026 – Só dados fictícios** até haver hospedagem e contrato institucionais.

## O que falta para uso real
1. Adaptador do motor com a API do Claude e leitura dos autos (PDF).
2. Hospedagem e contrato institucionais; parecer de LGPD; registro de acessos.
3. Migrações de banco (Alembic) e Postgres; limite de tentativas em armazenamento compartilhado.
4. Segundo fator no login; troca de senha pela pessoa.
5. Pauta lida do eproc ou do 365, em vez de digitada.
