import logging
import os
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
 
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__name__)))
 
log = os.path.join(parent_dir,'logs')
os.makedirs(log,exist_ok=True)
 
log_file = os.path.join(log, 'app.log')
 
handler = logging.FileHandler(log_file,encoding='utf-8')
handler.setLevel(logging.DEBUG)
 
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
 
 
logger.addHandler(handler)