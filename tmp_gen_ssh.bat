@echo off
set KEY=C:\Users\Fernando\.ssh\id_ed25519_openclaw
"C:\Windows\System32\OpenSSH\ssh-keygen.exe" -t ed25519 -C openclaw-main -f "%KEY%" -N ""
