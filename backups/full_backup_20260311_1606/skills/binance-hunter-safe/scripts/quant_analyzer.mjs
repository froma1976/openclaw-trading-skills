#!/usr/bin/env node

const symbol = process.argv[2] ? process.argv[2].toUpperCase().replace('/', '') : 'BTCUSDT';
const timeframe = process.argv[3] || '1h'; // 15m, 1h, 4h, 1d

// Math Utilities
function sma(data, period) {
  const result = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else {
      let sum = 0;
      for (let j = 0; j < period; j++) {
        sum += data[i - j];
      }
      result.push(sum / period);
    }
  }
  return result;
}

function ema(data, period) {
  const result = [];
  const k = 2 / (period + 1);
  let prevEma = null;
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null);
      if (i === period - 2) {
        let sum = 0;
        for (let j = 0; j <= i; j++) sum += data[j];
        prevEma = sum / (period - 1); // Simple seed
      }
    } else if (i === period - 1) {
      let sum = 0;
      for (let j = 0; j < period; j++) sum += data[j];
      const currentSma = sum / period;
      result.push(currentSma);
      prevEma = currentSma;
    } else {
      const currentEma = data[i] * k + prevEma * (1 - k);
      result.push(currentEma);
      prevEma = currentEma;
    }
  }
  return result;
}

function rsi(data, period = 14) {
  const result = [];
  let gains = [];
  let losses = [];
  
  for(let i=1; i<data.length; i++) {
    let diff = data[i] - data[i-1];
    gains.push(Math.max(0, diff));
    losses.push(Math.max(0, -diff));
  }
  
  let avgGain = 0;
  let avgLoss = 0;
  
  for(let i=0; i<data.length; i++) {
    if(i < period) {
      result.push(null);
      if (i === period - 1) {
          let sumG = 0; let sumL = 0;
          for(let j=0; j<period; j++) { sumG += gains[j]; sumL += losses[j]; }
          avgGain = sumG / period;
          avgLoss = sumL / period;
          let rs = avgGain / (avgLoss === 0 ? 0.0001 : avgLoss);
          result.push(100 - (100 / (1 + rs)));
      }
    } else {
      avgGain = ((avgGain * (period - 1)) + gains[i-1]) / period;
      avgLoss = ((avgLoss * (period - 1)) + losses[i-1]) / period;
      let rs = avgGain / (avgLoss === 0 ? 0.0001 : avgLoss);
      result.push(100 - (100 / (1 + rs)));
    }
  }
  return result;
}

function macd(data, fast=12, slow=26, signal=9) {
  const emaFast = ema(data, fast);
  const emaSlow = ema(data, slow);
  const macdLine = [];
  
  for(let i=0; i<data.length; i++) {
    if(emaFast[i] !== null && emaSlow[i] !== null) {
      macdLine.push(emaFast[i] - emaSlow[i]);
    } else {
      macdLine.push(null);
    }
  }
  
  // Calculate Signal line (EMA of MACD line)
  const validMacdLine = macdLine.filter(x => x !== null);
  const signalEmaValid = ema(validMacdLine, signal);
  
  const signalLine = [];
  let j = 0;
  for(let i=0; i<data.length; i++) {
    if (macdLine[i] !== null) {
       signalLine.push(signalEmaValid[j]);
       j++;
    } else {
       signalLine.push(null);
    }
  }
  
  const histogram = [];
  for(let i=0; i<data.length; i++) {
     if(macdLine[i] !== null && signalLine[i] !== null) {
        histogram.push(macdLine[i] - signalLine[i]);
     } else {
        histogram.push(null);
     }
  }
  
  return { macd: macdLine, signal: signalLine, hist: histogram };
}

function stdDev(data, period) {
    const result = [];
    for(let i=0; i<data.length; i++) {
        if (i < period - 1) {
            result.push(null);
        } else {
            let sum = 0;
            for(let j=0; j<period; j++) sum += data[i-j];
            let mean = sum / period;
            let variance = 0;
            for(let j=0; j<period; j++) variance += Math.pow(data[i-j] - mean, 2);
            result.push(Math.sqrt(variance / period));
        }
    }
    return result;
}

function bollingerBands(data, period=20, multiplier=2) {
    const smaLine = sma(data, period);
    const sdLine = stdDev(data, period);
    const upper = [];
    const lower = [];
    for(let i=0; i<data.length; i++) {
        if(smaLine[i] !== null && sdLine[i] !== null) {
            upper.push(smaLine[i] + (multiplier * sdLine[i]));
            lower.push(smaLine[i] - (multiplier * sdLine[i]));
        } else {
            upper.push(null);
            lower.push(null);
        }
    }
    return { sma: smaLine, upper, lower };
}

