// coletores/lexml_scraper.js - Coletor para LexML em Node.js

const axios = require('axios');
const cheerio = require('cheerio');

async function scrapeLexml(termoDeBusca) {
    console.error("\n--- INICIANDO SCRAPER LEXML (JS) ---");
    const documentos = [];
    try {
        const anoInicial = 2015;
        const anoAtual = new Date().getFullYear();
        const keywordComData = `${termoDeBusca};;year=${anoInicial};year-max=${anoAtual}`;
        let startDoc = 1;
        const maxDocumentos = 20; // Limite para uma busca rápida
        let continuar = true;
        let totalColetado = 0;

        while (continuar && totalColetado < maxDocumentos) {
            const url = `https://www.lexml.gov.br/busca/search?keyword=${encodeURIComponent(keywordComData)}&f1-tipoDocumento=Jurisprudência&startDoc=${startDoc}`;
            console.error(`Buscando em: ${url}`);

            const response = await axios.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
            console.error(`Status da resposta: ${response.status}`);

            const $ = cheerio.load(response.data);
            const resultados = $('div.docHit');
            console.error(`Encontrados ${resultados.length} resultados nesta página.`);

            if (resultados.length === 0) break;

            resultados.each((i, item) => {
                const tituloTd = $(item).find('td:contains("Título")');
                const urnTd = $(item).find('td:contains("URN")');
                if (!tituloTd.length || !urnTd.length) return;

                const docId = urnTd.next('td').text().trim();
                const tituloLinkTag = tituloTd.next('td').find('a');
                if (!docId || !tituloLinkTag.length) return;
                
                const dataTd = $(item).find('td:contains("Data")');
                const autoridadeTd = $(item).find('td:contains("Autoridade")');
                const ementaTd = $(item).find('td:contains("Ementa")');
                
                const documento = {
                    tipo_documento: "jurisprudencia",
                    id: docId,
                    titulo: tituloLinkTag.text().trim(),
                    ementa: ementaTd.length ? ementaTd.next('td').text().trim() : '',
                    data_julgamento: dataTd.length ? dataTd.next('td').text().trim() : '',
                    autoridade: autoridadeTd.length ? autoridadeTd.next('td').text().trim() : '',
                    link: `https://www.lexml.gov.br${tituloLinkTag.attr('href')}`,
                    fonte: "LexML"
                };
                documentos.push(documento);
                totalColetado++;
            });

            const linkProxima = $('a').filter((i, el) => $(el).text().trim() === 'Próxima');
            if (linkProxima.length > 0 && totalColetado < maxDocumentos) {
                startDoc += 20;
                await new Promise(resolve => setTimeout(resolve, 1000));
            } else {
                continuar = false;
            }
        }
        console.error(`--- SCRAPER LEXML (JS) FINALIZADO --- Total coletado: ${totalColetado}`);
        // Imprime o JSON para o stdout, que será capturado pelo Python
        console.log(JSON.stringify(documentos));

    } catch (error) {
        console.error(`Erro GERAL durante importação do LexML (JS): ${error.message}`);
        // Imprime um array vazio em caso de erro
        console.log(JSON.stringify([]));
    }
}

// Executa a função se o script for chamado diretamente
if (require.main === module) {
    const termo = process.argv[2]; // Pega o termo de busca dos argumentos da linha de comando
    if (!termo) {
        console.error("Erro: Nenhum termo de busca fornecido.");
        process.exit(1);
    }
    scrapeLexml(termo);
}