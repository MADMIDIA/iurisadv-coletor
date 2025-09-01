# app.py - VERSÃO CORRIGIDA COM FILTROS FUNCIONAIS E BUGS RESOLVIDOS

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
    """Cria o índice se não existir"""
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
      .search-bar button:hover { background-color: #2980b9; }
      .advanced-search-toggle { text-align: right; max-width: 800px; margin: 1em auto; }
      .advanced-search-toggle label { cursor: pointer; user-select: none; color: #3498db; }
      #toggle-filters { margin-right: 5px; }
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
      .result-item dt { font-weight: bold; color: #566573; float: left; width: 90px; clear: left; }
      .result-item dd { margin-left: 100px; margin-bottom: 0.5em; }
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
            <h2>Filtros Avançados</h2>
            <form action="/" method="GET" id="filters-form">
                <input type="hidden" name="q" value="{{ query }}">
                <input type="hidden" name="show_filters" value="true">
                <div class="filter-grid">
                    <div class="form-group">
                        <label for="sort">Ordenar por</label>
                        <select name="sort" id="sort">
                            <option value="relevance" {{ 'selected' if sort_order == 'relevance' else '' }}>Relevância</option>
                            <option value="date_desc" {{ 'selected' if sort_order == 'date_desc' else '' }}>Mais Recentes</option>
                            <option value="date_asc" {{ 'selected' if sort_order == 'date_asc' else '' }}>Mais Antigos</option>
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
                {% elif total is defined and total is not none %}
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

                {% if total_pages and total_pages > 1 %}
                <div class="pagination">
                    <a href="{{ url_for('home', q=query, page=1, sort=sort_order, year_min=year_min, year_max=year_max, show_filters=show_filters) }}">&laquo;</a>
                    {% for page_num in page_numbers %}
                        {% if page_num == '...' %}
                            <span class="dots">...</span>
                        {% elif page_num == current_page %}
                            <span class="current">{{ page_num }}</span>
                        {% else %}
                            <a href="{{ url_for('home', q=query, page=page_num, sort=sort_order, year_min=year_min, year_max=year_max, show_filters=show_filters) }}">{{ page_num }}</a>
                        {% endif %}
                    {% endfor %}
                    <a href="{{ url_for('home', q=query, page=total_pages, sort=sort_order, year_min=year_min, year_max=year_max, show_filters=show_filters) }}">&raquo;</a>
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

@app.route('/')
def home():
    """Rota principal com pesquisa e filtros"""
    try:
        # Captura dos parâmetros
        query = request.args.get('q', '').strip()
        page = request.args.get('page', 1, type=int)
        sort_order = request.args.get('sort', 'relevance')
        year_min = request.args.get('year_min', '')
        year_max = request.args.get('year_max', '')
        show_filters = request.args.get('show_filters', 'false')
        
        # Validação da página
        if page < 1:
            page = 1
            
        from_value = (page - 1) * RESULTS_PER_PAGE

        # Verificar se o índice existe
        if not es.indices.exists(index=INDEX_NAME):
            return render_template_string(
                INTERFACE_TEMPLATE, 
                needs_import=True, 
                query=query,
                sort_order=sort_order,
                year_min=year_min,
                year_max=year_max,
                show_filters=show_filters,
                results=[],
                page_numbers=[],
                current_page=1,
                total_pages=0,
                total=0,
                is_homepage=False,
                error=None,
                trigger_scrape=False
            )

        # Construir filtros do Elasticsearch
        filters_for_es = []
        
        # Filtro de ano mínimo
        if year_min and year_min.isdigit():
            filters_for_es.append({
                "range": {
                    "data_julgamento": {"gte": f"{year_min}-01-01"}
                }
            })
        
        # Filtro de ano máximo
        if year_max and year_max.isdigit():
            filters_for_es.append({
                "range": {
                    "data_julgamento": {"lte": f"{year_max}-12-31"}
                }
            })

        # Configurar ordenação
        sort_query = []
        if sort_order == 'date_desc':
            sort_query = [{"data_julgamento": {"order": "desc", "unmapped_type": "date"}}]
        elif sort_order == 'date_asc':
            sort_query = [{"data_julgamento": {"order": "asc", "unmapped_type": "date"}}]
        
        # Determinar se é homepage
        is_homepage = not query and not year_min and not year_max and sort_order == 'relevance'
        
        # Construir query de busca
        if is_homepage:
            # Homepage: mostrar 3 jurisprudências mais recentes
            search_body = {
                "query": {"match_all": {}},
                "from": 0,
                "size": 3,
                "sort": [{"data_julgamento": {"order": "desc", "unmapped_type": "date"}}]
            }
        else:
            # Busca com query e/ou filtros
            must_query = []
            if query:
                must_query.append({
                    "multi_match": {
                        "query": query,
                        "fields": ["titulo^2", "ementa^1.5", "texto_decisao", "autoridade"],
                        "type": "best_fields"
                    }
                })
            
            # Se não houver query mas houver filtros, usar match_all
            if not must_query and filters_for_es:
                must_query.append({"match_all": {}})
            
            search_body = {
                "from": from_value,
                "size": RESULTS_PER_PAGE
            }
            
            if must_query or filters_for_es:
                search_body["query"] = {
                    "bool": {
                        "must": must_query if must_query else [{"match_all": {}}],
                        "filter": filters_for_es
                    }
                }
            else:
                search_body["query"] = {"match_all": {}}
            
            if sort_query:
                search_body["sort"] = sort_query

        # Executar busca
        res = es.search(index=INDEX_NAME, body=search_body)
        
        # Processar resultados
        results = []
        for hit in res['hits']['hits']:
            doc = hit['_source']
            # Garantir que todos os campos existam
            result = {
                'titulo': doc.get('titulo', 'Sem título'),
                'link': doc.get('link', '#'),
                'autoridade': doc.get('autoridade', ''),
                'data': doc.get('data', ''),
                'data_julgamento': doc.get('data_julgamento', ''),
                'ementa': doc.get('ementa', ''),
                'id': doc.get('id', ''),
                'fonte': doc.get('fonte', '')
            }
            results.append(result)
        
        total = res['hits']['total']['value']
        total_pages = ceil(total / RESULTS_PER_PAGE) if not is_homepage else 0
        
        # Gerar números de paginação
        page_numbers = get_pagination_range(page, total_pages) if total_pages > 1 else []
        
        # Verificar se deve mostrar opção de scraping
        trigger_scrape = False
        if query and total == 0 and not is_homepage:
            trigger_scrape = True

        # Renderizar template com todas as variáveis necessárias
        return render_template_string(
            INTERFACE_TEMPLATE,
            query=query,
            results=results,
            total=total,
            current_page=page,
            total_pages=total_pages,
            sort_order=sort_order,
            year_min=year_min,
            year_max=year_max,
            show_filters=show_filters,
            is_homepage=is_homepage,
            page_numbers=page_numbers,
            needs_import=False,
            error=None,
            trigger_scrape=trigger_scrape
        )

    except Exception as e:
        print(f"Erro na rota de busca: {e}")
        import traceback
        traceback.print_exc()
        
        return render_template_string(
            INTERFACE_TEMPLATE,
            query=request.args.get('q', ''),
            results=[],
            total=0,
            current_page=1,
            total_pages=0,
            sort_order='relevance',
            year_min='',
            year_max='',
            show_filters='false',
            is_homepage=False,
            page_numbers=[],
            needs_import=False,
            error=f"Ocorreu um erro ao comunicar com o banco de dados: {str(e)}",
            trigger_scrape=False
        )

def get_pagination_range(current_page, total_pages, window=2):
    """Gera lista de páginas para paginação com elipses"""
    if total_pages <= 7:
        return list(range(1, total_pages + 1))
    
    pages = []
    
    # Sempre mostrar primeira página
    pages.append(1)
    
    # Adicionar elipse se necessário
    if current_page > window + 2:
        pages.append('...')
    
    # Páginas ao redor da atual
    start = max(2, current_page - window)
    end = min(total_pages - 1, current_page + window)
    
    for i in range(start, end + 1):
        if i not in pages:
            pages.append(i)
    
    # Adicionar elipse se necessário
    if current_page < total_pages - (window + 1):
        pages.append('...')
    
    # Sempre mostrar última página
    if total_pages not in pages:
        pages.append(total_pages)
    
    return pages

@app.route('/import-json')
def import_data_from_json():
    """Importa dados do arquivo JSON local"""
    try:
        create_index_if_not_exists()
        
        filepath = os.path.join('data', 'jurisprudencias.json')
        
        if not os.path.exists(filepath):
            return "Arquivo jurisprudencias.json não encontrado no diretório data/", 404
        
        with open(filepath, 'r', encoding='utf-8') as f:
            jurisprudencias = json.load(f)
        
        count = 0
        for doc in jurisprudencias:
            doc_id = doc.get("numero_processo")
            if not doc_id:
                continue
            
            # Preparar documento para indexação
            doc_to_index = {
                "id": doc_id,
                "titulo": doc.get("classe", "") + " - " + doc.get("assunto", ""),
                "classe": doc.get("classe"),
                "assunto": doc.get("assunto"),
                "magistrado": doc.get("magistrado"),
                "comarca": doc.get("comarca"),
                "data_julgamento": doc.get("data_julgamento"),
                "ementa": doc.get("ementa"),
                "texto_decisao": doc.get("inteiro_teor"),
                "fonte": "TJSC (Arquivo JSON)",
                "link": "#",
                "autoridade": doc.get("magistrado", "")
            }
            
            es.index(index=INDEX_NAME, id=doc_id, body=doc_to_index)
            count += 1
        
        es.indices.refresh(index=INDEX_NAME)
        print(f"Importados {count} documentos do arquivo JSON")
        
        return redirect(url_for('home'))
        
    except Exception as e:
        print(f"Erro ao importar JSON: {e}")
        import traceback
        traceback.print_exc()
        return f"Erro ao importar JSON: {e}", 500

@app.route('/importar-lexml')
def importar_lexml():
    """Importa dados do LexML via scraping"""
    termo_de_busca = request.args.get('q')
    if not termo_de_busca:
        return "Erro: Nenhum termo de busca fornecido.", 400
    
    try:
        create_index_if_not_exists()
        
        tipo_documento = 'Jurisprudência'
        start_doc = 1
        continuar = True
        total_coletado = 0
        max_documentos = 100
        
        # Buscar documentos de 2015 até hoje
        ano_inicial = 2015
        ano_atual = datetime.now().year
        keyword_com_data = f"{termo_de_busca};;year={ano_inicial};year-max={ano_atual}"

        while continuar and total_coletado < max_documentos:
            url = f"https://www.lexml.gov.br/busca/search?keyword={keyword_com_data}&f1-tipoDocumento={tipo_documento}&startDoc={start_doc}"
            print(f"Acessando página: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            resultados = soup.find_all('div', class_='docHit')

            if not resultados:
                print("Nenhum resultado encontrado nesta página")
                break

            for item in resultados:
                try:
                    # Extrair informações
                    titulo_tag = item.find(lambda tag: tag.name == 'td' and 'Título' in tag.text)
                    urn_tag = item.find(lambda tag: tag.name == 'td' and 'URN' in tag.text)
                    ementa_tag = item.find(lambda tag: tag.name == 'td' and 'Ementa' in tag.text)
                    data_tag = item.find(lambda tag: tag.name == 'td' and 'Data' in tag.text)
                    autoridade_tag = item.find(lambda tag: tag.name == 'td' and 'Autoridade' in tag.text)
                    
                    if not (titulo_tag and urn_tag):
                        continue

                    titulo_link = titulo_tag.find_next_sibling('td').find('a')
                    doc_id = urn_tag.find_next_sibling('td').text.strip()
                    
                    if not (titulo_link and doc_id):
                        continue
                    
                    # Preparar documento
                    documento = {
                        "id": doc_id,
                        "titulo": titulo_link.text.strip(),
                        "ementa": ementa_tag.find_next_sibling('td').text.strip() if ementa_tag else '',
                        "data": data_tag.find_next_sibling('td').text.strip() if data_tag else '',
                        "data_julgamento": data_tag.find_next_sibling('td').text.strip() if data_tag else '',
                        "autoridade": autoridade_tag.find_next_sibling('td').text.strip() if autoridade_tag else '',
                        "link": f"https://www.lexml.gov.br{titulo_link['href']}",
                        "fonte": "LexML",
                        "texto_decisao": "",
                        "classe": "",
                        "assunto": ""
                    }
                    
                    # Indexar no Elasticsearch
                    es.index(index=INDEX_NAME, id=doc_id, body=documento)
                    total_coletado += 1
                    
                except Exception as e:
                    print(f"Erro ao processar item: {e}")
                    continue
            
            print(f"Indexados {len(resultados)} documentos. Total: {total_coletado}")
            
            # Verificar próxima página
            link_proxima = soup.find('a', string=lambda text: text and 'Próxima' in text.strip())
            if link_proxima and total_coletado < max_documentos:
                start_doc += 20
                time.sleep(1)  # Delay para não sobrecarregar o servidor
            else:
                continuar = False

        es.indices.refresh(index=INDEX_NAME)
        print(f"Total de documentos importados: {total_coletado}")
        
        return redirect(url_for('home', q=termo_de_busca))
        
    except Exception as e:
        print(f"Erro durante importação do LexML: {e}")
        import traceback
        traceback.print_exc()
        return f"Erro durante a coleta: {e}", 500

if __name__ == '__main__':
    # Criar índice ao iniciar a aplicação
    try:
        create_index_if_not_exists()
    except Exception as e:
        print(f"Erro ao criar índice na inicialização: {e}")
    
    app.run(host='0.0.0.0', port=3000, debug=True)