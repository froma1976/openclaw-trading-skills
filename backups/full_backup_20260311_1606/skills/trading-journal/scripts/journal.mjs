#!/usr/bin/env node
import fs from 'fs';
import path from 'path';

// El archivo que almacenará todos tus apuntes y sus vectores
const DB_FILE = path.join(path.dirname(new URL(import.meta.url).pathname).replace(/^\/([A-Za-z]:)/, '$1'), '..', 'journal_db.json');

// Utilidad matemática para ver cuán similares son dos textos vectorizados (RAG puro)
function cosineSimilarity(vecA, vecB) {
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < vecA.length; i++) {
    dotProduct += vecA[i] * vecB[i];
    normA += vecA[i] * vecA[i];
    normB += vecB[i] * vecB[i];
  }
  if (normA === 0 || normB === 0) return 0;
  return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}

// Llama al motor local de Ollama para convertir palabras en conceptos matemáticos (embed)
async function getEmbedding(text) {
  try {
    const res = await fetch('http://127.0.0.1:11434/api/embeddings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'nomic-embed-text',
        prompt: text
      })
    });
    
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Ollama Error HTTP ${res.status}: ${errorText}`);
    }
    
    const data = await res.json();
    return data.embedding;
  } catch (err) {
    if (err.cause && err.cause.code === 'ECONNREFUSED') {
       throw new Error('CRITICAL: Ollama no está corriendo en localhost:11434. Asegúrate de encender Ollama antes de usar la memoria vectorial.');
    }
    throw new Error('No se pudo vectorizar el texto. Asegúrate de que tienes instalado el modelo: "ollama pull nomic-embed-text". Error: ' + err.message);
  }
}

// Carga o crea la Base de Datos Local
function loadDB() {
  if (!fs.existsSync(DB_FILE)) {
    return { records: [] };
  }
  return JSON.parse(fs.readFileSync(DB_FILE, 'utf-8'));
}

// Función principal
async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command) {
    console.error(JSON.stringify({ error: "Comando inválido. Usa 'add' o 'search'." }));
    process.exit(1);
  }

  if (command === 'add') {
    const text = args[1];
    if (!text) {
      console.error(JSON.stringify({ error: "Falta el texto a guardar." }));
      process.exit(1);
    }
    
    try {
      const db = loadDB();
      const embedding = await getEmbedding(text);
      
      const newRecord = {
        id: crypto.randomUUID(),
        timestamp_utc: new Date().toISOString(),
        content: text,
        embedding: embedding
      };
      
      db.records.push(newRecord);
      fs.writeFileSync(DB_FILE, JSON.stringify(db, null, 2));
      
      console.log(JSON.stringify({
        status: "success",
        message: "Memoria almacenada en el cerebro del modelo.",
        id: newRecord.id,
        stored_bytes: JSON.stringify(newRecord).length
      }, null, 2));
    } catch (err) {
      console.error(JSON.stringify({ error: err.message }));
    }
    
  } else if (command === 'search') {
    const query = args[1];
    const rawLimit = args[2] ? parseInt(args[2], 10) : 3;
    const limit = isNaN(rawLimit) ? 3 : rawLimit;

    if (!query) {
      console.error(JSON.stringify({ error: "Falta la consulta de búsqueda." }));
      process.exit(1);
    }

    try {
      const db = loadDB();
      if (db.records.length === 0) {
        console.log(JSON.stringify({ results: [], message: "La base de datos está vacía. No hay nada que recordar." }));
        process.exit(0);
      }

      const queryEmbedding = await getEmbedding(query);
      
      // Compute cosine similarity for all records
      const scoredRecords = db.records.map(record => {
        const score = cosineSimilarity(queryEmbedding, record.embedding);
        return {
          id: record.id,
          timestamp_utc: record.timestamp_utc,
          score: Number(score.toFixed(4)),
          content: record.content
        };
      });
      
      // Sort by best score descending
      scoredRecords.sort((a, b) => b.score - a.score);
      
      const topResults = scoredRecords.slice(0, limit);
      
      console.log(JSON.stringify({
         query: query,
         results: topResults,
         notice: "Utiliza estos contextos (si su score es alto, ej > 0.5) para fundamentar tus análisis al usuario."
      }, null, 2));
      
    } catch (err) {
      console.error(JSON.stringify({ error: err.message }));
    }
  } else {
    console.error(JSON.stringify({ error: "Comando desconocido." }));
  }
}

main();
