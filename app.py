# app.py - VERSÃO CORRIGIDA COM FILTROS FUNCIONAIS E BUGS RESOLVIDOS
import os
import json
import time
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, url_for
from elasticsearch import Elasticsearch
from math import ceil
from datetime import datetime
import traceback
import pypugjs

# 1. INICIALIZAÇÃO CORRETA DO FLASK
#    template_folder='.' informa ao Flask para procurar o 'interface.pug' no diretório raiz.
app = Flask(__name__, template_folder='.')
app.jinja_env.add_extension('pypugjs.ext.jinja.PyPugJSExtension')

INDEX_NAME = 'jurisprudencia'
RESULTS_PER_PAGE = 10

es = Elasticsearch("http://elasticsearch:9200")

INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "data_julgamento": {
                "type": "date",
                "format": "yyyy-MM-dd||yyyy-MM-dd HH:mm:ss||strict_date_optional_time||epoch_millis",
                "ignore_malformed": True
            },
            "data": {
                "type": "date",
                "format": "yyyy-MM-dd||yyyy-MM-dd HH:mm:ss||strict_date_optional_time||epoch_millis",
                "ignore_malformed": True
            },
            "fonte": {"type": "keyword"},
            "autoridade": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
            "classe": {"type": "keyword"},
            "titulo": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "ementa": {"type": "text"},
            "texto_decisao": {"type": "text"},
            "link": {"type": "keyword"},
            "id": {"type": "keyword"}
        }
    },
    "settings": {
        "index": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        }
    }
}

def create_index_if_not_exists():
    """Cria o índice se não existir"""
    try:
        if not es.indices.exists(index=INDEX_NAME):
            print(f"Índice '{INDEX_NAME}' não encontrado. Criando...")
            # Usando um mapeamento simplificado para evitar problemas,
            # já que seus indexadores .js lidam com a estrutura.
            es.indices.create(index=INDEX_NAME, ignore=400)
            print(f"Índice '{INDEX_NAME}' criado com sucesso.")
        else:
            print(f"Índice '{INDEX_NAME}' já existe.")
    except Exception as e:
        print(f"Erro ao criar índice: {e}")

