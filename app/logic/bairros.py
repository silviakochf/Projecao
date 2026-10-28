"""
Mapa de unidades por bairro (Palhoça/SC) — fonte: documento
"Fundamentais estaduais e municipais" da Secretaria de Educação.

>>> Para corrigir/incluir algo, edite os dicionários abaixo:
    - ESTADUAIS / MUNICIPAIS / CEIS ...... unidades por bairro
    - OVERRIDES_BAIRRO .................... unidade que não está no documento
    - BAIRROS_PROXIMOS .................... bairros vizinhos (do mais perto ao mais longe)
"""
import re
import unicodedata

ESTADUAIS = {
    "BELA VISTA":        ["EEB PROFESSOR ANGELO CASCAES TANCREDO", "EEB DOM JAIME DE BARROS CAMARA"],
    "CENTRO":            ["EEB GOV IVO SILVEIRA", "EEF VECESLAU BUENO"],
    "PACHECO":           ["EEB PROFESSOR MARIA DO CARMO"],
    "BARRA DO ARIRIÚ":   ["EEB SENADOR RENATO RAMOS DA SILVA"],
    "PONTE DO IMARUIM":  ["EEB GOV PEDRO IVO FIGUEIREDO DE CAMPO", "EEB HENRIQUE ESTEFANO KOERICH",
                          "EEB PROFESSORA CLAUDETE MARIA HOFFMAN"],
    "ARIRIÚ":            ["EEB JOÃO SILVEIRA"],
    "ALTO ARIRIÚ":       ["EEB PROFESSOR NICOLINA TANCREDO"],
    "ENSEADA DO BRITO":  ["EEB JOSÉ MARIA CARDOSO DE VEIGA"],
    "PINHEIRA":          ["EEB PEDRO VICENTE F CORDEIRO"],
    "BREJARU":           ["EEB PROFESSOR BENONIVIO JOÃO MARTINS"],
    "CAMINHO NOVO":      ["EEB PROFESSOR URSULINA SENNA CASTRO"],
    "PASSA VINTE":       ["EEB VICENTE SILVEIRA"],
    "SÃO SEBASTIÃO":     ["EEB PROFESSOR MARIA CLEMENTINA DE SOUZA LOPES"],
}

MUNICIPAIS = {
    "ARIRIÚ":              ["EB NOSSA SENHORA DE FATIMA"],
    "ARIRIÚ DA FORMIGA":   ["EB LAURITA SILVEIRA WAGNER"],
    "NOVA PALHOÇA":        ["EBM PROFESSOR OSMAR ANTONIO VIEIRA"],
    "RIO GRANDE":          ["EBM REINALDO WEINGARTNER", "GE EVANDA SUELLI MACHADO"],
    "CENTRO":              ["EB VIVIANE LAURITA DE QUADROS COELHO"],
    "BELA VISTA":          ["EB GUILHERME WIETHORN FILHO"],
    "JARDIM ELDORADO":     ["GE PEQUENO PRINCIPE"],
    "CAMINHO NOVO":        ["EB PROF ADRIANA WEINGARTNER"],
    "SÃO SEBASTIÃO":       ["EB PROF MARA LUIZA VIEIRA LIBERATO", "ER MANOEL DA SILVA"],
    "FREI DAMIÃO":         ["EB FREI DAMIÃO"],
    "PRAIA DE FORA":       ["EB FRANCISCA RAIMUNDA DE FARIAS COSTA", "EB NERI BRASILIANO MARTINS"],
    "FURADINHO":           ["ER ISABEL BOTELHO DE PAULO"],
    "GUARDA DO CUBATÃO":   ["EB ANTONIETA SILVEIRA DE SOUZA", "ER DANIEL CARLOS WEINGARTNER"],
    "PASSA VINTE":         ["CAIC EB PROF FEBRONIO TANCREDO", "GE NAJLA CARONE GUEDERT"],
    "MORRETE":             ["EB ABILIO MANOEL DE ABREU"],
    "RINCÃO":              ["EI DO RINCÃO"],
    "GUARDA DO EMBAÚ":     ["ER OLGA CERINO"],
    "ALBARDÃO":            ["ER ALBARDÃO"],
    "TRÊS BARRAS":         ["ER BENTO JOSÉ DE NASCIMENTO"],
    "ENSEADA DA PINHEIRA": ["GE MARIA LUZIA DE SOUZA"],
    "PRAIA DO SONHO":      ["EB PROF MARIA DOS SANTOS SILVA"],
}

