# app.py - VERSÃO EVOLUÍDA COM ARQUITETURA DE COLETORES E NOVA UI

import os
import json
import time
from flask import Flask, render_template_string, request, redirect, url_for
from elasticsearch import Elasticsearch
from math import ceil
from datetime import datetime
import traceback

# Importa o novo scraper do pacote 'coletores'
from coletores.bnp_scraper import scrape_bnp
# Mantém a importação original para o scraper LexML
import requests
from bs4 import BeautifulSoup


app = Flask(__name__)
INDEX_NAME = 'jurisprudencia'
RESULTS_PER_PAGE = 10

es = Elasticsearch("http://elasticsearch:9200")

INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "tipo_documento": {"type": "keyword"},
            "data_julgamento": {"type": "text"},
            "ano_julgamento": {"type": "integer"},
            "fonte": {"type": "keyword"},
            "autoridade": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
            "classe": {"type": "keyword"},
            "titulo": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "ementa": {"type": "text"},
            "texto_decisao": {"type": "text"},
            "link": {"type": "keyword"},
            "id": {"type": "keyword"},
            "orgaoJulgador": {"type": "keyword"},
            "ramoDireito": {"type": "keyword"},
            "numeroUnico": {"type": "keyword"},
            "assuntos": {"type": "text"}
        }
    },
    "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}}
}

def extract_year(date_str):
    if not date_str or len(date_str.strip()) < 4: return None
    date_str = date_str.strip()
    try:
        year = int(datetime.strptime(date_str.strip()[:10], '%d/%m/%Y').strftime('%Y'))
        if 1800 < year < 2100: return year
    except (ValueError, IndexError): pass
    try:
        year = int(datetime.strptime(date_str.strip()[:10], '%Y-%m-%d').strftime('%Y'))
        if 1800 < year < 2100: return year
    except (ValueError, IndexError): pass
    print(f"AVISO: Ano não pôde ser extraído da string: '{date_str}'")
    return None

def create_index_if_not_exists():
    try:
        if not es.indices.exists(index=INDEX_NAME):
            print(f"Índice '{INDEX_NAME}' não encontrado. Criando com o novo mapeamento...")
            es.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)
            print(f"Índice '{INDEX_NAME}' criado com sucesso.")
        else:
            print(f"Índice '{INDEX_NAME}' já existe.")
    except Exception as e:
        print(f"Erro ao criar índice: {e}")

