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
| Motor | `MotorDemo` (padrão): esqueleto marcado, sem IA. `MotorClaude` (`app/motor_claude.py`): relatório dos autos pela API do Claude, só com dados fictícios | verificação de fontes, depois fundamentação; ficha de audiência; leitura de página digitalizada |
| Conexão | `ConexaoPlanilha`: planilha do SIG entra, .docx sai | API do SIG ou MNI do eproc, se o MPSC abrir |

## Segurança (referência: OWASP ASVS)
- Senha com Argon2id, mínimo de 12 caracteres; resposta igual para e-mail inexistente e senha errada.
- Sessão em cookie assinado, `HttpOnly`, `SameSite=Lax`, `Secure` em produção, 8 horas; renovada no login.
- Token CSRF em todo POST e PUT. Limite de 5 tentativas de login por 15 minutos.
- CSP sem `unsafe-inline`; `X-Frame-Options: DENY`; `no-store` nas páginas; HSTS em produção.
- Entrada validada no servidor (tetos de tamanho, estilos em lista fechada); saída escapada pelo Jinja.
- Isolamento por usuário em toda consulta, com teste.
- PDF dos autos: conferido pelo conteúdo; aberto num processo filho em modo isolado, sem o ambiente da aplicação (nenhum segredo), com teto de tempo (60 s), de memória (1 GB) e de processador. Em produção, se o sistema não aplicar os tetos, o PDF não é lido. Nada do arquivo é executado nem servido de volta.
- Limites do envio: 50 MB, 2.000 páginas e 8 milhões de caracteres por arquivo; 5 arquivos e 120 s de leitura por envio; 30 arquivos por processo; 200 milhões de caracteres por usuário.
- O servidor não enfileira leitura: duas ao mesmo tempo no total, uma por usuário; sem vaga, a pessoa é avisada na hora. A conexão do banco é devolvida enquanto o PDF é lido.
- Número de processo com dígito verificador válido (no texto ou no nome do arquivo) barra o envio em servidor de dados fictícios. É um alerta contra engano, não uma garantia: página digitalizada, nome e CPF não são vistos. A regra de só usar dados fictícios continua sendo de quem usa.
- Toda requisição tem teto de tamanho, conferido antes de ler o corpo: 60 MB para quem entrou, 64 KB para quem não entrou.

## Autos
O usuário envia o PDF na tela do processo. Fica guardado o texto de cada página (`arquivos_autos`, `paginas_autos`), com o número da página, para o motor citar de onde tirou cada afirmação. O arquivo original é descartado depois da leitura. Remover o arquivo apaga o texto, inclusive das páginas livres do banco (SQLite, `secure_delete`).

Página digitalizada não tem texto: é contada e avisada. A leitura dessas páginas (OCR ou leitura de imagem pelo motor) é assunto da etapa do motor, e é lá que se decide se o original precisa ser guardado.

## Motor de IA
O usuário envia os autos e pede o relatório na tela do processo. A escrita roda numa tarefa fora da requisição (`tarefas_minuta` guarda o estado); a tela acompanha e recarrega quando termina.

- **O que sai do servidor:** a classe, o assunto e o texto das páginas dos autos daquele processo, inteiro (sem retirar CPF, endereço ou telefone). Não saem o número do processo nem o nome dos arquivos. Destino: API da Anthropic, em endereço e com credencial fixados no código (variável de ambiente que os mudaria impede a partida), com processamento pedido para os Estados Unidos (`inference_geo`). Hoje, só dados fictícios: a aplicação não parte com motor de IA e dado real, e processo com número real não é enviado.
- **O que o modelo pode escrever:** relatório dos fatos, com a página de cada parágrafo, e pontos a enfrentar. A resposta tem formato fixo, sem campo para fundamentação nem pedido. Os pontos ficam numa lista na tela, fora da peça.
- **O que a conferência garante, e o que não garante:** página citada que não foi enviada é descartada. Isso confirma que a página existe, não que ela diz o que o parágrafo afirma. Por isso todo relatório de IA é mostrado como "a conferir": essa é a garantia. Além dela, ficam marcados o parágrafo sem página e os que trazem formas comuns de citação de lei ou julgado e de fórmula de pedido. As marcas não pegam todas as formas.
- **Texto dos autos é dado:** os sinais de menor e de maior do texto são trocados antes do envio, então uma página não fecha as marcas nem forja outra página. A instrução do modelo manda relatar, não obedecer. Uma ordem escondida nos autos pode, no máximo, levar a um parágrafo de relatório errado, que o promotor confere; não muda a estrutura da peça.
- **Sem troca automática de modelo:** se o modelo declina, a escrita falha com aviso, em vez de a API passar o pedido a outro modelo.
- **Registro:** `pedidos_ia` guarda quem pediu, para qual processo, quando, o resultado e o modelo que respondeu. Sem conteúdo. O registro de depuração e a telemetria da biblioteca ficam desligados, porque trariam o texto dos autos.
- **Limites:** 1,5 milhão de caracteres de autos por pedido; uma escrita por vez por usuário e quatro no servidor; 20 pedidos por hora e 60 por dia por usuário; 10 minutos para a resposta inteira, sem nova tentativa automática; escrita com mais de 15 minutos é dada como falha, e um resultado que chegue depois disso é descartado. Os limites de concorrência valem por processo do servidor.

## Decisões
- **13/11/2026 – Projeto separado do Gabinete** (titular). A aplicação web não muda a estrutura do Gabinete; reuso por cópia.
- **13/11/2026 – Páginas feitas no servidor**, com pouco JavaScript: menos peças, carregamento rápido, CSP estrita.
- **13/11/2026 – Só dados fictícios** até haver hospedagem e contrato institucionais.
- **13/11/2026 – Dos autos guarda-se o texto, não o arquivo**: menos dado sensível parado no servidor e nenhuma rota que devolva arquivo enviado.
- **13/11/2026 – Motor pela API do Claude direta** (titular); jurisprudência conferida pelo JuriBase; fonte de legislação vigente a definir.

## O que falta para uso real
As decisões que são do titular estão em `docs/CARTOES.md`.

1. Verificação de fontes, e só então fundamentação escrita pelo motor; leitura das páginas digitalizadas; ficha de audiência pelo motor.
2. Hospedagem e contrato institucionais; parecer de LGPD; registro de acessos.
3. Migrações de banco (Alembic) e Postgres; limite de tentativas em armazenamento compartilhado.
4. Segundo fator no login; troca de senha pela pessoa.
5. Pauta lida do eproc ou do 365, em vez de digitada.
6. Motor de IA, antes de dado real: contrato e parecer (C4), retenção do lado do fornecedor, retirar dados pessoais de terceiros antes do envio, teto de gasto no painel do fornecedor (C8).
7. Prazo de guarda do registro de pedidos à IA (`pedidos_ia`) e exclusão junto com o processo e o usuário.
8. Autos: prazo de guarda do texto e exclusão de processo e de usuário; decidir se a impressão digital (`sha256`) do arquivo continua guardada; rever cota e limites com autos reais.
9. Hospedagem: um processo de servidor só, ou vagas de leitura em armazenamento compartilhado (hoje valem por processo); pasta da aplicação só de leitura; proxy com prazo para o corpo da requisição; disco e pasta temporária cifrados (o envio passa pelo disco antes da leitura); com Postgres, rotina de limpeza no lugar do `secure_delete`.
10. Conferência de dependências no CI (`pip-audit` ou Dependabot) e versões fixadas por hash.
