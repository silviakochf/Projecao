"""
Motor de progressão de alunos.
Regras:
  - GT5 → 1º ANO (fundamental municipal/estadual)
  - 5º ANO → 6º ANO (se escola só vai até 5º)
  - 8º ANO → 9º ANO (se escola só vai até 8º)
  - 9º ANO → 1º ANO ensino medio (se creche só vai até GT3)
  - GT4 → GT3 (se creche vai até GT2)
  - GT1 → GT2 (se creche vai até GT1)
Prioridade: 1) Estadual mesmo bairro 2) Municipal mesmo bairro 3) Bairros próximos
"""

from .bairros import (ESTADUAIS, MUNICIPAIS, BAIRROS_PROXIMOS,
                       get_bairro_by_escola, get_bairros_proximos)


# Regras de progressão: serie_atual → serie_destino
REGRAS_PROGRESSAO = {
    "GT 5": "1º ANO",
    "GT5":  "1º ANO",
    "5º ANO": "6º ANO",
    "3º ANO": "4º ANO",
    "2º ANO": "3º ANO",
    "8º ANO": "9º ANO",
    "9º ANO": "1º ANO MEDIO",  # para ensino médio estadual
    "GT 3": "GT 4",   # progressão interna CEI
    "GT 2": "GT 3",   # se creche vai até GT2
    "GT 1": "GT 2",
}

# Tipo de escola destino por série
TIPO_DESTINO = {
    "1º ANO MEDIO": "ensino medio",
    "1º ANO": "fundamental",
    "4º ANO": "fundamental",
    "5º ANO": "fundamental",
    "3º ANO": "fundamental",
    "6º ANO": "fundamental",
    "9º ANO": "fundamental",
    "GT 3":   "cei",
    "GT 2":   "cei",
}


def normaliza_serie(serie: str) -> str:
    s = serie.upper().strip()
    s = s.replace("º", "º").replace("°", "º")
    return s


def get_serie_destino(serie_atual: str) -> str:
    s = normaliza_serie(serie_atual)
    for k, v in REGRAS_PROGRESSAO.items():
        if k.upper() in s or s in k.upper():
            return v
    return ""


def sugerir_escola(escola_origem: str, bairro_origem: str,
                   serie_destino: str, turno: str,
                   vagas_municipais: dict, vagas_estaduais: dict) -> list:
    """
    Retorna lista de sugestões ordenadas por prioridade.
    vagas_municipais: {escola: {serie: {turno: vagas_disponiveis}}}
    vagas_estaduais:  {escola: {serie: {turno: vagas_disponiveis}}}
    """
    sugestoes = []
    tipo = TIPO_DESTINO.get(serie_destino, "fundamental")
    bairro_orig = bairro_origem.upper()

    # Ordem de bairros a verificar
    bairros_ordem = [bairro_orig] + get_bairros_proximos(bairro_orig)

    for bairro in bairros_ordem:
        # 1. Estaduais do bairro
        for escola in ESTADUAIS.get(bairro, []):
            vagas = _get_vagas(escola, serie_destino, turno, vagas_estaduais)
            if vagas is not None:
                sugestoes.append({
                    'escola': escola,
                    'tipo': 'ESTADUAL',
                    'bairro': bairro,
                    'serie': serie_destino,
                    'turno': turno,
                    'vagas_disponiveis': vagas,
                    'prioridade': 1 if bairro == bairro_orig else 2,
                    'mesmo_bairro': bairro == bairro_orig
                })

        # 2. Municipais do bairro
        for escola in MUNICIPAIS.get(bairro, []):
            vagas = _get_vagas(escola, serie_destino, turno, vagas_municipais)
            if vagas is not None:
                sugestoes.append({
                    'escola': escola,
                    'tipo': 'MUNICIPAL',
                    'bairro': bairro,
                    'serie': serie_destino,
                    'turno': turno,
                    'vagas_disponiveis': vagas,
                    'prioridade': 3 if bairro == bairro_orig else 4,
                    'mesmo_bairro': bairro == bairro_orig
                })

    # Ordena: mesmo bairro primeiro, estadual antes de municipal, mais vagas
    sugestoes.sort(key=lambda x: (x['prioridade'], -x['vagas_disponiveis']))
    return sugestoes


def _get_vagas(escola: str, serie: str, turno: str, vagas_dict: dict) -> int | None:
    """Busca vagas disponíveis de forma fuzzy."""
    escola_up = escola.upper()
    for k, series_data in vagas_dict.items():
        if _match_escola(escola_up, k.upper()):
            serie_data = series_data.get(serie, {})
            if not isinstance(serie_data, dict):
                continue
            # Turno exato ou qualquer turno
            if turno.upper() in serie_data:
                return serie_data[turno.upper()]
            # Qualquer turno com vaga
            total = sum(v for v in serie_data.values() if isinstance(v, int))
            return total if total > 0 else None
    return None


def _match_escola(a: str, b: str) -> bool:
    """Match fuzzy entre nomes de escola."""
    words_a = set(w for w in a.split() if len(w) > 3)
    words_b = set(w for w in b.split() if len(w) > 3)
    common = words_a & words_b
    return len(common) >= 2


def processar_turmas_para_progressao(turmas_alunos: list,
                                      vagas_municipais: dict,
                                      vagas_estaduais: dict,
                                      bairro_escola: str) -> list:
    """
    turmas_alunos: [{turma, serie, turno, alunos: [{nome, codigo,...}]}]
    Retorna: lista de turmas com sugestões de destino
    """
    resultado = []
    for turma in turmas_alunos:
        serie_destino = get_serie_destino(turma['serie'])
        if not serie_destino:
            continue

        sugestoes = sugerir_escola(
            escola_origem=turma.get('escola', ''),
            bairro_origem=bairro_escola,
            serie_destino=serie_destino,
            turno=turma.get('turno', 'MANHÃ'),
            vagas_municipais=vagas_municipais,
            vagas_estaduais=vagas_estaduais
        )

        resultado.append({
            'turma': turma['turma'],
            'serie_atual': turma['serie'],
            'serie_destino': serie_destino,
            'turno': turma['turno'],
            'total_alunos': len(turma.get('alunos', [])),
            'alunos': turma.get('alunos', []),
            'sugestoes': sugestoes[:5],  # top 5
            'escola_sugerida': sugestoes[0] if sugestoes else None
        })

    return resultado