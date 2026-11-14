# Registro de mudanças

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões em [SemVer](https://semver.org/lang/pt-BR/).

## [0.4.0] - 2026-11-14

### Adicionado
- O texto dos autos é apagado sozinho 30 dias depois de o processo ser concluído (cartão C1). A minuta fica. Se o processo voltar à fila, a contagem para; numa nova conclusão, recomeça.
- Ao concluir, o aviso diz que a minuta fica e em que data o texto dos autos será apagado; a tela do processo concluído repete a data e diz como manter (devolver à fila).
- Processo concluído não recebe autos novos nem pedido de relatório: para isso, devolve-se à fila.
- Comando `python -m app.cli limpar-autos`, para o agendador da hospedagem. Os pontos a enfrentar tirados dos autos pela IA saem junto com os autos.
- A imagem do servidor usa o horário de Brasília: a data prometida na tela é a do usuário.

### Segurança
- O banco não guarda mais o `sha256` do arquivo enviado, nem o tamanho exato do arquivo e a contagem exata de caracteres (cartão C2). A impressão também leva o processo: o mesmo arquivo em dois processos não fica com a mesma impressão. Fica uma impressão feita com chave do servidor: continua avisando arquivo repetido, mas fora do servidor não prova que alguém teve um documento.
- Banco de versão anterior é convertido na partida. No SQLite (`secure_delete`) o valor antigo some do arquivo; num Postgres futuro ele só some depois do VACUUM (ARQUITETURA, item 9). Trocar o segredo do servidor faz os arquivos já guardados deixarem de ser reconhecidos como repetidos.

## [0.3.0] - 2026-11-14

### Adicionado
- Motor de IA pela API do Claude (`NEWMPSC_MOTOR=claude`): na tela do processo, com os autos enviados, o botão "Escrever o relatório" pede o relatório ao modelo. Cada parágrafo sai com a página dos autos de onde veio.
- O motor escreve só o relatório dos fatos. Fundamentação e pedido ficam marcados para o promotor; os pontos a enfrentar aparecem numa lista na tela e não entram no arquivo.
- Trechos a completar ou conferir ficam entre colchetes, destacados na folha. Baixar ou copiar com trechos pendentes pede confirmação.
- A escrita roda fora da tela: a pessoa pode sair e voltar, e a mesa mostra "Escrevendo…", "Relatório pronto" ou "Relatório falhou". Falha do serviço mantém a minuta anterior e mostra o motivo.
- Minuta já editada só é substituída por um relatório novo com confirmação.
- Com o motor de IA, o processo chega à mesa com a minuta em branco e a ficha de audiência sai em branco.

### Segurança
- O motor de IA não liga com dado real, por nenhum caminho de configuração. Em servidor de dados fictícios, processo com número real não é enviado.
- Sai do servidor só a classe, o assunto e o texto das páginas dos autos daquele processo. Não saem o número do processo nem o nome dos arquivos. O processamento é pedido para os Estados Unidos.
- O texto dos autos vai ao modelo como dado, entre marcas que ele não consegue fechar. A resposta só tem campo para relatório e pontos. Parágrafo sem página, com citação jurídica ou com fórmula de pedido sai marcado para conferência.
- Destino e chave do serviço fixados no código; registro de depuração e telemetria da biblioteca desligados; modelo só de uma lista fechada.
- Cada pedido fica registrado (quem, qual processo, quando, qual modelo respondeu), sem conteúdo. Limites por usuário: uma escrita por vez, 20 pedidos por hora e 60 por dia.

## [0.2.0] - 2026-11-13

### Adicionado
- Autos em PDF: na tela do processo, o PDF é enviado e lido página a página. Só o texto fica guardado; o arquivo, não.
- O resultado de cada envio aparece dentro do cartão dos autos. Página sem texto (digitalizada) e arquivo que não cita o número do processo ficam marcados na lista.
- Arquivo com senha para abrir, danificado, com mais de 50 MB, de 2.000 páginas ou com texto demais é recusado com orientação. PDF que só tem restrição de impressão é lido.
- Em servidor de dados fictícios, PDF com número de processo de dígito verificador válido não entra. É um alerta, não uma garantia: não enxerga página digitalizada, nomes nem CPF.

### Segurança
- O PDF é aberto num processo à parte, sem os segredos da aplicação, com teto de tempo, de memória e de processador. Em produção, não lê se o sistema não aplicar os tetos.
- Uma leitura por vez por usuário e duas no servidor; quem não acha vaga é avisado na hora, sem fila. A conexão do banco é devolvida durante a leitura.
- Cota de texto de autos por usuário. Texto removido é apagado também do arquivo do banco (SQLite).
- Teto para o tamanho de toda requisição: 60 MB para quem entrou, 64 KB para quem não entrou.
- FastAPI, Starlette, python-multipart e Jinja2 atualizados para versões sem falha conhecida no envio de arquivo.

### Corrigido
- A coluna lateral da tela do processo rola sozinha quando é mais alta que a janela; o foco do teclado na área de soltar arquivo fica visível.

## [0.1.0] - 2026-11-13

### Adicionado
- Login por convite, com sessão, proteção contra CSRF e limite de tentativas.
- Mesa de processos: importação da planilha do SIG ou colagem de números; fila por prioridade (réu preso, vista urgente, intimação).
- Minuta pronta a um clique, editável numa folha no padrão do Manual de Redação do MPSC, com salvamento automático, exportação .docx e cópia do texto.
- Pauta de audiências com ficha.
- Portas de troca para a IA (motor de demonstração) e para o SIG (planilha).
