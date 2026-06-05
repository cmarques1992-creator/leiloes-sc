"""
=============================================================
  PAINEL DE LEILÕES JUDICIAIS — SC
  Servidor local Flask | Lê o banco leiloes_sc.db
=============================================================

INSTALAÇÃO (rodar uma vez):
    pip install flask

COMO USAR:
    1. Coloque este arquivo na mesma pasta que o leiloes_sc_scraper.py
    2. Rode: python painel_leiloes.py
    3. Abra no navegador: http://localhost:5000

"""

from flask import Flask, jsonify, request, render_template_string
import sqlite3
import os

DB_PATH = "leiloes_sc.db"
app = Flask(__name__)

# ─────────────────────────────────────────────
#  API — dados do banco
# ─────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/api/imoveis")
def api_imoveis():
    busca  = request.args.get("q", "").strip()
    fonte  = request.args.get("fonte", "").strip()
    cidade = request.args.get("cidade", "").strip()

    conn = get_db()
    query = "SELECT * FROM imoveis WHERE 1=1"
    params = []

    if busca:
        query += " AND (descricao LIKE ? OR numero_processo LIKE ? OR cidade LIKE ?)"
        like = f"%{busca}%"
        params += [like, like, like]
    if fonte:
        query += " AND fonte = ?"
        params.append(fonte)
    if cidade:
        query += " AND cidade LIKE ?"
        params.append(f"%{cidade}%")

    query += " ORDER BY criado_em DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/stats")
def api_stats():
    conn = get_db()
    total   = conn.execute("SELECT COUNT(*) FROM imoveis").fetchone()[0]
    fontes  = conn.execute("SELECT fonte, COUNT(*) as n FROM imoveis GROUP BY fonte").fetchall()
    hoje    = conn.execute(
        "SELECT COUNT(*) FROM imoveis WHERE date(criado_em) = date('now','localtime')"
    ).fetchone()[0]
    conn.close()
    return jsonify({
        "total": total,
        "hoje":  hoje,
        "fontes": [dict(r) for r in fontes]
    })

@app.route("/api/fontes")
def api_fontes():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT fonte FROM imoveis ORDER BY fonte").fetchall()
    conn.close()
    return jsonify([r[0] for r in rows])

@app.route("/api/cidades")
def api_cidades():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT cidade FROM imoveis ORDER BY cidade").fetchall()
    conn.close()
    return jsonify([r[0] for r in rows])

