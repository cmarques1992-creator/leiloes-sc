import sys
import asyncio
import sqlite3
import os
import re
import requests
import tempfile
import logging
from datetime import datetime
from playwright.async_api import async_playwright

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

WHATSAPP_API_URL   = "https://SEU_PROVEDOR_WHATSAPP/api/send"
WHATSAPP_API_TOKEN = "SEU_TOKEN_AQUI"
WHATSAPP_PHONE     = "5548999999999"
DB_PATH = "leiloes_sc.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("leiloes_sc.log", encoding="utf-8")]
)
log = logging.getLogger(__name__)

def p(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode('ascii'))

def init_db():
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
            criado_em        TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(numero_processo)
        )
    """)
    conn.commit()
    conn.close()

def salvar_imovel(imovel):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO imoveis (numero_processo, descricao, valor_avaliacao, cidade, fonte, url_edital)
            VALUES (:numero_processo, :descricao, :valor_avaliacao, :cidade, :fonte, :url_edital)
        """, imovel)
        conn.commit()
        conn.close()
        p("  [NOVO] " + imovel['numero_processo'] + " - " + imovel['cidade'])
        return True
    except sqlite3.IntegrityError:
        p("  [JA EXISTE] " + imovel['numero_processo'])
        return False

REGEX_PROCESSO = re.compile(r'\b\d{7}-\d{2}\.\d{4}\.\d{1}\.\d{2}\.\d{4}\b')

def extrair_processo_texto(texto):
    match = REGEX_PROCESSO.search(texto or "")
    return match.group(0) if match else None

def extrair_processo_pdf(url_pdf):
    if not pdfplumber:
        return None
    try:
        resp = requests.get(url_pdf, timeout=30)
        resp.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name
        numero = None
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                numero = extrair_processo_texto(page.extract_text() or "")
                if numero:
                    break
        os.unlink(tmp_path)
        return numero
    except:
        return None

def enviar_whatsapp(imovel):
    if "SEU_TOKEN" in WHATSAPP_API_TOKEN:
        return
    msg = (
        "NOVO LEILAO JUDICIAL SC\n"
        "------------------------\n"
        "Processo: " + imovel['numero_processo'] + "\n"
        "Imovel: " + (imovel['descricao'] or '') + "\n"
        "Cidade: " + (imovel['cidade'] or '') + "\n"
        "Avaliacao: " + (imovel['valor_avaliacao'] or '') + "\n"
        "Fonte: " + (imovel['fonte'] or '') + "\n"
        "------------------------"
    )
    try:
        requests.post(
            WHATSAPP_API_URL,
            json={"number": WHATSAPP_PHONE, "message": msg},
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + WHATSAPP_API_TOKEN},
            timeout=15
        )
    except:
        pass

async def txt(el, sel):
    try:
        e = await el.query_selector(sel)
        return (await e.inner_text()).strip() if e else None
    except:
        return None

def valor(texto):
    m = re.search(r'R\$\s*[\d.,]+', texto or "")
    return m.group(0) if m else "Nao informado"

def cidade_sc(texto):
    cidades = ["Florianopolis","Joinville","Blumenau","Itapema","Balneario Camboriu",
               "Chapeco","Criciuma","Lages","Jaragua do Sul","Palhoca","Biguacu",
               "Sao Jose","Tubarao","Camboriu","Navegantes","Gaspar","Brusque"]
    for c in cidades:
        if c.lower() in (texto or "").lower():
            return c
    return "SC"

async def scrape_leiloesjudiciais(page):
    imoveis = []
    try:
        await page.goto("https://www.leiloesjudiciais.com.br/imoveis?estado=SC", wait_until="networkidle", timeout=60000)
        await page.wait_for_selector(".leilao-card, .card-leilao, article", timeout=15000)
        cards = await page.query_selector_all(".leilao-card, .card-leilao, article")
        p("  leiloesjudiciais: " + str(len(cards)) + " cards")
        for card in cards:
            try:
                texto = await card.inner_text()
                link_el = await card.query_selector("a")
                url_e = await link_el.get_attribute("href") if link_el else None
                numero = extrair_processo_texto(texto)
                if not numero and url_e and url_e.endswith(".pdf"):
                    numero = extrair_processo_pdf(url_e)
                if numero:
                    imoveis.append({
                        "numero_processo": numero,
                        "descricao": await txt(card, "h2,h3,.titulo,.descricao") or "Nao identificado",
                        "valor_avaliacao": await txt(card, ".valor,.avaliacao") or "Nao informado",
                        "cidade": await txt(card, ".cidade,.local") or "SC",
                        "fonte": "leiloesjudiciais.com.br",
                        "url_edital": url_e,
                    })
            except:
                pass
    except Exception as e:
        log.error("Erro leiloesjudiciais: %s", e)
    return imoveis

