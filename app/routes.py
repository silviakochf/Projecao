from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, send_file, current_app

from app.logic.parser_vagas_pdf import parse_vagas_pdf, get_resumo_vagas
from app.logic.parser_alunos_html import parse_estudantes_html
from app.logic.progressao_engine import processar
from app.logic.excel_progressao import gerar_excel_progressao
from app.logic import carta_encaminhamento as cartas_lib
from app.logic.bairros import get_bairro_escola, listar_estaduais
from app.services.drive_service import upload_to_drive
from app.services.excel_service import gerar_excel_vagas

main_bp = Blueprint('main', __name__)
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


@main_bp.context_processor
def inject_now():
    return {'now': datetime.now()}


# ── páginas ─────────────────────────────────────────────────────
@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/progressao')
def progressao():
    return render_template('progressao.html')

@main_bp.route('/cartas')
def cartas():
    return render_template('cartas.html')


# ══ PROGRESSÃO (nada é salvo no servidor) ═══════════════════════
@main_bp.route('/api/importar_vagas_pdf', methods=['POST'])
def importar_vagas_pdf():
    arquivo = request.files.get('file')
    if not arquivo:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
    try:
        report = {}
        dados = parse_vagas_pdf(arquivo.read(), report)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Não consegui ler o PDF: {e}'}), 400
    if not dados:
        return jsonify({'success': False,
                        'error': 'Nenhuma turma encontrada. É o relatório "Lista de Vagas por Série e Turma"?'}), 400

    resumo = get_resumo_vagas(dados)
    ceis = [e for e, series in dados.items() if all(s.startswith('GT') for s in series)]
    return jsonify({
        'success': True, 'vagas': dados, 'resumo': resumo,
        'unidades': len(dados), 'ceis': len(ceis), 'escolas': len(dados) - len(ceis),
        'total_existentes': sum(r['vagas_existentes'] for r in resumo),
        'total_ocupadas': sum(r['vagas_ocupadas'] for r in resumo),
        'total_disponiveis': sum(r['vagas_disponiveis'] for r in resumo),
        'inativas': sorted(report.get('inativas', [])),
        'sem_bairro': [e for e in dados if not get_bairro_escola(e)],
        'nao_lidas': len(report.get('nao_lidas', [])),
    })

@main_bp.route('/api/escolas_estaduais')
def escolas_estaduais():
    return jsonify(listar_estaduais())

@main_bp.route('/api/analisar_progressao', methods=['POST'])
def analisar_progressao():
    req = request.get_json(silent=True) or {}
    vagas = req.get('vagas') or {}
    if not vagas:
        return jsonify({'success': False, 'error': 'Importe o PDF de vagas primeiro'}), 400
    resultado = processar(vagas, req.get('estaduais') or [], req.get('inativas') or [])
    if not resultado['turmas']:
        return jsonify({'success': False,
                        'error': 'Nenhuma turma de série final encontrada neste PDF'}), 400
    return jsonify({'success': True, **resultado})

def _excel_do_pedido():
    req = request.get_json(silent=True) or {}
    resultado = req.get('resultado') or {}
    if not resultado.get('turmas'):
        return None, None
    return gerar_excel_progressao(resultado), f"progressao_{datetime.now().strftime('%d-%m-%Y_%H%M')}.xlsx"

@main_bp.route('/api/baixar_excel_progressao', methods=['POST'])
def baixar_excel_progressao():
    buf, nome = _excel_do_pedido()
    if buf is None:
        return jsonify({'success': False, 'error': 'Execute a análise primeiro'}), 400
    return send_file(buf, as_attachment=True, download_name=nome, mimetype=XLSX)

@main_bp.route('/api/exportar_excel_progressao', methods=['POST'])
def exportar_excel_progressao():
    buf, nome = _excel_do_pedido()
    if buf is None:
        return jsonify({'success': False, 'error': 'Execute a análise primeiro'}), 400
    pasta = (request.get_json(silent=True) or {}).get('folder_id', current_app.config['DRIVE_FOLDER_PROGRESSAO'])
    r = upload_to_drive(buf.getvalue(), nome, pasta, XLSX)
    if r.get('success'):
        return jsonify({'success': True, 'fileId': r.get('fileId'), 'filename': nome})
    buf.seek(0)                                   # Drive indisponível -> baixa o arquivo
    return send_file(buf, as_attachment=True, download_name=nome, mimetype=XLSX)