async function fetchBinanceData(sym, interval) {
  const res = await fetch(`https://api.binance.com/api/v3/klines?symbol=${sym}&interval=${interval}&limit=100`);
  if (!res.ok) throw new Error("Binance API error");
  const data = await res.json();
  
  const closes = data.map(k => parseFloat(k[4]));
  const highs = data.map(k => parseFloat(k[2]));
  const lows = data.map(k => parseFloat(k[3]));
  const volumes = data.map(k => parseFloat(k[5]));
  return { closes, highs, lows, volumes };
}

async function fetchTicker(sym) {
  const res = await fetch(`https://api.binance.com/api/v3/ticker/24hr?symbol=${sym}`);
  if (!res.ok) throw new Error("Binance API error");
  return await res.json();
}

async function main() {
  try {
    const ticker = await fetchTicker(symbol);
    const { closes, highs, lows, volumes } = await fetchBinanceData(symbol, timeframe);
    
    // Indicators calculation
    const currentPrice = closes[closes.length - 1];
    
    const ema9 = ema(closes, 9);
    const ema21 = ema(closes, 21);
    const ema50 = ema(closes, 50);
    const ema200 = ema(closes, 200);
    
    const rsiLine = rsi(closes, 14);
    const macdData = macd(closes, 12, 26, 9);
    const bbData = bollingerBands(closes, 20, 2);
    
    const currEma9 = ema9[ema9.length - 1];
    const currEma21 = ema21[ema21.length - 1];
    const currEma50 = ema50[ema50.length - 1];
    const currEma200 = ema200[ema200.length - 1];
    const currRSI = rsiLine[rsiLine.length -1];
    
    const currMacd = macdData.macd[macdData.macd.length - 1];
    const currMacdHist = macdData.hist[macdData.hist.length - 1];
    const prevMacdHist = macdData.hist[macdData.hist.length - 2];
    
    const bbUpper = bbData.upper[bbData.upper.length - 1];
    const bbLower = bbData.lower[bbData.lower.length - 1];
    
    // AI Interpretation logic built-in
    let trend = "SIDEWAYS";
    if (currEma9 > currEma21 && currEma21 > currEma50) trend = "BULLISH";
    if (currEma9 < currEma21 && currEma21 < currEma50) trend = "BEARISH";
    
    let momentum = "NEUTRAL";
    if (currMacdHist > 0 && currMacdHist > prevMacdHist) momentum = "STRONG_BULLISH";
    if (currMacdHist < 0 && currMacdHist < prevMacdHist) momentum = "STRONG_BEARISH";
    if (currRSI > 70) momentum = "OVERBOUGHT (CAUTION)";
    if (currRSI < 30) momentum = "OVERSOLD (REVERSAL EXPECTED)";

    const result = {
        scan_time_utc: new Date().toISOString(),
        asset: symbol,
        timeframe: timeframe,
        current_price: currentPrice,
        price_change_24h_pct: parseFloat(ticker.priceChangePercent),
        trend_analysis: {
            overall_trend: trend,
            ema_9: Number(currEma9.toFixed(4)),
            ema_21: Number(currEma21.toFixed(4)),
            ema_50: currEma50 !== null ? Number(currEma50.toFixed(4)) : null,
            ema_200: currEma200 !== null ? Number(currEma200.toFixed(4)) : null
        },
        momentum_oscillators: {
            momentum_state: momentum,
            rsi_14: Number(currRSI.toFixed(2)),
            macd_line: currMacd !== null ? Number(currMacd.toFixed(4)) : null,
            macd_histogram: currMacdHist !== null ? Number(currMacdHist.toFixed(4)) : null
        },
        volatility_bb: {
            upper_band: bbUpper !== null ? Number(bbUpper.toFixed(4)) : null,
            lower_band: bbLower !== null ? Number(bbLower.toFixed(4)) : null,
            distance_to_upper_pct: bbUpper ? Number(((bbUpper - currentPrice) / currentPrice * 100).toFixed(2)) : null,
            distance_to_lower_pct: bbLower ? Number(((currentPrice - bbLower) / currentPrice * 100).toFixed(2)) : null
        },
        summary: `El activo ${symbol} se encuentra en tendencia ${trend}. RSI en ${Number(currRSI.toFixed(2))}. MACD Histograma: ${Number(currMacdHist?.toFixed(4))}.`
    };
    
    console.log(JSON.stringify(result, null, 2));
  } catch(e) {
    console.error(JSON.stringify({ error: e.message }));
  }
}

main();
