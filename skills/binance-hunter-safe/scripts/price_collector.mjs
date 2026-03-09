#!/usr/bin/env node
import fs from 'fs';
import path from 'path';

const DB_DIR = path.join(path.dirname(new URL(import.meta.url).pathname).replace(/^\/([A-Za-z]:)/, '$1'), '..', '..', '..', 'memory');
if (!fs.existsSync(DB_DIR)) {
  fs.mkdirSync(DB_DIR, { recursive: true });
}
const DB_FILE = path.join(DB_DIR, 'price_warehouse.csv');

const ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "TSLA"]; 

async function getBinancePrice(symbol) {
  try {
     const res = await fetch(`https://api.binance.com/api/v3/ticker/price?symbol=${symbol}`);
     if(!res.ok) return null;
     const data = await res.json();
     return parseFloat(data.price);
  } catch(e) {
     return null;
  }
}

async function collect() {
  let isNew = !fs.existsSync(DB_FILE);
  if (isNew) {
      fs.writeFileSync(DB_FILE, "timestamp_utc,asset,price\n", "utf8");
  }
  
  let count = 0;
  const now = new Date().toISOString();
  
  for (const asset of ASSETS) {
     if(asset.endsWith("USDT")) {
         const px = await getBinancePrice(asset);
         if(px !== null) {
            fs.appendFileSync(DB_FILE, `${now},${asset},${px}\n`, "utf8");
            count++;
         }
     }
  }
  
  console.log(`Guardados ${count} precios correctamente en el Warehouse (CSV).`);
}

collect();
