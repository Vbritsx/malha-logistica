/**
 * data.js — Dados mock dos hubs logísticos
 *
 * Estrutura preparada para substituição fácil por dados reais (Excel → JSON).
 * Cada hub possui: id, nome, lat, lng, volume, cidade, uf
 */

const HUBS_DATA = [
    {
        id: "HBAU",
        nome: "Hub HBAU",
        lat: -22.3147,
        lng: -49.0606,
        volume: 2733933,
        cidade: "Bauru",
        uf: "SP"
    },
    {
        id: "JDI",
        nome: "Hub JDI",
        lat: -23.1864,
        lng: -46.8974,
        volume: 2203167,
        cidade: "Jundiaí",
        uf: "SP"
    },
    {
        id: "IND",
        nome: "Hub IND",
        lat: -23.0905,
        lng: -47.2082,
        volume: 701567,
        cidade: "Indaiatuba",
        uf: "SP"
    },
    {
        id: "PIR",
        nome: "Hub PIR",
        lat: -22.7338,
        lng: -47.6476,
        volume: 494000,
        cidade: "Piracicaba",
        uf: "SP"
    },
    {
        id: "LIM",
        nome: "Hub LIM",
        lat: -22.5641,
        lng: -47.4015,
        volume: 497000,
        cidade: "Limeira",
        uf: "SP"
    },
    {
        id: "CPS",
        nome: "Hub CPS",
        lat: -22.9099,
        lng: -47.0626,
        volume: 1850420,
        cidade: "Campinas",
        uf: "SP"
    },
    {
        id: "GRU",
        nome: "Hub GRU",
        lat: -23.4356,
        lng: -46.4731,
        volume: 4120300,
        cidade: "Guarulhos",
        uf: "SP"
    },
    {
        id: "CWB",
        nome: "Hub CWB",
        lat: -25.4284,
        lng: -49.2733,
        volume: 1620800,
        cidade: "Curitiba",
        uf: "PR"
    },
    {
        id: "RIO",
        nome: "Hub RIO",
        lat: -22.9068,
        lng: -43.1729,
        volume: 3450100,
        cidade: "Rio de Janeiro",
        uf: "RJ"
    },
    {
        id: "BHZ",
        nome: "Hub BHZ",
        lat: -19.9167,
        lng: -43.9345,
        volume: 1980750,
        cidade: "Belo Horizonte",
        uf: "MG"
    },
    {
        id: "VTM",
        nome: "Hub VTM",
        lat: -23.5431,
        lng: -46.6327,
        volume: 5200000,
        cidade: "São Paulo",
        uf: "SP"
    },
    {
        id: "SJC",
        nome: "Hub SJC",
        lat: -23.1791,
        lng: -45.8872,
        volume: 890340,
        cidade: "São José dos Campos",
        uf: "SP"
    }
];

/**
 * Formata um número com separador de milhar (ponto)
 * Ex: 2733933 → "2.733.933"
 */
function formatarNumero(num) {
    return num.toLocaleString("pt-BR");
}
