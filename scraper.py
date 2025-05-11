#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Web scraper para a plataforma Supreme Posta.
Coleta dados e envia para o Google BigQuery.
"""

import os
import time
from pathlib import Path
from typing import Optional, List
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
from google.cloud.bigquery import Client, LoadJobConfig
from google.cloud import bigquery
from functools import wraps
from time import sleep

load_dotenv()

# Constantes
LOGIN_URL = "https://afiliado.supremaposta.com/login"
REPORT_TYPES = [
    "Relatório de Mídia",
    "Relatório de Registros",
    "Relatório de Ganhos",
    "Relatório de atividades"
]

TABLE_MAPPING = {
    'data.csv': 'midia',           # Arquivo data.csv vai para tabela mídia
    'data (1).csv': 'registros',   # Arquivo data (1).csv vai para tabela registros
    'data (2).csv': 'ganhos',      # Arquivo data (2).csv vai para tabela ganhos
    'data (3).csv': 'atividades'   # Arquivo data (3).csv vai para tabela atividades
}

LOGS_DIR = Path("/app/logs")
TEMP_DIR = Path("/tmp/scraper")

# Criar diretórios necessários
LOGS_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

# Configurações do BigQuery
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
DATASET_ID = os.getenv("BQ_DATASET_ID")
TABLE_PREFIX = "relatorio_"

logger.add(
    LOGS_DIR / "scraper_{time}.log",
    rotation="1 day",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

def retry_on_error(max_attempts: int = 3, delay: int = 5):
    """
    Decorador para realizar retentativas em caso de erro.
    
    Args:
        max_attempts: Número máximo de tentativas
        delay: Tempo de espera entre tentativas em segundos
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    remaining_attempts = max_attempts - attempt - 1
                    logger.warning(
                        f"Tentativa {attempt + 1} falhou para {func.__name__}: {str(e)}. "
                        f"Tentativas restantes: {remaining_attempts}"
                    )
                    if remaining_attempts > 0:
                        sleep(delay)
                    continue
            
            logger.error(
                f"Todas as {max_attempts} tentativas falharam para {func.__name__}. "
                f"Último erro: {str(last_exception)}"
            )
            return False
        return wrapper
    return decorator

@retry_on_error(max_attempts=5, delay=5)
def setup_bigquery() -> Optional[Client]:
    """Inicializa e retorna um cliente BigQuery."""
    try:
        client = bigquery.Client(project=PROJECT_ID)
        return client
    except Exception as e:
        logger.error(f"Falha ao configurar cliente BigQuery: {e}")
        raise

@retry_on_error(max_attempts=5, delay=5)
def setup_browser() -> Optional[webdriver.Chrome]:
    """Inicializa e retorna um navegador Chrome configurado."""
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        
        # Configurar diretório de download
        prefs = {
            "download.default_directory": str(TEMP_DIR),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True
        }
        options.add_experimental_option("prefs", prefs)
        
        # Usar navegador Chromium local
        options.binary_location = "/usr/bin/chromium"
        driver = webdriver.Chrome(options=options)
        return driver
    except Exception as e:
        logger.error(f"Falha ao configurar navegador: {e}")
        raise

