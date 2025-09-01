// server.js - VERSÃO FINAL E AUTOSSUFICIENTE

const express = require('express');
const { Client } = require('@elastic/elasticsearch');
const path = require('path');
const fs = require('fs');

const app = express();
const client = new Client({ node: 'http://elasticsearch:9200' });
const port = 3000;
const INDEX_NAME = 'jurisprudencia';

app.set('views', path.join(__dirname));
app.set('view engine', 'pug');

// ROTA PRINCIPAL: Exibe a página de busca
app.get('/', async (req, res) => {
  const query = req.query.q || '';
  try {
    const indexExists = await client.indices.exists({ index: INDEX_NAME });

    if (!indexExists.body) {
      return res.render('interface', {
        query: query,
        results: [],
        total: 0,
        error: `O banco de dados está vazio.`,
        needs_import: true // Variável para mostrar o botão de importação
      });
    }

    const searchBody = {
      index: INDEX_NAME,
      body: { from: 0, size: 100, query: {} }
    };

    if (query) {
      searchBody.body.query = { multi_match: { query: query, fields: ['titulo', 'ementa', 'texto_decisao'] } };
    } else {
      searchBody.body.query = { match_all: {} };
    }

    const { body } = await client.search(searchBody);
    const results = body.hits.hits.map(hit => hit._source);

    res.render('interface', {
      query: query,
      results: results,
      total: body.hits.total.value
    });
  } catch (error) {
    console.error('Erro na rota de busca:', error);
    res.render('interface', {
      query: query,
      results: [],
      total: 0,
      error: 'Ocorreu um erro ao comunicar com o banco de dados.'
    });
  }
});

// NOVA ROTA: Para importar os dados
app.get('/import', async (req, res) => {
    console.log('--- [IMPORTAÇÃO] Rota /import acionada ---');
    try {
        const filePath = path.resolve(__dirname, 'data', 'jurisprudencias.json');
        
        if (!fs.existsSync(filePath)) {
            throw new Error(`Arquivo de dados não encontrado em /data/jurisprudencias.json`);
        }
        
        const fileContent = fs.readFileSync(filePath, 'utf8');
        const jurisprudencias = JSON.parse(fileContent);
        
        await client.indices.create({ index: INDEX_NAME }, { ignore: [400] });

        for (const doc of jurisprudencias) {
            const documentoParaIndexar = {
                id: doc.numero_processo,
                classe: doc.classe,
                assunto: doc.assunto,
                magistrado: doc.magistrado,
                comarca: doc.comarca,
                data_julgamento: doc.data_julgamento,
                ementa: doc.ementa,
                texto_decisao: doc.inteiro_teor,
                fonte: 'TJSC (Arquivo JSON)'
            };

            if (!documentoParaIndexar.id) continue;

            await client.index({
                index: INDEX_NAME,
                id: documentoParaIndexar.id,
                body: documentoParaIndexar
            });
        }
        
        await client.indices.refresh({ index: INDEX_NAME });
        
        console.log('--- [IMPORTAÇÃO] SUCESSO! ---');
        res.redirect('/');

    } catch (error) {
        console.error('Ocorreu um erro fatal durante a importação:', error);
        res.status(500).send('Erro durante a importação: ' + error.message);
    }
});

app.listen(port, () => {
  console.log(`>>> Servidor iurisadv.ai rodando em http://localhost:${port}`);
});