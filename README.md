# 🌊 Suíte Racional Pro

[![QGIS](https://img.shields.io/badge/QGIS-3.x-green.svg?logo=qgis&logoColor=white)](https://qgis.org/)
[![License](https://img.shields.io/badge/License-Proprietary-blue.svg)](LICENSE)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://GitHub.com/eduolijfbr/Suite_Racional/graphs/commit-activity)

A **Suíte Racional Pro** é um conjunto robusto de plugins para o **QGIS**, desenvolvido especificamente para transformar e acelerar o fluxo de trabalho de engenheiros e gestores urbanos. O projeto unifica o cálculo hidrológico, geração de Modelos Digitais de Terreno (MDT) e dimensionamento hidráulico em uma única interface inteligente para QGIS.

## 📦 Instalação Fácil (QGIS)

Para instalar a suíte completa no seu QGIS:

1.  Baixe este repositório como um arquivo **ZIP** (clicando no botão verde `<> Code` > `Download ZIP`).
2.  No QGIS, vá em **Complementos** > **Gerenciar e Instalar Complementos**.
3.  Selecione a aba **Instalar a partir do ZIP**.
4.  Selecione o arquivo baixado e clique em **Instalar complemento**.

> [!NOTE]
> Esta estrutura foi otimizada para evitar erros de `ModuleNotFoundError` comuns em instalações manuais. O pacote agora é reconhecido como uma única suíte integrada.

---

## 🛠️ Ferramentas Integradas

O ecossistema é composto por três ferramentas integradas:

| Ferramenta | Descrição |
| :--- | :--- |
| **📦 Método Racional Pro** | Módulo central para cálculos hidrológicos e dimensionamento hidráulico de galerias. |
| **⛰️ Gerador de MDT** | Criação rápida de Modelos Digitais de Terreno a partir de curvas de nível. |
| **📏 Medir 3D** | Análise altimétrica avançada e medições em ambiente tridimensional. |

---

## 🚀 Principais Funcionalidades

O **Método Racional Pro** guia o projetista por um fluxo de trabalho intuitivo:

1.  **Integração Espacial**: Extração de cotas diretamente do MDT integrado.
2.  **Análise de Superfície**: Classificação visual de imagens para definição do coeficiente de escoamento (C).
3.  **Hidrologia Avançada**: Cálculo do *Tempo de Concentração (Tc)* via Kirpich, Giandotti e Ventura.
4.  **Módulo IDF**: Personalização de parâmetros de chuva para qualquer localidade brasileira.
5.  **Cálculo Automático**: Dimensionamento de galerias com verificações de velocidade e Número de Froude.
6.  **Memória Técnica**: Geração instantânea de relatórios padronizados e perfis longitudinais.

---

## 📋 Requisitos e Diretrizes

*   **Plataforma**: Desenvolvido exclusivamente para **QGIS**.
*   **Aplicação**: Ideal para bacias de microdrenagem urbana até **200 hectares**.
*   **Melhores Práticas**: Para áreas extensas ou simulações dinâmicas complexas, recomenda-se integração complementar com o SWMM.

---

## 💡 Transparência Técnica

Esta suíte foi projetada para oferecer **precisão técnica** e **agilidade na decisão**, prevenindo desastres urbanos e otimizando o uso de recursos públicos através de um planejamento eficiente.

---
<p align="center">
  Desenvolvido por <b>Eduardo Oliveira e Leonardo Leon Leite Moreira</b> <br>
</p>