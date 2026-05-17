    const POLLING_INTERVALO_MS = 5000;
    const COLSPAN_TOP5 = 6;
    const STATUS_SEM_TREINO = new Set(["aguardando", "erro"]);
    const IDS_GRAFICOS = [
      "grafico_top5",
      "grafico_evolucao",
      "grafico_melhor_inner",
      "grafico_residuos_inner",
    ];

    const ELEMENTOS = Object.freeze({
      statusBadge: document.getElementById("status_badge"),
      statusValor: document.getElementById("status_valor"),
      modoValor: document.getElementById("modo_valor"),
      rodadaValor: document.getElementById("rodada_valor"),
      execucoesValor: document.getElementById("execucoes_valor"),
      melhorErroValor: document.getElementById("melhor_erro_valor"),
      melhorArimaValor: document.getElementById("melhor_arima_valor"),
      tendenciaValor: document.getElementById("tendencia_valor"),
      mapeValor: document.getElementById("mape_valor"),
      barraProgresso: document.getElementById("barra_progresso"),
      textoProgresso: document.getElementById("texto_progresso"),
      fonteEstado: document.getElementById("fonte_estado"),
      top5Tbody: document.getElementById("top5_tbody"),
      configuracaoLinhas: document.getElementById("configuracao_linhas"),
      resumoLinhas: document.getElementById("resumo_linhas"),
      logs: document.getElementById("logs"),
    });
    const LIMITE_LOGS_PAINEL = 80;
    const LOGS_PAINEL = [];

    function escaparHtml(valor) {
      const texto = valor === null || valor === undefined ? "" : String(valor);
      return texto
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function valorOuTraco(valor) {
      return valor === null || valor === undefined || valor === "" ? "-" : valor;
    }

    function numeroOuZero(valor) {
      const numero = Number(valor);
      return Number.isFinite(numero) ? numero : 0;
    }

    function formatarNumero(valor, casas = 6) {
      const numero = Number(valor);
      return Number.isFinite(numero) ? numero.toFixed(casas) : "-";
    }

    function formatarPercentual(valor, casas = 2) {
      const numero = Number(valor);
      return Number.isFinite(numero) ? `${numero.toFixed(casas)}%` : "-";
    }

    function formatarDataBr(valorData) {
      if (!valorData) {
        return "-";
      }

      const data = new Date(valorData);
      if (Number.isNaN(data.getTime())) {
        return String(valorData).split(" ")[0];
      }

      const dia = String(data.getDate()).padStart(2, "0");
      const mes = String(data.getMonth() + 1).padStart(2, "0");
      const ano = data.getFullYear();
      return `${dia}/${mes}/${ano}`;
    }

    function obterListaMelhores(estado) {
      return Array.isArray(estado.melhores) ? estado.melhores : [];
    }

    function obterMelhorModelo(estado) {
      const melhores = obterListaMelhores(estado);
      return melhores.length ? melhores[0] : null;
    }

    function construirTextoPeriodo(inicio, fim) {
      return `${formatarDataBr(inicio)} até ${formatarDataBr(fim)}`;
    }

    function filtrarUltimosDias(datas, valores, quantidadeDias = 30) {
      if (!Array.isArray(datas) || !Array.isArray(valores)) {
        return { datas: [], valores: [] };
      }

      const tamanho = Math.min(datas.length, valores.length);
      const paresValidos = [];

      for (let indice = 0; indice < tamanho; indice += 1) {
        const data = new Date(datas[indice]);
        const valor = Number(valores[indice]);

        if (!Number.isNaN(data.getTime()) && Number.isFinite(valor)) {
          paresValidos.push({ data, valor });
        }
      }

      if (!paresValidos.length) {
        return { datas: [], valores: [] };
      }

      const ultimaData = new Date(paresValidos[paresValidos.length - 1].data);
      const dataLimite = new Date(ultimaData);
      dataLimite.setDate(dataLimite.getDate() - quantidadeDias);

      const filtrados = paresValidos.filter((item) => item.data >= dataLimite);
      return {
        datas: filtrados.map((item) => item.data.toISOString()),
        valores: filtrados.map((item) => item.valor),
      };
    }

    function calcularResiduos(datas, reais, previsoes) {
      if (!Array.isArray(datas) || !Array.isArray(reais) || !Array.isArray(previsoes)) {
        return { datas: [], valores: [] };
      }

      const tamanho = Math.min(datas.length, reais.length, previsoes.length);
      const residuos = [];

      for (let indice = 0; indice < tamanho; indice += 1) {
        const real = Number(reais[indice]);
        const previsto = Number(previsoes[indice]);

        if (Number.isFinite(real) && Number.isFinite(previsto)) {
          residuos.push({
            data: datas[indice],
            valor: real - previsto,
          });
        }
      }

      return {
        datas: residuos.map((item) => item.data),
        valores: residuos.map((item) => item.valor),
      };
    }

    function renderizarLinhas(linhas) {
      return linhas.map(([chave, valor]) => `
        <div class="info-row">
          <span class="info-chave">${escaparHtml(chave)}</span>
          <span class="info-valor">${escaparHtml(valor)}</span>
        </div>
      `).join("");
    }

    function atualizarBadgeStatus(status) {
      const statusNormalizado = String(status || "aguardando").toLowerCase();
      ELEMENTOS.statusBadge.className = "badge";

      if (statusNormalizado === "erro") {
        ELEMENTOS.statusBadge.classList.add("erro");
      } else if (statusNormalizado === "aguardando") {
        ELEMENTOS.statusBadge.classList.add("aguardando");
      }

      ELEMENTOS.statusBadge.textContent = `Status: ${statusNormalizado}`;
    }

    function atualizarFonteEstado(estado) {
      const origem = estado._arquivo_estado || estado._arquivo_estado_esperado || estado._pasta_estado || "-";
      ELEMENTOS.fonteEstado.textContent = `Origem do estado: ${origem}`;
    }

    function _normalizarErro(erro) {
      if (!erro) {
        return "Erro desconhecido";
      }
      if (erro instanceof Error) {
        return `${erro.name}: ${erro.message}`;
      }
      return String(erro);
    }

    function _serializarDetalhesLog(detalhes) {
      if (!detalhes) {
        return "";
      }
      try {
        return JSON.stringify(detalhes);
      } catch (_erro) {
        return String(detalhes);
      }
    }

    function registrarLogPainel(nivel, mensagem, detalhes) {
      const nivelNormalizado = String(nivel || "info").toUpperCase();
      const timestamp = new Date().toLocaleTimeString("pt-BR");
      const sufixo = _serializarDetalhesLog(detalhes);
      const linha = sufixo
        ? `[${timestamp}] [${nivelNormalizado}] ${mensagem} | ${sufixo}`
        : `[${timestamp}] [${nivelNormalizado}] ${mensagem}`;

      LOGS_PAINEL.push(linha);
      if (LOGS_PAINEL.length > LIMITE_LOGS_PAINEL) {
        LOGS_PAINEL.splice(0, LOGS_PAINEL.length - LIMITE_LOGS_PAINEL);
      }

      if (nivelNormalizado === "ERROR") {
        console.error(linha);
      } else if (nivelNormalizado === "WARN") {
        console.warn(linha);
      } else {
        console.info(linha);
      }
    }

    function limparGraficos() {
      IDS_GRAFICOS.forEach((id) => {
        const elemento = document.getElementById(id);
        if (!elemento) {
          return;
        }

        elemento.innerHTML = "";
        if (typeof Plotly !== "undefined") {
          Plotly.purge(id);
        }
      });
    }

    function criarEixoXTemporal() {
      return {
        type: "date",
        tickformat: "%d/%m\n%H:%M",
        hoverformat: "%d/%m/%Y %H:%M",
        nticks: 8,
        rangeslider: { visible: true },
        rangeselector: {
          buttons: [
            { count: 1, label: "1d", step: "day", stepmode: "backward" },
            { count: 7, label: "7d", step: "day", stepmode: "backward" },
            { count: 30, label: "30d", step: "day", stepmode: "backward" },
            { step: "all", label: "Tudo" }
          ]
        }
      };
    }

    function criarLayoutGrafico(titulo, opcoesExtras = {}) {
      return {
        title: titulo,
        height: 320,
        paper_bgcolor: "#1d2025",
        plot_bgcolor: "#1d2025",
        font: { color: "#e0e2e9" },
        margin: { l: 55, r: 20, t: 45, b: 55 },
        legend: {
          orientation: "h",
          y: -0.25
        },
        ...opcoesExtras,
      };
    }

    function renderizarGrafico(id, traces, layout) {
      if (typeof Plotly === "undefined") {
        throw new Error("Biblioteca Plotly.js não foi carregada.");
      }

      const possuiDados = Array.isArray(traces) && traces.length > 0;
      const layoutFinal = possuiDados
        ? layout
        : criarLayoutGrafico(layout && layout.title ? layout.title : "Gráfico", {
          annotations: [{
            text: "Sem dados suficientes para exibir este gráfico.",
            x: 0.5,
            y: 0.5,
            xref: "paper",
            yref: "paper",
            showarrow: false,
            font: { color: "#c0c7d3", size: 13 },
          }],
          xaxis: { visible: false },
          yaxis: { visible: false },
        });

      Plotly.react(id, possuiDados ? traces : [], layoutFinal, {
        responsive: true,
        displayModeBar: false,
      });
    }

    function montarTraceSerie(nome, serie, modo = "lines") {
      const datas = serie && Array.isArray(serie.datas) ? serie.datas : [];
      const valores = serie && Array.isArray(serie.valores) ? serie.valores : [];
      const tamanho = Math.min(datas.length, valores.length);

      if (tamanho === 0) {
        registrarLogPainel("warn", `Série sem dados para gráfico: ${nome}`, {
          possuiSerie: Boolean(serie),
          tamanhoDatas: datas.length,
          tamanhoValores: valores.length,
        });
        return null;
      }

      return {
        x: datas.slice(0, tamanho),
        y: valores.slice(0, tamanho),
        name: nome,
        type: "scatter",
        mode: modo,
        hovertemplate: "%{x|%d/%m/%Y %H:%M}<br>%{y}<extra>%{fullData.name}</extra>",
      };
    }

    function montarTraceBarra(nome, serie) {
      const datas = serie && Array.isArray(serie.datas) ? serie.datas : [];
      const valores = serie && Array.isArray(serie.valores) ? serie.valores : [];
      const tamanho = Math.min(datas.length, valores.length);

      if (tamanho === 0) {
        registrarLogPainel("warn", `Série sem dados para gráfico de barras: ${nome}`, {
          possuiSerie: Boolean(serie),
          tamanhoDatas: datas.length,
          tamanhoValores: valores.length,
        });
        return null;
      }

      return {
        x: datas.slice(0, tamanho),
        y: valores.slice(0, tamanho),
        name: nome,
        type: "bar",
        hovertemplate: "%{x|%d/%m/%Y %H:%M}<br>%{y}<extra>%{fullData.name}</extra>",
      };
    }

    function agruparSeriePorDia(datas, valores, estrategia = "ultimo") {
      if (!Array.isArray(datas) || !Array.isArray(valores)) {
        return { datas: [], valores: [] };
      }

      const tamanho = Math.min(datas.length, valores.length);
      const grupos = {};

      for (let indice = 0; indice < tamanho; indice += 1) {
        const data = new Date(datas[indice]);
        const valor = Number(valores[indice]);

        if (Number.isNaN(data.getTime()) || !Number.isFinite(valor)) {
          continue;
        }

        const chaveDia = data.toISOString().slice(0, 10);

        if (!grupos[chaveDia]) {
          grupos[chaveDia] = {
            datas: [],
            valores: []
          };
        }

        grupos[chaveDia].datas.push(data);
        grupos[chaveDia].valores.push(valor);
      }

      const diasOrdenados = Object.keys(grupos).sort();
      const datasAgrupadas = [];
      const valoresAgrupados = [];

      for (const dia of diasOrdenados) {
        const grupo = grupos[dia];
        let valorAgrupado;

        if (estrategia === "ultimo") {
          valorAgrupado = grupo.valores[grupo.valores.length - 1];
        } else if (estrategia === "media") {
          const soma = grupo.valores.reduce((acc, val) => acc + val, 0);
          valorAgrupado = soma / grupo.valores.length;
        } else if (estrategia === "soma") {
          valorAgrupado = grupo.valores.reduce((acc, val) => acc + val, 0);
        } else {
          valorAgrupado = grupo.valores[grupo.valores.length - 1];
        }

        datasAgrupadas.push(dia);
        valoresAgrupados.push(valorAgrupado);
      }

      return {
        datas: datasAgrupadas,
        valores: valoresAgrupados
      };
    }

    function criarLinhaZero(datas) {
      if (!datas.length) {
        return null;
      }

      return {
        x: datas,
        y: datas.map(() => 0),
        name: "Linha zero",
        type: "scatter",
        mode: "lines",
        line: { dash: "dash" },
      };
    }

    function preencherCardPrincipal(estado) {
      const progresso = Math.max(0, Math.min(100, numeroOuZero(estado.progresso_percentual)));
      const melhor = obterMelhorModelo(estado);

      ELEMENTOS.statusValor.textContent = valorOuTraco(estado.status);
      ELEMENTOS.modoValor.textContent = `Modo: ${valorOuTraco(estado.modo)}`;
      ELEMENTOS.rodadaValor.textContent = `${estado.rodada_atual || 0} / ${estado.total_rodadas || 0}`;
      ELEMENTOS.execucoesValor.textContent = `Testados: ${estado.execucoes_concluidas || 0} / ${estado.execucoes_total || 0}`;
      ELEMENTOS.melhorErroValor.textContent = formatarNumero(estado.melhor_erro);
      ELEMENTOS.melhorArimaValor.textContent = Array.isArray(estado.melhor_parametro)
        ? `(${estado.melhor_parametro.join(", ")})`
        : "-";
      ELEMENTOS.tendenciaValor.textContent = `Tendência: ${valorOuTraco(estado.trend)}`;
      ELEMENTOS.mapeValor.textContent = melhor ? formatarPercentual(melhor.mape) : "-";
      ELEMENTOS.barraProgresso.style.width = `${progresso.toFixed(2)}%`;
      ELEMENTOS.textoProgresso.textContent = `Progresso geral: ${progresso.toFixed(2)}%`;
    }

    function preencherResumoEConfiguracao(estado) {
      const configuracao = estado.configuracao_execucao || {};
      const periodos = estado.periodos || {};
      const resumo = estado.resumo_rodada || {};

      const linhasExecucao = [
        ["Execuções por rodada", valorOuTraco(configuracao.execucoes_por_rodada)],
        ["Top K", valorOuTraco(configuracao.top_k)],
        ["Semente", valorOuTraco(configuracao.semente_aleatoria)],
        ["Intervalo p", JSON.stringify(configuracao.intervalo_p === undefined ? "-" : configuracao.intervalo_p)],
        ["Intervalo d", JSON.stringify(configuracao.intervalo_d === undefined ? "-" : configuracao.intervalo_d)],
        ["Intervalo q", JSON.stringify(configuracao.intervalo_q === undefined ? "-" : configuracao.intervalo_q)],
        ["Max tentativas", valorOuTraco(configuracao.max_tentativas)],
      ];

      const linhasPeriodo = [
        ["Treino", construirTextoPeriodo(periodos.inicio_treino, periodos.fim_treino)],
        ["Avaliação", construirTextoPeriodo(periodos.inicio_avaliacao, periodos.fim_avaliacao)],
        ["Qtd treino", valorOuTraco(periodos.qtd_treino)],
        ["Qtd avaliação", valorOuTraco(periodos.qtd_avaliacao)],
      ];

      const linhasResumo = [
        ["Rodada atual", valorOuTraco(resumo.rodada_atual)],
        ["Testados", valorOuTraco(resumo.testados)],
        ["Válidos", valorOuTraco(resumo.validos)],
        ["Falhas", valorOuTraco(resumo.falhas)],
        ["Melhor taxa de erro da rodada", valorOuTraco(resumo.melhor_erro_rodada)],
        ["Taxa de erro média da rodada", valorOuTraco(resumo.erro_medio_rodada)],
        ["Pior taxa de erro da rodada", valorOuTraco(resumo.pior_erro_rodada)],
        ["Novo melhor geral", resumo.novo_melhor_geral ? "Sim" : "Não"],
      ];

      ELEMENTOS.configuracaoLinhas.innerHTML = `
        <p class="section-title">Execução</p>
        <div class="info-list">${renderizarLinhas(linhasExecucao)}</div>
        <p class="section-title section-title--spaced">Período</p>
        <div class="info-list">${renderizarLinhas(linhasPeriodo)}</div>
      `;

      ELEMENTOS.resumoLinhas.innerHTML = renderizarLinhas(linhasResumo);
    }

    function preencherTabelaTop5(estado) {
      const melhores = obterListaMelhores(estado).slice(0, 5);
      ELEMENTOS.top5Tbody.innerHTML = "";

      if (!melhores.length) {
        ELEMENTOS.top5Tbody.innerHTML = `<tr><td colspan="${COLSPAN_TOP5}">Nenhum indivíduo válido disponível até o momento.</td></tr>`;
        return;
      }

      melhores.forEach((item) => {
        const linha = document.createElement("tr");
        const parametros = Array.isArray(item.parametros) ? `(${item.parametros.join(", ")})` : "-";
        const observacao = item.rank === 1 ? "Melhor atual" : "Alternativa";

        linha.innerHTML = `
          <td>${valorOuTraco(item.rank)}</td>
          <td>${formatarNumero(item.erro)}</td>
          <td>${formatarPercentual(item.mape)}</td>
          <td>ARIMA</td>
          <td>${escaparHtml(parametros)}</td>
          <td>${escaparHtml(observacao)}</td>
        `;

        ELEMENTOS.top5Tbody.appendChild(linha);
      });
    }

    function atualizarGraficos(estado) {
      const treino = estado.treino || {};
      const avaliacao = estado.avaliacao_real || {};
      const melhores = obterListaMelhores(estado);
      const melhor = obterMelhorModelo(estado);

      const treinoFiltrado = filtrarUltimosDias(treino.datas || [], treino.valores || [], 30);
      const avaliacaoFiltrada = filtrarUltimosDias(avaliacao.datas || [], avaliacao.valores || [], 30);

      const tracesTop5 = [
        montarTraceSerie("Treino", treinoFiltrado),
        montarTraceSerie("Avaliação real", avaliacaoFiltrada),
        ...melhores.slice(0, 5).map((item) => {
          try {
            const previsao = filtrarUltimosDias(avaliacao.datas || [], item.previsoes || [], 30);
            const parametros = Array.isArray(item.parametros) ? `(${item.parametros.join(",")})` : "";
            const erro = formatarNumero(item.erro, 4);
            return montarTraceSerie(`ARIMA${parametros} - erro ${erro}`, previsao);
          } catch (erro) {
            registrarLogPainel("error", "Falha ao montar trace de previsão Top 5", {
              erro: _normalizarErro(erro),
              item,
            });
            return null;
          }
        }),
      ].filter(Boolean);

      renderizarGrafico(
        "grafico_top5",
        tracesTop5,
        criarLayoutGrafico("Comparação dos 5 melhores indivíduos", {
          xaxis: criarEixoXTemporal(),
          yaxis: { title: "Valor da série / preço BTC" },
        }),
      );

      const tracesMelhor = [
        montarTraceSerie("Avaliação real", avaliacaoFiltrada),
      ];

      if (melhor) {
        const previsaoMelhor = filtrarUltimosDias(avaliacao.datas || [], melhor.previsoes || [], 30);
        const parametros = Array.isArray(melhor.parametros) ? `(${melhor.parametros.join(",")})` : "";
        tracesMelhor.push(montarTraceSerie(`Melhor ARIMA${parametros}`, previsaoMelhor));
      }
      renderizarGrafico(
        "grafico_melhor_inner",
        tracesMelhor.filter(Boolean),
        criarLayoutGrafico("Melhor indivíduo atual", {
          xaxis: criarEixoXTemporal(),
        }),
      );

      const tracesResiduos = [];
      if (melhor) {
        const residuos = calcularResiduos(
          avaliacao.datas || [],
          avaliacao.valores || [],
          melhor.previsoes || [],
        );
        const residuosFiltrados = filtrarUltimosDias(residuos.datas, residuos.valores, 2);

        tracesResiduos.push(montarTraceBarra("Resíduo real - previsto", residuosFiltrados));
        tracesResiduos.push(criarLinhaZero(residuosFiltrados.datas));
      }

      renderizarGrafico(
        "grafico_residuos_inner",
        tracesResiduos.filter(Boolean),
        criarLayoutGrafico("Resíduos do melhor modelo - avaliação", {
          xaxis: criarEixoXTemporal(),
          yaxis: { title: "Real - previsto" },
        }),
      );

      const historico = Array.isArray(estado.historico_melhor_erro) ? estado.historico_melhor_erro : [];
      const traceHistorico = historico.length ? [{
        x: historico.map((item) => item.rodada),
        y: historico.map((item) => item.erro),
        name: "Melhor taxa de erro",
        type: "scatter",
        mode: "lines+markers",
      }] : [];

      renderizarGrafico(
        "grafico_evolucao",
        traceHistorico,
        criarLayoutGrafico("Evolução do melhor erro por rodada"),
      );
    }

    function preencherLogs(linhasBase, errosRenderizacao = []) {
      const linhas = Array.isArray(linhasBase) ? [...linhasBase] : [];

      if (errosRenderizacao.length) {
        linhas.push("");
        linhas.push("Erros de renderização detectados:");
        linhas.push(...errosRenderizacao);
      }

      if (LOGS_PAINEL.length) {
        linhas.push("");
        linhas.push("Logs internos do dashboard:");
        linhas.push(...LOGS_PAINEL.slice(-20));
      }

      ELEMENTOS.logs.textContent = linhas.filter(Boolean).join("\n");
    }

    // Funções para renderizar as novas seções de memória de parâmetros
    function renderizarMemoriaParametros(estado) {
      const memoria = estado.memoria_parametros || {};
      const tbody = document.getElementById("memoria_tbody");
      if (!tbody) return;

      const linhas = [
        ["Habilitada", memoria.habilitada ? "Sim" : "Não"],
        ["Arquivo", memoria.arquivo || "-"],
        ["Data memória anterior", memoria.data_memoria_anterior || "-"],
        ["Parâmetros herdados testados", memoria.quantidade_herdados_testados || 0],
        ["Destaques do dia", memoria.quantidade_destaques_dia || 0],
        ["Consolidados 2 dias", memoria.quantidade_consolidados || 0]
      ];

      tbody.innerHTML = linhas.map(([chave, valor]) => `
        <tr>
          <td>${escaparHtml(chave)}</td>
          <td>${escaparHtml(valor)}</td>
        </tr>
      `).join("");
    }

    function renderizarDestaquesDia(estado) {
      const destaques = estado.destaques_dia || [];
      const tbody = document.getElementById("destaques_tbody");
      const mensagem = document.getElementById("mensagem_sem_destaques");
      
      if (!tbody) return;
      
      if (!destaques.length) {
        tbody.innerHTML = `<tr><td colspan="6">Sem destaques do dia disponíveis.</td></tr>`;
        if (mensagem) mensagem.style.display = "block";
        return;
      }
      
      if (mensagem) mensagem.style.display = "none";
      
      tbody.innerHTML = destaques.map((item) => `
        <tr>
          <td>${valorOuTraco(item.rank)}</td>
          <td>${Array.isArray(item.parametros) ? `(${item.parametros.join(", ")})` : "-"}</td>
          <td>${formatarNumero(item.smape)}</td>
          <td>${formatarPercentual(item.mape)}</td>
          <td>${formatarNumero(item.erro)}</td>
          <td>${valorOuTraco(item.origem)}</td>
        </tr>
      `).join("");
    }

    function renderizarConsolidados2Dias(estado) {
      const consolidados = estado.consolidados_2dias || [];
      const tbody = document.getElementById("consolidados_tbody");
      const mensagem = document.getElementById("mensagem_sem_consolidados");
      
      if (!tbody) return;
      
      if (!consolidados.length) {
        tbody.innerHTML = `<tr><td colspan="7">Sem dados consolidados disponíveis. Eles aparecerão após a segunda execução diária.</td></tr>`;
        if (mensagem) mensagem.style.display = "block";
        return;
      }
      
      if (mensagem) mensagem.style.display = "none";
      
      tbody.innerHTML = consolidados.map((item) => `
        <tr>
          <td>${valorOuTraco(item.rank)}</td>
          <td>${Array.isArray(item.parametros) ? `(${item.parametros.join(", ")})` : "-"}</td>
          <td>${formatarNumero(item.smape_anterior)}</td>
          <td>${formatarNumero(item.smape_atual)}</td>
          <td>${formatarNumero(item.smape_medio_2dias)}</td>
          <td>${valorOuTraco(item.rank_anterior)}</td>
          <td>${valorOuTraco(item.rank_atual)}</td>
        </tr>
      `).join("");
    }

    function renderizarCandidatosProximoDia(estado) {
      const candidatos = estado.candidatos_proximo_dia || [];
      const tbody = document.getElementById("candidatos_tbody");
      const mensagem = document.getElementById("mensagem_sem_candidatos");
      
      if (!tbody) return;
      
      if (!candidatos.length) {
        tbody.innerHTML = `<tr><td colspan="4">Sem candidatos para o próximo dia disponíveis.</td></tr>`;
        if (mensagem) mensagem.style.display = "block";
        return;
      }
      
      if (mensagem) mensagem.style.display = "none";
      
      tbody.innerHTML = candidatos.map((item) => `
        <tr>
          <td>${Array.isArray(item.parametros) ? `(${item.parametros.join(", ")})` : "-"}</td>
          <td>${valorOuTraco(item.origem)}</td>
          <td>${formatarNumero(item.smape)}</td>
          <td>${valorOuTraco(item.rank)}</td>
        </tr>
      `).join("");
    }

    function renderizarEstadoSemTreino(estado) {
      preencherCardPrincipal(estado);
      ELEMENTOS.configuracaoLinhas.innerHTML = "";
      ELEMENTOS.resumoLinhas.innerHTML = "";
      ELEMENTOS.top5Tbody.innerHTML = `<tr><td colspan="${COLSPAN_TOP5}">${escaparHtml(estado.mensagem || "Sem dados disponíveis.")}</td></tr>`;
      limparGraficos();

      preencherLogs([
        estado.mensagem || "Sem dados disponíveis.",
        estado._pasta_estado ? `Pasta monitorada: ${estado._pasta_estado}` : "",
        estado._arquivo_estado_esperado ? `Arquivo de estado esperado: ${estado._arquivo_estado_esperado}` : "",
        estado._arquivo_historico_esperado ? `Arquivo de histórico esperado: ${estado._arquivo_historico_esperado}` : "",
        estado._arquivo_estado ? `Arquivo monitorado: ${estado._arquivo_estado}` : "",
      ]);
    }

    function executarComProtecao(etapa, funcao) {
      try {
        funcao();
        return null;
      } catch (erro) {
        const mensagem = `[${etapa}] ${_normalizarErro(erro)}`;
        registrarLogPainel("error", "Falha em etapa de renderização", { etapa, erro: mensagem });
        return mensagem;
      }
    }

    function renderizarEstadoCompleto(estado) {
      const errosRenderizacao = [];
      const etapas = [
        ["cards", () => preencherCardPrincipal(estado)],
        ["configuracao", () => preencherResumoEConfiguracao(estado)],
        ["tabela", () => preencherTabelaTop5(estado)],
        ["graficos", () => atualizarGraficos(estado)],
        ["memoria", () => renderizarMemoriaParametros(estado)],
        ["destaques", () => renderizarDestaquesDia(estado)],
        ["consolidados", () => renderizarConsolidados2Dias(estado)],
        ["candidatos", () => renderizarCandidatosProximoDia(estado)],
      ];

      etapas.forEach(([etapa, funcao]) => {
        const erro = executarComProtecao(etapa, funcao);
        if (erro) {
          errosRenderizacao.push(erro);
        }
      });

      const linhasLog = Array.isArray(estado.logs) ? [...estado.logs] : [];
      preencherLogs(linhasLog, errosRenderizacao);
    }

    async function buscarEstadoAtual() {
      const resposta = await fetch("/api/estado", { cache: "no-store" });
      if (!resposta.ok) {
        throw new Error(`Falha HTTP ${resposta.status}`);
      }
      return resposta.json();
    }

    async function atualizarPainel() {
      try {
        const estado = await buscarEstadoAtual();
        const statusNormalizado = String(estado.status || "aguardando").toLowerCase();
        atualizarBadgeStatus(statusNormalizado);
        atualizarFonteEstado(estado);

        if (STATUS_SEM_TREINO.has(statusNormalizado)) {
          renderizarEstadoSemTreino(estado);
          return;
        }

        renderizarEstadoCompleto(estado);
      } catch (erro) {
        registrarLogPainel("error", "Erro ao atualizar painel", { erro: _normalizarErro(erro) });
        atualizarBadgeStatus("erro");
        preencherLogs([`Erro ao atualizar painel: ${_normalizarErro(erro)}`]);
      }
    }

    // Busca o estado imediatamente e depois mantém o polling periódico.
    atualizarPainel();
    setInterval(atualizarPainel, POLLING_INTERVALO_MS);
