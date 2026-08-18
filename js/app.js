/**
 * app.js — Inicialização do mapa e orquestração geral
 *
 * - Cria o mapa Leaflet com tiles escuros (CartoDB Dark Matter)
 * - Plota marcadores dos hubs (de data.js)
 * - Conecta o painel lateral com a ferramenta de medição (measurement.js)
 */

/* ══════════════════════════════════════════════════════════════════════════════
   Variáveis globais
   ══════════════════════════════════════════════════════════════════════════════ */

let map;
let measurementTool;
let hubMarkers = {};  // id → L.marker
let partnerMarkers = {}; // partner_id → L.circleMarker
let partnerLayerGroup;
let flowLayerGroup;

/**
 * Formata um número para o padrão de exibição brasileiro.
 */
function formatarNumero(num) {
    if (num === null || num === undefined) return "0";
    return Number(num).toLocaleString("pt-BR");
}

/* ══════════════════════════════════════════════════════════════════════════════
   Inicialização
   ══════════════════════════════════════════════════════════════════════════════ */

document.addEventListener("DOMContentLoaded", () => {
    initMap();
    plotHubs();
    plotPartners();
    initMeasurementTool();
    initPanelControls();
});

/**
 * Inicializa o mapa Leaflet centrado no Sudeste do Brasil.
 */
function initMap() {
    map = L.map("map", {
        center: [-22.5, -46.5],
        zoom: 7,
        zoomControl: true,
        attributionControl: true,
    });

    // Tiles — CartoDB Dark Matter (tema escuro)
    L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        {
            attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
            subdomains: "abcd",
            maxZoom: 19,
        }
    ).addTo(map);

    // Grupos de camadas para parceiros e fluxos
    partnerLayerGroup = L.layerGroup().addTo(map);
    flowLayerGroup = L.layerGroup().addTo(map);
}

/**
 * Plota todos os hubs do HUBS_DATA como marcadores no mapa.
 */
function plotHubs() {
    HUBS_DATA.forEach(hub => {
        const marker = L.marker([hub.lat, hub.lng], {
            icon: L.divIcon({
                className: "",
                html: `<div class="hub-marker" data-hub-id="${hub.id}"></div>`,
                iconSize: [14, 14],
                iconAnchor: [7, 7],
            }),
        });

        // Popup ao clicar
        const popupContent = `
            <div class="hub-popup">
                <div class="hub-name">
                    <span class="status-dot"></span>
                    ${hub.nome}
                </div>
                <div class="hub-location">${hub.cidade} - ${hub.uf}</div>
                <div class="hub-volume">Volume: <strong>${formatarNumero(hub.volume)}</strong> pacotes</div>
            </div>
        `;
        marker.bindPopup(popupContent, {
            closeButton: true,
            maxWidth: 250,
        });

        marker.addTo(map);
        hubMarkers[hub.id] = marker;
    });
}

/**
 * Inicializa a ferramenta de medição.
 */
function initMeasurementTool() {
    measurementTool = new MeasurementTool(map);
}


/* ══════════════════════════════════════════════════════════════════════════════
   Controles do Painel
   ══════════════════════════════════════════════════════════════════════════════ */

function initPanelControls() {
    // Selects de Hub
    const selectA = document.getElementById("select-hub-a");
    const selectB = document.getElementById("select-hub-b");

    // Popular selects com os hubs
    _popularSelect(selectA);
    _popularSelect(selectB);

    // Botões
    const btnMedir = document.getElementById("btn-medir");
    const btnNovaMedicao = document.getElementById("btn-nova-medicao");
    const btnCopiar = document.getElementById("btn-copiar");
    const btnDesativar = document.getElementById("btn-desativar");

    // Painel toggle
    const panelToggle = document.getElementById("panel-toggle");
    const panelClose = document.getElementById("panel-close");
    const sidePanel = document.getElementById("side-panel");

    // Ao mudar os selects, atualizar marcadores visuais e exibir fluxos
    selectA.addEventListener("change", () => {
        const hub = HUBS_DATA.find(h => h.id === selectA.value);
        measurementTool.setHubA(hub || null);
        _atualizarMarcadoresVisuais();
        _atualizarEstadoBotaoMedir();
        atualizarMapaFluxos(selectA.value);
    });

    selectB.addEventListener("change", () => {
        const hub = HUBS_DATA.find(h => h.id === selectB.value);
        measurementTool.setHubB(hub || null);
        _atualizarMarcadoresVisuais();
        _atualizarEstadoBotaoMedir();
        if (selectA.value) {
            atualizarMapaFluxos(selectA.value);
        } else {
            atualizarMapaFluxos(selectB.value);
        }
    });

    // Medir Rota
    btnMedir.addEventListener("click", async () => {
        btnMedir.disabled = true;
        btnMedir.innerHTML = '<span>⏳</span> Calculando...';

        try {
            const resultado = await measurementTool.medir();
            _exibirResultados(resultado);
        } catch (err) {
            alert("Erro: " + err.message);
        } finally {
            btnMedir.disabled = false;
            btnMedir.innerHTML = '<span>📐</span> Medir Rota';
        }
    });

    // Nova Medição
    btnNovaMedicao.addEventListener("click", () => {
        _resetarMedicao(selectA, selectB);
    });

    // Copiar Dados
    btnCopiar.addEventListener("click", () => {
        const texto = measurementTool.getTextoParaCopiar();
        if (texto) {
            navigator.clipboard.writeText(texto).then(() => {
                _mostrarToast("✅ Dados copiados para a área de transferência!");
            }).catch(() => {
                // Fallback
                _mostrarToast("⚠️ Não foi possível copiar.");
            });
        }
    });

    // Desativar Régua
    btnDesativar.addEventListener("click", () => {
        _resetarMedicao(selectA, selectB);
    });

    // Painel — Abrir/Fechar
    panelClose.addEventListener("click", () => {
        sidePanel.style.display = "none";
        panelToggle.classList.add("visible");
    });

    panelToggle.addEventListener("click", () => {
        sidePanel.style.display = "flex";
        panelToggle.classList.remove("visible");
    });
}


