/**
 * measurement.js — Ferramenta de Medição de Rotas
 *
 * Funcionalidades:
 * - Calcular distância geodésica (Haversine) entre dois pontos
 * - Chamar API OSRM para rota real de estrada
 * - Desenhar polylines no mapa (rota dirigida + linha reta)
 * - Exibir labels nos pontos A/B e info no ponto médio
 */

/* ══════════════════════════════════════════════════════════════════════════════
   Haversine — Distância em linha reta entre dois pontos (lat, lng)
   ══════════════════════════════════════════════════════════════════════════════ */

/**
 * Calcula a distância em km entre dois pontos usando a fórmula de Haversine.
 * @param {number} lat1 - Latitude do ponto A
 * @param {number} lng1 - Longitude do ponto A
 * @param {number} lat2 - Latitude do ponto B
 * @param {number} lng2 - Longitude do ponto B
 * @returns {number} Distância em km
 */
function calcularDistanciaReta(lat1, lng1, lat2, lng2) {
    const R = 6371; // Raio da Terra em km
    const dLat = _toRad(lat2 - lat1);
    const dLng = _toRad(lng2 - lng1);
    const a =
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(_toRad(lat1)) * Math.cos(_toRad(lat2)) *
        Math.sin(dLng / 2) * Math.sin(dLng / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

function _toRad(deg) {
    return deg * (Math.PI / 180);
}


/* ══════════════════════════════════════════════════════════════════════════════
   OSRM API — Rota real de estrada
   ══════════════════════════════════════════════════════════════════════════════ */

/**
 * Consulta a API OSRM para obter a rota dirigida entre dois pontos.
 * @param {number} lat1 - Latitude do ponto A
 * @param {number} lng1 - Longitude do ponto A
 * @param {number} lat2 - Latitude do ponto B
 * @param {number} lng2 - Longitude do ponto B
 * @returns {Promise<{distance: number, duration: number, coordinates: Array}>}
 *   distance em km, duration em minutos, coordinates como [[lat, lng], ...]
 */
async function buscarRotaOSRM(lat1, lng1, lat2, lng2) {
    // OSRM usa formato lng,lat (inverso)
    const url = `https://router.project-osrm.org/route/v1/driving/${lng1},${lat1};${lng2},${lat2}?overview=full&geometries=geojson`;

    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`OSRM API error: ${response.status}`);
    }

    const data = await response.json();

    if (data.code !== "Ok" || !data.routes || data.routes.length === 0) {
        throw new Error("OSRM: Nenhuma rota encontrada.");
    }

    const route = data.routes[0];
    // OSRM retorna coordinates como [lng, lat] — inverter para Leaflet [lat, lng]
    const coordinates = route.geometry.coordinates.map(coord => [coord[1], coord[0]]);

    return {
        distance: route.distance / 1000,    // metros → km
        duration: route.duration / 60,       // segundos → minutos
        coordinates: coordinates,
    };
}


/* ══════════════════════════════════════════════════════════════════════════════
   MeasurementTool — Classe principal
   ══════════════════════════════════════════════════════════════════════════════ */

class MeasurementTool {
    constructor(map) {
        this.map = map;
        this.hubA = null;
        this.hubB = null;
        this.routeLayer = null;          // Polyline da rota dirigida
        this.straightLineLayer = null;   // Polyline da linha reta
        this.pointLabelA = null;         // Marker label ponto A
        this.pointLabelB = null;         // Marker label ponto B
        this.routeInfoMarker = null;     // Marker com info no meio da rota
        this.isActive = false;
    }

    /**
     * Define o Hub A (origem).
     * @param {Object} hub - Objeto do hub (de HUBS_DATA)
     */
    setHubA(hub) {
        this.hubA = hub;
    }

    /**
     * Define o Hub B (destino).
     * @param {Object} hub - Objeto do hub (de HUBS_DATA)
     */
    setHubB(hub) {
        this.hubB = hub;
    }

    /**
     * Limpa todas as layers de medição do mapa.
     */
    limpar() {
        if (this.routeLayer) {
            this.map.removeLayer(this.routeLayer);
            this.routeLayer = null;
        }
        if (this.straightLineLayer) {
            this.map.removeLayer(this.straightLineLayer);
            this.straightLineLayer = null;
        }
        if (this.pointLabelA) {
            this.map.removeLayer(this.pointLabelA);
            this.pointLabelA = null;
        }
        if (this.pointLabelB) {
            this.map.removeLayer(this.pointLabelB);
            this.pointLabelB = null;
        }
        if (this.routeInfoMarker) {
            this.map.removeLayer(this.routeInfoMarker);
            this.routeInfoMarker = null;
        }
        this.isActive = false;
    }