async def scrape_megaleiloes(page):
    imoveis = []
    try:
        await page.goto("https://www.megaleiloes.com.br/imoveis?uf=SC", wait_until="networkidle", timeout=60000)
        await page.wait_for_selector(".item-leilao, .produto, .card", timeout=15000)
        cards = await page.query_selector_all(".item-leilao, .produto, .card")
        p("  megaleiloes: " + str(len(cards)) + " cards")
        for card in cards:
            try:
                texto = await card.inner_text()
                link_el = await card.query_selector("a")
                url_e = await link_el.get_attribute("href") if link_el else None
                numero = extrair_processo_texto(texto)
                if not numero and url_e and url_e.endswith(".pdf"):
                    numero = extrair_processo_pdf(url_e)
                if numero:
                    imoveis.append({
                        "numero_processo": numero,
                        "descricao": await txt(card, "h2,h3,.nome,.titulo") or "Nao identificado",
                        "valor_avaliacao": await txt(card, ".valor-avaliacao,.avaliacao") or "Nao informado",
                        "cidade": await txt(card, ".cidade,.municipio") or "SC",
                        "fonte": "megaleiloes.com.br",
                        "url_edital": url_e,
                    })
            except:
                pass
    except Exception as e:
        log.error("Erro megaleiloes: %s", e)
    return imoveis

async def scrape_tjsc(page):
    imoveis = []
    try:
        await page.goto("https://www.tjsc.jus.br/leiloes", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)
        links = await page.query_selector_all("a[href$='.pdf'], a[href*='edital']")
        p("  TJSC: " + str(len(links)) + " editais")
        for link in links:
            try:
                texto_link = (await link.inner_text()).strip()
                href = await link.get_attribute("href")
                if not href:
                    continue
                url_e = href if href.startswith("http") else "https://www.tjsc.jus.br" + href
                linha = await link.evaluate("el => el.closest('tr,li,div')?.innerText || ''")
                numero = extrair_processo_texto(linha or texto_link) or extrair_processo_pdf(url_e)
                if numero:
                    imoveis.append({
                        "numero_processo": numero,
                        "descricao": texto_link or "Edital TJSC",
                        "valor_avaliacao": valor(linha),
                        "cidade": cidade_sc(linha),
                        "fonte": "TJSC",
                        "url_edital": url_e,
                    })
            except:
                pass
    except Exception as e:
        log.error("Erro TJSC: %s", e)
    return imoveis

async def scrape_jfsc(page):
    imoveis = []
    try:
        await page.goto("https://www.jfsc.jus.br/acervo/leiloes", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)
        links = await page.query_selector_all("a[href$='.pdf'], a[href*='edital'], a[href*='leilao']")
        p("  JFSC: " + str(len(links)) + " editais")
        for link in links:
            try:
                texto_link = (await link.inner_text()).strip()
                href = await link.get_attribute("href")
                if not href:
                    continue
                url_e = href if href.startswith("http") else "https://www.jfsc.jus.br" + href
                linha = await link.evaluate("el => el.closest('tr,li,div')?.innerText || ''")
                numero = extrair_processo_texto(linha or texto_link) or extrair_processo_pdf(url_e)
                if numero:
                    imoveis.append({
                        "numero_processo": numero,
                        "descricao": texto_link or "Edital JFSC",
                        "valor_avaliacao": valor(linha),
                        "cidade": cidade_sc(linha),
                        "fonte": "JFSC",
                        "url_edital": url_e,
                    })
            except:
                pass
    except Exception as e:
        log.error("Erro JFSC: %s", e)
    return imoveis

async def executar_scraping():
    p("")
    p("=" * 50)
    p("  ROBO DE LEILOES JUDICIAIS SC")
    p("  " + datetime.now().strftime("%d/%m/%Y %H:%M"))
    p("=" * 50)
    init_db()
    total_novos = 0
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
        )
        await context.route("**/*.{png,jpg,gif,svg,woff,woff2,ttf,mp4,webp}", lambda route: route.abort())
        page = await context.new_page()
        for scraper in [scrape_leiloesjudiciais, scrape_megaleiloes, scrape_tjsc, scrape_jfsc]:
            nome = scraper.__name__.replace("scrape_", "")
            p("\nRaspando: " + nome)
            try:
                imoveis = await scraper(page)
                p("  -> " + str(len(imoveis)) + " imovel(is) encontrado(s)")
                for imovel in imoveis:
                    if salvar_imovel(imovel):
                        total_novos += 1
                        enviar_whatsapp(imovel)
            except Exception as e:
                log.error("Erro %s: %s", nome, e)
        await browser.close()
    p("")
    p("-" * 50)
    p("Concluido! Novos imoveis: " + str(total_novos))
    p("Acesse o painel: http://localhost:5000")
    p("-" * 50)

if __name__ == "__main__":
    asyncio.run(executar_scraping())
