# coletores/bnp_scraper.py - Módulo para o scraper do Pangea BNP com Selenium em Python

import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import traceback

def scrape_bnp(termo_de_busca):
    """
    Controla um navegador headless para buscar e extrair precedentes do Pangea BNP.
    """
    print("\n--- INICIANDO SCRAPER PANGEA BNP (Python/Selenium) ---")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/5.37.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    driver = None
    try:
        # O chromedriver está no PATH do sistema, o Selenium o encontrará.
        driver = webdriver.Chrome(options=chrome_options)
        documentos = []
        url = f"https://pangeabnp.pdpj.jus.br/precedentes?q={termo_de_busca}"
        print(f"Acessando: {url}")
        driver.get(url)

        print("Aguardando o carregamento dinâmico dos resultados...")
        # Espera explícita para garantir que os resultados carreguem
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "app-card-precedente-item"))
        )
        print("Página carregada, iniciando extração.")

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        resultados = soup.find_all('app-card-precedente-item')
        print(f"Encontrados {len(resultados)} resultados na página.")

        for item in resultados:
            try:
                titulo_tag = item.find('h5', class_='card-title')
                link_tag = item.find('a', class_='card-title-link')
                if not (titulo_tag and link_tag): continue

                titulo = titulo_tag.get_text(strip=True)
                link = link_tag['href']

                detalhes = {
                    dl.find('dt').get_text(strip=True): dl.find('dd').get_text(strip=True)
                    for dl in item.find_all('dl') if dl.find('dt') and dl.find('dd')
                }
                
                ementa_tag = item.find('p', class_='card-text')
                ementa = ementa_tag.get_text(strip=True) if ementa_tag else ''
                original_date_str = detalhes.get('Data de Julgamento:', '')
                numero_unico = detalhes.get('Número Único:', '')
                doc_id = f"BNP-{numero_unico}" if numero_unico else f"BNP-{hash(titulo)}"

                documento = {
                    "tipo_documento": "precedente", "id": doc_id, "titulo": titulo,
                    "link": f"https://pangeabnp.pdpj.jus.br{link}", "fonte": "Pangea BNP",
                    "data_julgamento": original_date_str,
                    "orgaoJulgador": detalhes.get('Órgão Julgador:', ''),
                    "ramoDireito": detalhes.get('Ramo do Direito:', ''),
                    "numeroUnico": numero_unico, "assuntos": detalhes.get('Assuntos:', ''), "ementa": ementa
                }
                documentos.append(documento)
            except Exception as e:
                print(f"Erro ao processar um item individual do BNP: {e}")
        
        print(f"--- SCRAPER BNP FINALIZADO --- Total coletado: {len(documentos)}")
        return documentos
    
    except Exception as e:
        print(f"ERRO CRÍTICO no scraper do BNP: {e}")
        traceback.print_exc()
        return []
    finally:
        if driver:
            driver.quit()
            print("Navegador Selenium finalizado.")

