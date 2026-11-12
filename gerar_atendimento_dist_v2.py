"""
gerar_atendimento_dist_v2.py
============================
Gera/atualiza Atendimento_dist.xlsx aplicando a regra:
  - REGIONAL == "SPM"
  - Direção == "SAÍDA"

Produz duas abas:
  1. "SPM - Atual": Pares únicos (CD, Canteiro) da malha atual de São Paulo (SAÍDA).
  2. "Pq Novo Mundo": Distribuição a partir do único CD Parque Novo Mundo para os canteiros (SAÍDA).
"""

import json
import os
import subprocess
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_MATRIZ = os.path.join(BASE_DIR, "Matriz_Malha_Logistica.xlsx")
EXCEL_ATENDIMENTO = os.path.join(BASE_DIR, "Atendimento_dist.xlsx")
CEP_CACHE_PATH = os.path.join(BASE_DIR, "cep_cache.json")
DIST_CACHE_PATH = os.path.join(BASE_DIR, "dist_cache.json")

# CD Parque Novo Mundo
CD_PNM_CODE = "1"
CD_PNM_NAME = "Parque Novo Mundo"
CD_PNM_ADDR = "Avenida Educador Paulo Freire, 986 - São Paulo"
CD_PNM_LAT = -23.5136874
CD_PNM_LNG = -46.5606266

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_road_distance(lat1, lng1, lat2, lng2, dist_cache):
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
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data.get("code") == "Ok" and data.get("routes"):
                dist_km = round(data["routes"][0]["distance"] / 1000, 1)
                if dist_cache is not None:
                    dist_cache[cache_key] = dist_km
                return dist_km
    except Exception as e:
        print(f"    ⚠ Erro OSRM: {e}")

    return None

def write_sheet(ws, rows_data, sheet_title):
    ws.delete_rows(1, ws.max_row + 1)
    ws.title = sheet_title

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

    headers = [
        "Código CD", "Nome CD", "Endereço CD",
        "Código Fornecedor\n(Canteiro)", "Cidade Canteiro",
        "Distância Rodoviária\n(km)"
    ]
    col_widths = [12, 28, 55, 20, 22, 18]

    for c, (header, width) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(1, c, header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(c)].width = width

    ws.row_dimensions[1].height = 35

    for i, res in enumerate(rows_data, 2):
        row_values = [
            res["cd_code"],
            res["cd_name"],
            res["cd_addr"],
            res["cod_forn"],
            res["cidade_cant"],
            res["dist_km"],
        ]

        use_alt = (i % 2 == 0)

        for c, val in enumerate(row_values, 1):
            cell = ws.cell(i, c, val)
            cell.font = cell_font
            cell.border = thin_border
            if c == 6 and val is not None:
                cell.number_format = '#,##0.0'
                cell.alignment = center_align
            elif c in (1, 4):
                cell.alignment = center_align
            else:
                cell.alignment = cell_align

            if use_alt:
                cell.fill = alt_fill

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:F{len(rows_data) + 1}"

