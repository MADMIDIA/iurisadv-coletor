// coletores/importar_json.js - VERSÃO FINAL COM O CAMINHO CORRETO

const fs = require('fs');
const path = require('path');
const { Client } = require('@elastic/elasticsearch');

const client = new Client({ node: 'http://elasticsearch:9200' });

async function importarDadosDeArquivo() {
    console.log('Iniciando o importador de arquivo JSON...');
    try {
        // --- CORREÇÃO FINALÍSSIMA: Aponta para a pasta 'data' na raiz do projeto ---
        const filePath = path.resolve(__dirname, '..', 'data', 'jurisprudencias.json');

        console.log(`Lendo o arquivo de dados: ${filePath}`);

        if (!fs.existsSync(filePath)) {
            // Mensagem de erro clara caso o arquivo não seja encontrado
            throw new Error(`Arquivo não encontrado! Certifique-se de que o arquivo "jurisprudencias.json" que você baixou está dentro de uma pasta "data" na raiz do projeto.`);
        }
        
        const fileContent = fs.readFileSync(filePath, 'utf8');
        const jurisprudencias = JSON.parse(fileContent);

        console.log(`Encontrados ${jurisprudencias.length} registros no arquivo.`);

        // Garante que o índice (a "tabela") exista no Elasticsearch
        await client.indices.create({ index: 'jurisprudencia' }, { ignore: [400] });

        for (const doc of jurisprudencias) {
            // Adapta a estrutura dos dados do arquivo para o nosso banco de dados
            const documentoParaIndexar = {
                id: doc.numero_processo,
                classe: doc.classe,
                assunto: doc.assunto,
                magistrado: doc.magistrado,
                comarca: doc.comarca,
                data_julgamento: doc.data_julgamento,
                ementa: doc.ementa,
                texto_decisao: doc.inteiro_teor, // O campo se chama 'inteiro_teor' neste arquivo
                fonte: 'TJSC (Arquivo JSON)'
            };

            if (!documentoParaIndexar.id) {
                console.warn('Documento sem número de processo foi encontrado e será pulado.');
                continue;
            }

            await client.index({
                index: 'jurisprudencia',
                id: documentoParaIndexar.id,
                body: documentoParaIndexar
            });
            console.log(`Documento ${documentoParaIndexar.id} indexado com sucesso.`);
        }
        
        console.log('--- VITÓRIA! ---');
        console.log('Importação do arquivo JSON finalizada com sucesso.');

    } catch (error) {
        console.error('Ocorreu um erro fatal durante a importação:', error);
    }
}

importarDadosDeArquivo();