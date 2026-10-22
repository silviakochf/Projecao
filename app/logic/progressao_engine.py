"""Motor de progressão — aloca TURMAS INTEIRAS priorizando estaduais."""
import re
from .bairros import ESTADUAIS, MUNICIPAIS, get_bairros_proximos

REGRAS = {
    "GT 5": "1º ANO", "GT5": "1º ANO",
    "5º ANO": "6º ANO",
    "8º ANO": "9º ANO",
    "9º ANO": "GT 3",
    "GT 4": "GT 3",
    "GT 3": "GT 2",
    "GT 2": "GT 3",
    "GT 1": "GT 2",
}

def get_serie_destino(serie: str) -> str:
    s = serie.upper().strip()
    for k, v in REGRAS.items():
        if k.upper() in s or s in k.upper():
            return v
    return ""

def _match_escola(a: str, b: str) -> bool:
    wa = set(w for w in a.upper().split() if len(w) > 3)
    wb = set(w for w in b.upper().split() if len(w) > 3)
    return len(wa & wb) >= 2

def _vagas_escola(escola: str, serie: str, turno: str, vagas_dict: dict) -> int:
    for k, series in vagas_dict.items():
        if _match_escola(escola, k):
            sd = series.get(serie, {})
            if not isinstance(sd, dict):
                continue
            if turno in sd and sd[turno] > 0:
                return sd[turno]
            total = sum(v for v in sd.values() if isinstance(v, int) and v > 0)
            if total > 0:
                return total
            if serie in series:
                return 0
    return -1

def _encontrar_escola(bairro_origem, serie_destino, turno, n_alunos,
                      vagas_mun, vagas_est, escolas_usadas):
    bairros = [bairro_origem.upper()] + get_bairros_proximos(bairro_origem.upper())
    candidatos = []
    for bairro in bairros:
        mesmo = bairro == bairro_origem.upper()
        for escola in ESTADUAIS.get(bairro, []):
            v = _vagas_escola(escola, serie_destino, turno, vagas_est)
            if v < 0: continue
            usadas = escolas_usadas.get(f"{escola}|{serie_destino}|{turno}", 0)
            candidatos.append({"escola":escola,"tipo":"ESTADUAL","bairro":bairro,
                "vagas_disponiveis": v - usadas, "vagas_totais": v,
                "mesmo_bairro": mesmo, "prioridade": 1 if mesmo else 2})
        for escola in MUNICIPAIS.get(bairro, []):
            v = _vagas_escola(escola, serie_destino, turno, vagas_mun)
            if v < 0: continue
            usadas = escolas_usadas.get(f"{escola}|{serie_destino}|{turno}", 0)
            candidatos.append({"escola":escola,"tipo":"MUNICIPAL","bairro":bairro,
                "vagas_disponiveis": v - usadas, "vagas_totais": v,
                "mesmo_bairro": mesmo, "prioridade": 3 if mesmo else 4})

    candidatos.sort(key=lambda x: (x["prioridade"], -x["vagas_disponiveis"]))

    # Prefere escola que cabe a turma toda
    for c in candidatos:
        if c["vagas_disponiveis"] >= n_alunos:
            return c
    # Fallback: maior capacidade disponível
    return candidatos[0] if candidatos else None

def processar_turmas(turmas_alunos, vagas_mun, vagas_est, bairro):
    resultado = []
    escolas_usadas = {}
    # Turmas maiores primeiro (mais difíceis de alocar)
    turmas_sorted = sorted(turmas_alunos, key=lambda t: -t.get("total", 0))

    for t in turmas_sorted:
        serie_dest = get_serie_destino(t["serie"])
        if not serie_dest: continue
        n_alunos = t.get("total", len(t.get("alunos", [])))
        turno    = t.get("turno", "MANHÃ")

        sug = _encontrar_escola(bairro, serie_dest, turno, n_alunos,
                                vagas_mun, vagas_est, escolas_usadas)
        if sug:
            key = f"{sug['escola']}|{serie_dest}|{turno}"
            escolas_usadas[key] = escolas_usadas.get(key, 0) + n_alunos
            sug = {**sug, "serie": serie_dest,
                   "cabe_toda": sug["vagas_disponiveis"] >= n_alunos}

        # Outras sugestões (sem descontar)
        outras = []
        for b in [bairro.upper()] + get_bairros_proximos(bairro.upper()):
            for escola in ESTADUAIS.get(b, []) + MUNICIPAIS.get(b, []):
                if sug and escola == sug.get("escola"): continue
                v_e = _vagas_escola(escola, serie_dest, turno, vagas_est)
                v_m = _vagas_escola(escola, serie_dest, turno, vagas_mun)
                v = max(v_e, v_m)
                tipo = "ESTADUAL" if v_e >= 0 else "MUNICIPAL"
                if v >= 0:
                    outras.append({"escola":escola,"tipo":tipo,"bairro":b,"vagas_disponiveis":v})
        outras.sort(key=lambda x: -x["vagas_disponiveis"])

        resultado.append({
            "turma": t["turma"], "serie_atual": t["serie"],
            "serie_destino": serie_dest, "turno": turno,
            "total_alunos": n_alunos, "alunos": t.get("alunos", []),
            "escola_sugerida": sug, "sugestoes": outras[:4],
        })

    resultado.sort(key=lambda x: x["turma"])
    return resultado
