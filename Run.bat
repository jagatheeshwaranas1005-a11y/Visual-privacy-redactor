@echo off
setlocal
set "SSL_CERT_FILE=%~dp0.venv\Lib\site-packages\certifi\cacert.pem"
set "REQUESTS_CA_BUNDLE=%SSL_CERT_FILE%"
set "CURL_CA_BUNDLE=%SSL_CERT_FILE%"
call "%~dp0.venv\Scripts\streamlit.exe" run "%~dp0app.py" %*
