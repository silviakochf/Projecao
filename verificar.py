"""
Diagnóstico do projeto.  Rode na pasta do projeto:   python verificar.py
Mostra, em português, o que está faltando e como corrigir.
"""
import os
import sys
import importlib

try:
    sys.stdout.reconfigure(errors='replace')      # evita erro de acento no terminal do Windows
except Exception:
    pass

OK, ERRO = '[OK]  ', '[ERRO]'
AQUI = os.path.dirname(os.path.abspath(__file__))
os.chdir(AQUI)
sys.path.insert(0, AQUI)
problemas = []

print(f'Python {sys.version.split()[0]}  |  pasta: {AQUI}\n')

print('1) Pacotes instalados')
faltando = []
for modulo, pacote in [('flask', 'flask'), ('dotenv', 'python-dotenv'), ('openpyxl', 'openpyxl'),
                       ('lxml', 'lxml'), ('requests', 'requests'), ('pypdf', 'pypdf'), ('docx', 'python-docx')]:
    try:
        importlib.import_module(modulo)
        print(f'   {OK} {pacote}')
    except Exception as e:
        print(f'   {ERRO} {pacote}  ({type(e).__name__})')
        faltando.append(pacote)
if faltando:
    problemas.append('Instale os pacotes que faltam (com o ambiente virtual ativado):\n'
                     '        pip install ' + ' '.join(faltando))

print('\n2) Arquivos de código (todos precisam ser da mesma versão)')
esperado = {
    'app.logic.parser_vagas_pdf':     ['parse_vagas_pdf', 'get_resumo_vagas'],
    'app.logic.parser_alunos_html':   ['parse_estudantes_html'],
    'app.logic.progressao_engine':    ['processar'],
    'app.logic.excel_progressao':     ['gerar_excel_progressao'],
    'app.logic.projecao_engine':      ['calcular_projecao', 'inventario_salas', 'capacidade_sala'],
    'app.logic.excel_projecao':       ['gerar_excel_projecao'],
    'app.logic.carta_encaminhamento': ['TEXTO_PADRAO', 'ler_excel_progressao', 'montar_cartas', 'gerar_arquivos',
                                       'gerar_zip', 'carta_renderizada', 'campos_desconhecidos'],
    'app.logic.bairros':              ['get_bairro_escola', 'listar_estaduais', 'distancias_bairro'],
    'app.services.drive_service':     ['upload_to_drive'],
    'app.services.excel_service':     ['gerar_excel_vagas'],
}
desatualizados = []
for modulo, funcoes in esperado.items():
    arquivo = modulo.replace('.', '/') + '.py'
    try:
        m = importlib.import_module(modulo)
        faltam = [f for f in funcoes if not hasattr(m, f)]
        if faltam:
            print(f'   {ERRO} {arquivo}  -> DESATUALIZADO (falta: {", ".join(faltam)})')
            desatualizados.append(arquivo)
        else:
            print(f'   {OK} {arquivo}')
    except Exception as e:
        print(f'   {ERRO} {arquivo}  -> {type(e).__name__}: {e}')
        if not isinstance(e, ImportError) or 'No module named' not in str(e):
            desatualizados.append(arquivo)
if desatualizados:
    problemas.append('Estes arquivos estão desatualizados ou com problema. Copie-os de novo do zip\n'
                     '        (o mais seguro é substituir a pasta "app" inteira pela do zip):\n        - '
                     + '\n        - '.join(desatualizados))

print('\n3) Páginas, scripts e estilos')
marcadores = {   # arquivo: (precisa conter, NÃO pode conter)
    'app/templates/base.html':       ('css/main.css', 'let _tt'),
    'app/templates/progressao.html': ('removerPDF', None),
    'app/templates/projecao.html':   ('calcularProjecao', None),
    'app/templates/cartas.html':     ('id="texto"', None),
    'app/static/js/main.js':         ('postForm', None),
    'app/static/js/progressao.js':   ('executarAnalise', None),
    'app/static/js/projecao.js':     ('calcularProjecao', None),
    'app/static/js/cartas.js':       ('montarCartas', None),
    'app/static/css/main.css':       ('step-header', None),
}
velhos = []
for arq, (deve, nao_deve) in marcadores.items():
    if not os.path.exists(arq):
        print(f'   {ERRO} {arq}  -> NÃO EXISTE'); velhos.append(arq); continue
    txt = open(arq, encoding='utf-8', errors='replace').read()
    if deve not in txt or (nao_deve and nao_deve in txt):
        print(f'   {ERRO} {arq}  -> versão antiga'); velhos.append(arq)
    else:
        print(f'   {OK} {arq}')
if velhos:
    problemas.append('Estes arquivos estão faltando ou são de uma versão antiga. Copie de novo do zip:\n        - '
                     + '\n        - '.join(velhos))

print('\n4) O aplicativo inicia?')
try:
    from run import app
    rotas = {r.rule for r in app.url_map.iter_rules()}
    falta = [r for r in ('/progressao', '/projecao', '/cartas', '/api/cartas/preparar', '/api/calcular_projecao') if r not in rotas]
    if falta:
        print(f'   {ERRO} rotas ausentes: {falta}'); problemas.append('routes.py está desatualizado: copie de novo do zip.')
    else:
        print(f'   {OK} sim, {len(rotas)} rotas carregadas')
except Exception as e:
    print(f'   {ERRO} não inicia -> {type(e).__name__}: {e}')
    if not problemas:
        problemas.append('O aplicativo não inicia. Copie a mensagem acima e envie para análise.')

print('\n' + '=' * 62)
if problemas:
    print('PROBLEMAS ENCONTRADOS:\n')
    for i, p in enumerate(problemas, 1):
        print(f'  {i}. {p}\n')
    sys.exit(1)
print('TUDO CERTO. Para iniciar:   python run.py   e abra  http://127.0.0.1:5000')
