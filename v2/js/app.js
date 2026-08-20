/**
 * app.js — Inicialização do mapa e orquestração geral
 *
 * - Cria o mapa Leaflet com tiles escuros (CartoDB Dark Matter)
 * - Plota marcadores dos CDs da Sabesp (de data.js)
 * - Conecta o painel lateral com a ferramenta de medição CD-Parceiro
 */

/* ══════════════════════════════════════════════════════════════════════════════
   Variáveis globais
   ══════════════════════════════════════════════════════════════════════════════ */

let map;
let measurementTool;
let cdMarkers = {};  // id → L.marker
let partnerMarkers = {}; // partner_id → L.circleMarker
let partnerLayerGroup;
let flowLayerGroup;
let currentTileLayer;
let isDarkMode = true;

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
    plotCDs();
    plotPartners();
    initMeasurementTool();
    initPanelControls();
});

/**
 * Inicializa o mapa Leaflet centrado no Estado de São Paulo.
 */
function initMap() {
    map = L.map("map", {
        center: [-23.5, -46.6],
        zoom: 8,
        zoomControl: true,
        attributionControl: true,
    });

    _setMapTheme();

    // Event listener for theme toggle
    const themeBtn = document.getElementById("map-theme-toggle");
    if (themeBtn) {
        themeBtn.addEventListener("click", () => {
            isDarkMode = !isDarkMode;
            themeBtn.innerHTML = isDarkMode ? '<span class="icon">☀️</span>' : '<span class="icon">🌙</span>';
            _setMapTheme();
        });
    }

    // Grupos de camadas para parceiros e fluxos
    partnerLayerGroup = L.layerGroup().addTo(map);
    flowLayerGroup = L.layerGroup().addTo(map);
}

function _setMapTheme() {
    if (currentTileLayer) {
        map.removeLayer(currentTileLayer);
    }
    const tileUrl = isDarkMode 
        ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

    currentTileLayer = L.tileLayer(tileUrl, {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
        subdomains: "abcd",
        maxZoom: 19,
    }).addTo(map);
}

/**
 * Plota todos os CDs do CDS_DATA como marcadores no mapa.
 */