INTERFACE_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <title>iurisadv.ai - Pesquisa Jurídica Avançada</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f7fc; color: #333; }
      .header { background-color: #fff; padding: 1em 2em; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
      .container { max-width: 900px; margin: auto; padding: 2em; }
      h1 { color: #2c3e50; font-size: 1.5em; }
      .search-container { text-align: center; margin-bottom: 1em; }
      form { display: block; }
      .search-type-selector { display: flex; justify-content: center; margin-bottom: 1.5em; background-color: #e9ecef; border-radius: 8px; padding: 5px; max-width: 400px; margin-left: auto; margin-right: auto;}
      .search-type-selector input[type="radio"] { display: none; }
      .search-type-selector label { flex: 1; padding: 10px 15px; text-align: center; cursor: pointer; border-radius: 6px; transition: all 0.2s ease-in-out; font-weight: 500; color: #495057; }
      .search-type-selector input[type="radio"]:checked + label { background-color: #fff; color: #0d6efd; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
      .search-bar { display: flex; max-width: 800px; margin: auto; gap: 10px; }
      .search-bar input { flex-grow: 1; padding: 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 1em; }
      .search-bar button { padding: 12px 20px; border: none; background-color: #3498db; color: white; border-radius: 4px; font-size: 1em; cursor: pointer; }
      .search-bar button:hover { background-color: #2980b9; }
      
      /* NOVO ESTILO PARA O BOTÃO DE FILTROS AVANÇADOS */
      .advanced-search-toggle { display: flex; justify-content: flex-end; align-items-center; max-width: 800px; margin: 1em auto; gap: 10px; }
      .advanced-search-toggle label { font-weight: 500; color: #495057; }
      .toggle-switch { position: relative; display: inline-block; width: 50px; height: 28px; }
      .toggle-switch input { opacity: 0; width: 0; height: 0; }
      .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 28px; }
      .slider:before { position: absolute; content: ""; height: 20px; width: 20px; left: 4px; bottom: 4px; background-color: white; transition: .4s; border-radius: 50%; }
      input:checked + .slider { background-color: #2196F3; }
      input:checked + .slider:before { transform: translateX(22px); }

      .filters-box { background-color: #fff; border: 1px solid #e1e8ed; border-radius: 8px; padding: 1.5em; margin-top: 1em; display: none; max-width: 800px; margin-left: auto; margin-right: auto; }
      .filters-box.visible { display: block; }
      .filters-box h2 { margin-top: 0; color: #2c3e50; }
      .filter-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1em; }
      .filters-box .form-group { margin-bottom: 1em; text-align: left; }
      .filters-box label { display: block; margin-bottom: 0.5em; font-weight: bold; color: #566573; }
      .filters-box input, .filters-box select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box;}
      .filters-box .year-group { display: flex; gap: 10px; }
      .content-wrapper { display: flex; gap: 2em; align-items: flex-start; }
      .results-column { flex-grow: 1; }
      .result-item { background-color: #fff; border: 1px solid #e1e8ed; border-radius: 8px; margin-bottom: 1.5em; padding: 1.5em; }
      .result-item h3 a { text-decoration: none; color: #1b4f72; font-size: 1.1em;}
      .result-item h3 a:hover { text-decoration: underline; }
      .result-item dl { margin: 1em 0 0 0; }
      .result-item dt { font-weight: bold; color: #566573; float: left; width: 120px; clear: left; }
      .result-item dd { margin-left: 130px; margin-bottom: 0.5em; }
      .pagination { text-align: center; margin: 2em 0; display: flex; justify-content: center; align-items: center; }
      .pagination a, .pagination span { margin: 0 2px; padding: 8px 12px; border: 1px solid #ddd; text-decoration: none; color: #3498db; border-radius: 4px; }
      .pagination a:hover { background-color: #f8f9fa; }
      .pagination span.current { background-color: #3498db; color: white; border-color: #3498db; }
      .pagination span.dots { border: none; padding: 8px 4px;}
      .message-box { background-color: #fff; border: 1px solid #e1e8ed; border-radius: 8px; padding: 1.5em; margin-bottom: 1.5em; }
      .message-box.import { background-color: #fff5e6; border-color: #ffcc80; }
      .message-box.error { background-color: #ffebee; border-color: #ef5350; }
      .results-info { color: #666; margin-bottom: 1em; }
    </style>
</head>
<body>
    <div class="header"><h1>iurisadv.ai</h1></div>
    <div class="container">
        <form action="/" method="GET">
            <div class="search-type-selector">
                <input type="radio" id="type_juris" name="type" value="jurisprudencia" {% if search_type == 'jurisprudencia' %}checked{% endif %}>
                <label for="type_juris">Jurisprudências</label>
                <input type="radio" id="type_prec" name="type" value="precedente" {% if search_type == 'precedente' %}checked{% endif %}>
                <label for="type_prec">Precedentes</label>
            </div>

            <div class="search-container">
                <div class="search-bar">
                    <input type="text" name="q" placeholder="Digite sua busca..." value="{{ query }}">
                    <button type="submit">Pesquisar</button>
                </div>
                <div class="advanced-search-toggle">
                    <label for="toggle-filters">Pesquisa Avançada</label>
                    <label class="toggle-switch">
                        <input type="checkbox" id="toggle-filters" onchange="toggleFilters()" {% if show_filters == 'true' %}checked{% endif %}>
                        <span class="slider"></span>
                    </label>
                </div>
            </div>

            <div class="filters-box" id="filters-box">
                <h2>Filtros Avançados</h2>
                <input type="hidden" name="show_filters" value="true">
                <div class="filter-grid">
                    <div class="form-group">
                        <label for="sort">Ordenar por</label>
                        <select name="sort" id="sort">
                            <option value="relevance" {% if sort_order == 'relevance' %}selected{% endif %}>Relevância</option>
                            <option value="date_desc" {% if sort_order == 'date_desc' %}selected{% endif %}>Mais Recentes</option>
                            <option value="date_asc" {% if sort_order == 'date_asc' %}selected{% endif %}>Mais Antigos</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Ano de Publicação</label>
                        <div class="year-group">
                            <input type="number" name="year_min" placeholder="De" value="{{ year_min }}" min="1900" max="2030">
                            <input type="number" name="year_max" placeholder="Até" value="{{ year_max }}" min="1900" max="2030">
                        </div>
                    </div>
                </div>
                <button type="submit" style="width: 100%; padding: 12px; border: none; background-color: #27ae60; color: white; border-radius: 4px; font-size: 1em; cursor: pointer; margin-top: 1em;">Aplicar Filtros</button>
            </div>
        </form>

        <div class="content-wrapper">
            <div class="results-column">
                {% if needs_import %}
                    <div class="message-box import">
                        <p><strong>O banco de dados está vazio.</strong></p>
                        <a href="{{ url_for('import_data_from_json') }}">Importar Dados de Teste (Arquivo Local)</a>
                    </div>
                {% elif error %}
                     <div class="message-box error"><p>{{ error }}</p></div>
                {% elif trigger_scrape %}
                    <div class="message-box import">
                         <p><strong>Nenhum resultado encontrado para "{{ query }}".</strong></p>
                         {% if search_type == 'jurisprudencia' %}
                            <a href="{{ url_for('importar_lexml', q=query) }}">Buscar e importar Jurisprudência do LexML</a>
                         {% else %}
                            <a href="{{ url_for('importar_bnp', q=query) }}">Buscar e importar Precedentes do Pangea BNP</a>
                         {% endif %}
                    </div>
                {% elif total is defined and total is not none and not is_homepage %}
                     <div class="results-info"><p>Exibindo página {{ current_page }} de {{ total_pages }} ({{ total }} resultados no total).</p></div>
                {% endif %}

                {% if is_homepage %}
                    <h2>Documentos Mais Recentes</h2>
                {% endif %}
                
                {% for result in results %}
                    <div class="result-item">
                        <h3><a href="{{ result.link }}" target="_blank">{{ result.titulo }}</a></h3>
                        <dl>
                            {% if result.tipo_documento == 'precedente' %}
                                {% if result.orgaoJulgador %}<dt>Órgão Julgador:</dt><dd>{{ result.orgaoJulgador }}</dd>{% endif %}
                                {% if result.ramoDireito %}<dt>Ramo do Direito:</dt><dd>{{ result.ramoDireito }}</dd>{% endif %}
                                {% if result.numeroUnico %}<dt>Número Único:</dt><dd>{{ result.numeroUnico }}</dd>{% endif %}
                                {% if result.assuntos %}<dt>Assuntos:</dt><dd>{{ result.assuntos }}</dd>{% endif %}
                                {% if result.data_julgamento %}<dt>Data:</dt><dd>{{ result.data_julgamento }}</dd>{% endif %}
                            {% else %}
                                {% if result.autoridade %}<dt>Autoridade:</dt><dd>{{ result.autoridade }}</dd>{% endif %}
                                {% if result.data_julgamento %}<dt>Data:</dt><dd>{{ result.data_julgamento }}</dd>{% endif %}
                                {% if result.ementa %}<dt>Ementa:</dt><dd>{{ result.ementa }}</dd>{% endif %}
                            {% endif %}
                            {% if result.fonte %}<dt>Fonte:</dt><dd>{{ result.fonte }}</dd>{% endif %}
                        </dl>
                    </div>
                {% endfor %}

                {% if total_pages and total_pages > 1 %}
                <div class="pagination">
                    <a href="{{ url_for('home', q=query, type=search_type, page=1, sort=sort_order, year_min=year_min, year_max=year_max, show_filters=show_filters) }}">&laquo;</a>
                    {% for page_num in page_numbers %}
                        {% if page_num == '...' %}
                            <span class="dots">...</span>
                        {% elif page_num == current_page %}
                            <span class="current">{{ page_num }}</span>
                        {% else %}
                            <a href="{{ url_for('home', q=query, type=search_type, page=page_num, sort=sort_order, year_min=year_min, year_max=year_max, show_filters=show_filters) }}">{{ page_num }}</a>
                        {% endif %}
                    {% endfor %}
                    <a href="{{ url_for('home', q=query, type=search_type, page=total_pages, sort=sort_order, year_min=year_min, year_max=year_max, show_filters=show_filters) }}">&raquo;</a>
                </div>
                {% endif %}
            </div>
        </div>
    </div>
    <script>
        function toggleFilters() {
            const filtersBox = document.getElementById('filters-box');
            filtersBox.classList.toggle('visible');
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('show_filters') === 'true' || 
                urlParams.get('year_min') || 
                urlParams.get('year_max') || 
                (urlParams.get('sort') && urlParams.get('sort') !== 'relevance')) {
                document.getElementById('filters-box').classList.add('visible');
                document.getElementById('toggle-filters').checked = true;
            }
        });
    </script>
</body>
</html>
"""

@app.route('/', endpoint='home')
def home():
    """Rota principal com pesquisa por tipo, filtros por ano."""
    try:
        query = request.args.get('q', '').strip()
        search_type = request.args.get('type', 'jurisprudencia')
        page = request.args.get('page', 1, type=int)
        sort_order = request.args.get('sort', 'relevance')
        year_min = request.args.get('year_min', '')
        year_max = request.args.get('year_max', '')
        show_filters = request.args.get('show_filters', 'false')
        
        if page < 1: page = 1
        from_value = (page - 1) * RESULTS_PER_PAGE

        if not es.indices.exists(index=INDEX_NAME):
            return render_template_string(
                INTERFACE_TEMPLATE, needs_import=True, query=query, search_type=search_type,
                sort_order=sort_order, year_min=year_min, year_max=year_max, show_filters=show_filters,
                results=[], page_numbers=[], current_page=1, total_pages=0, total=0,
                is_homepage=False, error=None, trigger_scrape=False
            )
        
        filters_for_es = [{"term": {"tipo_documento.keyword": search_type}}]
        
        year_range_filter = {}
        if year_min and year_min.isdigit(): year_range_filter["gte"] = int(year_min)
        if year_max and year_max.isdigit(): year_range_filter["lte"] = int(year_max)
        if year_range_filter: filters_for_es.append({"range": {"ano_julgamento": year_range_filter}})

        sort_query = []
        if sort_order == 'date_desc': sort_query = [{"ano_julgamento": {"order": "desc", "missing": "_last"}}]
        elif sort_order == 'date_asc': sort_query = [{"ano_julgamento": {"order": "asc", "missing": "_last"}}]
        
        is_homepage = not query and not year_min and not year_max and sort_order == 'relevance'
        
        search_body = {"from": from_value, "size": RESULTS_PER_PAGE}
        
        if is_homepage:
            search_body["query"] = {"bool": {"filter": filters_for_es, "must": {"match_all": {}}}}
            search_body["sort"] = [{"ano_julgamento": {"order": "desc", "missing": "_last"}}]
            search_body["size"] = 3
        else:
            must_clause = {"match_all": {}}
            if query:
                must_clause = {"multi_match": {"query": query, "fields": ["titulo^2", "ementa^1.5", "texto_decisao", "autoridade", "assuntos"], "type": "best_fields", "operator": "or"}}
            search_body["query"] = {"bool": {"must": must_clause, "filter": filters_for_es}}
            if sort_query: search_body["sort"] = sort_query
        
        print(f"CONSULTA ELASTICSEARCH:\n{json.dumps(search_body, indent=2, ensure_ascii=False)}\n")
        res = es.search(index=INDEX_NAME, body=search_body)
        
        results = [hit['_source'] for hit in res['hits']['hits']]
        total = res['hits']['total']['value']
        total_pages = ceil(total / RESULTS_PER_PAGE) if not is_homepage else 0
        if page > total_pages and total_pages > 0: page = total_pages
        
        page_numbers = get_pagination_range(page, total_pages)
        trigger_scrape = query and total == 0 and not is_homepage

        return render_template_string(
            INTERFACE_TEMPLATE,
            query=query, search_type=search_type, results=results, total=total, current_page=page, total_pages=total_pages,
            sort_order=sort_order, year_min=year_min, year_max=year_max, show_filters=show_filters,
            is_homepage=is_homepage, page_numbers=page_numbers, needs_import=False, error=None,
            trigger_scrape=trigger_scrape
        )

    except Exception as e:
        print(f"Erro na rota de busca: {e}")
        traceback.print_exc()
        return render_template_string(
            INTERFACE_TEMPLATE, query=request.args.get('q', ''), search_type=request.args.get('type', 'jurisprudencia'), 
            results=[], total=0, current_page=1, total_pages=0, sort_order=request.args.get('sort', 'relevance'),
            year_min=request.args.get('year_min', ''), year_max=request.args.get('year_max', ''),
            show_filters=request.args.get('show_filters', 'false'), is_homepage=False,
            page_numbers=[], needs_import=False, error=f"Ocorreu um erro ao processar a busca: {str(e)}",
            trigger_scrape=False
        )

def get_pagination_range(current_page, total_pages, window=2):
    if total_pages is None or total_pages <= 1: return []
    if total_pages <= 7: return list(range(1, total_pages + 1))
    pages = [1]
    if current_page > window + 2: pages.append('...')
    start, end = max(2, current_page - window), min(total_pages - 1, current_page + window)
    for i in range(start, end + 1):
        if i not in pages: pages.append(i)
    if current_page < total_pages - (window + 1): pages.append('...')
    if total_pages not in pages: pages.append(total_pages)
    return pages

@app.route('/import-json')
def import_data_from_json():
    try:
        create_index_if_not_exists()
        filepath = os.path.join('data', 'jurisprudencias.json')
        if not os.path.exists(filepath): return "Arquivo jurisprudencias.json não encontrado no diretório data/", 404
        with open(filepath, 'r', encoding='utf-8') as f:
            jurisprudencias = json.load(f)
        count = 0
        for doc in jurisprudencias:
            doc_id = doc.get("numero_processo")
            if not doc_id: continue
            original_date = doc.get("data_julgamento")
            doc_to_index = {
                "tipo_documento": "jurisprudencia", "id": doc_id, "titulo": doc.get("classe", "") + " - " + doc.get("assunto", ""),
                "classe": doc.get("classe"), "assunto": doc.get("assunto"), "magistrado": doc.get("magistrado"), "comarca": doc.get("comarca"),
                "data_julgamento": original_date, "ano_julgamento": extract_year(original_date), "ementa": doc.get("ementa"),
                "texto_decisao": doc.get("inteiro_teor"), "fonte": "TJSC (Arquivo JSON)", "link": "#", "autoridade": doc.get("magistrado", "")
            }
            es.index(index=INDEX_NAME, id=doc_id, body=doc_to_index)
            count += 1
        es.indices.refresh(index=INDEX_NAME)
        print(f"Importados {count} documentos do arquivo JSON")
        return redirect(url_for('home'))
    except Exception as e:
        print(f"Erro ao importar JSON: {e}")
        traceback.print_exc()
        return f"Erro ao importar JSON: {e}", 500

@app.route('/importar-lexml')
def importar_lexml():
    termo_de_busca = request.args.get('q')
    if not termo_de_busca: return "Erro: Nenhum termo de busca fornecido.", 400
    try:
        # ... (Lógica do LexML scraper permanece a mesma)
        create_index_if_not_exists()
        total_coletado = 0
        ano_inicial, ano_atual = 2015, datetime.now().year
        keyword_com_data = f"{termo_de_busca};;year={ano_inicial};year-max={ano_atual}"
        start_doc = 1
        max_documentos = 100
        continuar = True
        while continuar and total_coletado < max_documentos:
            url = f"https://www.lexml.gov.br/busca/search?keyword={keyword_com_data}&f1-tipoDocumento=Jurisprudência&startDoc={start_doc}"
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            resultados = soup.find_all('div', class_='docHit')
            if not resultados: break
            for item in resultados:
                try:
                    titulo_tag = item.find(lambda t: t.name == 'td' and 'Título' in t.text)
                    urn_tag = item.find(lambda t: t.name == 'td' and 'URN' in t.text)
                    if not (titulo_tag and urn_tag): continue
                    doc_id = urn_tag.find_next_sibling('td').text.strip()
                    titulo_link = titulo_tag.find_next_sibling('td').find('a')
                    if not (doc_id and titulo_link): continue
                    data_tag = item.find(lambda t: t.name == 'td' and 'Data' in t.text)
                    autoridade_tag = item.find(lambda t: t.name == 'td' and 'Autoridade' in t.text)
                    ementa_tag = item.find(lambda t: t.name == 'td' and 'Ementa' in t.text)
                    original_date_str = data_tag.find_next_sibling('td').text.strip() if data_tag else ''
                    documento = {
                        "tipo_documento": "jurisprudencia", "id": doc_id, "titulo": titulo_link.text.strip(),
                        "ementa": ementa_tag.find_next_sibling('td').text.strip() if ementa_tag else '',
                        "data_julgamento": original_date_str, "ano_julgamento": extract_year(original_date_str),
                        "autoridade": autoridade_tag.find_next_sibling('td').text.strip() if autoridade_tag else '',
                        "link": f"https://www.lexml.gov.br{titulo_link['href']}", "fonte": "LexML",
                        "texto_decisao": "", "classe": "", "assunto": ""
                    }
                    es.index(index=INDEX_NAME, id=doc_id, body=documento)
                    total_coletado += 1
                except Exception as e:
                    print(f"Erro ao processar item: {e}")
            link_proxima = soup.find('a', string=lambda text: text and 'Próxima' in text.strip())
            if link_proxima and total_coletado < max_documentos:
                start_doc += 20
                time.sleep(1)
            else:
                continuar = False
        es.indices.refresh(index=INDEX_NAME)
        print(f"Total de documentos importados: {total_coletado}")
        return redirect(url_for('home', q=termo_de_busca, type='jurisprudencia'))
    except Exception as e:
        print(f"Erro durante importação do LexML: {e}")
        traceback.print_exc()
        return f"Erro durante a coleta: {e}", 500


@app.route('/importar-bnp')
def importar_bnp():
    """Importa dados de Precedentes do Pangea BNP via scraping."""
    termo_de_busca = request.args.get('q')
    if not termo_de_busca: return "Erro: Nenhum termo de busca fornecido.", 400
    try:
        create_index_if_not_exists()
        
        # Chama a função do nosso novo módulo coletor
        documentos = scrape_bnp(termo_de_busca)
        total_coletado = 0
        
        for doc in documentos:
            doc['ano_julgamento'] = extract_year(doc.get('data_julgamento'))
            es.index(index=INDEX_NAME, id=doc['id'], body=doc)
            total_coletado += 1
            
        es.indices.refresh(index=INDEX_NAME)
        print(f"Total de precedentes indexados do Pangea BNP: {total_coletado}")
        return redirect(url_for('home', q=termo_de_busca, type='precedente'))

    except Exception as e:
        print(f"Erro durante importação do Pangea BNP: {e}")
        traceback.print_exc()
        return f"Erro durante a coleta do Pangea BNP: {e}", 500


if __name__ == '__main__':
    max_retries = 10
    retry_count = 0
    while retry_count < max_retries:
        try:
            if es.ping():
                print("Conectado ao Elasticsearch com sucesso!")
                create_index_if_not_exists()
                break
        except Exception as e:
            retry_count += 1
            print(f"Tentativa {retry_count}/{max_retries} - Erro ao conectar ao Elasticsearch: {e}")
            if retry_count < max_retries: time.sleep(5)
            else: print("Não foi possível conectar ao Elasticsearch. A aplicação pode não funcionar.")
    
    app.run(host='0.0.0.0', port=3000, debug=True)

