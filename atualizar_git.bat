@echo off
:: Script para atualizar o repositório Suíte Racional no GitHub
:: Desenvolvido para facilitar o fluxo de trabalho

echo [1/3] Adicionando arquivos modificados...
git add .

echo.
echo [2/3] Criando commit...
:: O comando abaixo usa a data e hora atual no nome do commit para facilitar o rastreamento
set commit_message="Atualizacao automatica: %date% %time%"
git commit -m %commit_message%

echo.
echo [3/3] Enviando para o GitHub (branch main)...
git push origin main

echo.
echo ==========================================
echo Atualizacao concluida com sucesso!
echo ==========================================
pause
