# -*- coding: utf-8 -*-
"""
Implementação do Método Racional para Cálculo de Drenagem
"""

import math
import numpy as np


class MetodoRacional:
    """
    Implementação completa do Método Racional.
    
    Fórmula: Q = (C * I * A) / 3.6
    Onde:
    Q = vazão (m³/s)
    C = coeficiente de escoamento superficial
    I = intensidade de precipitação (mm/h)
    A = área da bacia (km²)
    """
    
    def __init__(self):
        self.resultados = {}
        
    def calcular_vazao(self, C, I, A):
        """
        Calcula vazão pelo método racional.
        
        Parâmetros:
            C: Coeficiente de escoamento (0-1)
            I: Intensidade de precipitação (mm/h)
            A: Área da bacia (km²)
            
        Retorna:
            float: Vazão em m³/s
        """
        Q = (C * I * A) / 3.6
        return Q
    
    def calcular_intensidade_idf(self, TR, duracao, parametros_idf):
        """
        Calcula intensidade pela equação IDF local.
        
        Equação geral: I = (K * TR^a) / (t + b)^c
        
        Parâmetros:
            TR: tempo de retorno (anos)
            duracao: duração da chuva (min)
            parametros_idf: dict com K, a, b, c
            
        Retorna:
            float: Intensidade em mm/h
        """
        K = parametros_idf['K']
        a = parametros_idf['a']
        b = parametros_idf['b']
        c = parametros_idf['c']
        
        I = (K * (TR ** a)) / ((duracao + b) ** c)
        return I
    
    def dimensionar_conduto(self, Q, declividade, rugosidade):
        """
        Dimensiona conduto pelo método de Manning.
        
        Parâmetros:
            Q: Vazão (m³/s)
            declividade: Declividade do conduto (m/m)
            rugosidade: Coeficiente de Manning
            
        Retorna:
            dict: Resultados do dimensionamento circular e lado quadrado equivalente
        """
        return self._dimensionar_circular(Q, declividade, rugosidade)
    
    def _dimensionar_circular(self, Q, S, n):
        """
        Dimensionamento de seção circular.
        
        Fórmula de Manning: Q = (1/n) * A * R^(2/3) * S^(1/2)
        
        Parâmetros:
            Q: Vazão (m³/s)
            S: Declividade (m/m)
            n: Coeficiente de Manning
            
        Retorna:
            dict: Resultados do dimensionamento
        """
        # Assume escoamento com y/D = 0.85 (recomendado)
        y_sobre_D = 0.85
        
        # Cálculo iterativo para encontrar diâmetro
        diametro = self._iteracao_manning_circular(Q, S, n, y_sobre_D)
        
        # Cálculos complementares
        theta = 2 * math.acos(1 - 2 * y_sobre_D)
        area = (diametro ** 2 / 8) * (theta - math.sin(theta))
        perimetro_molhado = (diametro / 2) * theta
        raio_hidraulico = area / perimetro_molhado
        velocidade = Q / area
        
        # Profundidade hidráulica
        largura_superficie = diametro * math.sin(theta / 2)
        prof_hidraulica = area / largura_superficie if largura_superficie > 0 else diametro * y_sobre_D
        
        # Número de Froude
        g = 9.81
        froude = velocidade / math.sqrt(g * prof_hidraulica)
        
        # Verificações
        status = self._verificar_condicoes(velocidade, froude, y_sobre_D)
        
        area_total = (math.pi * diametro ** 2) / 4
        lado_galeria = math.sqrt(area_total)
        
        return {
            'diametro': diametro,
            'lado_galeria': lado_galeria,
            'velocidade': velocidade,
            'numero_froude': froude,
            'lamina_altura': y_sobre_D,
            'raio_hidraulico': raio_hidraulico,
            'area': area,
            'area_secao': area_total,
            'perimetro_molhado': perimetro_molhado,
            'status': status,
            'observacoes': self._gerar_observacoes(velocidade, froude)
        }
    
    def _iteracao_manning_circular(self, Q, S, n, y_sobre_D):
        """
        Iteração para encontrar diâmetro de seção circular.
        """
        # Estimativa inicial
        D = 1.0
        
        for _ in range(100):
            theta = 2 * math.acos(1 - 2 * y_sobre_D)
            area = (D ** 2 / 8) * (theta - math.sin(theta))
            perimetro = (D / 2) * theta
            raio = area / perimetro
            
            # Vazão calculada
            Q_calc = (1 / n) * area * (raio ** (2/3)) * (S ** 0.5)
            
            # Ajuste do diâmetro
            if abs(Q_calc - Q) / Q < 0.001:
                break
                
            # Fator de correção
            D = D * (Q / Q_calc) ** 0.4
            
        return D

    
    def _verificar_condicoes(self, velocidade, froude, lamina):
        """
        Verifica condições hidráulicas do projeto.
        
        Critérios:
        - Velocidade mínima: 0.6 m/s (autolimpante)
        - Velocidade máxima: 5.0 m/s (erosão)
        - Número de Froude < 1 (subcrítico preferível)
        - Lâmina/Diâmetro: 0.5 - 0.85
        """
        status = []
        
        if velocidade < 0.6:
            status.append("ALERTA: Velocidade baixa - risco de sedimentação")
        elif velocidade > 5.0:
            status.append("ALERTA: Velocidade alta - risco de erosão")
        else:
            status.append("OK: Velocidade adequada")
            
        if froude >= 1:
            status.append("ALERTA: Escoamento supercrítico")
        else:
            status.append("OK: Escoamento subcrítico")
            
        if lamina > 0.85:
            status.append("ALERTA: Lâmina d'água elevada")
        elif lamina < 0.5:
            status.append("INFO: Capacidade ociosa")
        else:
            status.append("OK: Lâmina adequada")
            
        return "; ".join(status)
    
    def _gerar_observacoes(self, velocidade, froude):
        """
        Gera observações técnicas sobre os resultados.
        """
        obs = []
        
        if velocidade < 0.6:
            obs.append("Considere aumentar a declividade ou reduzir o diâmetro para evitar sedimentação.")
        elif velocidade > 5.0:
            obs.append("Considere estruturas de dissipação de energia ou reduzir a declividade.")
            
        if froude > 0.8 and froude < 1.2:
            obs.append("Escoamento próximo ao regime crítico - evitar esta condição.")
        elif froude >= 1.2:
            obs.append("Verificar necessidade de estrutura para ressalto hidráulico.")
            
        if not obs:
            obs.append("Dimensionamento dentro dos parâmetros recomendados.")
            
        return " ".join(obs)
    
    def verificar_projeto(self, resultados):
        """
        Verifica condições hidráulicas do projeto.
        
        Retorna:
            dict: Resultado das verificações
        """
        verificacoes = {
            'velocidade': {
                'valor': resultados['velocidade'],
                'min': 0.6,
                'max': 5.0,
                'status': 'OK' if 0.6 <= resultados['velocidade'] <= 5.0 else 'ALERTA'
            },
            'froude': {
                'valor': resultados['numero_froude'],
                'limite': 1.0,
                'status': 'OK' if resultados['numero_froude'] < 1.0 else 'ALERTA'
            },
            'lamina': {
                'valor': resultados['lamina_altura'],
                'min': 0.5,
                'max': 0.85,
                'status': 'OK' if 0.5 <= resultados['lamina_altura'] <= 0.85 else 'INFO'
            }
        }
        
        return verificacoes


