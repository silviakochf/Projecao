"""
Leitor do "RELATÓRIO DE ESTUDANTES MATRICULADOS" (EducarWEB, HTML).

A turma de cada aluno vem do cabeçalho "Turma: 5º ANO - 1 (UNIDADE ...", que às vezes
vem truncado (sem o ")"), e o cabeçalho se repete a cada página. Por isso a turma é
lida pela posição: vale o último cabeçalho antes de cada registro de aluno.
Cada registro = 9 campos: código, nome, sexo, nascimento, unidade, série, turno,
situação, data da situação.
"""
import re
from lxml import html as lhtml

SUFIXOS_UNIDADE = r'\s*-\s*(?:FUNDAMENTAL|INFANTIL|ENSINO\s+\w+|EDUCAÇÃO\s+\w+|\d{6,9})\b.*$'


def limpar_unidade(texto: str) -> str:
    """'CAIC - PROFº ... - FUNDAMENTAL - 42129370' -> 'CAIC - PROFº ...'."""
    nome = re.sub(r'\s+', ' ', texto.strip())
    anterior = None
    while anterior != nome:
        anterior = nome
        nome = re.sub(SUFIXOS_UNIDADE, '', nome, flags=re.IGNORECASE).strip()
    return nome


def chave_turma(rotulo: str) -> str:
    """'1º ANO - 1' e '1º ANO 1' viram a mesma chave: '1º ANO 1'."""
    t = re.sub(r'\s+', ' ', rotulo.upper().replace('°', 'º').replace('–', '-')).strip()
    t = re.sub(r'\s*-\s*', ' ', t)
    return re.sub(r'(\d)\s*O\s+ANO', r'\1º ANO', t)


def parse_estudantes_html(conteudo: str) -> list:
    """Lista de estudantes: {codigo, nome, sexo, nascimento, unidade, turma, serie, turno, situacao}."""
    arvore = lhtml.fromstring(conteudo)
    spans = [s.text_content().replace('\xa0', ' ').strip()
             for s in arvore.xpath('//span') if s.text_content().strip()]

    turma_por_posicao = {}
    for i, t in enumerate(spans):
        if t.startswith('Turma:'):
            turma_por_posicao[i] = re.match(r'Turma:\s*(.*?)\s*(?:\(|$)', t).group(1).strip()
    posicoes = sorted(turma_por_posicao)

    estudantes = []
    for k, t in enumerate(spans):
        if not re.match(r'^\d{5,7}$', t):
            continue
        reg = spans[k:k + 9]
        if len(reg) < 9 or not re.match(r'^[MF]$', reg[2]) or not re.match(r'^\d{2}/\d{2}/\d{4}$', reg[3]):
            continue                                   # não é registro de aluno
        anteriores = [p for p in posicoes if p < k]
        turma = turma_por_posicao[anteriores[-1]] if anteriores else ''
        estudantes.append({
            'codigo': reg[0], 'nome': reg[1], 'sexo': reg[2], 'nascimento': reg[3],
            'unidade': limpar_unidade(reg[4]), 'turma': turma, 'serie': reg[5].strip(),
            'turno': reg[6].strip().upper(), 'situacao': reg[7].strip().upper(),
        })
    return estudantes