function plotCDs() {
    CDS_DATA.forEach(cd => {
        const houseSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>`;
        const marker = L.marker([cd.lat, cd.lng], {
            icon: L.divIcon({
                className: "",
                html: `<div class="hub-marker" data-cd-id="${cd.id}">${houseSvg}</div>`,
                iconSize: [28, 28],
                iconAnchor: [14, 14],
            }),
        });

        const popupContent = `
            <div class="hub-popup">
                <div class="hub-name">
                    <span class="status-dot"></span>
                    CD: ${cd.nome}
                </div>
                <div class="hub-location">${cd.cidade} - ${cd.uf}</div>
                <div class="hub-location" style="font-size: 11px; margin-top: -6px; color: var(--text-muted);">${cd.endereco}</div>
                <div class="hub-volume">Volume Total: <strong>${formatarNumero(cd.volume)}</strong></div>
            </div>
        `;
        marker.bindPopup(popupContent, {
            closeButton: true,
            maxWidth: 280,
        });

        marker.addTo(map);
        cdMarkers[cd.id] = marker;
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
    const selectCd = document.getElementById("select-cd");
    const selectParceiro = document.getElementById("select-parceiro");
    const checkInbound = document.getElementById("check-inbound");
    const checkOutbound = document.getElementById("check-outbound");

    // Popular select de CDs
    _popularSelectCDs(selectCd);

    // Botões
    const btnMedir = document.getElementById("btn-medir");
    const btnNovaMedicao = document.getElementById("btn-nova-medicao");
    const btnCopiar = document.getElementById("btn-copiar");
    const btnDesativar = document.getElementById("btn-desativar");

    // Painel toggle
    const panelToggle = document.getElementById("panel-toggle");
    const panelClose = document.getElementById("panel-close");
    const sidePanel = document.getElementById("side-panel");

    // Ao mudar o CD, atualizar mapa e dropdown de parceiros
    selectCd.addEventListener("change", () => {
        const cdId = selectCd.value;
        const inboundChecked = checkInbound.checked;
        const outboundChecked = checkOutbound.checked;

        measurementTool.limpar();
        document.getElementById("measurement-results").classList.remove("active");

        atualizarDropdownParceiros(cdId, inboundChecked, outboundChecked);
        atualizarMapaFluxos(cdId);
        _atualizarMarcadoresVisuais();
        _atualizarEstadoBotaoMedir();
    });

    // Ao mudar os checkboxes
    const triggerFiltroDirecao = () => {
        const cdId = selectCd.value;
        const inboundChecked = checkInbound.checked;
        const outboundChecked = checkOutbound.checked;

        measurementTool.limpar();
        document.getElementById("measurement-results").classList.remove("active");

        atualizarDropdownParceiros(cdId, inboundChecked, outboundChecked);
        atualizarMapaFluxos(cdId);
        _atualizarMarcadoresVisuais();
        _atualizarEstadoBotaoMedir();
    };

    checkInbound.addEventListener("change", triggerFiltroDirecao);
    checkOutbound.addEventListener("change", triggerFiltroDirecao);

    // Ao mudar o parceiro
    selectParceiro.addEventListener("change", () => {
        measurementTool.limpar();
        document.getElementById("measurement-results").classList.remove("active");

        _atualizarMarcadoresVisuais();
        _atualizarEstadoBotaoMedir();
    });

    // Medir Rota
    btnMedir.addEventListener("click", async () => {
        const cdId = selectCd.value;
        const partnerId = selectParceiro.value;

        const cdObj = CDS_DATA.find(c => c.id === cdId);
        const partnerObj = PARCEIROS_DATA.find(p => p.id === partnerId);

        if (!cdObj || !partnerObj) return;

        btnMedir.disabled = true;
        btnMedir.innerHTML = '<span>⏳</span> Calculando Rota...';

        try {
            measurementTool.setHubA(cdObj);
            measurementTool.setHubB(partnerObj);
            const resultado = await measurementTool.medir();
            _exibirResultados(resultado);
            _atualizarMarcadoresVisuais(); // Realça o parceiro destino no mapa
        } catch (err) {
            alert("Erro: " + err.message);
        } finally {
            btnMedir.disabled = false;
            btnMedir.innerHTML = '<span>📐</span> Medir Rota';
        }
    });

    // Nova Medição (Limpa a rota ativa para selecionar outro parceiro)
    btnNovaMedicao.addEventListener("click", () => {
        measurementTool.limpar();
        selectParceiro.value = "";
        _atualizarMarcadoresVisuais();
        _atualizarEstadoBotaoMedir();
        document.getElementById("measurement-results").classList.remove("active");
    });

    // Copiar Dados
    btnCopiar.addEventListener("click", () => {
        const texto = measurementTool.getTextoParaCopiar();
        if (texto) {
            navigator.clipboard.writeText(texto).then(() => {
                _mostrarToast("✅ Dados copiados para a área de transferência!");
            }).catch(() => {
                _mostrarToast("⚠️ Não foi possível copiar.");
            });
        }
    });

    // Limpar Filtros
    btnDesativar.addEventListener("click", () => {
        _resetarFiltros(selectCd, selectParceiro, checkInbound, checkOutbound);
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
 * Popula o select com os CDs disponíveis.
 */
function _popularSelectCDs(selectEl) {
    CDS_DATA.forEach(cd => {
        const opt = document.createElement("option");
        opt.value = cd.id;
        opt.textContent = `${cd.id} — ${cd.nome}`;
        selectEl.appendChild(opt);
    });
}

/**
 * Atualiza o visual dos marcadores para refletir seleção do CD.
 */
function _atualizarMarcadoresVisuais() {
    // Reset de estilos de realce de CD
    Object.values(cdMarkers).forEach(marker => {
        const el = marker.getElement();
        if (el) {
            const dot = el.querySelector(".hub-marker");
            if (dot) {
                dot.classList.remove("selected-a", "selected-b");
            }
        }
    });

    const selectCdVal = document.getElementById("select-cd").value;
    const selectPartnerVal = document.getElementById("select-parceiro").value;

    // Highlight CD (Ponto A) e escurecer os não selecionados
    if (selectCdVal) {
        Object.keys(cdMarkers).forEach(id => {
            const marker = cdMarkers[id];
            const el = marker.getElement();
            if (el) {
                const dot = el.querySelector(".hub-marker");
                if (dot) {
                    if (id === selectCdVal) {
                        dot.classList.add("selected-a");
                        dot.style.opacity = "1";
                    } else {
                        dot.style.opacity = "0.2"; // Escurece os CDs não filtrados
                    }
                }
            }
        });
    } else {
        // Restaurar opacidade de todos se nenhum CD estiver selecionado
        Object.values(cdMarkers).forEach(marker => {
            const el = marker.getElement();
            if (el) {
                const dot = el.querySelector(".hub-marker");
                if (dot) dot.style.opacity = "1";
            }
        });
    }

    // Ponto B (Parceiro) é tratado no redesenho dos fluxos, mas se medido, realça ele.
    if (selectPartnerVal && partnerMarkers[selectPartnerVal]) {
        // Estilizar parceiro selecionado se medição estiver ativa
        if (measurementTool.isActive) {
            partnerMarkers[selectPartnerVal].setStyle({
                radius: 8,
                fillColor: "#fbbf24", // Amarelo para Ponto B final
                fillOpacity: 1.0,
                weight: 2,
                color: "#ffffff"
            });
        }
    }

    // Ocultar levemente as linhas macro para dar destaque à rota medida
    flowLayerGroup.eachLayer(layer => {
        if (measurementTool.isActive) {
            layer.setStyle({ opacity: 0.1 });
        } else {
            layer.setStyle({ opacity: 0.5 });
        }
    });
}

/**
 * Habilita/desabilita o botão Medir conforme seleção.
 */
function _atualizarEstadoBotaoMedir() {
    const cdId = document.getElementById("select-cd").value;
    const partnerId = document.getElementById("select-parceiro").value;
    const btn = document.getElementById("btn-medir");
    btn.disabled = !(cdId && partnerId);
}

/**
 * Exibe os resultados da medição no painel.
 */
function _exibirResultados(resultado) {
    const container = document.getElementById("measurement-results");
    container.classList.add("active");

    const cd = CDS_DATA.find(c => c.id === document.getElementById("select-cd").value);
    const partner = PARCEIROS_DATA.find(p => p.id === document.getElementById("select-parceiro").value);

    document.getElementById("result-from").innerHTML =
        `Origem: <strong>🔶 CD ${cd.nome}</strong>`;
    document.getElementById("result-to").innerHTML =
        `Destino: <strong>🔷 ID ${partner.codigo} (${partner.tipo})</strong>`;

    document.getElementById("result-rota-value").textContent =
        `${resultado.rota.toFixed(1)} km`;
    document.getElementById("result-tempo-value").textContent =
        `~${Math.round(resultado.duracao)} min`;
}

/**
 * Reseta todos os filtros e medições do mapa.
 */
function _resetarFiltros(selectCd, selectParceiro, checkInbound, checkOutbound) {
    measurementTool.limpar();
    selectCd.value = "";
    selectParceiro.value = "";
    selectParceiro.disabled = true;
    checkInbound.checked = true;
    checkOutbound.checked = true;

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

const svgTruck = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>`;

const svgConstruction = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 22v-5l5-5 5 5-5 5z"/><path d="M9.5 14.5L16 8"/><path d="m17 2 5 5-.5.5a2.12 2.12 0 0 1-3 0l-1.5-1.5a2.12 2.12 0 0 1 0-3L17 2z"/></svg>`;

const iconInactive = L.divIcon({
    className: 'partner-icon-inactive',
    html: '<div class="dot-inactive"></div>',
    iconSize: [12, 12],
    iconAnchor: [6, 6]
});

const iconFornecedor = L.divIcon({
    className: 'partner-icon-fornecedor',
    html: `<div class="icon-wrapper truck-icon">${svgTruck}</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14]
});

const iconCanteiro = L.divIcon({
    className: 'partner-icon-canteiro',
    html: `<div class="icon-wrapper canteiro-icon">${svgConstruction}</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14]
});

/**
 * Plota todos os parceiros (Clientes/Fornecedores) como pequenos marcadores inativos no mapa.
 */
function plotPartners() {
    PARCEIROS_DATA.forEach(p => {
        const marker = L.marker([p.lat, p.lng], {
            icon: iconInactive,
            opacity: 0.8
        });

        const materiaisStr = p.materiais && p.materiais.length > 0 ? p.materiais.join(", ") : "Não informado";
        const valorFormatado = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(p.valorTotal || 0);

        const popupContent = `
            <div class="hub-popup" style="width: 240px;">
                <div class="hub-name">
                    <span class="status-dot" style="background-color: var(--text-secondary)"></span>
                    Parceiro: ${p.codigo}
                </div>
                <div class="hub-location">${p.cidade} | CEP: ${p.cep}</div>
                <div class="hub-volume" style="margin-top: 6px;">Volume: <strong>${formatarNumero(p.volume)}</strong></div>
                <div class="hub-volume">Movimentações: <strong>${formatarNumero(p.movimentacoes)}</strong></div>
                <div class="hub-volume">Valor Total: <strong style="color: #4ade80;">${valorFormatado}</strong></div>
                <div class="hub-volume" style="margin-top: 6px; border-top: 1px solid #3f3f46; padding-top: 6px;">
                    Material: <strong>${materiaisStr}</strong>
                </div>
            </div>
        `;
        marker.bindPopup(popupContent, { maxWidth: 250 });

        partnerMarkers[p.id] = marker;
        partnerLayerGroup.addLayer(marker);
    });
}

/**
 * Atualiza o dropdown de parceiros com base no CD e tipo de operação selecionados.
 */
function atualizarDropdownParceiros(cdId, inboundChecked, outboundChecked) {
    const selectParceiro = document.getElementById("select-parceiro");
    selectParceiro.innerHTML = '<option value="">Selecione o Parceiro...</option>';

    if (!cdId || (!inboundChecked && !outboundChecked)) {
        selectParceiro.disabled = true;
        return;
    }

    // Filtrar fluxos do CD
    const fluxosCD = FLUXOS_DATA.filter(f => {
        const matchCD = f.origem === cdId || f.destino === cdId;
        if (!matchCD) return false;

        if (f.direcao === "SAÍDA") return outboundChecked;
        if (f.direcao === "ENTRADA") return inboundChecked;
        return false;
    });

    const parceirosVistos = new Set();
    const parceirosFiltrados = [];

    fluxosCD.forEach(f => {
        const partnerId = f.origem === cdId ? f.destino : f.origem;
        if (!parceirosVistos.has(partnerId)) {
            parceirosVistos.add(partnerId);
            const pObj = PARCEIROS_DATA.find(p => p.id === partnerId);
            if (pObj) {
                parceirosFiltrados.push(pObj);
            }
        }
    });

    // Ordenar parceiros por código numérico/alfabético
    parceirosFiltrados.sort((a, b) => a.codigo.localeCompare(b.codigo));

    if (parceirosFiltrados.length > 0) {
        selectParceiro.disabled = false;
        parceirosFiltrados.forEach(p => {
            const opt = document.createElement("option");
            opt.value = p.id;
            const labelTipo = p.tipo === "Canteiro" ? "Canteiro" : (p.tipo === "Fornecedor" ? "Forn." : "Parc.");
            opt.textContent = `[${labelTipo}] ${p.codigo} — ${p.cidade} (${p.cep.substring(0, 5)})`;
            selectParceiro.appendChild(opt);
        });
    } else {
        selectParceiro.disabled = true;
    }
}

/**
 * Atualiza o mapa exibindo apenas os parceiros e fluxos vinculados ao CD selecionado.
 * Na V2, as linhas são rotas terrestres reais via OSRM.
 */

// Cache global de rotas OSRM para evitar chamadas repetidas
const _routeCache = {};

async function atualizarMapaFluxos(cdId) {
    const inboundChecked = document.getElementById("check-inbound").checked;
    const outboundChecked = document.getElementById("check-outbound").checked;

    // 1. Limpar fluxos anteriores
    flowLayerGroup.clearLayers();

    // 2. Se nenhum CD selecionado ou nenhuma direção marcada, restaurar todos os parceiros
    if (!cdId || (!inboundChecked && !outboundChecked)) {
        Object.values(partnerMarkers).forEach(marker => {
            marker.setIcon(iconInactive);
            if (!partnerLayerGroup.hasLayer(marker)) {
                partnerLayerGroup.addLayer(marker);
            }
        });
        return;
    }

    // 3. Filtrar fluxos do CD selecionado respeitando as direções
    const fluxosCD = FLUXOS_DATA.filter(f => {
        const matchCD = f.origem === cdId || f.destino === cdId;
        if (!matchCD) return false;

        if (f.direcao === "SAÍDA") return outboundChecked;
        if (f.direcao === "ENTRADA") return inboundChecked;
        return false;
    });

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

            marker.setIcon(isSaida ? iconCanteiro : iconFornecedor);

            if (!partnerLayerGroup.hasLayer(marker)) {
                partnerLayerGroup.addLayer(marker);
            }
        } else {
            // Ocultar parceiros sem relação
            partnerLayerGroup.removeLayer(marker);
        }
    });

    // 5. Desenhar rotas terrestres reais (OSRM)
    const cdObj = CDS_DATA.find(h => h.id === cdId);
    if (!cdObj) return;

    const cdLatLng = [cdObj.lat, cdObj.lng];
    const bounds = L.latLngBounds([cdLatLng]);

    // Calcular agregados de Inteligência do CD
    let qtdCanteiros = 0;
    let valorEnviado = 0;
    let materiaisSet = new Set();
    let volumeTotal = 0;
    let movimentacoesTotal = 0;
    let dist50 = 0;
    let dist100 = 0;
    let distMais = 0;
    const canteirosUnicos = new Set();

    function calcularDistanciaHaversine(lat1, lon1, lat2, lon2) {
        const R = 6371; // Raio da Terra em km
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                  Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
    }

    // Agrupar fluxos por parceiro único (evita duplicatas de rota)
    const parceirosUnicos = new Map();
    fluxosCD.forEach(f => {
        const partnerId = f.origem === cdId ? f.destino : f.origem;
        if (!parceirosUnicos.has(partnerId)) {
            parceirosUnicos.set(partnerId, f);
        }

        // Agregar de acordo com os filtros de In/Out ativos
        const matchOutbound = f.direcao === "SAÍDA" && outboundChecked;
        const matchInbound = f.direcao === "ENTRADA" && inboundChecked;

        if (matchOutbound || matchInbound) {
            volumeTotal += f.volume || 0;
            movimentacoesTotal += f.movimentacoes || 0;
            if (f.material) materiaisSet.add(f.material);

            if (!canteirosUnicos.has(partnerId)) {
                canteirosUnicos.add(partnerId);
                const partnerObj = PARCEIROS_DATA.find(p => p.id === partnerId);
                if (partnerObj) {
                    valorEnviado += partnerObj.valorTotal || 0;
                    const distKm = calcularDistanciaHaversine(cdObj.lat, cdObj.lng, partnerObj.lat, partnerObj.lng);
                    if (distKm <= 50) dist50++;
                    else if (distKm <= 100) dist100++;
                    else distMais++;
                }
            }
        }
    });

    qtdCanteiros = canteirosUnicos.size;

    // Atualizar UI do CD Footer
    const cdFooter = document.getElementById("cd-footer");
    if (cdFooter) {
        let title = "RESUMO GERAL";
        let lblQtd = "Qtd. Parceiros";
        let lblValor = "Valor Total";

        if (inboundChecked && !outboundChecked) {
            title = "RESUMO (FORNECEDORES)";
            lblQtd = "Qtd. Fornecedores";
            lblValor = "Valor Recebido";
        } else if (!inboundChecked && outboundChecked) {
            title = "RESUMO (CANTEIROS)";
            lblQtd = "Qtd. Canteiros";
            lblValor = "Valor Enviado";
        }

        const tagTitle = document.getElementById("cdf-tag-title");
        if (tagTitle) tagTitle.textContent = title;
        
        const spanQtd = document.getElementById("cdf-lbl-qtd");
        if (spanQtd) spanQtd.textContent = lblQtd;
        
        const spanValor = document.getElementById("cdf-lbl-valor");
        if (spanValor) spanValor.textContent = lblValor;

        document.getElementById("cdf-nome").textContent = cdObj.nome;
        document.getElementById("cdf-canteiros").textContent = qtdCanteiros;
        document.getElementById("cdf-valor").textContent = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valorEnviado);
        document.getElementById("cdf-materiais").textContent = materiaisSet.size;
        document.getElementById("cdf-volume").textContent = formatarNumero(volumeTotal);
        document.getElementById("cdf-movimentacoes").textContent = formatarNumero(movimentacoesTotal);

        document.getElementById("val-50").textContent = dist50;
        document.getElementById("val-100").textContent = dist100;
        document.getElementById("val-mais").textContent = distMais;

        const setBar = (id, val) => {
            const pct = qtdCanteiros === 0 ? 0 : (val / qtdCanteiros) * 100;
            document.getElementById(id).style.width = pct + "%";
        };
        setBar("bar-50", dist50);
        setBar("bar-100", dist100);
        setBar("bar-mais", distMais);

        if (qtdCanteiros > 0 || fluxosCD.length > 0) {
            cdFooter.classList.add("active");
        } else {
            cdFooter.classList.remove("active");
        }
    }

    // Processar rotas em lotes para não sobrecarregar a API
    const entries = Array.from(parceirosUnicos.entries());
    
    for (let i = 0; i < entries.length; i++) {
        const [partnerId, f] = entries[i];
        const partnerObj = PARCEIROS_DATA.find(p => p.id === partnerId);
        if (!partnerObj) continue;

        const partnerLatLng = [partnerObj.lat, partnerObj.lng];
        bounds.extend(partnerLatLng);

        const isSaida = f.direcao === "SAÍDA";
        const corLinha = isSaida ? "#00d4ff" : "#ff8c42";
        const peso = Math.max(1.5, Math.min(5, f.volume / 50000));

        // Chave de cache baseada nas coordenadas
        const cacheKey = `${cdObj.lat},${cdObj.lng}_${partnerObj.lat},${partnerObj.lng}`;

        let routeCoords;
        if (_routeCache[cacheKey]) {
            // Usar rota do cache
            routeCoords = _routeCache[cacheKey];
        } else {
            // Buscar rota real via OSRM
            try {
                const rotaData = await buscarRotaOSRM(cdObj.lat, cdObj.lng, partnerObj.lat, partnerObj.lng);
                routeCoords = rotaData.coordinates;
                _routeCache[cacheKey] = routeCoords;
            } catch (err) {
                // Fallback: linha reta se a API falhar
                routeCoords = [cdLatLng, partnerLatLng];
            }
            // Pequena pausa entre chamadas para respeitar rate limit da API
            if (i < entries.length - 1) {
                await new Promise(r => setTimeout(r, 80));
            }
        }

        const poly = L.polyline(routeCoords, {
            color: corLinha,
            weight: peso,
            opacity: 0.5,
            dashArray: isSaida ? null : "6, 6" // Tracejado para Entrada/Fornecedores, contínuo para Saída/Clientes
        });

        const tooltipContent = `
            <div style="font-family: 'Inter', sans-serif; font-size: 11px; padding: 4px 8px; background: rgba(15, 15, 35, 0.92); border: 1px solid ${corLinha}; border-radius: 4px; color: #fff; box-shadow: 0 4px 12px rgba(0,0,0,0.5);">
                <strong>${isSaida ? "Outbound (Saída para Canteiro)" : "Inbound (Entrada de Fornecedor)"}</strong><br/>
                Material: ${f.material}<br/>
                Volume: ${formatarNumero(f.volume)}<br/>
                Movs: ${f.movimentacoes}
            </div>
        `;
        poly.bindTooltip(tooltipContent, { sticky: true, opacity: 0.95 });
        flowLayerGroup.addLayer(poly);
    }

    // 6. Enquadrar no mapa
    if (parceirosConectados.size > 0) {
        map.fitBounds(bounds.pad(0.15));
    }
}
