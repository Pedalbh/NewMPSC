# Registro de mudanças

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões em [SemVer](https://semver.org/lang/pt-BR/).

## [0.6.0] - 2026-11-16

### Adicionado
- Espaço da promotoria (cartão C18): quem é da mesma promotoria vê a mesma mesa, com a fila, as minutas, os autos e a pauta. Ninguém de fora vê.
- Dois papéis: promotor e assessor. Os dois preparam a minuta; só o promotor envia ao SIG e tira o rascunho de lá.
- A tela do processo mostra quem alterou a minuta por último.
- Se duas pessoas editam a mesma minuta, quem salva depois é avisado e o texto da outra fica. Antes, o último salvamento apagava o anterior sem aviso.
- Registro de acessos: quem abriu, editou, baixou ou enviou cada processo, e quando, sem conteúdo. Listado por `python -m app.cli acessos "Promotoria"`.
- Linha de comando: `criar-usuario` recebe a promotoria e o papel; `mover-usuario` e `desligar-usuario` trocam ou tiram o acesso na hora, mesmo com a sessão aberta.
- Cartão C20: quem lê o registro de acessos e por quanto tempo ele fica.

### Alterado
- Limite 3 do projeto (`CLAUDE.md`), pelo cartão C18: cada promotoria vê só o que é seu.
- A promotoria deixa de ser um texto que a pessoa edita em "Seus dados": é definida por quem administra.
- Banco de versão anterior: na partida, cada conta ganha uma promotoria só dela e leva o que era seu. Contas não são juntadas sozinhas.
- Os pedidos à IA ficam em nome de quem pediu; a cota de texto dos autos passa a contar por promotoria.

### Corrigido
- Avisos marcados como escondidos apareciam mesmo assim, como uma caixa vazia (o estilo vencia o atributo).

## [0.5.1] - 2026-11-16

### Adicionado
- Materiais da Fase 1 do piloto em `docs/piloto/`: roteiro do ensaio, guia de uma página e termo do participante.
- Pedido de integração para levar à TI (`docs/PEDIDO-TI.md`): ler a fila e depositar rascunho, com as condições do projeto.
- Cartão C19 (onde roda o ensaio da Fase 1). Cartões C16, C17 e C18 decididos: opção A nos três.

### Alterado
- Limite 2 do projeto (`CLAUDE.md`), pelo cartão C16: a aplicação não assina nem protocola; no SIG, só deixa rascunho, por ato do usuário e pela integração oficial.

### Segurança
- Em servidor de dados fictícios, número de processo real não entra mais pela planilha, pela busca no SIG simulado, pela colagem nem pela pauta de audiências. Só entra número claramente fictício (na máscara, com dígito verificador inválido); número sem máscara, com espaços ou sem os zeros da frente também fica de fora, e o mesmo vale para linha da planilha com número real na classe ou no assunto. A tela diz quantas linhas ficaram de fora. O texto livre da minuta não é examinado. Antes a recusa só acontecia nos autos, no pedido à IA e no envio ao SIG.
- `python -m app.cli apagar-processo EMAIL NUMERO` apaga um processo e tudo o que é dele (minuta, autos, rascunho enviado, audiências), para dado que entrou por engano.

## [0.5.0] - 2026-11-15

### Adicionado
- Protótipo do envelope do SIG (`NEWMPSC_SIG=simulado`, só com dados fictícios): um SIG simulado faz o papel do SIG para mostrar o fluxo sem arquivo. Nada chega ao SIG de verdade nem ao eproc.
- Na mesa, o botão "Buscar no SIG" traz a fila com um clique. A planilha exportada continua disponível, recolhida.
- Na tela do processo, "Enviar ao SIG" deixa a minuta no SIG simulado como rascunho, sem assinatura, com recibo, e tira o processo da mesa. Assinar e protocolar continuam sendo da pessoa, no SIG. Trechos entre colchetes pedem confirmação antes do envio e vão contados no recibo.
- Tela "SIG simulado": o outro lado, com a fila que o SIG tem e os rascunhos que recebeu, cada um com o texto como chegou.
- Devolver o processo à fila retira o rascunho do SIG simulado; enviar de novo troca o rascunho. A tela avisa quando a minuta muda depois do envio.
- O rascunho chega ao SIG simulado com a formatação da folha. A contagem dos trechos a completar aparece acima do botão de enviar e acompanha a digitação.
- Se o SIG simulado não responde, a tela diz o que fazer e nada muda na mesa.
- Plano do piloto em promotorias criminais (`docs/PILOTO.md`) e três cartões novos para o titular (C16, C17 e C18).

### Alterado
- Os avisos de importação flexionam o número ("1 processo novo", "9 processos novos").

### Corrigido
- A marca "[CONFERIR: citação]" não dispara mais em palavras como "resposta" e "respeito" (o padrão de "REsp" casava com o começo da palavra).

### Segurança
- `NEWMPSC_DADOS_FICTICIOS` só aceita `0` ou `1`; qualquer outro valor impede a partida. Antes, `false` ou vazio passavam por "fictício" e soltavam as travas do motor de IA e do SIG simulado.
- O SIG simulado não liga com dado real, nem pelo ambiente nem montando a aplicação por código. Processo com número real não é enviado em servidor de dados fictícios.
- A porta do SIG recebe quem pede a fila e quem envia o rascunho: a integração oficial age com a identidade da pessoa, não com conta de serviço. Com a planilha (o padrão), as rotas da busca direta não existem.
- Rascunhos e fila do SIG simulado são filtrados por usuário, com teste de isolamento.

## [0.4.1] - 2026-11-14

### Alterado
- Se o modelo padrão (`claude-opus-5-5`) declinar o relatório antes de escrever, o próprio serviço passa o pedido ao `claude-opus-5`, e só a ele (cartão C14). Se declinar no meio da resposta, a escrita falha com aviso, para não juntar texto de quem declinou. Os outros modelos da lista seguem sem reserva.
- O registro do pedido guarda os modelos que receberam os autos, também quando a escrita falha.
- Pendente: confirmar com a chave da API (C8) que o `claude-opus-5` é reserva aceita para o `claude-opus-5-5`; se não for, todo pedido com o modelo padrão volta recusado.

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