class TempoConcentracao:
    """Cálculo de tempo de concentração por múltiplos métodos"""
    
    @staticmethod
    def kirpich(comprimento_m, desnivel_m):
        """
        Método de Kirpich.
        Tc = 57 * (L³ / H)^0.385
        
        Parâmetros:
            comprimento_m: Comprimento do talvegue (m)
            desnivel_m: Desnível (m)
            
        Retorna:
            float: Tempo de concentração (min)
        """
        L_km = comprimento_m / 1000
        tc = 57 * ((L_km ** 3) / desnivel_m) ** 0.385
        return tc
    
    @staticmethod
    def dooge(area_km2, comprimento_km):
        """
        Método de Dooge.
        Tc = 0.365 * (A^0.41) * (L^-0.17)
        """
        tc = 0.365 * (area_km2 ** 0.41) * (comprimento_km ** -0.17) * 60
        return tc
    
    @staticmethod
    def scs_lag(comprimento_m, cn, declividade_perc):
        """
        Método SCS Lag Time.
        """
        L_ft = comprimento_m * 3.281
        S = (1000 / cn) - 10
        Y = declividade_perc
        
        lag = (L_ft ** 0.8 * (S + 1) ** 0.7) / (1900 * Y ** 0.5)
        tc = lag / 0.6  # Tc = Lag / 0.6
        return tc
    
    @staticmethod
    def california_culverts(comprimento_m, desnivel_m):
        """
        Método California Culverts Practice.
        Tc = (11.9 * L³ / H)^0.385
        """
        L_km = comprimento_m / 1000
        tc = (11.9 * (L_km ** 3) / desnivel_m) ** 0.385 * 60
        return tc
    
    @staticmethod
    def ventura(area_km2, declividade_perc):
        """
        Método de Ventura.
        Tc = 0.127 * sqrt(A / i)
        """
        tc = 0.127 * math.sqrt(area_km2 / (declividade_perc / 100)) * 60
        return tc
    
    @staticmethod
    def giandotti(area_km2, comprimento_m, desnivel_m):
        """
        Método de Giandotti.
        Tc = (4√A + 1.5L) / (0.8√H) [horas] → convertido para minutos
        
        Adequado para bacias urbanas pequenas e médias.
        Muito utilizado no Brasil para justificativa em relatórios técnicos.
        
        Parâmetros:
            area_km2: Área da bacia (km²)
            comprimento_m: Comprimento do talvegue (m)
            desnivel_m: Desnível (m)
            
        Retorna:
            float: Tempo de concentração (min)
        """
        L_km = comprimento_m / 1000
        if desnivel_m <= 0:
            return 0
        tc_h = (4 * math.sqrt(area_km2) + 1.5 * L_km) / (0.8 * math.sqrt(desnivel_m))
        return tc_h * 60
    
    @staticmethod
    def bransby_williams(area_km2, comprimento_m, declividade_perc):
        """
        Método de Bransby-Williams.
        Tc = 14.6 × L / (A^0.1 × S^0.2) [minutos]
        
        Produz valores mais conservadores.
        Útil para análises comparativas e cenários críticos.
        
        Parâmetros:
            area_km2: Área da bacia (km²)
            comprimento_m: Comprimento do talvegue (m)
            declividade_perc: Declividade média (%)
            
        Retorna:
            float: Tempo de concentração (min)
        """
        L_km = comprimento_m / 1000
        S = declividade_perc / 100
        if S <= 0 or area_km2 <= 0:
            return 0
        return 14.6 * L_km / (area_km2 ** 0.1 * S ** 0.2)
    
    @staticmethod
    def calcular_todos(comprimento_m, desnivel_m, area_km2, cn=None, declividade_perc=None):
        """
        Calcula tempo de concentração por todos os métodos disponíveis.
        """
        resultados = {}
        
        # Kirpich
        if desnivel_m > 0:
            resultados['kirpich'] = TempoConcentracao.kirpich(comprimento_m, desnivel_m)
        
        # California
        if desnivel_m > 0:
            resultados['california'] = TempoConcentracao.california_culverts(comprimento_m, desnivel_m)
        
        # Dooge
        comprimento_km = comprimento_m / 1000
        if comprimento_km > 0:
            resultados['dooge'] = TempoConcentracao.dooge(area_km2, comprimento_km)
        
        # SCS (se CN disponível)
        if cn and declividade_perc and declividade_perc > 0:
            resultados['scs'] = TempoConcentracao.scs_lag(comprimento_m, cn, declividade_perc)
            
        # Ventura (se declividade disponível)
        if declividade_perc and declividade_perc > 0:
            resultados['ventura'] = TempoConcentracao.ventura(area_km2, declividade_perc)
        
        # Giandotti
        if desnivel_m > 0:
            resultados['giandotti'] = TempoConcentracao.giandotti(area_km2, comprimento_m, desnivel_m)
        
        # Bransby-Williams (se declividade disponível)
        if declividade_perc and declividade_perc > 0:
            resultados['bransby_williams'] = TempoConcentracao.bransby_williams(area_km2, comprimento_m, declividade_perc)
            
        # Média
        if resultados:
            resultados['media'] = sum(resultados.values()) / len(resultados)
        
        return resultados

