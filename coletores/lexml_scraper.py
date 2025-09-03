# coletores/lexml_scraper.py - Módulo para o scraper do LexML

import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import traceback

def scrape_lexml(termo_de_busca):
    """
    Raspa dados de jurisprudência do LexML.
    Esta lógica foi resgatada do seu app_py_fixed.py original e funcional.
    """
    print("\n--- INICIANDO SCRAPER LEXML (Python) ---")
    documentos = []
    try:
        total_coletado = 0
        ano_inicial, ano_atual = 2015, datetime.now().year
        keyword_com_data = f"{termo_de_busca};;year={ano_inicial};year-max={ano_atual}"
        start_doc = 1
        max_documentos = 20 # Limite para uma busca rápida
        continuar = True

        while continuar and total_coletado < max_documentos:
            url = f"https://www.lexml.gov.br/busca/search?keyword={keyword_com_data}&f1-tipoDocumento=Jurisprudência&startDoc={start_doc}"
            print(f"Buscando em: {url}")
            
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=30)
            print(f"Status da resposta: {response.status_code}")
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            resultados = soup.find_all('div', class_='docHit')
            print(f"Encontrados {len(resultados)} resultados nesta página.")
            
            if not resultados:
                break

            for item in resultados:
                try:
                    titulo_tag = item.find(lambda t: t.name == 'td' and 'Título' in t.text)
                    urn_tag = item.find(lambda t: t.name == 'td' and 'URN' in t.text)
                    if not (titulo_tag and urn_tag): continue
                    
                    doc_id = urn_tag.find_next_sibling('td').text.strip()
                    titulo_link_tag = titulo_tag.find_next_sibling('td').find('a')
                    if not (doc_id and titulo_link_tag): continue
                    
                    data_tag = item.find(lambda t: t.name == 'td' and 'Data' in t.text)
                    autoridade_tag = item.find(lambda t: t.name == 'td' and 'Autoridade' in t.text)
                    ementa_tag = item.find(lambda t: t.name == 'td' and 'Ementa' in t.text)
                    
                    original_date_str = data_tag.find_next_sibling('td').text.strip() if data_tag else ''
                    
                    documento = {
                        "tipo_documento": "jurisprudencia",
                        "id": doc_id,
                        "titulo": titulo_link_tag.text.strip(),
                        "ementa": ementa_tag.find_next_sibling('td').text.strip() if ementa_tag else '',
                        "data_julgamento": original_date_str,
                        "autoridade": autoridade_tag.find_next_sibling('td').text.strip() if autoridade_tag else '',
                        "link": f"https://www.lexml.gov.br{titulo_link_tag['href']}",
                        "fonte": "LexML"
                    }
                    documentos.append(documento)
                    total_coletado += 1
                except Exception as e:
                    print(f"Erro ao processar item do LexML: {e}")

            link_proxima = soup.find('a', string=lambda text: text and 'Próxima' in text.strip())
            if link_proxima and total_coletado < max_documentos:
                start_doc += 20
                time.sleep(1)
            else:
                continuar = False
        
        print(f"--- SCRAPER LEXML FINALIZADO --- Total coletado: {total_coletado}")
        return documentos
    except Exception as e:
        print(f"Erro GERAL durante importação do LexML: {e}")
        traceback.print_exc()
        return []

