# Arquitetura

## Ideia
O usuário trabalha no NewMPSC; o SIG fica como porta de entrada (planilha exportada) e de saída (minuta em .docx ou texto). Quando houver integração oficial, troca-se o adaptador, não a aplicação.

```
navegador ── HTTPS ── servidor (FastAPI)
                        ├─ app/main.py       rotas, sessão, cabeçalhos de segurança
                        ├─ app/servicos.py   regras: fila, minuta, pauta (sempre por usuário)
                        ├─ app/portas.py     Motor (IA) e Conexão (SIG): pontos de troca
                        ├─ app/autos.py      leitura do PDF dos autos, num processo à parte
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
- PDF dos autos: conferido pelo conteúdo, até 50 MB e 2.000 páginas; aberto num processo filho sem o ambiente da aplicação (nenhum segredo), com teto de tempo e de memória e duas leituras por vez. Nada do arquivo é executado nem servido de volta.
- Toda requisição tem teto de tamanho, conferido antes de ler o corpo: 60 MB para quem entrou, 64 KB para quem não entrou.

## Autos
O usuário envia o PDF na tela do processo. Fica guardado o texto de cada página (`arquivos_autos`, `paginas_autos`), com o número da página, para o motor citar de onde tirou cada afirmação. O arquivo original é descartado depois da leitura. Remover o arquivo apaga o texto.

Página digitalizada não tem texto: é contada e avisada. A leitura dessas páginas (OCR ou leitura de imagem pelo motor) é assunto da etapa do motor, e é lá que se decide se o original precisa ser guardado.

## Decisões
- **13/11/2026 – Projeto separado do Gabinete** (titular). A aplicação web não muda a estrutura do Gabinete; reuso por cópia.
- **13/11/2026 – Páginas feitas no servidor**, com pouco JavaScript: menos peças, carregamento rápido, CSP estrita.
- **13/11/2026 – Só dados fictícios** até haver hospedagem e contrato institucionais.
- **13/11/2026 – Dos autos guarda-se o texto, não o arquivo**: menos dado sensível parado no servidor e nenhuma rota que devolva arquivo enviado.
- **13/11/2026 – Motor pela API do Claude direta** (titular); jurisprudência conferida pelo JuriBase; fonte de legislação vigente a definir.

## O que falta para uso real
1. Adaptador do motor com a API do Claude, lendo os autos já guardados; leitura das páginas digitalizadas; verificação de fontes.
2. Hospedagem e contrato institucionais; parecer de LGPD; registro de acessos.
3. Migrações de banco (Alembic) e Postgres; limite de tentativas em armazenamento compartilhado.
4. Segundo fator no login; troca de senha pela pessoa.
5. Pauta lida do eproc ou do 365, em vez de digitada.
