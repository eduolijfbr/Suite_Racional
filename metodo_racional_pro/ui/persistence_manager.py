# -*- coding: utf-8 -*-
"""
Gerenciador de Persistência para o Plugin Método Racional Pro
Centraliza operações de salvamento e carregamento de dados no projeto QGIS
"""

from qgis.core import QgsProject
import json


class PersistenceManager:
    """Gerencia persistência de dados no projeto QGIS"""
    
    PREFIX = 'MetodoRacionalPro'
    
    @staticmethod
    def save(key: str, value) -> None:
        """
        Salva valor no projeto QGIS.
        
        Args:
            key: Chave única para identificar o dado
            value: Valor a ser salvo (str, int, float, bool, dict, list)
        """
        projeto = QgsProject.instance()
        full_key = f"{PersistenceManager.PREFIX}_{key}"
        
        if isinstance(value, (dict, list)):
            # Serializar estruturas complexas como JSON
            projeto.writeEntry(PersistenceManager.PREFIX, full_key, json.dumps(value, ensure_ascii=False))
        elif isinstance(value, bool):
            projeto.writeEntryBool(PersistenceManager.PREFIX, full_key, value)
        elif isinstance(value, int):
            projeto.writeEntryNum(PersistenceManager.PREFIX, full_key, value)
        elif isinstance(value, float):
            projeto.writeEntryDouble(PersistenceManager.PREFIX, full_key, value)
        else:
            projeto.writeEntry(PersistenceManager.PREFIX, full_key, str(value) if value is not None else '')
    
    @staticmethod
    def load(key: str, default=None, value_type=str):
        """
        Carrega valor do projeto QGIS.
        
        Args:
            key: Chave única do dado
            default: Valor padrão se não encontrado
            value_type: Tipo esperado (str, int, float, bool, dict, list)
            
        Returns:
            Valor carregado ou default
        """
        projeto = QgsProject.instance()
        full_key = f"{PersistenceManager.PREFIX}_{key}"
        
        if value_type == bool:
            value, ok = projeto.readBoolEntry(PersistenceManager.PREFIX, full_key, default if default is not None else False)
        elif value_type == int:
            value, ok = projeto.readNumEntry(PersistenceManager.PREFIX, full_key, default if default is not None else 0)
        elif value_type == float:
            value, ok = projeto.readDoubleEntry(PersistenceManager.PREFIX, full_key, default if default is not None else 0.0)
        elif value_type in (dict, list):
            str_value, ok = projeto.readEntry(PersistenceManager.PREFIX, full_key, '')
            if ok and str_value:
                try:
                    value = json.loads(str_value)
                except json.JSONDecodeError:
                    value = default
            else:
                value = default
            return value
        else:
            value, ok = projeto.readEntry(PersistenceManager.PREFIX, full_key, default if default is not None else '')
        
        return value if ok else default
    
    @staticmethod
    def save_calculation(calc_id: str, data: dict) -> None:
        """
        Salva cálculo completo com todos os dados de entrada e resultados.
        
        Args:
            calc_id: Identificador único do cálculo
            data: Dicionário com dados de entrada e resultados
        """
        PersistenceManager.save(f"calc_{calc_id}", data)
    
    @staticmethod
    def load_calculation(calc_id: str) -> dict:
        """
        Carrega cálculo completo.
        
        Args:
            calc_id: Identificador único do cálculo
            
        Returns:
            Dicionário com dados do cálculo ou None
        """
        return PersistenceManager.load(f"calc_{calc_id}", default=None, value_type=dict)
    
    @staticmethod
    def save_idf_state(state: dict) -> None:
        """
        Salva estado do dialog IDF.
        
        Args:
            state: Dicionário com estado do IDF (cidade, TR, duração, intensidade, tabela)
        """
        PersistenceManager.save("idf_state", state)
    
    @staticmethod
    def load_idf_state() -> dict:
        """
        Carrega estado do dialog IDF.
        
        Returns:
            Dicionário com estado salvo ou None
        """
        return PersistenceManager.load("idf_state", default=None, value_type=dict)
    
    @staticmethod
    def save_main_dialog_state(state: dict) -> None:
        """
        Salva estado do dialog principal.
        
        Args:
            state: Dicionário com valores dos campos de entrada e resultados
        """
        PersistenceManager.save("main_dialog_state", state)
    
    @staticmethod
    def load_main_dialog_state() -> dict:
        """
        Carrega estado do dialog principal.
        
        Returns:
            Dicionário com estado salvo ou None
        """
        return PersistenceManager.load("main_dialog_state", default=None, value_type=dict)
    
    @staticmethod
    def save_lock_state(is_locked: bool, original_data: dict = None) -> None:
        """
        Salva estado de bloqueio e dados originais bloqueados.
        
        Args:
            is_locked: Se o cálculo está bloqueado
            original_data: Dados originais para preservar durante bloqueio
        """
        PersistenceManager.save("is_locked", is_locked)
        if original_data is not None:
            PersistenceManager.save("locked_original_data", original_data)
    
    @staticmethod
    def load_lock_state() -> tuple:
        """
        Carrega estado de bloqueio.
        
        Returns:
            Tupla (is_locked, original_data)
        """
        is_locked = PersistenceManager.load("is_locked", default=False, value_type=bool)
        original_data = PersistenceManager.load("locked_original_data", default=None, value_type=dict)
        return is_locked, original_data
    
    @staticmethod
    def save_impermeability_state(state: dict) -> None:
        """
        Salva estado do dialog de impermeabilidade.
        
        Args:
            state: Dicionário com estado da impermeabilidade
        """
        PersistenceManager.save("impermeability_state", state)
    
    @staticmethod
    def load_impermeability_state() -> dict:
        """
        Carrega estado do dialog de impermeabilidade.
        
        Returns:
            Dicionário com estado salvo ou None
        """
        return PersistenceManager.load("impermeability_state", default=None, value_type=dict)
    
    @staticmethod
    def clear_all() -> None:
        """Remove todos os dados persistentes do plugin."""
        projeto = QgsProject.instance()
        # O QGIS não tem método direto para remover entradas,
        # então salvamos valores vazios
        keys_to_clear = [
            "main_dialog_state",
            "idf_state", 
            "is_locked",
            "locked_original_data",
            "impermeability_state",
            "camadas_config"
        ]
        for key in keys_to_clear:
            PersistenceManager.save(key, None)
    
    @staticmethod
    def save_feature_data(feature_id: str, layer_name: str, data: dict) -> None:
        """
        Salva dados específicos de uma feição.
        
        Args:
            feature_id: ID da feição
            layer_name: Nome da camada
            data: Dicionário com dados de entrada e resultados
        """
        # Criar chave única combinando camada e feature ID
        key = f"feature_{layer_name}_{feature_id}"
        PersistenceManager.save(key, data)
    
    @staticmethod
    def load_feature_data(feature_id: str, layer_name: str) -> dict:
        """
        Carrega dados específicos de uma feição.
        
        Args:
            feature_id: ID da feição
            layer_name: Nome da camada
            
        Returns:
            Dicionário com dados salvos ou None
        """
        key = f"feature_{layer_name}_{feature_id}"
        return PersistenceManager.load(key, default=None, value_type=dict)
    
    @staticmethod
    def get_current_feature_id(layer) -> str:
        """
        Obtém ID único da(s) feição(ões) selecionada(s).
        
        Args:
            layer: Camada QGIS
            
        Returns:
            String com ID(s) ou None se nenhuma seleção
        """
        if layer is None:
            return None
        
        selected = layer.selectedFeatures()
        if not selected:
            # Se não há seleção, usar todas as feições
            all_features = [f for f in layer.getFeatures()]
            if all_features:
                feature_ids = sorted([str(f.id()) for f in all_features])
                return "_".join(feature_ids)
            return None
        
        # Usar IDs das feições selecionadas (ordenados para consistência)
        feature_ids = sorted([str(f.id()) for f in selected])
        return "_".join(feature_ids)