CEIS = {
    "ARIRIÚ":            ["CEI ESPAÇO CRIATIVO", "CEI MARIA JOSÉ DE MEDEIROS", "CEI NOVA ESPERANÇA", "CEI PARAISO DO AMOR"],
    "ALTO ARIRIÚ":       ["CEI CHAPEUZINHO VERMELHO"],
    "PACHECO":           ["CEI ANJINHO DA GUARDA", "CEI CIRANDA COLORIDA", "CEI SANTA MARTA", "CEI INOVAÇÃO"],
    "BARRA DO ARIRIÚ":   ["CEI APRENDER BRINCANDO", "CEI DONA MARICOTA", "FUNDAÇÃO FÉ E ALEGRIA"],
    "CENTRO":            ["CEI VOVÓ MARIA"],
    "RIO GRANDE":        ["GE TEREZINHA MARIA ESPINDOLA MARTINS", "CEI CRIANÇA FELIZ"],
    "BELA VISTA":        ["CEI INTERAÇÃO", "CEI MUNDO ENCANTADO", "CEI PROFESSORA INES MARTA DA SILVA",
                          "CEI VOO LIVRE", "CEI VALE VERDE"],
    "BREJARU":           ["CEI CAMINHO DA IMAGINAÇÃO", "CEI PRIMEIROS PASSOS"],
    "JARDIM ELDORADO":   ["CEI CONVIVER", "CEI AQUARELA"],
    "CAMINHO NOVO":      ["CEI PADRE RÉUS", "CEI AMIGUINHOS DA COMUNIDADE", "CEI FLORZINHA AZUL"],
    "SÃO SEBASTIÃO":    ["FUNDAÇÃO HERMON", "CEI CANARINHO", "CEI RODA VIVA"],
    "ENSEADA DO BRITO":  ["CEI ARGEMIRA FARIAS DA SILVEIRA"],
    "FREI DAMIÃO":       ["CEI ULISSES GUIMARÃES", "CEI MUNDO MAGICO"],
    "FURADINHO":         ["CEI CAMINHO DO APRENDER", "CEI PAULO BRAULIO GOULART"],
    "GUARDA DO CUBATÃO": ["CEI JOSE MIGUEL DA FERREIRA"],
    "PASSA VINTE":       ["CEI BOLINHAS DE SABÃO", "CEI CAIC PROF FEBRONIO TANCREDO DE OLIVEIRA"],
    "PONTE DO IMARUIM":  ["CEI SNOOPY", "CEI VIDA MELHOR", "CEI VOVO DOLORES", "CEI VO LAURA",
                          "CEI ESTRELINHA", "CEI JOÃO PAULO II"],
    "RINCÃO":            ["EI DO RINCÃO"],
    "ALBARDÃO":          ["ER ALBARDÃO"],
    "TRÊS BARRAS":       ["ER PROF BENTO JOSÉ DO NASCIMENTO"],
    "PRAIA DO SONHO":    ["CEI PROF AURORA DA SILVA LOPES"],
    "PINHEIRA":          ["CEI NOVA GERAÇÃO"],
}

# Unidades que aparecem no PDF mas NÃO estão no documento de bairros.
# Preencha aqui:  "NOME COMO APARECE NO PDF": "BAIRRO"
OVERRIDES_BAIRRO = {
    "CENTRO EDUCACIONAL HERMON": "SÃO SEBASTIÃO",
}

# Bairros vizinhos, do mais próximo ao mais distante (o inverso é deduzido sozinho).
BAIRROS_PROXIMOS = {
    "PASSA VINTE":         ["CENTRO", "BELA VISTA", "PRAIA DE FORA", "JARDIM ELDORADO"],
    "CENTRO":              ["PASSA VINTE", "BELA VISTA", "NOVA PALHOÇA", "JARDIM ELDORADO"],
    "BELA VISTA":          ["CENTRO", "JARDIM ELDORADO", "FREI DAMIÃO", "PASSA VINTE"],
    "ARIRIÚ":              ["ALTO ARIRIÚ", "BARRA DO ARIRIÚ", "ARIRIÚ DA FORMIGA", "MORRETE", "PONTE DO IMARUIM"],
    "ALTO ARIRIÚ":         ["ARIRIÚ", "BARRA DO ARIRIÚ"],
    "ARIRIÚ DA FORMIGA":   ["ARIRIÚ", "ALTO ARIRIÚ", "BARRA DO ARIRIÚ"],
    "BARRA DO ARIRIÚ":     ["ARIRIÚ", "PACHECO", "RIO GRANDE", "NOVA PALHOÇA", "PONTE DO IMARUIM"],
    "NOVA PALHOÇA":        ["RIO GRANDE", "BARRA DO ARIRIÚ", "CENTRO", "BELA VISTA"],
    "RIO GRANDE":          ["NOVA PALHOÇA", "BARRA DO ARIRIÚ", "BELA VISTA"],
    "CAMINHO NOVO":        ["BREJARU", "SÃO SEBASTIÃO", "CENTRO", "PASSA VINTE"],
    "SÃO SEBASTIÃO":       ["CAMINHO NOVO", "BREJARU", "CENTRO"],
    "FREI DAMIÃO":         ["JARDIM ELDORADO", "BELA VISTA", "CENTRO"],
    "JARDIM ELDORADO":     ["FREI DAMIÃO", "BELA VISTA", "CENTRO", "PASSA VINTE"],
    "PRAIA DE FORA":       ["PASSA VINTE", "FURADINHO", "GUARDA DO CUBATÃO", "CENTRO"],
    "FURADINHO":           ["PRAIA DE FORA", "GUARDA DO CUBATÃO", "PASSA VINTE"],
    "GUARDA DO CUBATÃO":   ["FURADINHO", "PRAIA DE FORA"],
    "PACHECO":             ["PONTE DO IMARUIM", "BARRA DO ARIRIÚ", "ARIRIÚ", "CENTRO", "BELA VISTA"],
    "PONTE DO IMARUIM":    ["PACHECO", "ARIRIÚ", "BARRA DO ARIRIÚ"],
    "ENSEADA DO BRITO":    ["PINHEIRA", "ENSEADA DA PINHEIRA", "GUARDA DO EMBAÚ"],
    "PINHEIRA":            ["ENSEADA DO BRITO", "ENSEADA DA PINHEIRA", "PRAIA DO SONHO"],
    "ENSEADA DA PINHEIRA": ["PINHEIRA", "ENSEADA DO BRITO", "PRAIA DO SONHO"],
    "PRAIA DO SONHO":      ["ENSEADA DA PINHEIRA", "PINHEIRA"],
    "BREJARU":             ["CAMINHO NOVO", "SÃO SEBASTIÃO", "CENTRO"],
    "MORRETE":             ["ARIRIÚ", "BARRA DO ARIRIÚ", "PONTE DO IMARUIM"],
    "ALBARDÃO":            ["TRÊS BARRAS", "RINCÃO"],
    "TRÊS BARRAS":         ["ALBARDÃO", "RINCÃO"],
    "RINCÃO":              ["GUARDA DO EMBAÚ", "ALBARDÃO", "TRÊS BARRAS"],
    "GUARDA DO EMBAÚ":     ["RINCÃO", "ENSEADA DO BRITO"],
}


