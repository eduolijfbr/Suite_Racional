# MDT Generator - QGIS Plugin

## Descrição
Este plugin permite a geração de Modelos Digitais de Terreno (MDT) ou Modelos Digitais de Superfície (MDS) diretamente no QGIS a partir de camadas de curvas de nível (vetores de linhas). Ele utiliza o motor de interpolação robusto desenvolvido para o sistema MDT, garantindo alinhamento geográfico preciso e densificação de curvas para maior fidelidade.

## Funcionalidades
- **Grid Snap**: Alinhamento automático do raster a coordenadas métricas absolutas (multiplos da resolução), evitando deslocamentos sistemáticos.
- **Densificação Automática**: Adiciona pontos ao longo das curvas de nível para garantir que o TIN (Triangulated Irregular Network) não "pule" detalhes da topografia.
- **Background Processing**: A interpolação roda em segundo plano, sem travar a interface do QGIS.
- **Integração GDAL**: Gera arquivos GeoTIFF padrão da indústria compatíveis com qualquer software GIS.

## Instalação
1. Baixe o arquivo `MDT_QGIS_Plugin.zip`.
2. No QGIS, vá em **Complementos > Gerenciar e Instalar Complementos**.
3. Selecione a aba **Instalar a partir do ZIP**.
4. Selecione o arquivo `.zip` e clique em **Instalar Complemento**.

## Como Usar
1. Carregue sua camada de curvas de nível no QGIS.
2. Clique no ícone do **MDT Generator** na barra de ferramentas ou vá em **Complementos > MDT Generator**.
3. No painel:
   - Selecione a camada de entrada.
   - Escolha o campo que contém a cota (Z/Elevação).
   - Defina a resolução desejada (ex: 1.0m).
   - Escolha o local para salvar o GeoTIFF de saída.
4. Clique em **Generate MDT**.
5. O resultado será carregado automaticamente no mapa ao finalizar.

## Requisitos
- QGIS 3.40 ou superior.
- Python 3.12+ (incluído no instalador padrão do QGIS).
- Bibliotecas `numpy` e `scipy` (já presentes no QGIS padrão).

## Suporte e Erros
Caso ocorra algum erro, verifique o log detalhado em:
**Exibir > Painéis > Mensagens Log > MDT Plugin**
