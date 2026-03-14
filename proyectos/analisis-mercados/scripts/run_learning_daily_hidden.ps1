$ErrorActionPreference = 'Continue'
& "C:\Windows\py.exe" -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\learning_daily.py" | Out-Null
& "C:\Windows\py.exe" -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\learn_from_crypto_trades.py" | Out-Null
