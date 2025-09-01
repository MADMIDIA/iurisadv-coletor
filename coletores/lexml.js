// coletores/lexml.js - VERSÃO FINAL COM A QUERY CQL CORRETA

const fetch = require('node-fetch');
const { XMLParser } = require('fast-xml-parser');
const { Client } = require('@elastic/elasticsearch');

const client = new Client({ node: 'http://elasticsearch:9200' });

async function buscarEIndexarLexML() {
    console.log('Iniciando o coletor do LexML...');
    try {
        const termoDeBusca = 'marco civil da internet';
        
        // --- CORREÇÃO FINALÍSSIMA: Monta a query usando a sintaxe CQL ---
        const queryCQL = `cql.anywhere="${termoDeBusca}"`;
        const url = `http://www.lexml.gov.br/sru/rede?operation=searchRetrieve&query=${encodeURIComponent(queryCQL)}`;

        console.log(`Buscando com a query CQL correta: ${url}`);

        const response = await fetch(url, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        });

        if (!response.ok) {
            throw new Error(`Erro na requisição HTTP: ${response.statusText}`);
        }

        const xmlData = await response.text();
        const parser = new XMLParser({ ignoreAttributes: false });
        const jsonData = parser.parse(xmlData);
        
        const records = jsonData['searchRetrieveResponse']?.records?.record || [];
        
        if (records.length === 0) {
            console.log('Nenhum registro encontrado em formato XML. A API pode ter retornado uma página HTML ou nenhum resultado para a busca.');
            console.log('Resposta completa recebida:', JSON.stringify(jsonData, null, 2));
            return;
        }

        console.log(`Encontrados ${records.length} registros.`);

        const recordsArray = Array.isArray(records) ? records : [records];

        for (const record of recordsArray) {
            const recordData = record.recordData;
            if (!recordData || !recordData.urn) continue;

            const documento = {
                id: recordData.urn,
                titulo: recordData.titulo,
                subtitulo: recordData.subtitulo,
                tipo: recordData.tipo,
                data: recordData.data,
                fonte: 'LexML'
            };

            await client.index({
                index: 'jurisprudencia',
                id: documento.id,
                body: documento
            });
            console.log(`Documento ${documento.id} indexado com sucesso.`);
        }
        console.log('Coleta do LexML finalizada com sucesso!');

    } catch (error) {
        console.error('Ocorreu um erro fatal durante a coleta:', error);
    }
}

buscarEIndexarLexML();