import os
import json
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, send_file, current_app

from app.logic.parser_vagas_pdf import parse_vagas_pdf, get_resumo_vagas
from app.logic.parser_alunos_html import parse_alunos_html
from app.logic.progressao_engine import processar
from app.logic.excel_progressao import gerar_excel_progressao
from app.logic.carta_encaminhamento import gerar_todas_cartas
from app.logic.bairros import get_bairro_escola, listar_estaduais
from app.services.drive_service import upload_to_drive
from app.services.excel_service import gerar_excel_vagas

main_bp = Blueprint('main', __name__)
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


# ── armazenamento mínimo (só para a aba Cartas) ─────────────────
def _path(nome):
    pasta = current_app.config['UPLOAD_FOLDER']
    os.makedirs(pasta, exist_ok=True)
    return os.path.join(pasta, nome)

def _load(nome):
    p = _path(nome)
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    return {}

def _save(nome, dados):
    with open(_path(nome), 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False)


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


# ── Passo 1: PDF de vagas (nada é salvo no servidor) ────────────
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
        'success': True,
        'vagas': dados,
        'resumo': resumo,
        'unidades': len(dados),
        'ceis': len(ceis),
        'escolas': len(dados) - len(ceis),
        'total_existentes': sum(r['vagas_existentes'] for r in resumo),
        'total_ocupadas': sum(r['vagas_ocupadas'] for r in resumo),
        'total_disponiveis': sum(r['vagas_disponiveis'] for r in resumo),
        'inativas': sorted(report.get('inativas', [])),
        'sem_bairro': [e for e in dados if not get_bairro_escola(e)],
        'nao_lidas': len(report.get('nao_lidas', [])),
    })


# ── Passo 2: lista de escolas estaduais (dropdown) ──────────────
@main_bp.route('/api/escolas_estaduais')
def escolas_estaduais():
    return jsonify(listar_estaduais())


# ── Passo 3: análise automática ─────────────────────────────────
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

    _save('progressao_resultado.json', resultado['turmas'])   # a aba Cartas lê daqui
    return jsonify({'success': True, **resultado})


# ── Exportação (recebe o resultado do navegador) ────────────────
def _excel_do_pedido():
    req = request.get_json(silent=True) or {}
    resultado = req.get('resultado') or {}
    if not resultado.get('turmas'):
        return None, None
    nome = f"progressao_{datetime.now().strftime('%d-%m-%Y_%H%M')}.xlsx"
    return gerar_excel_progressao(resultado), nome

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
    pasta = (request.get_json(silent=True) or {}).get(
        'folder_id', current_app.config['DRIVE_FOLDER_PROGRESSAO'])
    r = upload_to_drive(buf.getvalue(), nome, pasta)
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


# ── Aba Cartas ──────────────────────────────────────────────────
@main_bp.route('/api/ultimo_resultado')
def ultimo_resultado():
    turmas = _load('progressao_resultado.json')
    return jsonify({'success': bool(turmas), 'turmas': turmas or []})

@main_bp.route('/api/importar_alunos_html', methods=['POST'])
def importar_alunos_html():
    arquivo = request.files.get('file')
    if not arquivo:
        return jsonify({'success': False, 'error': 'Nenhum arquivo'}), 400
    try:
        dados = parse_alunos_html(arquivo.read().decode('utf-8', errors='ignore'))
        _save('alunos.json', dados)
        total = sum(len(a) for s in dados.values() for t in s.values() for a in t.values())
        return jsonify({'success': True, 'escolas': list(dados), 'total_alunos': total})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/gerar_cartas', methods=['POST'])
def gerar_cartas():
    req = request.get_json(silent=True) or {}
    turmas = _load('progressao_resultado.json')
    if not turmas:
        return jsonify({'success': False, 'error': 'Execute a análise de progressão primeiro'}), 400
    pasta = req.get('folder_id', current_app.config['DRIVE_FOLDER_CARTAS'])
    enviados, erros = [], []
    for nome, buf in gerar_todas_cartas(turmas, req.get('template', {}),
                                        req.get('escola_origem', '')).items():
        r = upload_to_drive(buf.getvalue(), nome, pasta)
        (enviados if r.get('success') else erros).append(
            {'filename': nome, 'fileId': r.get('fileId'), 'error': r.get('error')})
    return jsonify({'success': bool(enviados), 'uploaded': enviados, 'errors': erros,
                    'total': len(enviados) + len(erros)})