@main_bp.route('/api/exportar_excel_vagas', methods=['POST'])
def exportar_excel_vagas():
    req = request.get_json(silent=True) or {}
    vagas = req.get('vagas') or {}
    if not vagas:
        return jsonify({'success': False, 'error': 'Nenhuma vaga carregada'}), 400
    est = {}
    for v in req.get('estaduais') or []:
        est.setdefault(v['escola'], {}).setdefault(v['serie'], {})['QUALQUER'] = int(v.get('vagas') or 0)
    buf = gerar_excel_vagas(vagas, est, 'Secretaria de Educação')
    return send_file(buf, as_attachment=True, mimetype=XLSX,
                     download_name=f"vagas_{datetime.now().strftime('%d-%m-%Y')}.xlsx")


# ══ CARTAS: uma carta por criança (nada é salvo no servidor) ════
@main_bp.route('/api/cartas/config')
def cartas_config():
    return jsonify({'texto_padrao': cartas_lib.TEXTO_PADRAO, 'campos': cartas_lib.CAMPOS})

@main_bp.route('/api/cartas/preparar', methods=['POST'])
def cartas_preparar():
    html, excel = request.files.get('html'), request.files.get('excel')
    if not html or not excel:
        return jsonify({'success': False, 'error': 'Envie o HTML dos estudantes e o Excel da progressão'}), 400
    try:
        estudantes = cartas_lib_parse(html)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Não consegui ler o HTML dos estudantes: {e}'}), 400
    if not estudantes:
        return jsonify({'success': False,
                        'error': 'Nenhum estudante encontrado no HTML. É o "Relatório de Estudantes Matriculados"?'}), 400
    try:
        linhas = cartas_lib.ler_excel_progressao(excel.read())
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    if not linhas:
        return jsonify({'success': False, 'error': 'O Excel não tem nenhuma turma na aba Progressão'}), 400
    return jsonify({'success': True, **cartas_lib.montar_cartas(estudantes, linhas)})

def cartas_lib_parse(arquivo):
    return parse_estudantes_html(arquivo.read().decode('utf-8', errors='ignore'))

@main_bp.route('/api/cartas/previa', methods=['POST'])
def cartas_previa():
    req = request.get_json(silent=True) or {}
    carta, cfg = req.get('carta'), req.get('cfg') or {}
    if not carta:
        return jsonify({'success': False}), 400
    return jsonify({'success': True, 'carta': cartas_lib.carta_renderizada(carta, cfg),
                    'desconhecidos': cartas_lib.campos_desconhecidos(cfg.get('texto', ''))})

def _arquivos_do_pedido():
    req = request.get_json(silent=True) or {}
    lista = req.get('cartas') or []
    if not lista:
        return None, req
    return cartas_lib.gerar_arquivos(lista, req.get('cfg') or {}), req

@main_bp.route('/api/cartas/gerar', methods=['POST'])
def cartas_gerar():
    arquivos, _ = _arquivos_do_pedido()
    if not arquivos:
        return jsonify({'success': False, 'error': 'Monte as cartas primeiro'}), 400
    return send_file(cartas_lib.gerar_zip(arquivos), as_attachment=True, mimetype='application/zip',
                     download_name=f"cartas_encaminhamento_{datetime.now().strftime('%d-%m-%Y')}.zip")

@main_bp.route('/api/cartas/drive', methods=['POST'])
def cartas_drive():
    arquivos, req = _arquivos_do_pedido()
    if not arquivos:
        return jsonify({'success': False, 'error': 'Monte as cartas primeiro'}), 400
    pasta = req.get('folder_id', current_app.config['DRIVE_FOLDER_CARTAS'])
    enviados, erros = [], []
    for nome, dados in arquivos.items():
        r = upload_to_drive(dados, nome, pasta, DOCX)
        (enviados if r.get('success') else erros).append(
            {'filename': nome, 'fileId': r.get('fileId'), 'error': r.get('error')})
    return jsonify({'success': bool(enviados), 'uploaded': enviados, 'errors': erros})
