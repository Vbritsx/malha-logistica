import openpyxl
import os
import json
import urllib.request
import time
import re

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

def geocodificar_cep(cep):
    cep_clean = str(cep).strip().replace(".", "").replace("-", "")
    if len(cep_clean) < 8:
        cep_clean = cep_clean.zfill(8)
    if len(cep_clean) != 8:
        return None

    # Tentar AwesomeAPI
    url = f"https://cep.awesomeapi.com.br/json/{cep_clean}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            lat = float(data.get("lat"))
            lng = float(data.get("lng"))
            return {"lat": lat, "lng": lng, "cep": cep_clean, "cidade": data.get("city"), "bairro": data.get("district")}
    except Exception:
        # Tentar BrasilAPI
        url_brasil = f"https://brasilapi.com.br/api/cep/v2/{cep_clean}"
        try:
            req = urllib.request.Request(url_brasil, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                coords = data.get("location", {}).get("coordinates", {})
                if coords:
                    return {"lat": float(coords.get("latitude")), "lng": float(coords.get("longitude")), "cep": cep_clean, "cidade": data.get("city"), "bairro": data.get("neighborhood")}
        except Exception:
            pass
    return None

def geocodificar_endereco(endereco_completo):
    # Usar Nominatim OpenStreetMap search API
    encoded_addr = urllib.parse.quote(endereco_completo)
    url = f"https://nominatim.openstreetmap.org/search?q={encoded_addr}&format=json&limit=1"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'AntigravityLogisticsDashboard/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data:
                return {
                    "lat": float(data[0]["lat"]),
                    "lng": float(data[0]["lon"]),
                    "display_name": data[0]["display_name"]
                }
    except Exception as e:
        print(f"Erro ao geocodificar endereco por Nominatim: {e}")
    return None

def processar():
    file_path = "Matriz_Malha_Logistica.xlsx"
    if not os.path.exists(file_path):
        print(f"Erro: {file_path} não encontrado.")
        return

    print("Carregando o arquivo Excel...")
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb["Consolidado"]
    
    rows = list(ws.iter_rows(values_only=True))
    header = rows[0]
    data = rows[1:]
    wb.close()
    
    # Índices com base no cabeçalho atualizado
    idx_direcao = header.index("Direção")
    idx_cd_label = header.index("deposito_label")
    idx_cd_name = header.index("Nome deposito")
    idx_cd_code = header.index("Deposito")
    idx_cd_addr = header.index("Endereço Deposito")
    idx_cd_city = header.index("Cidade deposito")
    idx_material = header.index("categoria_material")
    idx_forn_code = header.index("codigo_fornecedor")
    idx_forn_city = header.index("Cidade forn.-canteiro")
    idx_cep = header.index("CEP")
    idx_rua = header.index("Rua")
    idx_movs = header.index("Soma Linhas (Movimentações)")
    idx_volume = header.index("Soma qtde_positiva (volume)")
    idx_valor = header.index("Valor_Movimentado")
    
    cache = carregar_cache()
    novos_geocods = 0
    
    # 1. Mapear e geocodificar CDs
    print("Mapeando CDs únicos e seus endereços...")
    cds_info = {}
    for r in data:
        if not r: continue
        cd_code = r[idx_cd_code]
        cd_name = r[idx_cd_name]
        cd_addr = r[idx_cd_addr]
        cd_city = r[idx_cd_city]
        
        if cd_code and cd_code not in cds_info:
            # Tentar extrair CEP do endereço
            cep_cd = None
            if cd_addr:
                cep_match = re.search(r'\d{5}-\d{3}', str(cd_addr))
                if cep_match:
                    cep_cd = cep_match.group(0).replace("-", "")
            
            cds_info[cd_code] = {
                "id": cd_code,
                "nome": cd_name if cd_name != 0 and cd_name != "0" else f"CD {cd_code}",
                "endereco": cd_addr,
                "cidade": cd_city if cd_city != 0 and cd_city != "0" else "São Paulo",
                "cep": cep_cd,
                "lat": None,
                "lng": None
            }

    print(f"Total de CDs únicos para geocodificar: {len(cds_info)}")
    for cd_code, info in cds_info.items():
        # Geocodificar CD
        lat, lng = None, None
        
        # 1. Tentar por CEP
        if info["cep"]:
            cep_key = info["cep"]
            if cep_key in cache and cache[cep_key]:
                lat = cache[cep_key]["lat"]
                lng = cache[cep_key]["lng"]
                print(f"CD {cd_code} ({info['nome']}) geocodificado por CEP no cache.")
            else:
                print(f"Buscando coordenadas por CEP para CD {cd_code}...")
                res = geocodificar_cep(info["cep"])
                if res:
                    cache[cep_key] = res
                    lat, lng = res["lat"], res["lng"]
                    novos_geocods += 1
                    time.sleep(0.2)
                    
        # 2. Se falhar, tentar por Endereço no Nominatim
        if (lat is None or lng is None) and info["endereco"]:
            addr_key = f"ADDR_{info['endereco']}"
            if addr_key in cache and cache[addr_key]:
                lat = cache[addr_key]["lat"]
                lng = cache[addr_key]["lng"]
                print(f"CD {cd_code} ({info['nome']}) geocodificado por Endereço no cache.")
            else:
                print(f"Buscando coordenadas por Endereço para CD {cd_code}...")
                res = geocodificar_endereco(info["endereco"])
                if res:
                    cache[addr_key] = res
                    lat, lng = res["lat"], res["lng"]
                    novos_geocods += 1
                    time.sleep(0.5) # Delay maior para o Nominatim

        # 3. Fallback fixo de segurança se tudo falhar
        if lat is None or lng is None:
            # Usar coordenadas aproximadas anteriores ou padrão SP
            fallback_coords = {
                "D002": (-22.7388, -47.3323),
                "D019": (-23.5284, -46.7025),
                "D020": (-23.5593, -46.6083),
                "D024": (-23.6335, -46.6806),
                "D028": (-23.4930, -46.7230),
                "D029": (-23.4952, -46.4388),
                "D030": (-23.5788, -46.5922),
                "D034": (-23.4357, -46.6346),
                "D035": (-23.6599, -46.5298),
                "D040": (-23.5604, -46.3090),
                "D075": (-23.6062, -46.4678),
                "D094": (-23.5230, -46.7554),
            }
            lat, lng = fallback_coords.get(cd_code, (-23.5505, -46.6333))
            print(f"CD {cd_code} usando fallback fixo.")
            
        info["lat"] = lat
        info["lng"] = lng

    salvar_cache(cache)
    
    # 2. Mapear e geocodificar Parceiros (Clientes e Fornecedores)
    print("Mapeando CEPs únicos dos fornecedores/clientes...")
    ceps_unicos = set()
    for r in data:
        if not r: continue
        cep = r[idx_cep]
        if cep:
            cep_clean = str(cep).strip().replace(".", "").replace("-", "")
            if len(cep_clean) == 8:
                ceps_unicos.add(cep_clean)
                
    print(f"Total de CEPs únicos encontrados para parceiros: {len(ceps_unicos)}")
    
    total = len(ceps_unicos)
    for i, cep in enumerate(sorted(ceps_unicos)):
        if cep not in cache:
            print(f"[{i+1}/{total}] Geocodificando CEP parceiro: {cep}...")
            res = geocodificar_cep(cep)
            if res:
                cache[cep] = res
                novos_geocods += 1
            else:
                cache[cep] = None
            
            if novos_geocods % 20 == 0 and novos_geocods > 0:
                salvar_cache(cache)
            time.sleep(0.15)

    salvar_cache(cache)
    print("Geocodificação de parceiros concluída!")
    
    # 3. Consolidar CDs (com volume e movimentações acumulados)
    cds_dict = {}
    for code, info in cds_info.items():
        # Calcular volume total associado a esse CD
        vol_total = 0
        mov_total = 0
        for r in data:
            if not r: continue
            if r[idx_cd_code] == code:
                vol_total += r[idx_volume] or 0
                mov_total += r[idx_movs] or 0
                
        cds_dict[code] = {
            "id": code,
            "nome": info["nome"],
            "endereco": info["endereco"],
            "cidade": info["cidade"],
            "uf": "SP",
            "lat": info["lat"],
            "lng": info["lng"],
            "volume": vol_total,
            "movimentacoes": mov_total,
            "tipo": "CD"
        }
        
    # 4. Consolidar Parceiros
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
        valor = r[idx_valor] or 0
        material = r[idx_material] or "Outros"
        
        cep_clean = str(cep).strip().replace(".", "").replace("-", "") if cep else ""
        cep_coords = cache.get(cep_clean)
        
        # Só incluir se tivermos coordenadas válidas para CD e Parceiro
        if cep_coords and cd_code in cds_dict:
            lat = cep_coords["lat"]
            lng = cep_coords["lng"]
            
            partner_id = f"P_{forn_code}_{cep_clean}"
            # Se for OUTBOUND (SAÍDA), é Canteiro. Se for INBOUND (ENTRADA), é Fornecedor.
            tipo_parceiro = "Canteiro" if direcao == "SAÍDA" else "Fornecedor"
            
            if partner_id not in parceiros:
                parceiros[partner_id] = {
                    "id": partner_id,
                    "codigo": forn_code,
                    "cidade": forn_city,
                    "cep": cep_clean,
                    "rua": r[idx_rua] or "",
                    "lat": lat,
                    "lng": lng,
                    "tipo": tipo_parceiro,
                    "volume": 0,
                    "movimentacoes": 0,
                    "valorTotal": 0,
                    "materiais": []
                }
            
            # Se o mesmo parceiro atua em ambas direções, atualiza o tipo ou mantém genérico
            if parceiros[partner_id]["tipo"] != tipo_parceiro:
                parceiros[partner_id]["tipo"] = "Fornecedor/Canteiro"
                
            parceiros[partner_id]["volume"] += volume
            parceiros[partner_id]["movimentacoes"] += movs
            parceiros[partner_id]["valorTotal"] += valor
            if material and material not in parceiros[partner_id]["materiais"]:
                parceiros[partner_id]["materiais"].append(material)
            
            # Registrar fluxo
            fluxos.append({
                "origem": cd_code if direcao == "SAÍDA" else partner_id,
                "destino": partner_id if direcao == "SAÍDA" else cd_code,
                "volume": volume,
                "movimentacoes": movs,
                "material": material,
                "direcao": direcao,
                "cd": cd_code,
                "parceiro": partner_id
            })
            
    # Salvar em js/data.js
    saida_js = f"""// Dados gerados automaticamente a partir do Excel consolidado

const CDS_DATA = {json.dumps(list(cds_dict.values()), ensure_ascii=False, indent=4)};

const PARCEIROS_DATA = {json.dumps(list(parceiros.values()), ensure_ascii=False, indent=4)};

const FLUXOS_DATA = {json.dumps(fluxos, ensure_ascii=False, indent=4)};
"""
    
    with open("js/data.js", "w", encoding="utf-8") as f:
        f.write(saida_js)
        
    print(f"Salvo {len(cds_dict)} CDs, {len(parceiros)} parceiros e {len(fluxos)} fluxos em js/data.js!")

if __name__ == "__main__":
    processar()
