import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
import sys

# get the file of the root project folder, the file run.py

app_folder = Path(__file__).parent.parent.parent.resolve()
folder_logs = app_folder / "logs"

def setup_logger(env, name_process)->tuple[bool, logging.Logger]:

    try:
        name = str(name_process)

        logger = logging.getLogger(name)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] - %(message)s')
        start_server_time = datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')

        if env is not "prod":
            logger.setLevel(logging.DEBUG)

            # Configurar logging para stdout
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)
            
            # Configurar logging para arquivo para erros
            # Se a pasta não existe, criar
            if not folder_logs.exists():
                folder_logs.mkdir()
            file_name = folder_logs / f"{start_server_time}_{name}_errors.log"
            file_handler = RotatingFileHandler(file_name,
                                            maxBytes=1024*1024*5,  # Rola após 5MB
                                            backupCount=7,  # Mantém 7 backups
                                            encoding='utf-8')
            file_handler.setLevel(logging.ERROR)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            if env == None:
                # já incia com uma mensagem critica de que não foi definido o ambiente de execução
                logger.critical(f"[setup_logger] Environment not defined, please define the environment with the argument --env local or --env dev or --env prod in the command line. Ex.: python run.py --env local")

            return True, logger
            
        else:
            logger.setLevel(logging.ERROR)

            # Configurar logging para arquivo para críticos
            # Se a pasta não existe, criar
            if not folder_logs.exists():
                folder_logs.mkdir()
            file_name = folder_logs / f"{start_server_time}_{name}_criticals.log"
            file_handler = RotatingFileHandler(file_name,
                                            maxBytes=1024*1024*5,  # Rola após 5MB
                                            backupCount=7,  # Mantém 7 backups
                                            encoding='utf-8')
            file_handler.setLevel(logging.CRITICAL)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            return True, logger

    except Exception as e:
        error_message = f"[setup_logger] Erro ao configurar o logger: {str(e)}"
        return False, error_message

