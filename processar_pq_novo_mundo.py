"""
processar_pq_novo_mundo.py
==========================
Calcula as distâncias rodoviárias do novo CD 'Parque Novo Mundo' (SP)
para todos os 377 canteiros de obras de São Paulo (SPM) e atualiza a aba
'Pq Novo Mundo' no arquivo Atendimento_dist.xlsx.
"""

import json
import os
import time
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
CD_CODE = "1"
CD_NAME = "Parque Novo Mundo"
CD_ADDR = "Avenida Educador Paulo Freire, 986 - São Paulo"
CD_LAT = -23.5136874
CD_LNG = -46.5606266

OSRM_DELAY = 0.3  # segundos entre chamadas OSRM

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

def main():
    print("=" * 65)
    print("  Processando Distâncias: CD Parque Novo Mundo ↔ Canteiros SPM")
    print("=" * 65)

    cep_cache = load_json(CEP_CACHE_PATH)
    dist_cache = load_json(DIST_CACHE_PATH)

    print(f"\n📂 CEP Cache: {len(cep_cache)} registros")
    print(f"📂 Dist Cache: {len(dist_cache)} registros")

    # Ler canteiros SPM a partir do Consolidado da Matriz ou do SPM - Atual
    wb_at = openpyxl.load_workbook(EXCEL_ATENDIMENTO, data_only=True)
    ws_spm = wb_at["SPM - Atual"]

    canteiros = {}  # cod_forn -> dict
    for row in ws_spm.iter_rows(min_row=2, values_only=True):
        if not row or not row[3]:
            continue
        cod_forn = str(row[3]).strip()
        cidade_cant = str(row[4]).strip() if len(row) > 4 and row[4] else ""
        if cod_forn not in canteiros:
            canteiros[cod_forn] = {
                "cod_forn": cod_forn,
                "cidade_cant": cidade_cant
            }

    print(f"\n✅ Total de canteiros únicos SPM identificados: {len(canteiros)}")

    # Obter canteiros com CEP / Rua de Matriz_Malha_Logistica para garantir geocodificação
    wb_mat = openpyxl.load_workbook(EXCEL_MATRIZ, data_only=True)
    ws_mat = wb_mat["Consolidado"]

    for r in range(2, ws_mat.max_row + 1):
        forn = str(ws_mat.cell(r, 8).value or "").strip()
        if forn in canteiros:
            if "cep" not in canteiros[forn]:
                canteiros[forn]["cep"] = str(ws_mat.cell(r, 10).value or "").strip()
                canteiros[forn]["rua"] = str(ws_mat.cell(r, 11).value or "").strip()
                if not canteiros[forn]["cidade_cant"]:
                    canteiros[forn]["cidade_cant"] = str(ws_mat.cell(r, 9).value or "").strip()

    # Resgatar coords de cada canteiro
    cant_coords = {}
    for cod_forn, info in canteiros.items():
        cep_limpo = info.get("cep", "").replace("-", "").replace(".", "").strip()
        if cep_limpo and cep_limpo in cep_cache:
            entry = cep_cache[cep_limpo]
            if isinstance(entry, dict) and entry.get("lat") and entry.get("lng"):
                cant_coords[cod_forn] = (entry["lat"], entry["lng"])

    print(f"  ✅ Canteiros com coordenadas encontradas: {len(cant_coords)}/{len(canteiros)}")

    # Calcular distâncias de Parque Novo Mundo (CD_LAT, CD_LNG) para todos os canteiros
    print(f"\n🚗 Calculando distâncias para Parque Novo Mundo...")
    resultados = []
    cache_hits = 0
    erros = 0

    total = len(canteiros)
    for idx, (cod_forn, info) in enumerate(canteiros.items(), 1):
        coords = cant_coords.get(cod_forn)
        dist_km = None

        if coords:
            lat2, lng2 = coords
            cache_key = f"{CD_LAT:.5f},{CD_LNG:.5f}|{lat2:.5f},{lng2:.5f}"
            if cache_key in dist_cache:
                dist_km = dist_cache[cache_key]
                cache_hits += 1
            else:
                dist_km = get_road_distance(CD_LAT, CD_LNG, lat2, lng2, dist_cache)
                time.sleep(OSRM_DELAY)
            
            if dist_km is None:
                erros += 1
        else:
            erros += 1

        resultados.append({
            "cd_code": CD_CODE,
            "cd_name": CD_NAME,
            "cd_addr": CD_ADDR,
            "cod_forn": cod_forn,
            "cidade_cant": info["cidade_cant"],
            "dist_km": dist_km
        })

        if idx % 50 == 0 or idx == total:
            print(f"  ... {idx}/{total} canteiros processados (Cache hits: {cache_hits}, Erros: {erros})")
            save_json(DIST_CACHE_PATH, dist_cache)

    save_json(DIST_CACHE_PATH, dist_cache)

    # Ordenar por distância (menor para maior)
    resultados.sort(key=lambda x: (x["dist_km"] if x["dist_km"] is not None else 99999))

    # Escrever no Excel Atendimento_dist.xlsx
    print(f"\n📝 Atualizando {os.path.basename(EXCEL_ATENDIMENTO)}...")
    wb_out = openpyxl.load_workbook(EXCEL_ATENDIMENTO)

    target_sheet_name = None
    for name in wb_out.sheetnames:
        if "pq novo mundo" in name.strip().lower():
            target_sheet_name = name
            break

    if target_sheet_name:
        ws_out = wb_out[target_sheet_name]
        ws_out.delete_rows(1, ws_out.max_row + 1)
        ws_out.title = "Pq Novo Mundo"
    else:
        ws_out = wb_out.create_sheet(title="Pq Novo Mundo")

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
        cell = ws_out.cell(1, c, header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border
        ws_out.column_dimensions[get_column_letter(c)].width = width

    ws_out.row_dimensions[1].height = 35

    for i, res in enumerate(resultados, 2):
        row_data = [
            res["cd_code"],
            res["cd_name"],
            res["cd_addr"],
            res["cod_forn"],
            res["cidade_cant"],
            res["dist_km"],
        ]

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

            if i % 2 == 0:
                cell.fill = alt_fill

    ws_out.freeze_panes = "A2"
    ws_out.auto_filter.ref = f"A1:F{len(resultados) + 1}"

    wb_out.save(EXCEL_ATENDIMENTO)
    print(f"\n✅ Planilha atualizada com sucesso!")
    print(f"📊 Total de registros na aba 'Pq Novo Mundo': {len(resultados)}")
    print("=" * 65)

if __name__ == "__main__":
    main()
