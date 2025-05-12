#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Web scraper para a plataforma Supreme Posta.
Coleta dados e envia para o Google BigQuery.
"""

import os
import time
from pathlib import Path
from typing import Optional
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from dotenv import load_dotenv
from google.cloud.bigquery import Client, LoadJobConfig
from google.cloud import bigquery
from functools import wraps
from time import sleep

load_dotenv()

LOGIN_URL = "https://afiliado.supremaposta.com/login"
REPORT_TYPES = [
    "Relatório de Mídia",
    "Relatório de Registros",
    "Relatório de Ganhos",
    "Relatório de atividades"
]

REPORT_FILE_MAPPING = {
    'Relatório de Mídia': 'midia.csv',
    'Relatório de Registros': 'registros.csv',
    'Relatório de Ganhos': 'ganhos.csv',
    'Relatório de atividades': 'atividades.csv'
}

TABLE_MAPPING = {
    'midia.csv': 'midia',
    'registros.csv': 'registros',
    'ganhos.csv': 'ganhos',
    'atividades.csv': 'atividades'
}

LOGS_DIR = Path("/app/logs")
TEMP_DIR = Path("/tmp/scraper")
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
DATASET_ID = os.getenv("BQ_DATASET_ID")
TABLE_PREFIX = "relatorio_"

LOGS_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

logger.add(
    LOGS_DIR / "scraper_{time}.log",
    rotation="1 day",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

def retry_on_error(max_attempts: int = 3, delay: int = 5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt + 1 < max_attempts:
                        sleep(delay)
                    continue
            logger.error(f"Todas as {max_attempts} tentativas falharam para {func.__name__}")
            raise last_exception
        return wrapper
    return decorator

@retry_on_error(max_attempts=5, delay=5)
def setup_bigquery() -> Optional[Client]:
    try:
        return bigquery.Client(project=PROJECT_ID)
    except Exception as e:
        logger.error(f"Falha ao configurar BigQuery: {e}")
        raise

@retry_on_error(max_attempts=5, delay=5)
def setup_browser() -> Optional[webdriver.Chrome]:
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        prefs = {
            "download.default_directory": str(TEMP_DIR),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True
        }
        options.add_experimental_option("prefs", prefs)
        options.binary_location = "/usr/bin/chromium"
        return webdriver.Chrome(options=options)
    except Exception as e:
        logger.error(f"Falha ao configurar navegador: {e}")
        raise

@retry_on_error(max_attempts=5, delay=5*60)
def login(driver: webdriver.Chrome) -> bool:
    try:
        driver.get(LOGIN_URL)
        wait = WebDriverWait(driver, 10)
        
        username_field = wait.until(EC.presence_of_element_located((By.NAME, "user")))
        username_field.send_keys(os.getenv("USERNAME"))
        
        password_field = driver.find_element(By.NAME, "password")
        password_field.send_keys(os.getenv("PASSWORD"))
        
        login_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "submit-btn")))
        driver.execute_script("arguments[0].click();", login_button)
        
        wait.until(EC.presence_of_element_located((By.ID, "mobileToggle")))
        logger.info("Login realizado com sucesso")
        return True
    except Exception as e:
        logger.error(f"Falha no login: {e}")
        raise

def new_file_downloaded(driver, existing_files):
    try:
        current_files = set(f for f in os.listdir(TEMP_DIR) if f.endswith('.csv'))
        new_files = current_files - existing_files
        
        if not new_files:
            return False
            
        # Wait for file to be completely downloaded (no .tmp or .crdownload)
        downloading_files = [f for f in os.listdir(TEMP_DIR) if f.endswith(('.tmp', '.crdownload'))]
        if downloading_files:
            return False
            
        # Get the newest file
        newest_file = max([os.path.join(TEMP_DIR, f) for f in new_files], key=os.path.getctime)
        
        # Check if file size is stable (download completed)
        size1 = os.path.getsize(newest_file)
        time.sleep(1)
        size2 = os.path.getsize(newest_file)
        
        return size1 == size2 and size1 > 0
    except (FileNotFoundError, OSError):
        return False

def rename_downloaded_file(report_type: str) -> Optional[str]:
    try:
        csv_files = [f for f in os.listdir(TEMP_DIR) if f.endswith('.csv')]
        if not csv_files:
            logger.error("Nenhum arquivo CSV encontrado para renomear")
            return None
            
        latest_file = max([os.path.join(TEMP_DIR, f) for f in csv_files], key=os.path.getctime)
        new_filename = REPORT_FILE_MAPPING[report_type]
        new_filepath = os.path.join(TEMP_DIR, new_filename)
        
        if os.path.exists(new_filepath):
            os.remove(new_filepath)
            
        os.rename(latest_file, new_filepath)
        return new_filename
    except Exception as e:
        logger.error(f"Erro ao renomear arquivo: {e}")
        return None

@retry_on_error(max_attempts=5, delay=1*15)
def download_single_report(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    report_type: str,
    date_range: str
) -> bool:
    try:
        existing_files = set(f for f in os.listdir(TEMP_DIR) if f.endswith('.csv'))
        
        report_link = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.LINK_TEXT, report_type))
        )
        report_link.click()
        
        select_element = wait.until(EC.presence_of_element_located((By.TAG_NAME, "select")))
        Select(select_element).select_by_visible_text(date_range)
        
        generate_button = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Gerar relatório')]"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", generate_button)
        driver.execute_script("arguments[0].click();", generate_button)
        
        # Wait for data to be generated
        time.sleep(2)
        
        export_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Exportar relatório')]")
        if not export_buttons:
            logger.info(f"Nenhum dado disponível para {report_type}")
            return navigate_back_to_reports(driver, wait)
        
        export_button = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Exportar relatório')]"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", export_button)
        driver.execute_script("arguments[0].click();", export_button)
        
        # Wait for file to be downloaded with a longer timeout
        download_wait = WebDriverWait(driver, 2*60)
        try:
            download_wait.until(lambda x: new_file_downloaded(x, existing_files))
            logger.info(f"Download concluído para {report_type}")
        except Exception as e:
            logger.error(f"Timeout aguardando download do arquivo para {report_type}: {e}")
            return False
        
        # Additional wait to ensure file is ready
        time.sleep(2)
        
        if not rename_downloaded_file(report_type):
            logger.error(f"Falha ao renomear arquivo para {report_type}")
            return False
            
        return navigate_back_to_reports(driver, wait)
        
    except TimeoutException as e:
        logger.error(f"Timeout ao baixar {report_type}: {e}")
        raise
    except Exception as e:
        logger.error(f"Erro ao baixar {report_type}: {e}")
        raise

def navigate_back_to_reports(driver: webdriver.Chrome, wait: WebDriverWait) -> bool:
    try:
        # Scroll to top first
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)  # Let the scroll complete
        
        # Find and click mobile toggle
        mobile_toggle = wait.until(
            EC.element_to_be_clickable((By.ID, "mobileToggle"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", mobile_toggle)
        time.sleep(0.5)  # Let the scroll complete
        mobile_toggle.click()
        
        # Find and click reports link
        reports_link = wait.until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Relatórios"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", reports_link)
        time.sleep(0.5)  # Let the scroll complete
        reports_link.click()
        
        return True
    except Exception as e:
        logger.error(f"Erro ao navegar de volta para relatórios: {e}")
        return False

def download_reports(driver: webdriver.Chrome, date_range: str = "Ontem") -> bool:
    wait = WebDriverWait(driver, 10)
    
    driver.find_element(By.ID, "mobileToggle").click()
    driver.find_element(By.LINK_TEXT, "Relatórios").click()
    
    for report_type in REPORT_TYPES:
        if not download_single_report(driver, wait, report_type, date_range):
            return False
    
    return True

@retry_on_error(max_attempts=5, delay=30)
def process_and_upload_to_bigquery(bq_client: Client) -> bool:
    try:
        found_files = set(f for f in os.listdir(TEMP_DIR) if f.endswith('.csv'))
        
        if not found_files:
            logger.info("Nenhum arquivo para processar")
            return True
        
        for csv_file in found_files:
            if csv_file not in TABLE_MAPPING:
                logger.warning(f"Arquivo não mapeado encontrado: {csv_file}")
                continue
                
            table_name = TABLE_MAPPING[csv_file]
            table_id = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_PREFIX}{table_name}"
            csv_path = os.path.join(TEMP_DIR, csv_file)
            
            logger.info(f"Processando {csv_file}")
            
            df = pd.read_csv(csv_path, dtype=str)
            schema = [bigquery.SchemaField(col, "STRING") for col in df.columns]
            parquet_file = TEMP_DIR / f"{table_name}.parquet"
            
            table = pa.Table.from_pandas(df)
            pq.write_table(table, parquet_file)
            
            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.PARQUET,
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                schema=schema
            )
            
            with open(parquet_file, "rb") as source_file:
                load_job = bq_client.load_table_from_file(
                    source_file,
                    table_id,
                    job_config=job_config
                )
                load_job.result()
            
            logger.info(f"Arquivo {csv_file} enviado para BigQuery")
            os.remove(csv_path)
            parquet_file.unlink()
        
        return True
    except Exception as e:
        logger.error(f"Erro ao processar arquivos: {e}")
        raise

def cleanup(driver: Optional[webdriver.Chrome], temp_dir: Path) -> None:
    try:
        if driver:
            driver.quit()
        
        for file in temp_dir.glob("*"):
            file.unlink()
        temp_dir.rmdir()
    except Exception as e:
        logger.error(f"Erro durante limpeza: {e}")

def main() -> None:
    driver = None
    bq_client = None
    try:
        logger.info("Iniciando processo")
        
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
        
        logger.info("Processo concluído com sucesso")
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        raise
    finally:
        cleanup(driver, TEMP_DIR)

if __name__ == "__main__":
    main() 
