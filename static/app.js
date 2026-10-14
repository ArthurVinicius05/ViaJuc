/* Utilitários compartilhados */
const $ = (seletor, raiz = document) => raiz.querySelector(seletor);

const icone = (nome) =>
  `<svg class="ico" aria-hidden="true"><use href="#i-${nome}"></use></svg>`;

const escapar = (valor) =>
  String(valor ?? "").replace(/[&<>"']/g, (caractere) =>
    `&#${caractere.charCodeAt(0)};`,
  );

const dataISO = (valor) =>
  valor ? new Date(valor).toISOString().slice(0, 10) : "";

const dataCurta = (valor) => {
  const data = dataISO(valor);
  return data ? `${data.slice(8, 10)}/${data.slice(5, 7)}` : "";
};

const hoje = (deslocamento = 0) => {
  const data = new Date();
  data.setDate(data.getDate() + deslocamento);
  return new Date(data - data.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 10);
};

// O back-end usa 1 para segunda-feira e 7 para domingo.
const diaDaSemana = (valor) => new Date(`${valor}T12:00`).getDay() || 7;

const chipsHorarios = (horarios = []) =>
  horarios
    .map((horario) => `<span class="chip">${escapar(horario.replace(/^0/, ""))}</span>`)
    .join("");

const formatarPreco = (valor) =>
  valor == null ? "Preço a combinar" : `R$ ${Number(valor).toFixed(2).replace(".", ",")}`;

async function api(url, metodo = "GET", corpo) {
  const resposta = await fetch(url, {
    method: metodo,
    headers: { "Content-Type": "application/json" },
    body: corpo ? JSON.stringify(corpo) : undefined,
  });

  const dados =
    resposta.status === 204 ? {} : await resposta.json().catch(() => ({}));

  if (!resposta.ok) {
    throw new Error(dados.erro || "Algo deu errado. Tente novamente.");
  }

  return dados;
}

function mostrarAviso(elemento, mensagem, sucesso = false) {
  elemento.textContent = mensagem;
  elemento.className = `msg ${sucesso ? "ok" : "erro"}`;
}

function cartaoViagem(rota) {
  return `
    <a class="cartao" href="/rota/${rota.id_rota}">
      <span class="ico-bus">${icone("bus")}</span>
      <div class="corpo">
        <h3>${escapar(rota.origem)} – ${escapar(rota.destino)}</h3>
        <div class="chips">${chipsHorarios(rota.horarios_ida)}</div>
        <p class="pessoa">${icone("user")}${escapar(rota.motorista)}</p>
      </div>
      <span class="seta" aria-hidden="true">›</span>
    </a>`;
}

const paginas = {
  async inicio() {
    const formulario = $("#busca");
    const lista = $("#lista");
    const mensagem = $("#msg");

    $("#data").value = hoje();

    let cidades = [];

    try {
      cidades = await api("/api/cidades");
    } catch (erro) {
      mostrarAviso(mensagem, `Não foi possível carregar as cidades: ${erro.message}`);
    }

    $("#cidades").innerHTML = cidades
      .map((cidade) => `<option value="${escapar(cidade.nome)}">`)
      .join("");

    if (cidades.length < 2) {
      mostrarAviso(
        mensagem,
        "Cadastre pelo menos duas cidades no banco para pesquisar viagens.",
      );
    }

    const idDaCidade = (nome) =>
      cidades.find(
        (cidade) =>
          cidade.nome.toLowerCase() === nome.trim().toLowerCase(),
      )?.id_cidade;

    async function carregarRotas(parametros, mensagemVazia) {
      try {
        const rotas = await api(`/api/rotas?${parametros}`);
        lista.innerHTML = rotas.length
          ? rotas.map(cartaoViagem).join("")
          : `<p class="vazio">${mensagemVazia}</p>`;
      } catch (erro) {
        lista.innerHTML = `<p class="vazio">${escapar(erro.message)}</p>`;
      }
    }

    $("#trocar").addEventListener("click", () => {
      [formulario.origem.value, formulario.destino.value] = [
        formulario.destino.value,
        formulario.origem.value,
      ];
    });

    formulario.addEventListener("submit", (evento) => {
      evento.preventDefault();

      const origem = formulario.origem.value.trim();
      const destino = formulario.destino.value.trim();
      const parametros = new URLSearchParams();

      if (origem && !idDaCidade(origem)) {
        mostrarAviso(mensagem, "Origem não encontrada. Escolha uma cidade da lista.");
        return;
      }

      if (destino && !idDaCidade(destino)) {
        mostrarAviso(mensagem, "Destino não encontrado. Escolha uma cidade da lista.");
        return;
      }

      if (origem && destino && idDaCidade(origem) === idDaCidade(destino)) {
        mostrarAviso(mensagem, "Origem e destino devem ser diferentes.");
        return;
      }

      mostrarAviso(mensagem, "", true);

      if (origem) parametros.set("origem", idDaCidade(origem));
      if (destino) parametros.set("destino", idDaCidade(destino));
      if (formulario.data.value) {
        parametros.set("dia", diaDaSemana(formulario.data.value));
      }

      $("#titulo-lista").textContent = "Resultado da busca";
      carregarRotas(
        parametros,
        "Nenhuma viagem encontrada. Tente outra data ou outras cidades.",
      );
    });

    carregarRotas("", "Ainda não há viagens cadastradas.");
  },

  async rota() {
    const idRota = location.pathname.split("/").pop();
    const mensagem = $("#msg");

    try {
      const [rota, calendario] = await Promise.all([
        api(`/api/rotas/${idRota}`),
        api(`/api/rotas/${idRota}/datas?de=${hoje()}&ate=${hoje(30)}`),
      ]);

      $("#titulo").textContent = `${rota.origem} – ${rota.destino}`;

      const datas = calendario.datas.slice(0, 6);
      $("#datas").innerHTML = datas.length
        ? datas
            .map(
              (data) => `
                <div class="dia">
                  <h4>${dataCurta(data)}</h4>
                  ${rota.horarios_ida
                    .map(
                      (horario) => `
                        <button class="hora" data-h="${escapar(horario)}" data-d="${data}">
                          ${escapar(horario.replace(/^0/, ""))}
                          <span aria-hidden="true">›</span>
                        </button>`,
                    )
                    .join("")}
                </div>`,
            )
            .join("")
        : '<p class="vazio">Esta rota não tem saídas nos próximos 30 dias.</p>';

      $("#datas").addEventListener("click", (evento) => {
        const botao = evento.target.closest(".hora");
        if (!botao) return;

        document.querySelectorAll(".hora.sel").forEach((item) => {
          item.classList.remove("sel");
        });
        botao.classList.add("sel");

        $("#detalhe").innerHTML = `
          <h3>Saída em ${dataCurta(botao.dataset.d)} às ${escapar(botao.dataset.h.replace(/^0/, ""))}</h3>
          <p>Embarque: ${escapar(rota.local_embarque)}. Desembarque: ${escapar(rota.local_desembarque)}.</p>
          <p>${formatarPreco(rota.preco)}</p>
          <p>${escapar(rota.tipo)} ${escapar(rota.modelo)}, placa ${escapar(rota.placa)}</p>
          <p>Motorista: ${escapar(rota.motorista)}, <a href="tel:${escapar(rota.telefone)}">${escapar(rota.telefone)}</a></p>
          ${rota.horarios_volta.length
            ? `<p class="chips">Volta: ${chipsHorarios(rota.horarios_volta)}</p>`
            : ""}`;
      });
    } catch (erro) {
      mostrarAviso(mensagem, erro.message);
    }
  },

  login() {
    const formulario = $("#form");
    const mensagem = $("#msg");

    formulario.addEventListener("submit", async (evento) => {
      evento.preventDefault();

      try {
        await api(formulario.dataset.api, "POST", {
          email: formulario.elements.email.value,
          senha: formulario.elements.senha.value,
        });
        location.href = formulario.dataset.destino;
      } catch (erro) {
        mostrarAviso(mensagem, erro.message);
      }
    });
  },

  cadastro() {
    const formulario = $("#form");
    const mensagem = $("#msg");
    const valor = (nome) => formulario.elements[nome].value.trim();

    formulario.addEventListener("submit", async (evento) => {
      evento.preventDefault();

      const senha = formulario.elements.senha.value;

      try {
        await api("/api/motoristas", "POST", {
          nome: valor("nome"),
          email: valor("email"),
          senha,
          telefone: valor("telefone"),
        });

        await api("/api/auth/motorista/login", "POST", {
          email: valor("email"),
          senha,
        });

        await api("/api/motorista/veiculos", "POST", {
          tipo: valor("tipo"),
          modelo: valor("modelo"),
          placa: valor("placa"),
        });

        location.href = "/motorista/painel";
      } catch (erro) {
        mostrarAviso(mensagem, erro.message);
      }
    });
  },

  async painel() {
    const mensagem = $("#msg");
    const formulario = $("#form");
    const valor = (nome) => formulario.elements[nome].value;

    try {
      await api("/api/auth/me");
    } catch {
      location.href = "/motorista/login";
      return;
    }

    let cidades;
    let veiculos;

    try {
      [cidades, veiculos] = await Promise.all([
        api("/api/cidades"),
        api("/api/motorista/veiculos"),
      ]);
    } catch (erro) {
      mostrarAviso(mensagem, `Não foi possível carregar o formulário: ${erro.message}`);
      return;
    }

    const criarOpcoes = (itens) =>
      itens
        .map(
          ([id, texto]) =>
            `<option value="${id}">${escapar(texto)}</option>`,
        )
        .join("");

    const opcoesCidades = criarOpcoes(
      cidades.map((cidade) => [cidade.id_cidade, cidade.nome]),
    );

    formulario.elements.origem.innerHTML = opcoesCidades;
    formulario.elements.destino.innerHTML = opcoesCidades;
    formulario.elements.veiculo.innerHTML = criarOpcoes(
      veiculos
        .filter((veiculo) => veiculo.ativo)
        .map((veiculo) => [
          veiculo.id_veiculo,
          `${veiculo.modelo} (${veiculo.placa})`,
        ]),
    );

    formulario.elements.data.value = hoje();

    let rotas = [];
    let rotaEmEdicao = null;

    const normalizarHorarios = (texto) =>
      texto
        .split(/[\s,;]+/)
        .filter(Boolean)
        .map((horario) => horario.padStart(5, "0"));

    async function carregarRotas() {
      rotas = await api("/api/motorista/rotas");

      $("#lista").innerHTML = rotas.length
        ? rotas
            .map(
              (rota) => `
                <article class="cartao">
                  <span class="ico-bus">${icone("bus")}</span>
                  <div class="corpo">
                    <h3>${escapar(rota.origem)} – ${escapar(rota.destino)}</h3>
                    <div class="chips">${chipsHorarios(rota.horarios_ida)}</div>
                    <div class="chips">
                      ${rota.data_inicio
                        ? `<span class="chip">${dataCurta(rota.data_inicio)}</span>`
                        : ""}
                    </div>
                  </div>
                  <div class="acoes">
                    <button type="button" data-acao="editar" data-id="${rota.id_rota}" title="Editar" aria-label="Editar rota">${icone("edit")}</button>
                    <button type="button" data-acao="duplicar" data-id="${rota.id_rota}" title="Duplicar" aria-label="Duplicar rota">${icone("copy")}</button>
                    <button type="button" data-acao="excluir" data-id="${rota.id_rota}" title="Excluir" aria-label="Excluir rota">×</button>
                  </div>
                </article>`,
            )
            .join("")
        : '<p class="vazio">Você ainda não tem rotas. Preencha o formulário e clique em Salvar.</p>';
    }

    function preencherFormulario(rota, id = null) {
      rotaEmEdicao = id;

      const valores = {
        origem: rota.id_origem,
        destino: rota.id_destino,
        veiculo: rota.id_veiculo,
        embarque: rota.local_embarque,
        desembarque: rota.local_desembarque,
        preco: rota.preco ?? "",
        ida: rota.horarios_ida.join(", "),
        volta: rota.horarios_volta.join(", "),
        data: dataISO(rota.data_inicio) || hoje(),
      };

      Object.entries(valores).forEach(([nome, valorCampo]) => {
        formulario.elements[nome].value = valorCampo;
      });

      $("#salvar").textContent = id ? "Salvar alterações" : "Salvar";
      formulario.scrollIntoView({ behavior: "smooth" });
    }

    formulario.addEventListener("submit", async (evento) => {
      evento.preventDefault();

      const data = valor("data");
      const origem = valor("origem");
      const destino = valor("destino");

      if (!origem || !destino) {
        mostrarAviso(mensagem, "Selecione uma origem e um destino.");
        return;
      }

      if (origem === destino) {
        mostrarAviso(mensagem, "Origem e destino devem ser diferentes.");
        return;
      }

      const corpo = {
        id_veiculo: Number(valor("veiculo")),
        id_origem: Number(origem),
        id_destino: Number(destino),
        local_embarque: valor("embarque").trim(),
        local_desembarque: valor("desembarque").trim(),
        preco: valor("preco") || null,
        datas_semana: [diaDaSemana(data)],
        data_inicio: data,
        data_fim: data,
        horarios_ida: normalizarHorarios(valor("ida")),
        horarios_volta: normalizarHorarios(valor("volta")),
      };

      try {
        const url = rotaEmEdicao
          ? `/api/motorista/rotas/${rotaEmEdicao}`
          : "/api/motorista/rotas";
        const metodo = rotaEmEdicao ? "PATCH" : "POST";

        await api(url, metodo, corpo);
        mostrarAviso(mensagem, "Rota salva.", true);

        rotaEmEdicao = null;
        $("#salvar").textContent = "Salvar";
        await carregarRotas();
      } catch (erro) {
        mostrarAviso(mensagem, erro.message);
      }
    });

    $("#lista").addEventListener("click", async (evento) => {
      const botao = evento.target.closest("[data-acao]");
      if (!botao) return;

      const rota = rotas.find(
        (item) => item.id_rota === Number(botao.dataset.id),
      );
      if (!rota) return;

      if (botao.dataset.acao === "editar") {
        preencherFormulario(rota, rota.id_rota);
        return;
      }

      if (botao.dataset.acao === "duplicar") {
        preencherFormulario(rota);
        return;
      }

      if (botao.dataset.acao === "excluir" && confirm("Excluir esta rota?")) {
        try {
          await api(`/api/motorista/rotas/${rota.id_rota}`, "DELETE");
          mostrarAviso(mensagem, "Rota excluída.", true);
          await carregarRotas();
        } catch (erro) {
          mostrarAviso(mensagem, erro.message);
        }
      }
    });

    $("#sair").addEventListener("click", async () => {
      try {
        await api("/api/auth/logout", "POST");
        location.href = "/";
      } catch (erro) {
        mostrarAviso(mensagem, erro.message);
      }
    });

    try {
      await carregarRotas();
    } catch (erro) {
      mostrarAviso(mensagem, `Não foi possível carregar suas rotas: ${erro.message}`);
    }
  },
};

paginas[document.body.dataset.page]?.();
