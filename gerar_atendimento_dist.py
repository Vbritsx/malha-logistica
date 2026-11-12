"""
gerar_atendimento_dist.py
=========================
Gera o arquivo Atendimento_dist.xlsx a partir da Matriz_Malha_Logistica.xlsx.

Aba 1 (SPM): Cada linha é um par (CD, Canteiro) onde REGIONAL = "SPM".
  - Código CD, Nome CD, Endereço CD
  - Código Fornecedor (canteiro), Cidade Canteiro
  - Distância Rodoviária (km) via OSRM

Usa cache local para geocodificação (cep_cache.json) e para distâncias
já calculadas (dist_cache.json), evitando chamadas repetidas à API.
"""

import json
import os
import time
import urllib.request
import urllib.parse
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_IN = os.path.join(BASE_DIR, "Matriz_Malha_Logistica.xlsx")
EXCEL_OUT = os.path.join(BASE_DIR, "Atendimento_dist.xlsx")
CEP_CACHE_PATH = os.path.join(BASE_DIR, "cep_cache.json")
DIST_CACHE_PATH = os.path.join(BASE_DIR, "dist_cache.json")

# ── Rate limiting ────────────────────────────────────────────────────────────
OSRM_DELAY = 0.6          # segundos entre chamadas OSRM (respeitando rate limit)
GEOCODE_DELAY = 1.0        # segundos entre chamadas Nominatim