# ─────────────────────────────────────────────
#  FRONTEND — HTML completo embutido
# ─────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Leilões Judiciais SC</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,600;1,9..144,300&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:       #0d0f14;
    --surface:  #13161e;
    --border:   #1f2430;
    --accent:   #c8a96e;
    --accent2:  #5b8dd9;
    --danger:   #e05c5c;
    --success:  #4caf82;
    --text:     #e8e2d6;
    --muted:    #6b7080;
    --radius:   6px;
  }

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Mono', monospace;
    font-size: 13px;
    min-height: 100vh;
  }

  /* ── HEADER ── */
  header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 0 32px;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .logo {
    font-family: 'Fraunces', serif;
    font-size: 20px;
    font-weight: 600;
    color: var(--accent);
    letter-spacing: -0.5px;
  }

  .logo span {
    color: var(--muted);
    font-weight: 300;
    font-style: italic;
  }

  .header-meta {
    color: var(--muted);
    font-size: 11px;
  }

  /* ── STATS BAR ── */
  .stats-bar {
    display: flex;
    gap: 1px;
    background: var(--border);
    border-bottom: 1px solid var(--border);
  }

  .stat-card {
    flex: 1;
    background: var(--surface);
    padding: 16px 24px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .stat-label {
    color: var(--muted);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  .stat-value {
    font-family: 'Fraunces', serif;
    font-size: 28px;
    font-weight: 600;
    color: var(--accent);
    line-height: 1;
  }

  .stat-value.blue  { color: var(--accent2); }
  .stat-value.green { color: var(--success); }

  /* ── TOOLBAR ── */
  .toolbar {
    padding: 16px 32px;
    display: flex;
    gap: 10px;
    align-items: center;
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }

  .search-wrap {
    position: relative;
    flex: 1;
    min-width: 200px;
  }

  .search-wrap svg {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--muted);
    pointer-events: none;
  }

  input[type="text"], select {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    font-family: 'DM Mono', monospace;
    font-size: 13px;
    border-radius: var(--radius);
    padding: 9px 12px;
    outline: none;
    transition: border-color .2s;
  }

  input[type="text"] {
    width: 100%;
    padding-left: 36px;
  }

  input[type="text"]:focus, select:focus {
    border-color: var(--accent);
  }

  select {
    cursor: pointer;
    min-width: 160px;
  }

  .btn-refresh {
    background: var(--accent);
    color: #0d0f14;
    border: none;
    border-radius: var(--radius);
    padding: 9px 16px;
    font-family: 'DM Mono', monospace;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
    transition: opacity .2s;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .btn-refresh:hover { opacity: .85; }

  .count-badge {
    margin-left: auto;
    color: var(--muted);
    font-size: 12px;
    white-space: nowrap;
  }

  /* ── TABLE ── */
  .table-wrap {
    overflow-x: auto;
    padding: 0 32px 40px;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 16px;
  }

  thead th {
    text-align: left;
    padding: 10px 14px;
    color: var(--muted);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
  }

  thead th:hover { color: var(--accent); }

  thead th .sort-icon { opacity: .4; margin-left: 4px; }
  thead th.asc .sort-icon::after  { content: " ↑"; opacity: 1; }
  thead th.desc .sort-icon::after { content: " ↓"; opacity: 1; }

  tbody tr {
    border-bottom: 1px solid var(--border);
    transition: background .15s;
    animation: fadeIn .3s ease both;
  }

  tbody tr:hover { background: var(--surface); }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  td {
    padding: 12px 14px;
    vertical-align: middle;
  }

  .processo {
    font-family: 'DM Mono', monospace;
    color: var(--accent2);
    font-size: 12px;
    white-space: nowrap;
  }

  .descricao {
    max-width: 300px;
    color: var(--text);
    line-height: 1.4;
  }

  .valor {
    color: var(--success);
    white-space: nowrap;
  }

  .cidade {
    color: var(--text);
    white-space: nowrap;
  }

  .fonte-badge {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 3px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: .5px;
    white-space: nowrap;
    background: #1a1f2e;
    border: 1px solid var(--border);
    color: var(--muted);
  }

  .fonte-badge.tjsc  { border-color: #3a5a9a; color: #7aaaf0; }
  .fonte-badge.jfsc  { border-color: #3a7a5a; color: #6acfa0; }
  .fonte-badge.mega  { border-color: #7a3a3a; color: #e07070; }
  .fonte-badge.leilo { border-color: #7a6a3a; color: #d4a84b; }

  .data {
    color: var(--muted);
    font-size: 11px;
    white-space: nowrap;
  }

  .link-edital {
    color: var(--accent);
    text-decoration: none;
    font-size: 11px;
    opacity: .8;
    transition: opacity .2s;
  }

  .link-edital:hover { opacity: 1; }

  /* ── EMPTY STATE ── */
  .empty {
    text-align: center;
    padding: 60px 20px;
    color: var(--muted);
  }

  .empty svg { margin-bottom: 12px; opacity: .3; }

  .empty p { font-size: 14px; }

  /* ── LOADING ── */
  .loading {
    text-align: center;
    padding: 40px;
    color: var(--muted);
  }

  .spinner {
    display: inline-block;
    width: 20px; height: 20px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin .7s linear infinite;
    margin-right: 8px;
    vertical-align: middle;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── FOOTER ── */
  footer {
    text-align: center;
    padding: 20px;
    color: var(--muted);
    font-size: 11px;
    border-top: 1px solid var(--border);
  }
</style>
</head>
<body>

<header>
  <div class="logo">Leilões Judiciais <span>SC</span></div>
  <div class="header-meta" id="ultima-atualizacao">carregando...</div>
</header>

<div class="stats-bar">
  <div class="stat-card">
    <div class="stat-label">Total no banco</div>
    <div class="stat-value" id="stat-total">—</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Encontrados hoje</div>
    <div class="stat-value green" id="stat-hoje">—</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Fontes ativas</div>
    <div class="stat-value blue" id="stat-fontes">—</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Exibindo agora</div>
    <div class="stat-value" id="stat-exibindo">—</div>
  </div>
</div>

<div class="toolbar">
  <div class="search-wrap">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
    </svg>
    <input type="text" id="busca" placeholder="Buscar por processo, imóvel, cidade...">
  </div>

  <select id="filtro-fonte">
    <option value="">Todas as fontes</option>
  </select>

  <select id="filtro-cidade">
    <option value="">Todas as cidades</option>
  </select>

  <button class="btn-refresh" onclick="carregar()">
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>
      <path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>
      <path d="M8 16H3v5"/>
    </svg>
    Atualizar
  </button>
</div>

<div class="table-wrap">
  <div id="loading" class="loading">
    <span class="spinner"></span> Carregando imóveis...
  </div>

  <table id="tabela" style="display:none">
    <thead>
      <tr>
        <th data-col="numero_processo">Nº Processo <span class="sort-icon"></span></th>
        <th data-col="descricao">Descrição <span class="sort-icon"></span></th>
        <th data-col="valor_avaliacao">Avaliação <span class="sort-icon"></span></th>
        <th data-col="cidade">Cidade <span class="sort-icon"></span></th>
        <th data-col="fonte">Fonte <span class="sort-icon"></span></th>
        <th data-col="criado_em">Detectado em <span class="sort-icon"></span></th>
        <th>Edital</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>

  <div id="empty" class="empty" style="display:none">
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
    </svg>
    <p>Nenhum imóvel encontrado com esses filtros.</p>
  </div>
</div>

<footer>
  Painel local · banco <strong>leiloes_sc.db</strong> · atualizado pelo robô diariamente
</footer>

<script>
let dados = [];
let sortCol = 'criado_em';
let sortDir = 'desc';

// ── carrega filtros ──
async function carregarFiltros() {
  const [fontes, cidades] = await Promise.all([
    fetch('/api/fontes').then(r => r.json()),
    fetch('/api/cidades').then(r => r.json())
  ]);

  const sf = document.getElementById('filtro-fonte');
  fontes.forEach(f => {
    const o = document.createElement('option');
    o.value = f; o.textContent = f;
    sf.appendChild(o);
  });

  const sc = document.getElementById('filtro-cidade');
  cidades.forEach(c => {
    const o = document.createElement('option');
    o.value = c; o.textContent = c;
    sc.appendChild(o);
  });
}

// ── carrega stats ──
async function carregarStats() {
  const s = await fetch('/api/stats').then(r => r.json());
  document.getElementById('stat-total').textContent  = s.total.toLocaleString('pt-BR');
  document.getElementById('stat-hoje').textContent   = s.hoje.toLocaleString('pt-BR');
  document.getElementById('stat-fontes').textContent = s.fontes.length;
  document.getElementById('ultima-atualizacao').textContent =
    'Última consulta: ' + new Date().toLocaleString('pt-BR');
}

// ── carrega imóveis ──
async function carregar() {
  document.getElementById('loading').style.display = 'block';
  document.getElementById('tabela').style.display  = 'none';
  document.getElementById('empty').style.display   = 'none';

  const q      = document.getElementById('busca').value;
  const fonte  = document.getElementById('filtro-fonte').value;
  const cidade = document.getElementById('filtro-cidade').value;

  const params = new URLSearchParams();
  if (q)      params.set('q', q);
  if (fonte)  params.set('fonte', fonte);
  if (cidade) params.set('cidade', cidade);

  dados = await fetch('/api/imoveis?' + params).then(r => r.json());
  await carregarStats();
  renderizar();
}

// ── renderiza tabela ──
function renderizar() {
  const sorted = [...dados].sort((a, b) => {
    const va = (a[sortCol] || '').toString();
    const vb = (b[sortCol] || '').toString();
    return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
  });

  document.getElementById('loading').style.display = 'none';
  document.getElementById('stat-exibindo').textContent = sorted.length.toLocaleString('pt-BR');

  if (sorted.length === 0) {
    document.getElementById('empty').style.display = 'block';
    return;
  }

  document.getElementById('tabela').style.display = 'table';
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = '';

  sorted.forEach((im, i) => {
    const tr = document.createElement('tr');
    tr.style.animationDelay = Math.min(i * 20, 300) + 'ms';

    const fonteClass = {
      'TJSC': 'tjsc',
      'JFSC': 'jfsc',
      'megaleiloes.com.br': 'mega',
      'leiloesjudiciais.com.br': 'leilo'
    }[im.fonte] || '';

    const data = im.criado_em
      ? new Date(im.criado_em).toLocaleString('pt-BR', {day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'})
      : '—';

    tr.innerHTML = `
      <td class="processo">${im.numero_processo}</td>
      <td class="descricao">${im.descricao || '—'}</td>
      <td class="valor">${im.valor_avaliacao || '—'}</td>
      <td class="cidade">${im.cidade || '—'}</td>
      <td><span class="fonte-badge ${fonteClass}">${im.fonte}</span></td>
      <td class="data">${data}</td>
      <td>${im.url_edital
        ? `<a class="link-edital" href="${im.url_edital}" target="_blank">↗ abrir</a>`
        : '<span style="color:var(--muted)">—</span>'}</td>
    `;
    tbody.appendChild(tr);
  });

  // sort indicators
  document.querySelectorAll('thead th').forEach(th => {
    th.classList.remove('asc','desc');
    if (th.dataset.col === sortCol) th.classList.add(sortDir);
  });
}

// ── sort por coluna ──
document.querySelectorAll('thead th[data-col]').forEach(th => {
  th.addEventListener('click', () => {
    if (sortCol === th.dataset.col) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      sortCol = th.dataset.col;
      sortDir = 'desc';
    }
    renderizar();
  });
});

// ── filtros com debounce ──
let timer;
document.getElementById('busca').addEventListener('input', () => {
  clearTimeout(timer);
  timer = setTimeout(carregar, 350);
});
document.getElementById('filtro-fonte').addEventListener('change', carregar);
document.getElementById('filtro-cidade').addEventListener('change', carregar);

// ── inicializa ──
carregarFiltros().then(carregar);
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

# ─────────────────────────────────────────────
#  INICIALIZA BANCO SE NÃO EXISTIR
# ─────────────────────────────────────────────

def garantir_banco():
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS imoveis (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_processo  TEXT    NOT NULL,
                descricao        TEXT,
                valor_avaliacao  TEXT,
                cidade           TEXT,
                fonte            TEXT,
                url_edital       TEXT,
                criado_em        TEXT    DEFAULT (datetime('now','localtime')),
                UNIQUE(numero_processo)
            )
        """)
        conn.commit()
        conn.close()
        print(f"✅ Banco criado: {DB_PATH}")

if __name__ == "__main__":
    garantir_banco()
    print("\n" + "="*50)
    print("  PAINEL LEILÕES JUDICIAIS SC")
    print("="*50)
    print(f"  Banco: {os.path.abspath(DB_PATH)}")
    print("  Acesse: http://localhost:5000")
    print("  Para encerrar: Ctrl+C")
    print("="*50 + "\n")
    app.run(debug=False, host="127.0.0.1", port=5000)
