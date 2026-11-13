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
      if (soltar.dataset.enviando && titulo) { titulo.textContent = soltar.dataset.enviando; titulo.setAttribute("role", "status"); }
      soltar.classList.add("enviando");
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

  // ---- minuta: cada parágrafo é um bloco editável; salva sozinha pouco depois da última tecla
  const folha = document.getElementById("folha");
  const estado = document.getElementById("estado-salvar");
  if (folha && estado) {
    let espera = null, pendente = false, salvando = false;
    const marcar = (texto, classe) => { estado.textContent = texto; estado.className = "selo empurra " + (classe || ""); };
    const blocos = () => [...folha.querySelectorAll(".b")]
      .map((p) => ({ texto: p.innerText.replace(/ /g, " ").trim(), estilo: p.dataset.estilo }))
      .filter((b) => b.texto);

    const salvar = async () => {
      if (salvando) { pendente = true; return; }
      salvando = true; pendente = false; marcar("Salvando…", "andamento");
      try {
        const r = await fetch(folha.dataset.salvar, {
          method: "PUT", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify({ blocos: blocos() }),
        });
        const d = await r.json().catch(() => ({}));
        if (r.ok) marcar("Salva às " + d.salva_em, "ok");
        else marcar(d.erro || "Não salvou", "erro");
      } catch { marcar("Sem conexão: não salvou", "erro"); }
      salvando = false;
      if (pendente) salvar();
    };
    const agendar = () => { marcar("Alterada", "atencao"); clearTimeout(espera); espera = setTimeout(salvar, 900); };

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
      if (estado.textContent !== "Alterada") return;
      const destino = e.currentTarget.href;
      e.preventDefault(); clearTimeout(espera); await salvar(); window.location.href = destino;
    });
  }

  const copiar = document.getElementById("copiar");
  copiar?.addEventListener("click", async () => {
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
