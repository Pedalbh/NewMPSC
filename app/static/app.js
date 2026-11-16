// Casca da página: envio da planilha e dos autos, edição e salvamento da minuta, cópia do texto. A lógica fica no servidor.
(() => {
  "use strict";
  const csrf = document.querySelector('meta[name="csrf"]')?.content || "";

  // ---- planilha do SIG e PDF dos autos: escolher ou soltar o arquivo envia na hora
  document.querySelectorAll("label.soltar").forEach((soltar) => {
    const arquivo = soltar.querySelector('input[type="file"]');
    if (!arquivo) return;
    const enviar = () => {
      const titulo = soltar.querySelector(".soltar-titulo");
      const detalhe = soltar.querySelector(".soltar-detalhe");
      if (soltar.dataset.enviando && titulo) titulo.textContent = soltar.dataset.enviando;
      if (soltar.dataset.espera && detalhe) detalhe.textContent = soltar.dataset.espera;
      soltar.classList.add("enviando");
      arquivo.form.setAttribute("aria-busy", "true");
      arquivo.form.submit();
    };
    arquivo.addEventListener("change", () => { if (arquivo.files.length) enviar(); });
    ["dragenter", "dragover"].forEach((ev) => soltar.addEventListener(ev, (e) => {
      e.preventDefault(); soltar.classList.add("sobre");
    }));
    ["dragleave", "drop"].forEach((ev) => soltar.addEventListener(ev, () => soltar.classList.remove("sobre")));
    soltar.addEventListener("drop", (e) => {
      e.preventDefault();
      if (e.dataTransfer?.files.length) { arquivo.files = e.dataTransfer.files; enviar(); }
    });
  });

  // ---- relatório sendo escrito pela IA: acompanha, diz há quanto tempo e recarrega quando termina
  const escrevendo = document.getElementById("escrevendo");
  if (escrevendo) {
    const texto = document.getElementById("espera-texto");
    const inicio = Date.now() - 1000 * Number(escrevendo.dataset.decorrido || 0);
    let minutosDitos = 0;
    const olhar = async () => {
      try {
        const r = await fetch(escrevendo.dataset.acompanhar, { headers: { Accept: "application/json" } });
        // sessão encerrada ou resposta que não é do servidor: recarregar leva ao login ou mostra o estado certo
        if (!r.ok || !(r.headers.get("content-type") || "").includes("json")) { window.location.reload(); return; }
        if ((await r.json()).estado !== "escrevendo") { window.location.reload(); return; }
      } catch { /* sem conexão: tenta de novo */ }
      const minutos = Math.floor((Date.now() - inicio) / 60000);
      if (texto && minutos > minutosDitos) {
        minutosDitos = minutos;
        texto.textContent = minutos >= 4
          ? "Está demorando mais que o normal (há " + minutos + " min). Pode sair desta tela; o resultado fica aqui."
          : "Há " + minutos + " min. Costuma levar de um a três minutos. Pode sair desta tela.";
      }
      setTimeout(olhar, 3000);
    };
    setTimeout(olhar, 3000);
  }
  // resultado da escrita que acabou de chegar: leva o foco até ele, para ser visto e lido em voz alta
  document.querySelector("#resultado-escrita[data-foco]")?.focus();

  // ---- minuta: cada parágrafo é um bloco editável; salva sozinha pouco depois da última tecla
  const folha = document.getElementById("folha");
  const estado = document.getElementById("estado-salvar");
  // trechos entre colchetes que a pessoa ainda precisa completar, conferir ou definir
  const MARCA = /\[(?:(?:CONFERIR|ESCREVER|DEFINIR)[^\]]*|COMARCA|DEMONSTRAÇÃO)\]/g;
  const pendentes = () => (folha ? (folha.innerText.match(MARCA) || []).length : 0);
  const destacar = () => {   // pinta as marcas sem mexer no texto editável
    if (!window.Highlight || !CSS.highlights) return;
    const trechos = [];
    document.querySelectorAll(".folha").forEach((papel) => {   // a folha da mesa e os rascunhos recebidos
      const nos = document.createTreeWalker(papel, NodeFilter.SHOW_TEXT);
      for (let no = nos.nextNode(); no; no = nos.nextNode()) {
        for (const achado of no.data.matchAll(MARCA)) {
          const trecho = new Range();
          trecho.setStart(no, achado.index); trecho.setEnd(no, achado.index + achado[0].length);
          trechos.push(trecho);
        }
      }
    });
    CSS.highlights.set("marca", new Highlight(...trechos));
  };
  // enviar ao SIG: a contagem dos trechos a completar acompanha a digitação, e o envio só é a ação principal sem eles
  const contar = () => {
    const aviso = document.getElementById("trechos");
    const enviar = document.getElementById("enviar-sig");
    if (!aviso || !enviar) return;
    const n = pendentes();
    aviso.hidden = !n;
    aviso.parentElement.hidden = !n && !document.getElementById("mudou");
    aviso.textContent = n === 1 ? "1 trecho entre colchetes a completar" : n + " trechos entre colchetes a completar";
    enviar.classList.toggle("principal", !n && "principal" in enviar.dataset);
  };
  const podeSair = (acao) => {
    const n = pendentes();
    return !n || window.confirm((n === 1 ? "Ainda há 1 trecho entre colchetes a completar. "
      : "Ainda há " + n + " trechos entre colchetes a completar. ") + acao + " assim mesmo?");
  };
  destacar();
  if (folha && estado) {
    let espera = null, pendente = false, salvando = false, conflito = false;
    let versao = Number(folha.dataset.versao || 0);   // a versão que esta tela carregou: o servidor confere ao salvar
    const marcar = (texto, classe) => { estado.textContent = texto; estado.className = "selo empurra " + (classe || ""); };
    const blocos = () => [...folha.querySelectorAll(".b")]
      .map((p) => ({ texto: p.innerText.replace(/ /g, " ").trim(), estilo: p.dataset.estilo }))
      .filter((b) => b.texto);

    const salvar = async () => {
      if (conflito) return;   // outra pessoa salvou por cima: nada daqui é gravado até recarregar
      if (salvando) { pendente = true; return; }
      salvando = true; pendente = false; marcar("Salvando…", "andamento");
      try {
        const r = await fetch(folha.dataset.salvar, {
          method: "PUT", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify({ blocos: blocos(), versao }),
        });
        const d = await r.json().catch(() => ({}));
        if (r.ok) { versao = d.versao; marcar("Salva às " + d.salva_em, "ok"); }
        else if (r.status === 409) {
          conflito = true; pendente = false; marcar("Não salvou", "erro");
          const aviso = document.getElementById("conflito");
          aviso.hidden = false; aviso.focus();
        } else marcar(d.erro || "Não salvou", "erro");
      } catch { marcar("Sem conexão: não salvou", "erro"); }
      salvando = false;
      if (pendente) salvar();
    };
    const agendar = () => {
      if (conflito) return;
      marcar("Alterada", "atencao"); clearTimeout(espera); espera = setTimeout(salvar, 900); destacar(); contar();
    };

    folha.addEventListener("input", agendar);
    folha.addEventListener("paste", (e) => {   // cola sempre como texto simples, sem trazer formatação de fora
      e.preventDefault();
      const texto = (e.clipboardData?.getData("text/plain") || "").replace(/\r/g, "");
      const sel = window.getSelection();
      if (!sel.rangeCount) return;
      sel.deleteFromDocument();
      sel.getRangeAt(0).insertNode(document.createTextNode(texto));
      sel.collapseToEnd();
      agendar();
    });
    folha.addEventListener("keydown", (e) => {
      const p = e.target.closest(".b");
      if (!p) return;
      if (e.key === "Enter" && !e.shiftKey) {   // Enter abre um parágrafo novo de corpo
        e.preventDefault();
        const novo = document.createElement("p");
        novo.className = "b b-corpo"; novo.dataset.estilo = "corpo";
        novo.contentEditable = "true"; novo.spellcheck = true;
        p.after(novo); novo.focus(); agendar();
      } else if (e.key === "Backspace" && !p.innerText.trim() && folha.querySelectorAll(".b").length > 1) {
        e.preventDefault();
        const anterior = p.previousElementSibling || p.nextElementSibling;
        p.remove(); anterior.focus();
        const sel = window.getSelection(); sel.selectAllChildren(anterior); sel.collapseToEnd();
        agendar();
      }
    });
    window.addEventListener("beforeunload", (e) => {
      if (espera && estado.textContent === "Alterada") { e.preventDefault(); }
    });
    // antes de baixar, garante que o arquivo sai com a última versão
    document.getElementById("baixar-docx")?.addEventListener("click", async (e) => {
      if (!podeSair("Baixar")) { e.preventDefault(); return; }
      if (estado.textContent !== "Alterada") return;
      const destino = e.currentTarget.href;
      e.preventDefault(); clearTimeout(espera); await salvar(); window.location.href = destino;
    });
    // voltar pelo navegador devolve a página guardada: o envio precisa estar liberado de novo
    window.addEventListener("pageshow", (e) => {
      const formulario = document.getElementById("form-entregar");
      if (!e.persisted || !formulario) return;
      delete formulario.dataset.pronto;
      formulario.querySelector("button").disabled = false;
    });
    // enviar ao SIG: o rascunho sai com a última versão; trechos a completar pedem confirmação
    document.getElementById("form-entregar")?.addEventListener("submit", async (e) => {
      const formulario = e.currentTarget;
      if (formulario.dataset.pronto) return;
      e.preventDefault();
      if (!podeSair("Enviar ao SIG")) return;
      const botao = formulario.querySelector("button");
      botao.disabled = true;   // um envio só, mesmo com clique duplo
      clearTimeout(espera);
      if (estado.textContent === "Alterada") salvar();
      // espera o salvamento em curso e o que ficou pendente atrás dele: o rascunho leva o que está na tela
      while (salvando || pendente) await new Promise((r) => setTimeout(r, 50));
      if (estado.classList.contains("erro")) { botao.disabled = false; return; }   // não salvou: não envia
      formulario.dataset.pronto = "1"; formulario.submit();
    });
  }

  const copiar = document.getElementById("copiar");
  copiar?.addEventListener("click", async () => {
    if (!podeSair("Copiar")) return;
    const original = copiar.textContent;
    try {
      const texto = folha ? [...folha.querySelectorAll(".b")].map((p) => p.innerText.trim()).filter(Boolean).join("\n\n")
        : await (await fetch(copiar.dataset.origem)).text();
      await navigator.clipboard.writeText(texto);
      copiar.textContent = "Copiado";
    } catch { copiar.textContent = "Não foi possível copiar"; }
    setTimeout(() => { copiar.textContent = original; }, 1800);
  });

  document.getElementById("imprimir")?.addEventListener("click", () => window.print());
})();