def main():
    print("=" * 65)
    print("  Atualizando Atendimento_dist.xlsx (Filtro: Direção == SAÍDA)")
    print("=" * 65)

    cep_cache = load_json(CEP_CACHE_PATH)
    dist_cache = load_json(DIST_CACHE_PATH)

    # Ler Matriz_Malha_Logistica.xlsx
    wb_mat = openpyxl.load_workbook(EXCEL_MATRIZ, data_only=True)
    ws_mat = wb_mat["Consolidado"]

    # Mapeamento prévio de nomes e endereços de CDs
    known_cd_names = {
        "D002": "Ponte Pequena",
        "D024": "ABV | Alto da Boa Vista",
        "D094": "Vila dos Remédios",
        "D029": "São Miguel Paulista",
        "D028": "Pirituba",
        "D019": "Lapa",
        "D035": "Santo André",
        "D020": "Mooca",
        "D075": "São Mateus",
        "D030": "Vila Prudente",
        "D040": "Suzano",
        "D034": "Guaraú",
    }

    cd_addr_map = {}
    for r in range(2, ws_mat.max_row + 1):
        code = str(ws_mat.cell(r, 4).value or "").strip()
        addr = str(ws_mat.cell(r, 5).value or "").strip()
        name = str(ws_mat.cell(r, 3).value or "").strip()
        if code:
            if addr and str(addr) not in ("0", "None", ""):
                cd_addr_map[code] = addr
            if name and str(name) not in ("0", "None", "") and code not in known_cd_names:
                known_cd_names[code] = name

    # 1. Coletar dados da Aba 1 (SPM - Atual) com Direção == "SAÍDA"
    pares_spm_saida = []
    vistos_spm = set()
    canteiros_saida = {}

    for r in range(2, ws_mat.max_row + 1):
        direcao = str(ws_mat.cell(r, 1).value or "").strip()
        regional = str(ws_mat.cell(r, 19).value or "").strip()

        if regional != "SPM" or direcao.upper() != "SAÍDA":
            continue

        cd_code = str(ws_mat.cell(r, 4).value or "").strip()
        cd_name = known_cd_names.get(cd_code, str(ws_mat.cell(r, 3).value or "").strip())
        cd_addr = cd_addr_map.get(cd_code, str(ws_mat.cell(r, 5).value or "").strip())

        cod_forn = str(ws_mat.cell(r, 8).value or "").strip()
        cidade_cant = str(ws_mat.cell(r, 9).value or "").strip()
        cep_cant = str(ws_mat.cell(r, 10).value or "").strip()
        rua_cant = str(ws_mat.cell(r, 11).value or "").strip()

        chave_par = (cd_code, cod_forn)
        if chave_par not in vistos_spm:
            vistos_spm.add(chave_par)
            pares_spm_saida.append({
                "cd_code": cd_code,
                "cd_name": cd_name,
                "cd_addr": cd_addr,
                "cod_forn": cod_forn,
                "cidade_cant": cidade_cant,
                "cep_cant": cep_cant,
                "rua_cant": rua_cant,
            })

        if cod_forn not in canteiros_saida:
            canteiros_saida[cod_forn] = {
                "cod_forn": cod_forn,
                "cidade_cant": cidade_cant,
                "cep_cant": cep_cant,
                "rua_cant": rua_cant,
            }

    print(f"✅ Aba 'SPM - Atual' (Filtro SAÍDA): {len(pares_spm_saida)} pares (CD ↔ Canteiro)")
    print(f"✅ Aba 'Pq Novo Mundo' (Filtro SAÍDA): {len(canteiros_saida)} canteiros únicos")

    # ── Geocodificar CDs ───────────────────────────────────────────────────────
    cd_coords = {}
    for cd_code, cd_addr in cd_addr_map.items():
        parts = cd_addr.replace(",", " ").split()
        cep_cd = ""
        for part in parts:
            clean = part.strip()
            if len(clean.replace("-", "")) in (8, 9) and clean.replace("-", "").isdigit():
                cep_cd = clean
                break
        cep_limpo = cep_cd.replace("-", "").replace(".", "").strip()
        if cep_limpo and cep_limpo in cep_cache and cep_cache[cep_limpo].get("lat"):
            cd_coords[cd_code] = (cep_cache[cep_limpo]["lat"], cep_cache[cep_limpo]["lng"])

    # ── Resgatar coords Canteiros SAÍDA ───────────────────────────────────────
    cant_coords = {}
    for cod_forn, info in canteiros_saida.items():
        cep_limpo = info["cep_cant"].replace("-", "").replace(".", "").strip()
        if cep_limpo and cep_limpo in cep_cache and cep_cache[cep_limpo].get("lat"):
            cant_coords[cod_forn] = (cep_cache[cep_limpo]["lat"], cep_cache[cep_limpo]["lng"])

    # ── Processar resultados Aba 1 (SPM - Atual) ──────────────────────────────
    resultados_spm = []
    for p in pares_spm_saida:
        cd_code = p["cd_code"]
        cod_forn = p["cod_forn"]

        cd_ll = cd_coords.get(cd_code)
        cant_ll = cant_coords.get(cod_forn)

        dist_km = None
        if cd_ll and cant_ll:
            lat1, lng1 = cd_ll
            lat2, lng2 = cant_ll
            dist_km = get_road_distance(lat1, lng1, lat2, lng2, dist_cache)

        resultados_spm.append({
            "cd_code": cd_code,
            "cd_name": p["cd_name"],
            "cd_addr": p["cd_addr"],
            "cod_forn": cod_forn,
            "cidade_cant": p["cidade_cant"],
            "dist_km": dist_km,
        })

    resultados_spm.sort(key=lambda x: (x["cd_code"], x["dist_km"] if x["dist_km"] is not None else 99999))

    # ── Processar resultados Aba 2 (Pq Novo Mundo) ────────────────────────────
    resultados_pnm = []
    for cod_forn, info in canteiros_saida.items():
        cant_ll = cant_coords.get(cod_forn)

        dist_km = None
        if cant_ll:
            lat2, lng2 = cant_ll
            dist_km = get_road_distance(CD_PNM_LAT, CD_PNM_LNG, lat2, lng2, dist_cache)

        resultados_pnm.append({
            "cd_code": CD_PNM_CODE,
            "cd_name": CD_PNM_NAME,
            "cd_addr": CD_PNM_ADDR,
            "cod_forn": cod_forn,
            "cidade_cant": info["cidade_cant"],
            "dist_km": dist_km,
        })

    resultados_pnm.sort(key=lambda x: (x["dist_km"] if x["dist_km"] is not None else 99999))

    save_json(DIST_CACHE_PATH, dist_cache)

    # ── Gravar em Atendimento_dist.xlsx ───────────────────────────────────────
    print(f"\n📝 Gravando em {os.path.basename(EXCEL_ATENDIMENTO)}...")
    wb_out = openpyxl.Workbook()

    ws1 = wb_out.active
    write_sheet(ws1, resultados_spm, "SPM - Atual")

    ws2 = wb_out.create_sheet(title="Pq Novo Mundo")
    write_sheet(ws2, resultados_pnm, "Pq Novo Mundo")

    wb_out.save(EXCEL_ATENDIMENTO)

    print(f"\n✅ Planilha atualizada com sucesso!")
    print(f"📊 Aba 'SPM - Atual': {len(resultados_spm)} linhas")
    print(f"📊 Aba 'Pq Novo Mundo': {len(resultados_pnm)} linhas")
    print("=" * 65)

if __name__ == "__main__":
    main()