@retry_on_error(max_attempts=5, delay=5*60)
def login(driver: webdriver.Chrome) -> bool:
    """Realiza o login na plataforma."""
    try:
        driver.get(LOGIN_URL)
        wait = WebDriverWait(driver, 10)
        
        username_field = wait.until(
            EC.presence_of_element_located((By.NAME, "user"))
        )
        username_field.send_keys(os.getenv("USERNAME"))
        
        password_field = driver.find_element(By.NAME, "password")
        password_field.send_keys(os.getenv("PASSWORD"))
        
        login_button = wait.until(
            EC.element_to_be_clickable((By.CLASS_NAME, "submit-btn"))
        )
        driver.execute_script("arguments[0].click();", login_button)
        
        wait.until(EC.presence_of_element_located((By.ID, "mobileToggle")))
        logger.info("Login realizado com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"Falha no login: {e}")
        raise

def download_reports(driver: webdriver.Chrome, date_range: str = "Ontem") -> bool:
    """Baixa todos os relatórios disponíveis."""
    try:
        wait = WebDriverWait(driver, 10)
        
        driver.find_element(By.ID, "mobileToggle").click()
        time.sleep(0.5)
        driver.find_element(By.LINK_TEXT, "Relatórios").click()
        time.sleep(0.5)
        
        for report_type in REPORT_TYPES:
            if not download_single_report(driver, wait, report_type, date_range):
                return False
        
        logger.info("Todos os relatórios foram baixados com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao baixar relatórios: {e}")
        return False

@retry_on_error(max_attempts=5, delay=1*60)
def download_single_report(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    report_type: str,
    date_range: str
) -> bool:
    """Baixa um tipo específico de relatório."""
    try:
        driver.find_element(By.LINK_TEXT, report_type).click()
        time.sleep(0.5)
        
        select = Select(driver.find_element(By.TAG_NAME, "select"))
        select.select_by_visible_text(date_range)
        
        generate_button = next(
            (btn for btn in driver.find_elements(By.TAG_NAME, "button")
             if btn.text.startswith('G')),
            None
        )
        if not generate_button:
            raise ValueError(f"Botão de geração não encontrado para {report_type}")
        
        generate_button.click()
        time.sleep(1)
        
        export_button = wait.until(
            lambda d: next(
                (btn for btn in d.find_elements(By.TAG_NAME, "button")
                 if btn.text.startswith('E') and btn.is_enabled()),
                None
            )
        )
        export_button.click()
        time.sleep(10)
        
        driver.find_element(By.ID, "mobileToggle").click()
        time.sleep(0.5)
        driver.find_element(By.LINK_TEXT, "Relatórios").click()
        time.sleep(0.5)
        
        logger.info(f"Relatório {report_type} baixado com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao baixar {report_type}: {e}")
        raise

@retry_on_error(max_attempts=5, delay=30)
def process_and_upload_to_bigquery(bq_client: Client) -> bool:
    """Processa arquivos CSV baixados e envia para o BigQuery."""
    try:
        csv_files = list(TEMP_DIR.glob("data*.csv"))
        
        if len(csv_files) != 4:
            raise ValueError(f"Esperados 4 arquivos CSV, encontrados {len(csv_files)}")
        
        # Ordenar arquivos para garantir a ordem correta
        csv_files.sort()
        
        for i, csv_file in enumerate(csv_files):
            # Usar o mapeamento correto para as tabelas
            table_name = TABLE_MAPPING[csv_file.name]
            table_id = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_PREFIX}{table_name}"
            
            logger.info(f"Processando arquivo {csv_file.name} para tabela {table_name}")
            
            # Ler CSV para DataFrame, forçando todos os campos como string
            df = pd.read_csv(csv_file, dtype=str)
            
            # Criar schema com todos os campos como STRING
            schema = [bigquery.SchemaField(col, "STRING") for col in df.columns]
            
            # Converter para formato Parquet
            parquet_file = TEMP_DIR / f"{table_name}.parquet"
            
            # Converter para PyArrow Table - o pandas já mantém os tipos string
            table = pa.Table.from_pandas(df)
            
            # Salvar em formato Parquet
            pq.write_table(table, parquet_file)
            
            # Configurar job de carregamento com schema explícito
            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.PARQUET,
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                schema=schema  # Define explicitamente todos os campos como STRING
            )
            
            # Carregar dados para o BigQuery
            with open(parquet_file, "rb") as source_file:
                load_job = bq_client.load_table_from_file(
                    source_file,
                    table_id,
                    job_config=job_config
                )
                load_job.result()
            
            logger.info(f"Arquivo {csv_file.name} enviado para {table_id}")
            
            # Limpar arquivos temporários
            csv_file.unlink()
            parquet_file.unlink()
        
        return True
        
    except Exception as e:
        logger.error(f"Erro ao processar e enviar arquivos: {e}")
        raise

def cleanup(driver: Optional[webdriver.Chrome], temp_dir: Path) -> None:
    """Limpa recursos utilizados."""
    try:
        if driver:
            driver.quit()
        
        # Limpar diretório temporário
        for file in temp_dir.glob("*"):
            file.unlink()
        temp_dir.rmdir()
            
    except Exception as e:
        logger.error(f"Erro durante limpeza: {e}")

def main() -> None:
    """Ponto de entrada principal da aplicação."""
    driver = None
    bq_client = None
    try:
        logger.info("Iniciando processo de coleta de dados")
        
        driver = setup_browser()
        if not driver:
            return
            
        bq_client = setup_bigquery()
        if not bq_client:
            return
        
        if not login(driver):
            return
        
        if not download_reports(driver):
            return
        
        if not process_and_upload_to_bigquery(bq_client):
            return
        
        logger.info("Coleta e envio de dados concluídos com sucesso")
        
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        raise
        
    finally:
        cleanup(driver, TEMP_DIR)

if __name__ == "__main__":
    main() 