# ── Load caches ─────────────────────────────────────────────────────────────
def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Geocoding via Nominatim (OpenStreetMap) ─────────────────────────────────
def geocode_address(address, city="", cep="", cep_cache=None, skip_cache=False):
    """
    Tenta geocodificar um endereço.
    1. Primeiro tenta pelo CEP no cache local (se skip_cache=False)
    2. Se não encontrar, tenta via Nominatim com o endereço completo
    3. Fallback: tenta apenas com CEP + cidade
    """
    cep_limpo = cep.replace("-", "").replace(".", "").strip() if cep else ""

    # 1. Tentar cache de CEP (pular se skip_cache=True, para forçar busca precisa)
    if not skip_cache and cep_cache and cep_limpo and cep_limpo in cep_cache:
        entry = cep_cache.get(cep_limpo)
        if entry and isinstance(entry, dict) and entry.get("lat") and entry.get("lng"):
            return entry["lat"], entry["lng"]

    # 2. Tentar Nominatim com endereço completo
    queries = []
    if address:
        queries.append(f"{address}, {city}, São Paulo, Brazil")
    if cep_limpo:
        queries.append(f"{cep_limpo}, {city}, São Paulo, Brazil")
    if city:
        queries.append(f"{city}, São Paulo, Brazil")

    for query in queries:
        try:
            params = urllib.parse.urlencode({
                "q": query,
                "format": "json",
                "limit": 1,
                "countrycodes": "br"
            })
            url = f"https://nominatim.openstreetmap.org/search?{params}"
            req = urllib.request.Request(url, headers={
                "User-Agent": "MalhaLogistica/1.0 (internal)"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data and len(data) > 0:
                lat = float(data[0]["lat"])
                lng = float(data[0]["lon"])
                # Salvar no cache
                if cep_cache is not None and cep_limpo:
                    cep_cache[cep_limpo] = {
                        "lat": lat, "lng": lng,
                        "cep": cep_limpo, "cidade": city
                    }
                return lat, lng
            time.sleep(GEOCODE_DELAY)
        except Exception as e:
            print(f"    ⚠ Erro geocoding '{query[:50]}': {e}")
            time.sleep(GEOCODE_DELAY)

    return None, None


# ── Distância rodoviária via OSRM ───────────────────────────────────────────
def get_road_distance(lat1, lng1, lat2, lng2, dist_cache=None):
    """
    Calcula distância rodoviária (km) entre dois pontos via OSRM.
    Usa curl (subprocess) para contornar incompatibilidade SSL do Python 3.9/LibreSSL.
    Usa cache para evitar chamadas repetidas.
    """
    import subprocess

    # Cache key usando coords arredondadas para 5 decimais
    cache_key = f"{lat1:.5f},{lng1:.5f}|{lat2:.5f},{lng2:.5f}"
    if dist_cache is not None and cache_key in dist_cache:
        return dist_cache[cache_key]

    try:
        url = (
            f"https://router.project-osrm.org/route/v1/driving/"
            f"{lng1},{lat1};{lng2},{lat2}?overview=false"
        )
        result = subprocess.run(
            ["curl", "-s", "--max-time", "15", url],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode != 0:
            print(f"    ⚠ curl falhou: {result.stderr[:80]}")
            return None

        data = json.loads(result.stdout)

        if data.get("code") == "Ok" and data.get("routes"):
            dist_km = round(data["routes"][0]["distance"] / 1000, 1)
            if dist_cache is not None:
                dist_cache[cache_key] = dist_km
            return dist_km

    except Exception as e:
        print(f"    ⚠ Erro OSRM: {e}")

    return None


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  Gerador de Atendimento_dist.xlsx")
    print("=" * 65)

    # Carregar caches
    cep_cache = load_json(CEP_CACHE_PATH)
    dist_cache = load_json(DIST_CACHE_PATH)
    print(f"\n📂 CEPs em cache: {len(cep_cache)}")
    print(f"📂 Distâncias em cache: {len(dist_cache)}")

    # Ler Excel
    print(f"\n📖 Lendo: {os.path.basename(EXCEL_IN)}")
    wb = openpyxl.load_workbook(EXCEL_IN, data_only=True)
    ws = wb["Consolidado"]

    # Coletar dados SPM — pares únicos (CD, Canteiro)
    pares_spm = []      # Lista de dicts com dados de cada par
    pares_vistos = set()  # Para evitar duplicatas exatas

    for r in range(2, ws.max_row + 1):
        regional = ws.cell(r, 19).value
        if regional != "SPM":
            continue

        cd_code = str(ws.cell(r, 4).value or "").strip()
        cd_name = str(ws.cell(r, 3).value or "").strip()
        cd_addr = str(ws.cell(r, 5).value or "").strip()
        cod_forn = str(ws.cell(r, 8).value or "").strip()
        cidade_cant = str(ws.cell(r, 9).value or "").strip()
        cep_cant = str(ws.cell(r, 10).value or "").strip()
        rua_cant = str(ws.cell(r, 11).value or "").strip()

        chave = (cd_code, cod_forn)
        if chave in pares_vistos:
            continue
        pares_vistos.add(chave)

        pares_spm.append({
            "cd_code": cd_code,
            "cd_name": cd_name,
            "cd_addr": cd_addr,
            "cod_forn": cod_forn,
            "cidade_cant": cidade_cant,
            "cep_cant": cep_cant,
            "rua_cant": rua_cant,
        })

    print(f"\n✅ Pares únicos SPM (CD ↔ Canteiro): {len(pares_spm)}")

    # ── Geocodificar CDs (poucos, ~12) ───────────────────────────────────────
    print("\n🗺  Geocodificando CDs...")
    cd_coords = {}  # cd_code -> (lat, lng)
    cds_unicos = {p["cd_code"]: p["cd_addr"] for p in pares_spm}

    for cd_code, cd_addr in cds_unicos.items():
        # Extrair CEP do endereço do CD (último token com formato XXXXX-XXX)
        parts = cd_addr.replace(",", " ").split()
        cep_cd = ""
        for part in parts:
            clean = part.strip()
            if len(clean.replace("-", "")) in (8, 9) and clean.replace("-", "").isdigit():
                cep_cd = clean
                break

        # Extrair cidade do endereço (normalmente penúltimo campo separado por vírgula)
        addr_parts = [x.strip() for x in cd_addr.split(",")]
        cidade_cd = addr_parts[-2] if len(addr_parts) >= 2 else ""

        lat, lng = geocode_address(cd_addr, cidade_cd, cep_cd, cep_cache, skip_cache=True)
        if lat and lng:
            cd_coords[cd_code] = (lat, lng)
            print(f"  ✅ {cd_code}: ({lat:.5f}, {lng:.5f})")
        else:
            print(f"  ❌ {cd_code}: Não encontrado — {cd_addr[:60]}")

    # ── Geocodificar Canteiros ────────────────────────────────────────────────
    print(f"\n🗺  Geocodificando Canteiros ({len(pares_spm)} pares)...")
    cant_coords = {}  # (cod_forn, cep) -> (lat, lng)

    canteiros_unicos = {}
    for p in pares_spm:
        key = (p["cod_forn"], p["cep_cant"])
        if key not in canteiros_unicos:
            canteiros_unicos[key] = p

    total_cant = len(canteiros_unicos)
    for idx, (key, p) in enumerate(canteiros_unicos.items(), 1):
        address = p["rua_cant"] if p["rua_cant"] else ""
        lat, lng = geocode_address(address, p["cidade_cant"], p["cep_cant"], cep_cache)
        if lat and lng:
            cant_coords[key] = (lat, lng)
        else:
            print(f"  ❌ [{idx}/{total_cant}] {p['cod_forn']} ({p['cidade_cant']}): Não encontrado")

        if idx % 50 == 0:
            print(f"  ... {idx}/{total_cant} geocodificados")
            save_json(CEP_CACHE_PATH, cep_cache)

    save_json(CEP_CACHE_PATH, cep_cache)
    print(f"  ✅ Canteiros geocodificados: {len(cant_coords)}/{total_cant}")

    # ── Calcular distâncias rodoviárias via OSRM ─────────────────────────────
    print(f"\n🚗 Calculando distâncias rodoviárias ({len(pares_spm)} pares)...")
    resultados = []
    erros = 0
    cache_hits = 0

    for idx, p in enumerate(pares_spm, 1):
        cd_code = p["cd_code"]
        cod_forn = p["cod_forn"]
        cep_cant = p["cep_cant"]

        cd_lat_lng = cd_coords.get(cd_code)
        cant_lat_lng = cant_coords.get((cod_forn, cep_cant))

        dist_km = None
        if cd_lat_lng and cant_lat_lng:
            lat1, lng1 = cd_lat_lng
            lat2, lng2 = cant_lat_lng

            # Verificar cache antes de chamar API
            cache_key = f"{lat1:.5f},{lng1:.5f}|{lat2:.5f},{lng2:.5f}"
            if cache_key in dist_cache:
                dist_km = dist_cache[cache_key]
                cache_hits += 1
            else:
                dist_km = get_road_distance(lat1, lng1, lat2, lng2, dist_cache)
                time.sleep(OSRM_DELAY)

            if dist_km is None:
                erros += 1
        else:
            erros += 1

        resultados.append({
            "cd_code": cd_code,
            "cd_name": p["cd_name"],
            "cd_addr": p["cd_addr"],
            "cod_forn": cod_forn,
            "cidade_cant": p["cidade_cant"],
            "dist_km": dist_km,
        })

        if idx % 50 == 0:
            print(f"  ... {idx}/{len(pares_spm)} processados (cache: {cache_hits})")
            save_json(DIST_CACHE_PATH, dist_cache)

    save_json(DIST_CACHE_PATH, dist_cache)
    print(f"\n  ✅ Concluído: {len(resultados)} pares")
    print(f"  📊 Cache hits: {cache_hits}")
    print(f"  ⚠  Erros: {erros}")

    # ── Ordenar: por CD, depois por distância ─────────────────────────────────
    resultados.sort(key=lambda x: (x["cd_code"], x["dist_km"] or 99999))

    # ── Gerar Excel ───────────────────────────────────────────────────────────
    print(f"\n📝 Gerando: {os.path.basename(EXCEL_OUT)}")
    wb_out = openpyxl.Workbook()
    ws_out = wb_out.active
    ws_out.title = "SPM"

    # Estilos
    header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell_font = Font(name="Calibri", size=10)
    cell_align = Alignment(vertical="center")
    center_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )
    alt_fill = PatternFill(start_color="F2F7FB", end_color="F2F7FB", fill_type="solid")

    # Headers
    headers = [
        "Código CD", "Nome CD", "Endereço CD",
        "Código Fornecedor\n(Canteiro)", "Cidade Canteiro",
        "Distância Rodoviária\n(km)"
    ]
    col_widths = [12, 28, 55, 20, 22, 18]

    for c, (header, width) in enumerate(zip(headers, col_widths), 1):
        cell = ws_out.cell(1, c, header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border
        ws_out.column_dimensions[get_column_letter(c)].width = width

    ws_out.row_dimensions[1].height = 35

    # Data rows
    prev_cd = None
    for i, res in enumerate(resultados, 2):
        row_data = [
            res["cd_code"],
            res["cd_name"],
            res["cd_addr"],
            res["cod_forn"],
            res["cidade_cant"],
            res["dist_km"],
        ]

        use_alt = (res["cd_code"] != prev_cd and prev_cd is not None
                   and i % 2 == 0) or (prev_cd == res["cd_code"] and i % 2 == 0)

        for c, val in enumerate(row_data, 1):
            cell = ws_out.cell(i, c, val)
            cell.font = cell_font
            cell.border = thin_border
            if c == 6 and val is not None:
                cell.number_format = '#,##0.0'
                cell.alignment = center_align
            elif c in (1, 4):
                cell.alignment = center_align
            else:
                cell.alignment = cell_align

            # Zebra striping por CD
            if i % 2 == 0:
                cell.fill = alt_fill

        prev_cd = res["cd_code"]

    # Freeze panes
    ws_out.freeze_panes = "A2"

    # Auto filter
    ws_out.auto_filter.ref = f"A1:F{len(resultados) + 1}"

    wb_out.save(EXCEL_OUT)
    print(f"\n✅ Arquivo salvo: {EXCEL_OUT}")
    print(f"   Linhas: {len(resultados)}")
    print("=" * 65)


if __name__ == "__main__":
    main()