# ── utilitários ────────────────────────────────────────────────
def _sem_acento(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

def _palavras(s: str) -> set:
    s = re.sub(r'[^A-Z0-9 ]', ' ', _sem_acento(s).upper())
    return {w for w in s.split() if len(w) > 3}

def _parecidos(a: str, b: str):
    """
    (palavras em comum, aceito?)
    Aceita só se os nomes realmente se parecem: 2+ palavras em comum cobrindo
    pelo menos 60% do nome mais curto, ou nomes de 1 palavra idênticos
    (evita casar por sobrenome comum, ex.: "Silveira", "Maria Martins").
    """
    wa, wb = _palavras(a), _palavras(b)
    comum = len(wa & wb)
    menor = min(len(wa), len(wb)) or 1
    ok = (comum >= 2 and comum / menor >= 0.6) or (len(wa) == 1 and wa == wb)
    return comum, ok

def _todas_unidades():
    for mapa in (MUNICIPAIS, CEIS, ESTADUAIS):
        for bairro, nomes in mapa.items():
            for nome in nomes:
                yield bairro, nome

_cache = {}

def _bairros_conhecidos():
    nomes = set(BAIRROS_PROXIMOS)
    for mapa in (ESTADUAIS, MUNICIPAIS, CEIS):
        nomes |= set(mapa)
    return nomes


def get_bairro_escola(nome: str) -> str:
    """Bairro de uma unidade (município ou estado) pelo nome. '' se não achar."""
    if nome in _cache:
        return _cache[nome]
    resultado = ''
    # o PDF às vezes anexa o bairro ao nome: "CEI CANARINHO - SÃO SEBASTIÃO"
    m = re.search(r'-\s*([^-]+)$', nome)
    if m:
        sufixo = _sem_acento(m.group(1)).upper().strip()
        for b in _bairros_conhecidos():
            if _sem_acento(b).upper() == sufixo:
                _cache[nome] = b
                return b
    for chave, bairro in OVERRIDES_BAIRRO.items():
        if _sem_acento(chave).upper() in _sem_acento(nome).upper():
            resultado = bairro
            break
    if not resultado:
        melhor, melhor_comum = '', 0
        for bairro, cand in _todas_unidades():
            comum, ok = _parecidos(nome, cand)
            if ok and comum > melhor_comum:
                melhor, melhor_comum = bairro, comum
        resultado = melhor
    _cache[nome] = resultado
    return resultado

get_bairro_by_escola = get_bairro_escola      # compatibilidade
get_bairro_estadual  = get_bairro_escola


def get_bairros_proximos(bairro: str) -> list:
    """Vizinhos do bairro (do mais perto ao mais longe), já considerando o inverso."""
    b = (bairro or '').upper()
    lista = list(BAIRROS_PROXIMOS.get(b, []))
    for outro, vizinhos in BAIRROS_PROXIMOS.items():
        if b in vizinhos and outro not in lista and outro != b:
            lista.append(outro)
    return lista


def listar_estaduais() -> list:
    return [{'escola': e, 'bairro': b}
            for b, escolas in ESTADUAIS.items() for e in escolas]


def distancias_bairro(origem: str) -> dict:
    """Nº de 'saltos' entre bairros vizinhos a partir da origem (0 = mesmo bairro)."""
    from collections import deque
    o = (origem or '').upper()
    dist, fila = {o: 0}, deque([o])
    while fila:
        b = fila.popleft()
        for v in get_bairros_proximos(b):
            if v not in dist:
                dist[v] = dist[b] + 1
                fila.append(v)
    return dist