/* ══════════════════════════════════════════════════════════════════════════════
   Helpers internos
   ══════════════════════════════════════════════════════════════════════════════ */

/**
 * Popula um <select> com os hubs.
 */
function _popularSelect(selectEl) {
    HUBS_DATA.forEach(hub => {
        const opt = document.createElement("option");
        opt.value = hub.id;
        opt.textContent = `${hub.id} — ${hub.cidade} (${hub.uf})`;
        selectEl.appendChild(opt);
    });
}

/**
 * Atualiza o visual dos marcadores para refletir seleção A/B.
 */
function _atualizarMarcadoresVisuais() {
    // Reset all
    Object.values(hubMarkers).forEach(marker => {
        const el = marker.getElement();
        if (el) {
            const dot = el.querySelector(".hub-marker");
            if (dot) {
                dot.classList.remove("selected-a", "selected-b");
            }
        }
    });

    // Highlight A
    if (measurementTool.hubA && hubMarkers[measurementTool.hubA.id]) {
        const el = hubMarkers[measurementTool.hubA.id].getElement();
        if (el) {
            const dot = el.querySelector(".hub-marker");
            if (dot) dot.classList.add("selected-a");
        }
    }

    // Highlight B
    if (measurementTool.hubB && hubMarkers[measurementTool.hubB.id]) {
        const el = hubMarkers[measurementTool.hubB.id].getElement();
        if (el) {
            const dot = el.querySelector(".hub-marker");
            if (dot) dot.classList.add("selected-b");
        }
    }
}

/**
 * Habilita/desabilita o botão Medir conforme seleção.
 */
function _atualizarEstadoBotaoMedir() {
    const btn = document.getElementById("btn-medir");
    btn.disabled = !(measurementTool.hubA && measurementTool.hubB);
}

/**
 * Exibe os resultados da medição no painel.
 */
function _exibirResultados(resultado) {
    const container = document.getElementById("measurement-results");
    container.classList.add("active");

    // Preencher valores
    document.getElementById("result-from").innerHTML =
        `De: <strong>🔶 ${measurementTool.hubA.nome}</strong>`;
    document.getElementById("result-to").innerHTML =
        `Até: <strong>🔷 ${measurementTool.hubB.nome}</strong>`;

    document.getElementById("result-reta-value").textContent =
        `${resultado.reta.toFixed(1)} km`;
    document.getElementById("result-rota-value").textContent =
        `${resultado.rota.toFixed(1)} km`;
    document.getElementById("result-tempo-value").textContent =
        `~${Math.round(resultado.duracao)} min`;
}

/**
 * Reseta toda a medição (limpa mapa, reseta selects e resultados).
 */
function _resetarMedicao(selectA, selectB) {
    measurementTool.limpar();
    measurementTool.setHubA(null);
    measurementTool.setHubB(null);

    selectA.value = "";
    selectB.value = "";

    _atualizarMarcadoresVisuais();
    _atualizarEstadoBotaoMedir();
    atualizarMapaFluxos(null);

    const container = document.getElementById("measurement-results");
    container.classList.remove("active");
}

/**
 * Mostra um toast temporário.
 */
function _mostrarToast(msg) {
    const toast = document.getElementById("copy-toast");
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => {
        toast.classList.remove("show");
    }, 2500);
}

/**
 * Plota todos os parceiros (Clientes/Fornecedores) como pequenos círculos no mapa.
 */