# 2. FUNÇÃO 'HOME' ROBUSTA
@app.route('/', endpoint='home')
def home():
    """Rota principal com pesquisa e filtros, refatorada para maior robustez."""
    context = {
        'query': request.args.get('q', '').strip(),
        'page': request.args.get('page', 1, type=int),
        'sort_order': request.args.get('sort', 'relevance'),
        'year_min': request.args.get('year_min', ''),
        'year_max': request.args.get('year_max', ''),
        'show_filters': request.args.get('show_filters', 'false'),
        'results': [], 'total': 0, 'current_page': 1, 'total_pages': 0,
        'page_numbers': [], 'is_homepage': False, 'needs_import': False,
        'trigger_scrape': False, 'error': None
    }
    if context['page'] < 1: context['page'] = 1
    context['current_page'] = context['page']

    try:
        if not es.indices.exists(index=INDEX_NAME):
            context['needs_import'] = True
        else:
            from_value = (context['page'] - 1) * RESULTS_PER_PAGE
            filters_for_es = []
            if context['year_min'] and context['year_min'].isdigit():
                filters_for_es.append({"bool": {"should": [{"range": {"data_julgamento": {"gte": f"{context['year_min']}-01-01"}}}, {"range": {"data": {"gte": f"{context['year_min']}-01-01"}}}], "minimum_should_match": 1}})
            if context['year_max'] and context['year_max'].isdigit():
                filters_for_es.append({"bool": {"should": [{"range": {"data_julgamento": {"lte": f"{context['year_max']}-12-31"}}}, {"range": {"data": {"lte": f"{context['year_max']}-12-31"}}}], "minimum_should_match": 1}})

            sort_query = []
            if context['sort_order'] == 'date_desc':
                sort_query = [{"data_julgamento": {"order": "desc", "unmapped_type": "date", "missing": "_last"}}, {"data": {"order": "desc", "unmapped_type": "date", "missing": "_last"}}]
            elif context['sort_order'] == 'date_asc':
                sort_query = [{"data_julgamento": {"order": "asc", "unmapped_type": "date", "missing": "_last"}}, {"data": {"order": "asc", "unmapped_type": "date", "missing": "_last"}}]

            context['is_homepage'] = not context['query'] and not context['year_min'] and not context['year_max'] and context['sort_order'] == 'relevance'

            if context['is_homepage']:
                search_body = {"query": {"match_all": {}}, "from": 0, "size": 3, "sort": [{"data_julgamento": {"order": "desc", "unmapped_type": "date", "missing": "_last"}}, {"data": {"order": "desc", "unmapped_type": "date", "missing": "_last"}}]}
            else:
                search_body = {"from": from_value, "size": RESULTS_PER_PAGE}
                query_clause = {"match_all": {}}
                if context['query']:
                    query_clause = {"multi_match": {"query": context['query'], "fields": ["titulo^2", "ementa^1.5", "texto_decisao", "autoridade"], "type": "best_fields", "operator": "or"}}
                
                search_body["query"] = {"bool": {"must": query_clause, "filter": filters_for_es}}
                
                if sort_query:
                    search_body["sort"] = sort_query

            res = es.search(index=INDEX_NAME, body=search_body)
            
            for hit in res['hits']['hits']:
                doc = hit['_source']
                context['results'].append({
                    'titulo': doc.get('titulo', 'Sem título'), 'link': doc.get('link', '#'),
                    'autoridade': doc.get('autoridade', ''), 'data': doc.get('data', ''),
                    'data_julgamento': doc.get('data_julgamento', ''), 'ementa': doc.get('ementa', ''),
                    'id': doc.get('id', ''), 'fonte': doc.get('fonte', '')
                })
            
            context['total'] = res['hits']['total']['value']
            context['total_pages'] = ceil(context['total'] / RESULTS_PER_PAGE) if not context['is_homepage'] else 0
            if context['page'] > context['total_pages'] and context['total_pages'] > 0:
                context['current_page'] = context['total_pages']
            
            # A chamada para a função que estava faltando
            context['page_numbers'] = get_pagination_range(context['current_page'], context['total_pages'])
            if context['query'] and context['total'] == 0 and not context['is_homepage']:
                context['trigger_scrape'] = True
    
    except Exception as e:
        print(f"Erro na rota de busca: {e}")
        traceback.print_exc()
        context['error'] = f"Ocorreu um erro ao processar a busca: {str(e)}"

    return render_template('interface.pug', **context)

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
        traceback.print_exc()
        return f"Erro durante a coleta: {e}", 500

# 3. A FUNÇÃO AUXILIAR NECESSÁRIA
def get_pagination_range(current_page, total_pages, window=2):
    """Gera lista de páginas para paginação com elipses"""
    if total_pages is None or total_pages <= 1:
        return []
    if total_pages <= 7:
        return list(range(1, total_pages + 1))
    
    pages = [1]
    if current_page > window + 2:
        pages.append('...')
    
    start = max(2, current_page - window)
    end = min(total_pages - 1, current_page + window)
    
    for i in range(start, end + 1):
        if i not in pages:
            pages.append(i)
    
    if current_page < total_pages - (window + 1):
        pages.append('...')
    
    if total_pages not in pages:
        pages.append(total_pages)
    
    return pages

if __name__ == '__main__':
    # Verificar conexão com Elasticsearch
    max_retries = 5
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
            if retry_count < max_retries:
                time.sleep(5)
            else:
                print("Não foi possível conectar ao Elasticsearch. Iniciando aplicação mesmo assim...")
    
    app.run(host='0.0.0.0', port=3000, debug=True)