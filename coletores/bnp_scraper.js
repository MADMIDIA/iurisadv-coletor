// coletores/bnp_scraper.js - Coletor para Pangea BNP em Node.js com Selenium

const { Builder, By, until } = require('selenium-webdriver');
const chrome = require('selenium-webdriver/chrome');
const cheerio = require('cheerio');

async function scrapeBnp(termoDeBusca) {
    console.error("\n--- INICIANDO SCRAPER PANGEA BNP (JS) ---");
    
    const options = new chrome.Options();
    options.addArguments('--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu');
    options.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36');

    let driver;
    try {
        driver = await new Builder()
            .forBrowser('chrome')
            .setChromeOptions(options)
            .build();

        const url = `https://pangeabnp.pdpj.jus.br/precedentes?q=${encodeURIComponent(termoDeBusca)}`;
        console.error(`Acessando: ${url}`);
        await driver.get(url);

        console.error("Aguardando o carregamento dinâmico dos resultados...");
        await driver.wait(until.elementLocated(By.tagName("app-card-precedente-item")), 30000);
        console.error("Página carregada, iniciando extração.");
        
        const pageSource = await driver.getPageSource();
        const $ = cheerio.load(pageSource);

        const resultados = $('app-card-precedente-item');
        console.error(`Encontrados ${resultados.length} resultados na página.`);
        const documentos = [];

        resultados.each((i, item) => {
            const tituloTag = $(item).find('h5.card-title');
            const linkTag = $(item).find('a.card-title-link');
            if (!tituloTag.length || !linkTag.length) return;

            const detalhes = {};
            $(item).find('dl').each((idx, dl) => {
                const dt = $(dl).find('dt').text().trim();
                const dd = $(dl).find('dd').text().trim();
                if (dt && dd) detalhes[dt] = dd;
            });
            
            const ementa = $(item).find('p.card-text').text().trim() || '';
            const numeroUnico = detalhes['Número Único:'] || '';
            const titulo = tituloTag.text().trim();

            const documento = {
                tipo_documento: "precedente",
                id: numeroUnico ? `BNP-${numeroUnico}` : `BNP-${Buffer.from(titulo).toString('hex')}`,
                titulo: titulo,
                link: `https://pangeabnp.pdpj.jus.br${linkTag.attr('href')}`,
                fonte: "Pangea BNP",
                data_julgamento: detalhes['Data de Julgamento:'] || '',
                orgaoJulgador: detalhes['Órgão Julgador:'] || '',
                ramoDireito: detalhes['Ramo do Direito:'] || '',
                numeroUnico: numeroUnico,
                assuntos: detalhes['Assuntos:'] || '',
                ementa: ementa
            };
            documentos.push(documento);
        });

        console.error(`--- SCRAPER BNP (JS) FINALIZADO --- Total coletado: ${documentos.length}`);
        console.log(JSON.stringify(documentos));

    } catch (error) {
        console.error(`ERRO CRÍTICO no scraper do BNP (JS): ${error.message}`);
        console.log(JSON.stringify([]));
    } finally {
        if (driver) {
            await driver.quit();
            console.error("Navegador Selenium finalizado.");
        }
    }
}

if (require.main === module) {
    const termo = process.argv[2];
    if (!termo) {
        console.error("Erro: Nenhum termo de busca fornecido.");
        process.exit(1);
    }
    scrapeBnp(termo);
}