function plotPartners() {
    PARCEIROS_DATA.forEach(p => {
        const marker = L.circleMarker([p.lat, p.lng], {
            radius: 4,
            fillColor: "#9898b8",
            color: "#1a1a2e",
            weight: 1,
            opacity: 0.8,
            fillOpacity: 0.6
        });

        const popupContent = `
            <div class="hub-popup">
                <div class="hub-name">
                    <span class="status-dot" style="background-color: var(--text-secondary)"></span>
                    Parceiro: ${p.codigo}
                </div>
                <div class="hub-location">${p.cidade} | CEP: ${p.cep}</div>
                <div class="hub-volume">Volume Total: <strong>${formatarNumero(p.volume)}</strong></div>
                <div class="hub-volume">Movimentações: <strong>${formatarNumero(p.movimentacoes)}</strong></div>
            </div>
        `;
        marker.bindPopup(popupContent, { maxWidth: 250 });

        partnerMarkers[p.id] = marker;
        partnerLayerGroup.addLayer(marker);
    });
}

/**
 * Atualiza o mapa exibindo apenas os parceiros e fluxos vinculados ao CD selecionado.
 */
function atualizarMapaFluxos(cdId) {
    // 1. Limpar fluxos anteriores
    flowLayerGroup.clearLayers();

    // 2. Se nenhum CD selecionado, restaurar todos os parceiros com estilo original
    if (!cdId) {
        Object.values(partnerMarkers).forEach(marker => {
            marker.setStyle({
                radius: 4,
                fillColor: "#9898b8",
                fillOpacity: 0.6
            });
            if (!partnerLayerGroup.hasLayer(marker)) {
                partnerLayerGroup.addLayer(marker);
            }
        });
        return;
    }

    // 3. Filtrar fluxos do CD selecionado
    const fluxosCD = FLUXOS_DATA.filter(f => f.origem === cdId || f.destino === cdId);
    const parceirosConectados = new Set();

    fluxosCD.forEach(f => {
        const partnerId = f.origem === cdId ? f.destino : f.origem;
        parceirosConectados.add(partnerId);
    });

    // 4. Mostrar e estilizar apenas os parceiros conectados
    Object.entries(partnerMarkers).forEach(([id, marker]) => {
        if (parceirosConectados.has(id)) {
            const fluxo = fluxosCD.find(f => f.origem === id || f.destino === id);
            const isSaida = fluxo.direcao === "SAÍDA";

            marker.setStyle({
                radius: 6,
                fillColor: isSaida ? "#00d4ff" : "#ff8c42", // Ciano para saída (Clientes), Laranja para entrada (Fornecedores)
                fillOpacity: 0.95
            });

            if (!partnerLayerGroup.hasLayer(marker)) {
                partnerLayerGroup.addLayer(marker);
            }
        } else {
            // Ocultar parceiros sem relação com este CD
            partnerLayerGroup.removeLayer(marker);
        }
    });

    // 5. Desenhar linhas de fluxo
    const cdObj = HUBS_DATA.find(h => h.id === cdId);
    if (!cdObj) return;

    const cdLatLng = [cdObj.lat, cdObj.lng];
    const bounds = L.latLngBounds([cdLatLng]);

    fluxosCD.forEach(f => {
        const partnerId = f.origem === cdId ? f.destino : f.origem;
        const partnerObj = PARCEIROS_DATA.find(p => p.id === partnerId);
        if (!partnerObj) return;

        const partnerLatLng = [partnerObj.lat, partnerObj.lng];
        bounds.extend(partnerLatLng);

        const isSaida = f.direcao === "SAÍDA";
        const corLinha = isSaida ? "#00d4ff" : "#ff8c42";

        // Espessura proporcional ao volume
        const peso = Math.max(1.5, Math.min(7, f.volume / 50000));

        const poly = L.polyline([cdLatLng, partnerLatLng], {
            color: corLinha,
            weight: peso,
            opacity: 0.5,
            dashArray: isSaida ? null : "6, 6" // Tracejado para Entrada/Fornecedores, contínuo para Saída/Clientes
        });

        const tooltipContent = `
            <div style="font-family: 'Inter', sans-serif; font-size: 11px; padding: 4px 8px; background: rgba(15, 15, 35, 0.92); border: 1px solid ${corLinha}; border-radius: 4px; color: #fff; box-shadow: 0 4px 12px rgba(0,0,0,0.5);">
                <strong>${isSaida ? "Outbound ➔ Cliente" : "Inbound ➔ CD"}</strong><br/>
                Material: ${f.material}<br/>
                Volume: ${formatarNumero(f.volume)}<br/>
                Movs: ${f.movimentacoes}
            </div>
        `;
        poly.bindTooltip(tooltipContent, { sticky: true, opacity: 0.95 });
        flowLayerGroup.addLayer(poly);
    });

    // 6. Enquadrar no mapa
    if (parceirosConectados.size > 0) {
        map.fitBounds(bounds.pad(0.15));
    }
}
