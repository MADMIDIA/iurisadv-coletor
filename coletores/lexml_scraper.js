// coletores/lexml_scraper.js - VERSÃO COM PAGINAÇÃO

const fetch = require('node-fetch');
const cheerio = require('cheerio');
const { Client } = require('@elastic/elasticsearch');

const client = new Client({ node: 'http://elasticsearch:9200' });

// --- NOVA FUNÇÃO: Pausa para sermos educados com o servidor ---
// Esta função espera um número de milissegundos antes de continuar.
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function rasparLexML() {
    console.log('Iniciando o scraper do LexML com paginação...');
    try {
        const termoDeBusca = 'dano moral in re ipsa';
        const tipoDocumento = 'Jurisprudência';
        let startDoc = 1; // Começamos na primeira página
        let continuar = true;
        let totalColetado = 0;

        // Garante que o índice exista antes de começar o loop
        await client.indices.create({ index: 'jurisprudencia' }, { ignore: [400] });

        // --- O LOOP DE PAGINAÇÃO ---
        while (continuar) {
            const url = `https://www.lexml.gov.br/busca/search?keyword=${encodeURIComponent(termoDeBusca)}&f1-tipoDocumento=${encodeURIComponent(tipoDocumento)}&startDoc=${startDoc}`;
            
            console.log(`Acessando página com startDoc=${startDoc}... URL: ${url}`);

            const response = await fetch(url, {
                headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36' }
            });

            if (!response.ok) {
                console.log(`Erro ao buscar a página ${startDoc}. Parando.`);
                break;
            }

            const html = await response.text();
            const $ = cheerio.load(html);

            const resultadosDaPagina = [];
            $('div.docHit').each((index, element) => {
                const item = $(element);
                const titulo = item.find('td:contains("Título")').next('td.col3').find('a').text().trim();
                const link = item.find('td:contains("Título")').next('td.col3').find('a').attr('href');
                const data = item.find('td:contains("Data")').next('td.col3').text().trim();
                const ementa = item.find('td:contains("Ementa")').next('td.col3').text().trim().replace(/\s+/g, ' ');
                const urn = item.find('td:contains("URN")').next('td.col3').text().trim();

                if (urn && titulo) {
                    resultadosDaPagina.push({
                        id: urn,
                        titulo: titulo,
                        data: data,
                        ementa: ementa,
                        link: `https://www.lexml.gov.br${link}`,
                        fonte: 'LexML (Scraper)'
                    });
                }
            });

            if (resultadosDaPagina.length === 0) {
                console.log('Nenhum resultado encontrado nesta página. Finalizando a coleta.');
                continuar = false;
            } else {
                for (const doc of resultadosDaPagina) {
                    await client.index({
                        index: 'jurisprudencia',
                        id: doc.id,
                        body: doc
                    });
                }
                totalColetado += resultadosDaPagina.length;
                console.log(`    -> Indexados ${resultadosDaPagina.length} documentos desta página. Total: ${totalColetado}`);
                
                // --- VERIFICA SE HÁ UMA PRÓXIMA PÁGINA ---
                const linkProxima = $('a').filter((i, el) => $(el).text().trim() === 'Próxima').first();
                if (linkProxima.length > 0) {
                    startDoc += 20; // Prepara para a próxima iteração
                    await sleep(1000); // Espera 1 segundo antes de buscar a próxima página
                } else {
                    console.log('Fim dos resultados. Não há mais link "Próxima".');
                    continuar = false;
                }
            }
        }
        
        console.log('--- VITÓRIA COMPLETA! ---');
        console.log(`Scraping e indexação de todas as páginas finalizados. Total de ${totalColetado} documentos coletados.`);

    } catch (error) {
        console.error('Ocorreu um erro fatal durante o scraping:', error);
    }
}

rasparLexML();