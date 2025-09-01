# coletores/bnp_scraper.py - Módulo dedicado para o scraping do Pangea BNP

import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def scrape_bnp(termo_de_busca):
    """
    Controla um navegador headless para buscar e extrair precedentes do Pangea BNP.
    """
    print("Iniciando scraper para Pangea BNP...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    try:
        # Usa webdriver-manager para instalar e gerenciar o driver do Chrome automaticamente
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
    except Exception as e:
        print(f"ERRO CRÍTICO: Não foi possível iniciar o WebDriver do Chrome. Verifique a instalação. Erro: {e}")
        return []

    documentos = []
    try:
        url = f"https://pangeabnp.pdpj.jus.br/precedentes?q={termo_de_busca}"
        driver.get(url)

        # Espera o JavaScript carregar. 10 segundos é um tempo de espera generoso.
        print("Aguardando o carregamento dinâmico da página...")
        time.sleep(10) 

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        resultados = soup.find_all('app-card-precedente-item')
        print(f"Encontrados {len(resultados)} resultados na página.")

        for item in resultados:
            try:
                titulo_tag = item.find('h5', class_='card-title')
                link_tag = item.find('a', class_='card-title-link')

                if not (titulo_tag and link_tag):
                    continue

                titulo = titulo_tag.get_text(strip=True)
                link = link_tag['href']

                detalhes = {}
                for dl_item in item.find_all('dl'):
                    dt_tag = dl_item.find('dt')
                    dd_tag = dl_item.find('dd')
                    if dt_tag and dd_tag:
                        detalhes[dt_tag.get_text(strip=True)] = dd_tag.get_text(strip=True)
                
                ementa_tag = item.find('p', class_='card-text')
                ementa = ementa_tag.get_text(strip=True) if ementa_tag else ''

                original_date_str = detalhes.get('Data de Julgamento:', '')
                numero_unico = detalhes.get('Número Único:', '')
                doc_id = f"BNP-{numero_unico}" if numero_unico else f"BNP-{hash(titulo)}"

                documento = {
                    "tipo_documento": "precedente",
                    "id": doc_id,
                    "titulo": titulo,
                    "link": f"https://pangeabnp.pdpj.jus.br{link}",
                    "fonte": "Pangea BNP",
                    "data_julgamento": original_date_str,
                    "orgaoJulgador": detalhes.get('Órgão Julgador:', ''),
                    "ramoDireito": detalhes.get('Ramo do Direito:', ''),
                    "numeroUnico": numero_unico,
                    "assuntos": detalhes.get('Assuntos:', ''),
                    "ementa": ementa
                }
                documentos.append(documento)
            except Exception as e:
                print(f"Erro ao processar um item individual do BNP: {e}")
    
    except Exception as e:
        print(f"Erro geral durante o scraping do BNP: {e}")
    finally:
        driver.quit()
    
    print(f"Scraping do BNP finalizado. Total de documentos coletados: {len(documentos)}")
    return documentos
