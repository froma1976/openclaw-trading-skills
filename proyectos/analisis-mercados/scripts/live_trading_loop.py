#!/usr/bin/env python3
import time
import subprocess
import sys
import os
from datetime import datetime

# Rutas absolutas
BASE_DIR = r"c:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados"
AUTOPILOT_SCRIPT = os.path.join(BASE_DIR, "scripts", "run_crypto_scalp_autopilot.py")
PYTHON_EXE = sys.executable

def run_trading_cycle():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Escaneando mercado...")
    try:
        # Ejecutamos el autopilot. 
        # Nota: run_crypto_scalp_autopilot.py ya importa y ejecuta los ingestores al final de su ejecución
        # según vimos en el código anterior (líneas 1072-1078).
        result = subprocess.run([PYTHON_EXE, AUTOPILOT_SCRIPT], capture_output=True, text=True, cwd=BASE_DIR)
        
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(f"Error: {result.stderr.strip()}", file=sys.stderr)
            
    except Exception as e:
        print(f"CRITICAL ERROR in cycle: {e}")

def main():
    print("--- CONVICTION AI: LIVE TRADING ENGINE STARTED ---")
    print(f"Intervalo: 10 segundos | Script: {AUTOPILOT_SCRIPT}")
    print("Presiona Ctrl+C para detener.")
    
    try:
        while True:
            start_time = time.time()
            run_trading_cycle()
            
            # Mantener un ciclo constante de 10 segundos
            elapsed = time.time() - start_time
            wait_time = max(1, 10 - elapsed)
            time.sleep(wait_time)
    except KeyboardInterrupt:
        print("\n--- Motor detenido por el usuario ---")

if __name__ == "__main__":
    main()
