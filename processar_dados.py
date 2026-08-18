import openpyxl
import os
import json
import urllib.request
import time

CACHE_FILE = "cep_cache.json"

def carregar_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("Erro ao carregar cache:", e)
    return {}

def salvar_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print("Erro ao salvar cache:", e)

def geocodificar_cep(cep, cidade_default=None):
    # Limpar CEP
    cep_clean = str(cep).strip().replace(".", "").replace("-", "")
    if len(cep_clean) < 8:
        # Preencher com zeros à esquerda se necessário
        cep_clean = cep_clean.zfill(8)
        
    if len(cep_clean) != 8:
        return None

    # AwesomeAPI
    url = f"https://cep.awesomeapi.com.br/json/{cep_clean}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            lat = float(data.get("lat"))
            lng = float(data.get("lng"))
            return {"lat": lat, "lng": lng, "cep": cep_clean, "cidade": data.get("city"), "bairro": data.get("district")}
    except Exception as e:
        # Tentar BrasilAPI
        url_brasil = f"https://brasilapi.com.br/api/cep/v2/{cep_clean}"
        try:
            req = urllib.request.Request(url_brasil, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                coords = data.get("location", {}).get("coordinates", {})
                if coords:
                    return {"lat": float(coords.get("latitude")), "lng": float(coords.get("longitude")), "cep": cep_clean, "cidade": data.get("city"), "bairro": data.get("neighborhood")}
        except Exception as e2:
            pass
            
    return None

# Coordenadas fixas estimadas para os 12 CDs
COORDS_CDS = {
    "D002": {"lat": -22.7388, "lng": -47.3323, "nome": "Materiais Gerais (Americana)", "cidade": "Americana"},
    "D019": {"lat": -23.5284, "lng": -46.7025, "nome": "Lapa", "cidade": "Lapa"},
    "D020": {"lat": -23.5593, "lng": -46.6083, "nome": "Mooca", "cidade": "Mooca"},
    "D024": {"lat": -23.6335, "lng": -46.6806, "nome": "ABV | Alto da Boa Vista", "cidade": "Santo Amaro"},
    "D028": {"lat": -23.4930, "lng": -46.7230, "nome": "Pirituba", "cidade": "Pirituba"},
    "D029": {"lat": -23.4952, "lng": -46.4388, "nome": "São Miguel Paulista", "cidade": "São Miguel Paulista"},
    "D030": {"lat": -23.5788, "lng": -46.5922, "nome": "Vila Prudente", "cidade": "Vila Prudente"},
    "D034": {"lat": -23.4357, "lng": -46.6346, "nome": "Guaraú", "cidade": "Guaraú"},
    "D035": {"lat": -23.6599, "lng": -46.5298, "nome": "Santo André", "cidade": "Santo André"},
    "D040": {"lat": -23.5604, "lng": -46.3090, "nome": "Suzano", "cidade": "Suzano"},
    "D075": {"lat": -23.6062, "lng": -46.4678, "nome": "São Mateus", "cidade": "São Mateus"},
    "D094": {"lat": -23.5230, "lng": -46.7554, "nome": "Vila dos Remédios", "cidade": "Vila dos Remédios"}
}

def processar():
    file_path = "Matriz_Malha_Logistica.xlsx"
    if not os.path.exists(file_path):
        print(f"Erro: {file_path} não encontrado.")
        return

    print("Carregando o arquivo Excel...")
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb["Consolidado"]
    
    # Extrair linhas
    rows = list(ws.iter_rows(values_only=True))
    header = rows[0]
    data = rows[1:]
    wb.close()
    
    # Índices das colunas
    idx_cd_code = header.index("Deposito")
    idx_cd_name = header.index("Nome deposito")
    idx_cd_city = header.index("Cidade deposito")
    idx_cep = header.index("CEP")
    idx_rua = header.index("Rua")
    idx_forn_code = header.index("codigo_fornecedor")
    idx_forn_city = header.index("Cidade forn.-canteiro")
    idx_material = header.index("categoria_material")
    idx_volume = header.index("Soma qtde_positiva (volume)")
    idx_movs = header.index("Soma Linhas (Movimentações)")
    idx_direcao = header.index("Direção")
    
    print("Mapeando CEPs únicos dos fornecedores/clientes...")
    ceps_unicos = set()
    for r in data:
        if not r: continue
        cep = r[idx_cep]
        if cep:
            cep_clean = str(cep).strip().replace(".", "").replace("-", "")
            if len(cep_clean) == 8:
                ceps_unicos.add(cep_clean)
                
    print(f"Total de CEPs únicos encontrados para geocodificar: {len(ceps_unicos)}")
    
    # Geocodificar
    cache = carregar_cache()
    novos_geocods = 0
    total = len(ceps_unicos)
    
    print("Iniciando geocodificação (usando cache local se disponível)...")
    for i, cep in enumerate(sorted(ceps_unicos)):
        if cep not in cache:
            print(f"[{i+1}/{total}] Geocodificando CEP: {cep}...")
            res = geocodificar_cep(cep)
            if res:
                cache[cep] = res
                novos_geocods += 1
            else:
                cache[cep] = None # Para não tentar de novo
            
            # Salvar cache a cada 20 requisições
            if novos_geocods % 20 == 0 and novos_geocods > 0:
                salvar_cache(cache)
                
            time.sleep(0.15) # Delay para respeitar rate limits

    salvar_cache(cache)
    print("Geocodificação concluída!")
    
    # Construir dados finais
    hubs = []
    for code, info in COORDS_CDS.items():
        # Calcular volume total associado a esse CD no Excel
        vol_total = 0
        mov_total = 0
        for r in data:
            if not r: continue
            if r[idx_cd_code] == code:
                vol_total += r[idx_volume] or 0
                mov_total += r[idx_movs] or 0
                
        hubs.append({
            "id": code,
            "nome": info["nome"],
            "cidade": info["cidade"],
            "uf": "SP",
            "lat": info["lat"],
            "lng": info["lng"],
            "volume": vol_total,
            "movimentacoes": mov_total,
            "tipo": "CD"
        })
        
    # Construir fornecedores/clientes únicos
    parceiros = {}
    fluxos = []
    
    for r in data:
        if not r: continue
        cd_code = r[idx_cd_code]
        cep = r[idx_cep]
        forn_code = r[idx_forn_code]
        forn_city = r[idx_forn_city]
        direcao = r[idx_direcao]
        volume = r[idx_volume] or 0
        movs = r[idx_movs] or 0
        material = r[idx_material] or "Outros"
        
        cep_clean = str(cep).strip().replace(".", "").replace("-", "") if cep else ""
        cep_coords = cache.get(cep_clean)
        
        # Só plotar se tivermos coordenadas válidas
        if cep_coords:
            lat = cep_coords["lat"]
            lng = cep_coords["lng"]
            
            # Definir chave única do parceiro (pode ser o código ou CEP)
            partner_id = f"P_{forn_code}_{cep_clean}"
            
            if partner_id not in parceiros:
                parceiros[partner_id] = {
                    "id": partner_id,
                    "codigo": forn_code,
                    "cidade": forn_city,
                    "cep": cep_clean,
                    "rua": r[idx_rua] or "",
                    "lat": lat,
                    "lng": lng,
                    "tipo": "Cliente/Fornecedor",
                    "volume": 0,
                    "movimentacoes": 0
                }
                
            parceiros[partner_id]["volume"] += volume
            parceiros[partner_id]["movimentacoes"] += movs
            
            # Registrar fluxo entre CD e parceiro
            fluxos.append({
                "origem": cd_code if direcao == "SAÍDA" else partner_id,
                "destino": partner_id if direcao == "SAÍDA" else cd_code,
                "volume": volume,
                "movimentacoes": movs,
                "material": material,
                "direcao": direcao
            })
            
    # Salvar em js/data.js
    saida_js = f"""// Dados gerados automaticamente a partir do Excel consolidado

const HUBS_DATA = {json.dumps(hubs, ensure_ascii=False, indent=4)};

const PARCEIROS_DATA = {json.dumps(list(parceiros.values()), ensure_ascii=False, indent=4)};

const FLUXOS_DATA = {json.dumps(fluxos, ensure_ascii=False, indent=4)};
"""
    
    with open("js/data.js", "w", encoding="utf-8") as f:
        f.write(saida_js)
        
    print(f"Salvo {len(hubs)} CDs, {len(parceiros)} parceiros e {len(fluxos)} fluxos em js/data.js!")

if __name__ == "__main__":
    processar()