    /**
     * Executa a medição completa: calcula distâncias, desenha no mapa, retorna resultados.
     * @returns {Promise<{reta: number, rota: number, duracao: number}>}
     */
    async medir() {
        if (!this.hubA || !this.hubB) {
            throw new Error("Selecione os dois hubs (A e B) antes de medir.");
        }
        if (this.hubA.id === this.hubB.id) {
            throw new Error("Os hubs A e B devem ser diferentes.");
        }

        // Limpar medição anterior
        this.limpar();
        this.isActive = true;

        const { lat: lat1, lng: lng1 } = this.hubA;
        const { lat: lat2, lng: lng2 } = this.hubB;

        // 1. Distância em linha reta
        const distanciaReta = calcularDistanciaReta(lat1, lng1, lat2, lng2);

        // 2. Rota OSRM
        let rotaData;
        try {
            rotaData = await buscarRotaOSRM(lat1, lng1, lat2, lng2);
        } catch (err) {
            console.error("Erro ao buscar rota OSRM:", err);
            // Fallback: usar só a linha reta
            rotaData = {
                distance: distanciaReta * 1.3, // Estimativa grosseira
                duration: (distanciaReta * 1.3) / 80 * 60, // ~80km/h
                coordinates: [[lat1, lng1], [lat2, lng2]],
            };
        }

        // 3. Desenhar no mapa
        this._desenharLinhaReta(lat1, lng1, lat2, lng2);
        this._desenharRotaDirigida(rotaData.coordinates);
        this._criarLabelPontoA();
        this._criarLabelPontoB();
        this._criarInfoRotaMeio(rotaData, distanciaReta);

        // 4. Ajustar o zoom do mapa para enquadrar a rota
        const bounds = L.latLngBounds([
            [lat1, lng1],
            [lat2, lng2],
        ]);
        this.map.fitBounds(bounds.pad(0.3));

        return {
            reta: distanciaReta,
            rota: rotaData.distance,
            duracao: rotaData.duration,
        };
    }

    /**
     * Retorna os dados da última medição como texto formatado para copiar.
     */
    getTextoParaCopiar() {
        if (!this.hubA || !this.hubB || !this.isActive) {
            return "";
        }
        // Os valores exibidos nos inputs de resultado serão usados
        const retaEl = document.getElementById("result-reta-value");
        const rotaEl = document.getElementById("result-rota-value");
        const tempoEl = document.getElementById("result-tempo-value");

        const reta = retaEl ? retaEl.textContent : "N/A";
        const rota = rotaEl ? rotaEl.textContent : "N/A";
        const tempo = tempoEl ? tempoEl.textContent : "N/A";

        return `Medição de Rota\n` +
               `De: ${this.hubA.nome} (${this.hubA.cidade} - ${this.hubA.uf})\n` +
               `Até: ${this.hubB.nome} (${this.hubB.cidade} - ${this.hubB.uf})\n` +
               `Linha reta: ${reta}\n` +
               `Rota dirigida: ${rota}\n` +
               `Tempo estimado: ${tempo}\n`;
    }


    /* ── Métodos internos de desenho ── */

    _desenharLinhaReta(lat1, lng1, lat2, lng2) {
        this.straightLineLayer = L.polyline(
            [[lat1, lng1], [lat2, lng2]],
            {
                color: "#fbbf24",
                weight: 2.5,
                dashArray: "10, 8",
                opacity: 0.8,
            }
        ).addTo(this.map);
    }

    _desenharRotaDirigida(coordinates) {
        this.routeLayer = L.polyline(coordinates, {
            color: "#00d4ff",
            weight: 4,
            opacity: 0.9,
            lineJoin: "round",
            lineCap: "round",
        }).addTo(this.map);
    }

    _criarLabelPontoA() {
        const hub = this.hubA;
        const html = `
            <div class="point-label-card">
                <div class="point-tag tag-a">PONTO A</div>
                <div class="point-hub-name">${hub.nome}</div>
                <div class="point-volume">Volume: ${formatarNumero(hub.volume)} pacotes</div>
            </div>
        `;
        this.pointLabelA = L.marker([hub.lat, hub.lng], {
            icon: L.divIcon({
                className: "route-point-label",
                html: html,
                iconSize: [160, 70],
                iconAnchor: [80, 90],
            }),
            interactive: false,
        }).addTo(this.map);
    }

    _criarLabelPontoB() {
        const hub = this.hubB;
        const html = `
            <div class="point-label-card">
                <div class="point-tag tag-b">PONTO B</div>
                <div class="point-hub-name">${hub.nome}</div>
                <div class="point-volume">Volume: ${formatarNumero(hub.volume)} pacotes</div>
            </div>
        `;
        this.pointLabelB = L.marker([hub.lat, hub.lng], {
            icon: L.divIcon({
                className: "route-point-label",
                html: html,
                iconSize: [160, 70],
                iconAnchor: [80, -10],
            }),
            interactive: false,
        }).addTo(this.map);
    }

    _criarInfoRotaMeio(rotaData, distanciaReta) {
        // Ponto médio da rota real (usa o ponto do meio do array de coordenadas)
        const coords = rotaData.coordinates;
        const midIdx = Math.floor(coords.length / 2);
        const midPoint = coords[midIdx];

        const distKm = rotaData.distance.toFixed(1);
        const tempoMin = Math.round(rotaData.duration);
        const retaKm = distanciaReta.toFixed(1);

        const html = `
            <div class="route-info-card">
                <div class="route-driven">
                    🚗 Rota: ${distKm} km
                    <span class="time-badge">~${tempoMin}min</span>
                </div>
                <div class="route-straight">
                    <span>📏</span> Reta: ${retaKm} km
                </div>
            </div>
        `;

        this.routeInfoMarker = L.marker(midPoint, {
            icon: L.divIcon({
                className: "route-info-popup",
                html: html,
                iconSize: [220, 60],
                iconAnchor: [110, 30],
            }),
            interactive: false,
            zIndexOffset: 1000,
        }).addTo(this.map);
    }
}
