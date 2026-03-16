# -*- coding: utf-8 -*-
"""
Verificações Técnicas para Projetos de Drenagem
"""


class VerificacoesTecnicas:
    """Classe para verificações técnicas de projetos de drenagem"""
    
    # Limites normativos
    VELOCIDADE_MIN = 0.6  # m/s - autolimpeza
    VELOCIDADE_MAX = 5.0  # m/s - erosão
    FROUDE_LIMITE = 1.0   # subcrítico/supercrítico
    LAMINA_MIN = 0.50     # 50% do diâmetro
    LAMINA_MAX = 0.85     # 85% do diâmetro
    TENSAO_TRATIVA_MIN = 1.0  # Pa
    AREA_LIMITE_RACIONAL = 2.0  # km² - limite para o Método Racional
    
    @staticmethod
    def verificar_velocidade(velocidade):
        """
        Verifica se a velocidade está dentro dos limites.
        
        Retorna:
            dict: Status e mensagem
        """
        if velocidade < VerificacoesTecnicas.VELOCIDADE_MIN:
            return {
                'status': 'ALERTA',
                'codigo': 'VEL_BAIXA',
                'mensagem': f'Velocidade {velocidade:.2f} m/s abaixo do mínimo ({VerificacoesTecnicas.VELOCIDADE_MIN} m/s). Risco de sedimentação.',
                'recomendacao': 'Aumentar declividade ou reduzir diâmetro.'
            }
        elif velocidade > VerificacoesTecnicas.VELOCIDADE_MAX:
            return {
                'status': 'ALERTA',
                'codigo': 'VEL_ALTA',
                'mensagem': f'Velocidade {velocidade:.2f} m/s acima do máximo ({VerificacoesTecnicas.VELOCIDADE_MAX} m/s). Risco de erosão.',
                'recomendacao': 'Reduzir declividade ou prever dissipadores de energia.'
            }
        else:
            return {
                'status': 'OK',
                'codigo': 'VEL_OK',
                'mensagem': f'Velocidade {velocidade:.2f} m/s dentro dos limites.',
                'recomendacao': None
            }
    
    @staticmethod
    def verificar_froude(froude):
        """
        Verifica o número de Froude.
        
        Retorna:
            dict: Status e mensagem
        """
        if froude < 0.8:
            return {
                'status': 'OK',
                'codigo': 'FR_SUBCRITICO',
                'mensagem': f'Escoamento subcrítico estável (Fr = {froude:.2f}).',
                'regime': 'subcrítico'
            }
        elif 0.8 <= froude < 1.2:
            return {
                'status': 'ALERTA',
                'codigo': 'FR_CRITICO',
                'mensagem': f'Escoamento próximo ao regime crítico (Fr = {froude:.2f}). Evitar esta condição.',
                'regime': 'crítico'
            }
        else:
            return {
                'status': 'ALERTA',
                'codigo': 'FR_SUPERCRITICO',
                'mensagem': f'Escoamento supercrítico (Fr = {froude:.2f}). Verificar ressalto hidráulico.',
                'regime': 'supercrítico'
            }
    
    @staticmethod
    def verificar_lamina(lamina_sobre_diametro):
        """
        Verifica a relação lâmina/diâmetro.
        
        Retorna:
            dict: Status e mensagem
        """
        lamina_perc = lamina_sobre_diametro * 100
        
        if lamina_sobre_diametro < VerificacoesTecnicas.LAMINA_MIN:
            return {
                'status': 'INFO',
                'codigo': 'LAM_BAIXA',
                'mensagem': f'Lâmina d\'água {lamina_perc:.0f}% - capacidade ociosa.',
                'recomendacao': 'Considerar diâmetro menor para otimização.'
            }
        elif lamina_sobre_diametro > VerificacoesTecnicas.LAMINA_MAX:
            return {
                'status': 'ALERTA',
                'codigo': 'LAM_ALTA',
                'mensagem': f'Lâmina d\'água {lamina_perc:.0f}% - próximo à capacidade máxima.',
                'recomendacao': 'Considerar diâmetro maior para segurança.'
            }
        else:
            return {
                'status': 'OK',
                'codigo': 'LAM_OK',
                'mensagem': f'Lâmina d\'água {lamina_perc:.0f}% - adequada.',
                'recomendacao': None
            }
    
    @staticmethod
    def calcular_tensao_trativa(raio_hidraulico, declividade):
        """
        Calcula tensão trativa.
        
        τ = γ * R * S
        
        Parâmetros:
            raio_hidraulico: Raio hidráulico (m)
            declividade: Declividade (m/m)
            
        Retorna:
            float: Tensão trativa (Pa)
        """
        gamma = 9810  # N/m³ (peso específico da água)
        tensao = gamma * raio_hidraulico * declividade
        return tensao
    
    @staticmethod
    def verificar_tensao_trativa(tensao):
        """
        Verifica se a tensão trativa é suficiente para autolimpeza.
        
        Retorna:
            dict: Status e mensagem
        """
        if tensao < VerificacoesTecnicas.TENSAO_TRATIVA_MIN:
            return {
                'status': 'ALERTA',
                'codigo': 'TT_BAIXA',
                'mensagem': f'Tensão trativa {tensao:.2f} Pa insuficiente para autolimpeza.',
                'recomendacao': 'Aumentar declividade.'
            }
        else:
            return {
                'status': 'OK',
                'codigo': 'TT_OK',
                'mensagem': f'Tensão trativa {tensao:.2f} Pa adequada.',
                'recomendacao': None
            }
    
    @staticmethod
    def verificar_area(area_km2):
        """
        Verifica se a área está dentro do limite recomendado para o Método Racional.
        
        Retorna:
            dict: Status e mensagem
        """
        if area_km2 > VerificacoesTecnicas.AREA_LIMITE_RACIONAL:
            return {
                'status': 'ALERTA',
                'codigo': 'AREA_EXCEDENTE',
                'mensagem': f'Área ({area_km2:.2f} km²) excede o limite recomendado de {VerificacoesTecnicas.AREA_LIMITE_RACIONAL} km² para o Método Racional.',
                'recomendacao': 'Considerar o uso do Método de I-Pai-Wu ou Modelagem Hidrológica (SCS/Horton).'
            }
        else:
            return {
                'status': 'OK',
                'codigo': 'AREA_OK',
                'mensagem': f'Área ({area_km2:.2f} km²) adequada para o Método Racional.',
                'recomendacao': None
            }
    
    @staticmethod
    def verificar_completo(resultados):
        """
        Realiza todas as verificações técnicas.
        
        Parâmetros:
            resultados: dict com velocidade, numero_froude, lamina_altura, raio_hidraulico, declividade
            
        Retorna:
            dict: Todas as verificações
        """
        verificacoes = {}
        
        # Velocidade
        verificacoes['velocidade'] = VerificacoesTecnicas.verificar_velocidade(
            resultados['velocidade']
        )
        
        # Froude
        verificacoes['froude'] = VerificacoesTecnicas.verificar_froude(
            resultados['numero_froude']
        )
        
        # Lâmina
        verificacoes['lamina'] = VerificacoesTecnicas.verificar_lamina(
            resultados['lamina_altura']
        )
        
        # Tensão trativa (se dados disponíveis)
        if 'raio_hidraulico' in resultados and 'declividade' in resultados:
            tensao = VerificacoesTecnicas.calcular_tensao_trativa(
                resultados['raio_hidraulico'],
                resultados['declividade']
            )
            verificacoes['tensao_trativa'] = VerificacoesTecnicas.verificar_tensao_trativa(tensao)
            verificacoes['tensao_trativa']['valor'] = tensao
            
        # Área (se disponível)
        if 'area' in resultados:
            verificacoes['area'] = VerificacoesTecnicas.verificar_area(
                resultados['area']
            )
        
        # Status geral
        alertas = sum(1 for v in verificacoes.values() if v['status'] == 'ALERTA')
        if alertas == 0:
            verificacoes['status_geral'] = 'APROVADO'
        elif alertas <= 2:
            verificacoes['status_geral'] = 'APROVADO COM RESSALVAS'
        else:
            verificacoes['status_geral'] = 'REPROVADO'
            
        return verificacoes
    
    @staticmethod
    def gerar_relatorio_verificacoes(verificacoes):
        """
        Gera relatório textual das verificações.
        
        Retorna:
            str: Relatório formatado
        """
        linhas = []
        linhas.append("=" * 60)
        linhas.append("RELATÓRIO DE VERIFICAÇÕES TÉCNICAS")
        linhas.append("=" * 60)
        linhas.append("")
        
        for nome, verif in verificacoes.items():
            if nome in ['status_geral', 'tensao_trativa']:
                # Tensão trativa é tratada em dict específico se necessário, 
                # mas aqui tratamos os itens básicos do loop
                if nome == 'status_geral': continue
                
            status_icon = "✓" if verif['status'] == 'OK' else "⚠" if verif['status'] == 'ALERTA' else "ℹ"
            linhas.append(f"{status_icon} {nome.upper()}: {verif['mensagem']}")
            
            if verif.get('recomendacao'):
                linhas.append(f"   Recomendação: {verif['recomendacao']}")
            linhas.append("")
        
        linhas.append("-" * 60)
        linhas.append(f"STATUS GERAL: {verificacoes.get('status_geral', 'N/A')}")
        linhas.append("=" * 60)
        
        return "\n".join(linhas)
