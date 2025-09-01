# app.py - VERSÃO FINAL COM UI CORRIGIDA, FILTROS AVANÇADOS COM TOGGLE E CORREÇÃO DE BUGS

import os
import json
import time
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string, request, redirect, url_for
from elasticsearch import Elasticsearch
from math import ceil
from datetime import datetime

app = Flask(__name__)
INDEX_NAME = 'jurisprudencia'
RESULTS_PER_PAGE = 10

es = Elasticsearch("http://elasticsearch:9200")

INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "data_julgamento": {"type": "date"},
            "data": {"type": "date"},
            "fonte": {"type": "keyword"},
            "autoridade": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
            "classe": {"type": "keyword"}
        }
    }
}

def create_index_if_not_exists():
    if not es.indices.exists(index=INDEX_NAME):
        print(f"Índice '{INDEX_NAME}' não encontrado. A criar com o mapeamento correto...")
        es.indices.create(index=INDEX_NAME, body=INDEX_MAPPING, ignore=400)

INTERFACE_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <title>iurisadv.ai - Pesquisa Jurisprudencial</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f7fc; color: #333; }
      .header { background-color: #fff; padding: 1em 2em; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
      .container { max-width: 900px; margin: auto; padding: 2em; }
      h1 { color: #2c3e50; font-size: 1.5em; }
      .search-container { text-align: center; margin-bottom: 1em; }
      .search-bar form { display: flex; max-width: 800px; margin: auto; gap: 10px; }
      .search-bar input { flex-grow: 1; padding: 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 1em; }
      .search-bar button { padding: 12px 20px; border: none; background-color: #3498db; color: white; border-radius: 4px; font-size: 1em; cursor: pointer; }
      .advanced-search-toggle { text-align: right; max-width: 800px; margin: 1em auto; }
      .advanced-search-toggle label { cursor: pointer; user-select: none; }
      #toggle-filters { margin-right: 5px; }
      .filters-box { background-color: #fff; border: 1px solid #e1e8ed; border-radius: 8px; padding: 1.5em; margin-top: 1em; display: none; }
      .filters-box.visible { display: block; }
      .filters-box h2 { margin-top: 0; }
      .filter-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1em; }
      .filters-box .form-group { margin-bottom: 1em; text-align: left; }
      .filters-box label { display: block; margin-bottom: 0.5em; font-weight: bold; }
      .filters-box input, .filters-box select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box;}
      .filters-box .year-group { display: flex; gap: 10px; }
      .content-wrapper { display: flex; gap: 2em; align-items: flex-start; }
      .results-column { flex-grow: 1; }
      .filters-column { width: 280px; flex-shrink: 0; }
      .result-item { background-color: #fff; border: 1px solid #e1e8ed; border-radius: 8px; margin-bottom: 1.5em; padding: 1.5em; }
      .result-item h3 a { text-decoration: none; color: #1b4f72; font-size: 1.1em;}
      .result-item dl { margin: 1em 0 0 0; }
      .result-item dt { font-weight: bold; color: #566573; float: left; width: 90px; clear: left; }
      .result-item dd { margin-left: 100px; margin-bottom: 0.5em; }
      .pagination { text-align: center; margin: 2em 0; display: flex; justify-content: center; align-items: center; }
      .pagination a, .pagination span { margin: 0 2px; padding: 8px 12px; border: 1px solid #ddd; text-decoration: none; color: #3498db; border-radius: 4px; }
      .pagination span.current { background-color: #3498db; color: white; border-color: #3498db; }
      .pagination span.dots { border: none; padding: 8px 4px;}
    </style>
</head>
<body>
    <div class="header"><h1>iurisadv.ai</h1></div>
    <div class="container">
        <div class="search-container">
            <div class="search-bar">
                 <form action="/" method="GET" id="search-form">
                    <input type="text" name="q" placeholder="Digite sua busca..." value="{{ query }}">
                    <button type="submit">Pesquisar</button>
                </form>
            </div>
            <div class="advanced-search-toggle">
                <input type="checkbox" id="toggle-filters" onchange="toggleFilters()">
                <label for="toggle-filters">Pesquisa Avançada</label>
            </div>
        </div>

        <div class="filters-box" id="filters-box">
            <form action="/" method="GET" id="filters-form">
                <input type="hidden" name="q" value="{{ query }}">
                <input type="hidden" name="show_filters" value="true">
                <div class="filter-grid">
                    <div class="form-group">
                        <label for="sort">Ordenar por</label>
                        <select name="sort" id="sort">
                            <option value="relevance" {{ 'selected' if sort_order == 'relevance' }}>Relevância</option>
                            <option value="date_desc" {{ 'selected' if sort_order == 'date_desc' }}>Mais Recentes</option>
                            <option value="date_asc" {{ 'selected' if sort_order == 'date_asc' }}>Mais Antigos</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Ano de Publicação</label>
                        <div class="year-group">
                            <input type="number" name="year_min" placeholder="De" value="{{ filters.get('year_min') or '' }}">
                            <input type="number" name="year_max" placeholder="Até" value="{{ filters.get('year_max') or '' }}">
                        </div>
                    </div>
                </div>
                <button type="submit" style="width: 100%; padding: 12px; border: none; background-color: #27ae60; color: white; border-radius: 4px; font-size: 1em; cursor: pointer; margin-top: 1em;">Aplicar Filtros</button>
            </form>
        </div>

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
                         <a href="{{ url_for('importar_lexml', q=query) }}">Buscar e importar do LexML (a partir de 2015)</a>
                    </div>
                {% elif total is not none %}
                     <div class="results-info"><p>Exibindo página {{ current_page }} de {{ total_pages }} ({{ total }} resultados no total).</p></div>
                {% endif %}

                {% if is_homepage %}
                    <h2>Jurisprudências Mais Recentes</h2>
                {% endif %}
                
                {% for result in results %}
                    <div class="result-item">
                        <h3><a href="{{ result.link }}" target="_blank">{{ result.titulo }}</a></h3>
                        <dl>
                            {% if result.autoridade %}<dt>Autoridade:</dt><dd>{{ result.autoridade }}</dd>{% endif %}
                            {% if result.data or result.data_julgamento %}<dt>Data:</dt><dd>{{ result.data or result.data_julgamento }}</dd>{% endif %}
                            {% if result.ementa %}<dt>Ementa:</dt><dd>{{ result.ementa }}</dd>{% endif %}
                            {% if result.id %}<dt>URN:</dt><dd>{{ result.id }}</dd>{% endif %}
                            {% if result.fonte %}<dt>Fonte:</dt><dd>{{ result.fonte }}</dd>{% endif %}
                        </dl>
                    </div>
                {% endfor %}

                {% if total_pages > 1 %}
                <div class="pagination">
                    <a href="{{ url_for('home', q=query, page=1, sort=sort_order, year_min=filters.get('year_min', ''), year_max=filters.get('year_max', '')) }}">&laquo;</a>
                    {% for page_num in page_numbers %}
                        {% if page_num == '...' %}
                            <span class="dots">...</span>
                        {% elif page_num == current_page %}
                            <span class="current">{{ page_num }}</span>
                        {% else %}
                            <a href="{{ url_for('home', q=query, page=page_num, sort=sort_order, year_min=filters.get('year_min', ''), year_max=filters.get('year_max', '')) }}">{{ page_num }}</a>
                        {% endif %}
                    {% endfor %}
                    <a href="{{ url_for('home', q=query, page=total_pages, sort=sort_order, year_min=filters.get('year_min', ''), year_max=filters.get('year_max', '')) }}">&raquo;</a>
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
            if (urlParams.get('show_filters') === 'true' || urlParams.get('year_min') || urlParams.get('year_max') || urlParams.get('sort') !== 'relevance') {
                document.getElementById('filters-box').classList.add('visible');
                document.getElementById('toggle-filters').checked = true;
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    args = request.args.copy()
    query = args.get('q', '').strip()
    page = args.get('page', 1, type=int)
    sort_order = args.get('sort', 'relevance')
    year_min_str = args.get('year_min', '')
    year_max_str = args.get('year_max', '')
    show_filters = args.get('show_filters', 'false').lower() == 'true'
    from_value = (page - 1) * RESULTS_PER_PAGE

    try:
        if not es.indices.exists(index=INDEX_NAME):
            return render_template_string(INTERFACE_TEMPLATE, needs_import=True, query=query, filters={}, request=request)

        active_filters = {key: val for key, val in args.items() if val and key != 'page'}
        filters_for_es = []
        if year_min_str.isdigit():
            filters_for_es.append({"range": {"data_julgamento": {"gte": f"{year_min_str}-01-01"}}})
        if year_max_str.isdigit():
            filters_for_es.append({"range": {"data_julgamento": {"lte": f"{year_max_str}-12-31"}}})

        sort_query = []
        if sort_order == 'date_desc':
            sort_query.append({"data_julgamento": {"order": "desc", "unmapped_type": "date"}})
        elif sort_order == 'date_asc':
            sort_query.append({"data_julgamento": {"order": "asc", "unmapped_type": "date"}})
        
        search_body = {"from": from_value, "size": RESULTS_PER_PAGE, "sort": sort_query}

        is_homepage = not query and not active_filters
        if is_homepage:
            search_body['query'] = {"match_all": {}}
            search_body['sort'] = [{"data_julgamento": {"order": "desc", "unmapped_type": "date"}}]
            search_body['size'] = 3
        else:
            must_query = [{"multi_match": {"query": query, "fields": ["titulo", "ementa", "texto_decisao"]}}] if query else []
            search_body['query'] = {"bool": {"must": must_query, "filter": filters_for_es}}

        res = es.search(index=INDEX_NAME, body=search_body)
        
        results = [hit['_source'] for hit in res['hits']['hits']]
        total = res['hits']['total']['value']
        total_pages = ceil(total / RESULTS_PER_PAGE)
        
        page_numbers = get_pagination_range(current_page=page, total_pages=total_pages)
        filters_visible = show_filters or bool(active_filters)

        if total == 0 and query:
            return render_template_string(INTERFACE_TEMPLATE, query=query, results=[], total=0, trigger_scrape=True, sort_order=sort_order, filters=active_filters, filters_visible=True, request=request, page_numbers=[])
        
        return render_template_string(INTERFACE_TEMPLATE, 
            query=query, results=results, total=total, current_page=page, total_pages=total_pages, 
            sort_order=sort_order, is_homepage=is_homepage, page_numbers=page_numbers, 
            filters=active_filters, filters_visible=filters_visible, request=request)

    except Exception as e:
        print(f"Erro na rota de busca: {e}")
        return render_template_string(INTERFACE_TEMPLATE, query=query, results=[], total=0, error="Ocorreu um erro ao comunicar com o banco de dados.", filters={}, request=request)

def get_pagination_range(current_page, total_pages, window=2):
    if total_pages <= 7: return list(range(1, total_pages + 1))
    
    pages = []
    if current_page > window + 2:
        pages.extend([1, '...'])
    
    start = max(1, current_page - window)
    end = min(total_pages, current_page + window)
    pages.extend(range(start, end + 1))

    if current_page < total_pages - (window + 1):
        pages.extend(['...', total_pages])
            
    final_pages = []
    [final_pages.append(p) for p in pages if p not in final_pages]
    return final_pages

# (As rotas /import-json e /importar-lexml e a função create_index_if_not_exists permanecem as mesmas)

@app.route('/import-json')
def import_data_from_json():
    try:
        create_index_if_not_exists()
        filepath = os.path.join('data', 'jurisprudencias.json')
        with open(filepath, 'r', encoding='utf-8') as f:
            jurisprudencias = json.load(f)
        
        for doc in jurisprudencias:
            doc_id = doc.get("numero_processo")
            if not doc_id: continue
            
            es.index(index=INDEX_NAME, id=doc_id, body={
                "id": doc_id, "classe": doc.get("classe"), "assunto": doc.get("assunto"),
                "magistrado": doc.get("magistrado"), "comarca": doc.get("comarca"),
                "data_julgamento": doc.get("data_julgamento"), "ementa": doc.get("ementa"),
                "texto_decisao": doc.get("inteiro_teor"), "fonte": "TJSC (Arquivo JSON)"
            })
        
        es.indices.refresh(index=INDEX_NAME)
        return redirect(url_for('home'))
    except Exception as e:
        print(f"Erro ao importar JSON: {e}")
        return f"Erro ao importar JSON: {e}", 500

@app.route('/importar-lexml', endpoint='importar_lexml')
def importar_lexml():
    termo_de_busca = request.args.get('q')
    if not termo_de_busca:
        return "Erro: Nenhum termo de busca fornecido.", 400
    
    try:
        create_index_if_not_exists()
        create_index_if_not_exists()
        tipo_documento = 'Jurisprudência'
        start_doc = 1
        continuar = True
        total_coletado_nesta_sessao = 0
        
        ano_inicial = 2015
        ano_atual = datetime.now().year
        keyword_com_data = f"{termo_de_busca};;year={ano_inicial};year-max={ano_atual}"

        while continuar and total_coletado_nesta_sessao < 100:
            url = f"https://www.lexml.gov.br/busca/search?keyword={keyword_com_data}&f1-tipoDocumento={tipo_documento}&startDoc={start_doc}"
            print(f"A aceder à página: {url}")
            
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            resultados_da_pagina = soup.find_all('div', class_='docHit')

            if not resultados_da_pagina:
                break

            for item in resultados_da_pagina:
                try:
                    titulo_tag = item.find(lambda tag: tag.name == 'td' and 'Título' in tag.text)
                    urn_tag = item.find(lambda tag: tag.name == 'td' and 'URN' in tag.text)
                    ementa_tag = item.find(lambda tag: tag.name == 'td' and 'Ementa' in tag.text)
                    data_tag = item.find(lambda tag: tag.name == 'td' and 'Data' in tag.text)
                    autoridade_tag = item.find(lambda tag: tag.name == 'td' and 'Autoridade' in tag.text)
                    
                    if not (titulo_tag and urn_tag): continue

                    titulo_final_tag = titulo_tag.find_next_sibling('td').find('a')
                    doc_id = urn_tag.find_next_sibling('td').text.strip()
                    
                    if not (titulo_final_tag and doc_id): continue
                    
                    documento = {
                        "id": doc_id,
                        "titulo": titulo_final_tag.text.strip(),
                        "ementa": ementa_tag.find_next_sibling('td').text.strip().replace('\\n', ' ') if ementa_tag else '',
                        "data": data_tag.find_next_sibling('td').text.strip() if data_tag else '',
                        "autoridade": autoridade_tag.find_next_sibling('td').text.strip().replace('\\n', ' ').replace('\\t', ' ') if autoridade_tag else '',
                        "link": f"https://www.lexml.gov.br{titulo_final_tag['href']}",
                        "fonte": "LexML (Scraper)"
                    }
                    es.index(index=INDEX_NAME, id=doc_id, body=documento)
                    total_coletado_nesta_sessao += 1
                except Exception as e:
                    print(f"    -> Erro ao processar um item, pulando. Erro: {e}")
            
            print(f"    -> Indexados {len(resultados_da_pagina)} documentos. Total nesta sessão: {total_coletado_nesta_sessao}")
            
            link_proxima = soup.find('a', string=lambda text: text and 'Próxima' in text.strip())
            if link_proxima:
                start_doc += 20
                time.sleep(1)
            else:
                continuar = False

        es.indices.refresh(index=INDEX_NAME)
        return redirect(url_for('home', q=termo_de_busca))
    except Exception as e:
        print(f"Ocorreu um erro fatal durante a coleta do LexML: {e}")
        return f"Erro durante a coleta: {e}", 500

def create_index_if_not_exists():
    if not es.indices.exists(index=INDEX_NAME):
        print(f"Índice '{INDEX_NAME}' não encontrado. A criar com o mapeamento correto...")
        es.indices.create(index=INDEX_NAME, body=INDEX_MAPPING, ignore=400)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)