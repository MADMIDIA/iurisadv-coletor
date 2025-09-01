// coletores/json_file_importer.js

const fs = require('fs');
const path = require('path');
const { Client } = require('@elastic/elasticsearch');

// Conecta ao Elasticsearch usando o nome do serviço do Docker
const client = new Client({ node: 'http://elasticsearch:9200' });

async function importarDadosDeArquivo() {
    console.log('Iniciando o importador de arquivo JSON...');
    try {
        // Caminho para o arquivo JSON que vamos usar.
        // Este caminho é relativo à raiz do projeto, de dentro do contêiner.
        const filePath = path.join(__dirname, '..', 'jonas-elias', 'jurisprudencia-sc-processamento', 'summarization-dataset', 'export_dataset_jurisprudencias.zip', 'export_1000_SAUDE_ID_1_1000.json');

        console.log(`Lendo o arquivo: ${filePath}`);
        
        // Lê o conteúdo do arquivo
        const fileContent = fs.readFileSync(filePath, 'utf8');
        // Converte o texto do arquivo (que é um JSON) em um objeto JavaScript
        const jurisprudencias = JSON.parse(fileContent);

        console.log(`Encontrados ${jurisprudencias.length} registros no arquivo.`);

        // Garante que o índice 'jurisprudencia' exista no Elasticsearch
        await client.indices.create({
            index: 'jurisprudencia'
        }, { ignore: [400] }); // Ignora o erro se o índice já existir

        for (const doc of jurisprudencias) {
            // Monta o nosso documento com os campos que nos interessam
            const documentoParaIndexar = {
                id: doc.PROCESSO, // Usando o número do processo como ID
                classe: doc.CLASSE,
                assunto: doc.ASSUNTO,
                magistrado: doc.MAGISTRADO,
                comarca: doc.COMARCA,
                data_julgamento: doc.DATA_JULGAMENTO,
                ementa: doc.EMENTA,
                texto_decisao: doc.TEXTO_DECISAO,
                fonte: 'TJSC (Arquivo JSON)'
            };

            // Indexa o documento no Elasticsearch
            await client.index({
                index: 'jurisprudencia',
                id: documentoParaIndexar.id,
                body: documentoParaIndexar
            });
            console.log(`Documento ${documentoParaIndexar.id} indexado com sucesso.`);
        }
        
        console.log('Importação do arquivo JSON finalizada com sucesso!');

    } catch (error) {
        console.error('Ocorreu um erro fatal durante a importação:', error);
    }
}

importarDadosDeArquivo();