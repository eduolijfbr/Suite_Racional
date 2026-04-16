@echo off
setlocal
set PLUGIN_NAME=Suite_Racional_Pro
set ZIP_NAME=%PLUGIN_NAME%.zip

echo ======================================================
echo Empacotando Plugin QGIS: %PLUGIN_NAME%
echo ======================================================

rem 1. Limpar pacotes antigos
if exist "%ZIP_NAME%" del /f /q "%ZIP_NAME%"
if exist "temp_build" rd /s /q "temp_build"

rem 2. Criar estrutura de pastas (nome do projeto na raiz do zip)
mkdir "temp_build\%PLUGIN_NAME%"

echo Copiando arquivos essenciais...

rem 3. Copiar arquivos da raiz
copy "metadata.txt" "temp_build\%PLUGIN_NAME%\" > nul
copy "__init__.py" "temp_build\%PLUGIN_NAME%\" > nul
copy "suite_main.py" "temp_build\%PLUGIN_NAME%\" > nul

rem 4. Copiar módulos selecionados ignorando arquivos de cache e banco local
rem ROBOCOPY opcoes: /E (subdirs incluindo vazios) /XF (excluir arquivos) /XD (excluir dirs)
echo Copiando medir_3d...
robocopy "medir_3d" "temp_build\%PLUGIN_NAME%\medir_3d" /E /XF *.gpkg *.png *.pyc /XD __pycache__ > nul

echo Copiando mdt_qgis_plugin...
robocopy "mdt_qgis_plugin" "temp_build\%PLUGIN_NAME%\mdt_qgis_plugin" /E /XF *.pyc /XD __pycache__ > nul

echo Copiando metodo_racional_pro...
robocopy "metodo_racional_pro" "temp_build\%PLUGIN_NAME%\metodo_racional_pro" /E /XF *.pyc /XD __pycache__ > nul

rem 5. Criar o arquivo ZIP via PowerShell
echo Criando arquivo ZIP...
powershell -command "Compress-Archive -Path 'temp_build\%PLUGIN_NAME%' -DestinationPath '%ZIP_NAME%'"

rem 6. Limpeza final
rd /s /q "temp_build"

echo ======================================================
echo SUCESSO! Pacote gerado: %ZIP_NAME%
echo ======================================================
pause
endlocal
