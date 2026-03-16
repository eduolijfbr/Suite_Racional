# Método Racional Pro 🌊

[![QGIS](https://img.shields.io/badge/QGIS-3.4+-brightgreen.svg)](https://qgis.org/)
[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)

O **Método Racional Pro** é uma solução avançada e intuitiva desenvolvida especificamente para auxiliar engenheiros e técnicos de prefeituras de pequeno e médio porte no cálculo e dimensionamento de sistemas de drenagem pluvial urbana.

## 📋 Sobre o Projeto

Este plugin para QGIS automatiza o fluxo de trabalho do **Método Racional**, transformando processos manuais complexos em um fluxo digital integrado. Ele foi projetado para ser uma ferramenta de apoio à decisão, garantindo precisão técnica e agilidade na elaboração de projetos de infraestrutura urbana.

### Por que usar o Método Racional Pro?
- **Foco em Gestão Pública**: Ideal para secretarias de obras e planejamento urbano.
- **Padronização**: Garante que todos os cálculos sigam normas técnicas brasileiras.
- **Produtividade**: Reduz o tempo de elaboração de projetos de dias para horas.
- **Transparência**: Gera relatórios detalhados que facilitam a fiscalização e auditoria.
- **Análise Automatizada**: Classificação inteligente de impermeabilidade usando imagens de satélite.

## ✨ Funcionalidades Principais

### 💧 Hidrologia Avançada
- **Cálculo de Vazão**: Implementação rigorosa do Método Racional (Q = C × i × A).
- **Tempos de Concentração**: Kirpich, Dooge, SCS, Ventura, Passini e outros métodos.
- **Curvas IDF**: Banco de dados integrado com centenas de cidades brasileiras (ajustável).
- **CN Ponderado**: Cálculo automático baseado no uso do solo e tipo de solo (Curve Number).
- **Coeficiente de Escoamento**: Determinação automática ou manual do coeficiente C.

### 🛰️ Análise de Impermeabilidade (NOVO!)
- **Classificação Ternária RGB**: Algoritmo avançado que classifica pixels em três categorias:
  - **Vegetação**: Identificada por índice ExG (Excess Green) e saturação HSV
  - **Água/Sombra**: Detectada por baixa intensidade luminosa
  - **Impermeável**: Superfícies urbanas (asfalto, concreto, edificações)
- **Suporte a Múltiplas Fontes**:
  - Imagens locais (GeoTIFF, PNG, JPG)
  - Camadas XYZ Tiles (Google Satellite, Bing, etc.)
  - Serviços WMS
- **Dois Métodos de Processamento**:
  - `impermeabilidade_raster.py`: Usa Rasterio e scikit-image para máxima precisão
  - `impermeabilidade_qgis.py`: API nativa do QGIS, sem dependências externas
- **Visualização**: Geração automática de mapas de classificação e relatórios estatísticos

### 🗺️ Inteligência Geográfica
- **Processamento de MDT**: Extração automática de declividades e comprimentos de talvegue.
- **Delimitação de Bacias**: Ferramentas para identificação automática de áreas de contribuição.
- **Análise Espacial**: Integração total com camadas vetoriais e raster do QGIS.
- **Extração de Parâmetros**: Cálculo automático de área, perímetro, declividade média.
- **Identificação de Exutório**: Localização automática do ponto mais baixo da bacia.

### 🏗️ Dimensionamento Hidráulico
- **Condutos**: Dimensionamento de galerias circulares e celulares.
- **Verificações Técnicas**: 
  - Velocidade mínima (≥ 0.60 m/s) e máxima (≤ 5.0 m/s)
  - Número de Froude:
    - **Subcrítico (Fr < 0.8)**: Escoamento estável.
    - **Crítico/Instável (0.8 ≤ Fr ≤ 1.2)**: Alerta de instabilidade de lâmina d'água.
    - **Supercrítico (Fr > 1.2)**: Escoamento torrencial, requer dissipadores.
  - Tensão trativa (autolimpeza)
  - Lâmina d'água (y/D ≤ 0.82)
- **Materiais**: Banco de dados com coeficientes de rugosidade (Manning) para diversos materiais.
- **Alertas Automáticos**: Avisos visuais quando parâmetros estão fora das normas.

### 📊 Gestão de Dados e Relatórios
- **Banco de Dados**: 
  - SQLite (local, ideal para projetos individuais)
  - PostgreSQL/PostGIS (rede, ideal para equipes)
- **Relatórios Profissionais**: 
  - Exportação automática para DOCX e PDF
  - Memória de cálculo completa
  - Gráficos e tabelas técnicas
- **Interoperabilidade**: Exportação para GeoPackage, Shapefile, CSV, KML e Excel.

## 📁 Estrutura do Projeto

```
metodo_racional_pro/
├── __init__.py                    # Inicialização do plugin
├── metodo_racional_pro.py         # Classe principal do plugin
├── metadata.txt                   # Metadados do plugin QGIS
├── requirements.txt               # Dependências Python
├── README.md                      # Este arquivo
├── INSTALACAO.txt                 # Guia de instalação detalhado
├── criar_pacote_qgis.bat          # Script para gerar ZIP do plugin
├── update_github.bat              # Script principal de sincronização
├── update_github_manual.bat       # Script para commit manual (com prompt)
├── update_github_auto.bat         # Script para commit automático (data/hora)
│
├── banco_dados/                   # Módulo de persistência
│   ├── gerenciador.py            # Gerenciador de conexões SQLite/PostgreSQL
│   └── schema.sql                # Esquema do banco de dados
│
├── dados/                         # Dados técnicos
│   ├── curvas_idf_brasil.json    # Curvas IDF de cidades brasileiras
│   ├── materiais_rugosidade.json # Coeficientes de Manning
│   └── tabelas_cn.json           # Tabelas de Curve Number (SCS)
│
├── hidrologia/                    # Cálculos hidrológicos
│   ├── metodo_racional.py        # Implementação do Método Racional
│   ├── curvas_idf.py             # Processamento de curvas IDF
│   └── verificacoes.py           # Verificações técnicas hidráulicas
│
├── processamento/                 # Processamento geoespacial
│   ├── delimitador_bacia.py      # Delimitação automática de bacias
│   ├── extrator_parametros.py    # Extração de parâmetros do MDT
│   ├── impermeabilidade_raster.py # Análise de impermeabilidade (Rasterio)
│   └── impermeabilidade_qgis.py  # Análise de impermeabilidade (QGIS nativo)
│
├── relatorios/                    # Geração de relatórios
│   ├── gerador_docx.py           # Exportação para Word
│   └── templates/                # Templates de relatórios
│
├── recursos/                      # Recursos visuais
│   └── icons/                    # Ícones do plugin
│
└── ui/                           # Interface gráfica
    ├── main_dialog.py            # Janela principal
    ├── idf_dialog.py             # Diálogo de seleção de IDF
    ├── impermeabilidade_dialog.py # Diálogo de análise de impermeabilidade
    └── help_dialog.py            # Ajuda e documentação
```

## 🚀 Instalação

### Requisitos
- **QGIS**: 3.4 ou superior
- **Python**: 3.7+
- **Sistema Operacional**: Windows, Linux ou macOS

### Método 1: Instalação Manual
1. Baixe o repositório como ZIP ou clone via Git:
   ```bash
   git clone https://github.com/eduolijfbr/Racional_2.git
   ```

2. Extraia/copie o conteúdo na pasta de plugins do QGIS:
   - **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\metodo_racional_pro`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/metodo_racional_pro`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/metodo_racional_pro`

3. Abra o QGIS e ative o plugin em:
   ```
   Complementos > Gerenciar e Instalar Complementos > Instalados
   ```
   Marque a caixa ao lado de **Método Racional Pro**.

### Método 2: Usando o Script de Empacotamento
Execute o script `criar_pacote_qgis.bat` (Windows) para gerar automaticamente o arquivo ZIP do plugin.

### Dependências Python
Instale as dependências necessárias no ambiente Python do QGIS:

```bash
pip install -r requirements.txt
```

**Dependências principais:**
- `numpy` - Processamento numérico
- `scipy` - Cálculos científicos
- `pandas` - Manipulação de dados
- `geopandas` - Dados geoespaciais
- `rasterio` - Processamento de raster (opcional, para impermeabilidade_raster.py)
- `shapely` - Geometrias
- `python-docx` - Geração de relatórios Word
- `matplotlib` - Visualizações
- `sqlalchemy` - ORM para banco de dados

> **Nota**: O módulo `impermeabilidade_qgis.py` funciona sem dependências externas, usando apenas a API nativa do QGIS.

## 📖 Como Usar

### Fluxo de Trabalho Básico

1. **Preparação de Dados**:
   - Carregue as camadas necessárias no QGIS:
     - MDT (Modelo Digital de Terreno)
     - Área de estudo (polígono)
     - Imagem de satélite (opcional, para análise de impermeabilidade)

2. **Configuração Inicial**:
   - Abra o plugin: `Complementos > Método Racional Pro`
   - Selecione a cidade para obter a curva IDF correspondente
   - Configure o período de retorno (Tr) desejado

3. **Análise de Impermeabilidade** (Opcional):
   - Acesse: `Ferramentas > Análise de Impermeabilidade`
   - Selecione a camada raster (imagem de satélite)
   - Defina a área de estudo
   - Execute a classificação automática
   - Revise os resultados e estatísticas

4. **Cálculo Hidrológico**:
   - Selecione a área de contribuição
   - O plugin extrairá automaticamente:
     - Área da bacia
     - Declividade média
     - Comprimento do talvegue
   - Calcule o tempo de concentração (método de sua escolha)
   - Determine a intensidade de chuva (curva IDF)
   - Calcule a vazão de projeto

5. **Dimensionamento Hidráulico**:
   - Escolha o material do conduto
   - Selecione o diâmetro comercial
   - O sistema verificará automaticamente:
     - Velocidades (mín/máx)
     - Número de Froude
     - Tensão trativa
     - Lâmina d'água

6. **Geração de Relatório**:
   - Clique em `Gerar Relatório`
   - Escolha o formato (DOCX ou PDF)
   - O relatório incluirá toda a memória de cálculo

### Dicas de Uso

- **Verificações Técnicas**: Preste atenção aos alertas visuais (ícones de aviso) que indicam parâmetros fora das normas.
- **Banco de Dados**: Use PostgreSQL/PostGIS para projetos em equipe, permitindo acesso simultâneo.
- **Impermeabilidade**: Para áreas urbanas complexas, use o método ternário de classificação para maior precisão.
- **Exportação**: Exporte seus dados para GeoPackage para compartilhar com outros usuários QGIS.

## 🔬 Metodologia Técnica

### Análise de Impermeabilidade

O plugin implementa um algoritmo de classificação ternária baseado em índices espectrais:

1. **Excess Green Index (ExG)**: `ExG = 2G - R - B`
   - Identifica vegetação por realce do canal verde

2. **Saturação HSV**: Conversão RGB → HSV
   - Diferencia vegetação (alta saturação) de superfícies cinzas (baixa saturação)

3. **Intensidade Luminosa**: `I = (R + G + B) / 3`
   - Detecta áreas escuras (água, sombras)

**Regras de Classificação:**
- **Vegetação**: ExG > 0 AND Saturação > 0.12
- **Água/Sombra**: Intensidade < 50 AND ExG < 0
- **Impermeável**: Demais pixels dentro da área de estudo

### Método Racional

Fórmula: **Q = C × i × A**

Onde:
- **Q**: Vazão de pico (m³/s ou L/s)
- **C**: Coeficiente de escoamento superficial (adimensional)
- **i**: Intensidade de chuva (mm/h)
- **A**: Área da bacia (km² ou ha)

### Limitações Técnicas do Método
1. **Aplicabilidade**: Recomendado para bacias de microdrenagem urbanas (geralmente < 50-100 hectares), onde a intensidade da chuva pode ser considerada uniforme.
2. **Áreas Extensas**: Para áreas maiores (> 2 km²), os resultados devem ser interpretados como pré-dimensionamento, sendo necessária a validação por Métodos de Hidrograma Unitário (SCS/NRCS) ou modelagem dinâmica (SWMM).
3. **Impermeabilização**: O coeficiente C é estático. Mudanças futuras no uso do solo invalidam a vazão de projeto.

## 🛠️ Tecnologias Utilizadas

- **QGIS API (PyQGIS)**: Interface e processamento geográfico
- **PyQt5**: Interface gráfica do usuário
- **NumPy/SciPy**: Processamento numérico e científico
- **Pandas/GeoPandas**: Manipulação de dados tabulares e espaciais
- **Rasterio**: Processamento de imagens raster
- **Shapely**: Operações geométricas
- **SQLAlchemy**: ORM para banco de dados
- **SQLite/PostgreSQL**: Persistência de dados
- **Python-Docx**: Geração de relatórios Word
- **ReportLab**: Geração de relatórios PDF
- **Matplotlib**: Visualizações e gráficos

## 🤝 Contribuindo

Contribuições são bem-vindas! Para contribuir:

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

### Diretrizes de Contribuição

- Siga o padrão PEP 8 para código Python
- Adicione docstrings para funções e classes
- Inclua testes para novas funcionalidades
- Atualize a documentação conforme necessário

## 📄 Licença

Este projeto está licenciado sob a **GNU General Public License v3.0** (GPL-3.0).

Você é livre para:
- ✅ Usar o software para qualquer propósito
- ✅ Estudar como o software funciona e adaptá-lo
- ✅ Distribuir cópias do software
- ✅ Melhorar o software e distribuir suas melhorias

Sob as condições:
- 📋 Divulgar o código-fonte
- 📋 Licenciar trabalhos derivados sob a mesma licença
- 📋 Documentar mudanças significativas

Veja o arquivo [LICENSE](LICENSE) para detalhes completos.

## 👥 Suporte e Contato

**Desenvolvido para fortalecer a engenharia pública brasileira.**

- 🐛 **Reportar Bugs**: Abra uma [Issue](https://github.com/eduolijfbr/Racional_2/issues)
- 💡 **Sugestões**: Use as [Discussions](https://github.com/eduolijfbr/Racional_2/discussions)
- 📧 **Contato Direto**: eduolijfbr@gmail.com
- 👨‍💻 **Desenvolvedor**: [Eduardo Oliveira](https://github.com/eduolijfbr)

## 📊 Status do Projeto

- ✅ **Versão Atual**: 1.1.0
- ✅ **Status**: Estável (Produção)
- ✅ **QGIS**: 3.4+
- ✅ **Python**: 3.7+

## 🗺️ Roadmap

### Versão 1.1 (Planejado)
- [ ] Suporte a imagens multiespectrais (NIR)
- [ ] Classificação supervisionada com machine learning
- [ ] Integração com Google Earth Engine
- [ ] Análise de séries temporais de impermeabilidade

### Versão 1.2 (Futuro)
- [ ] Modelagem hidráulica completa (SWMM)
- [ ] Análise de cenários de mudança climática
- [ ] API REST para integração com outros sistemas
- [ ] Aplicativo mobile para coleta de dados em campo

---

**Última atualização**: Março 2026  
**Versão**: 1.1.0  
**Mantenedor**: Eduardo Oliveira
