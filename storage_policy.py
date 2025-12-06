#!/usr/bin/env python3
"""
存储策略配置模块
用于配置 Cloudreve 将文件存储到 Datasets
"""
import os
import json
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StoragePolicyManager:
    def __init__(self, db_path='/app/cloudreve.db'):
        self.db_path = db_path
        self.hf_token = os.getenv('HF_TOKEN')
        self.dataset_repo = os.getenv('HF_DATASET_REPO', 'storage-data')
    
    def init_storage_policy(self):
        """初始化存储策略，配置使用 Datasets"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建存储策略表（如果不存在）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS policies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    max_size INTEGER DEFAULT 0,
                    file_type TEXT DEFAULT '[]',
                    options TEXT DEFAULT '{}',
                    auto_rename INTEGER DEFAULT 0,
                    dir_name_rule TEXT DEFAULT 'uploads/{uid}/{path}',
                    file_name_rule TEXT DEFAULT '{uid}_{randomkey8}_{originname}',
                    is_origin_link_enable INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 检查是否已存在 Datasets 策略
            cursor.execute("SELECT id FROM policies WHERE name='Datasets Storage'")
            existing = cursor.fetchone()
            
            if not existing:
                # 创建 Datasets 存储策略
                policy_options = json.dumps({
                    'hf_token': self.hf_token,
                    'dataset_repo': self.dataset_repo,
                    'chunk_size': 5242880,  # 5MB chunks for large files
                    'max_parallel': 3,
                    'retry_count': 3
                })
                
                cursor.execute('''
                    INSERT INTO policies (
                        name, type, max_size, options, 
                        dir_name_rule, file_name_rule
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    'Datasets Storage',
                    'remote',
                    107374182400,  # 100GB max
                    policy_options,
                    'uploads/{uid}/{date}',
                    '{originname}'
                ))
                
                logger.info("已创建 Datasets 存储策略")
            
            # 设置为默认存储策略
            policy_id = existing[0] if existing else cursor.lastrowid
            cursor.execute('''
                UPDATE settings 
                SET option_value=? 
                WHERE option_name='default_policy'
            ''', (str(policy_id),))
            
            conn.commit()
            conn.close()
            
            logger.info(f"存储策略已配置: ID={policy_id}")
            return True
            
        except Exception as e:
            logger.error(f"配置存储策略失败: {e}")
            return False
    
    def configure_large_file_handling(self):
        """配置大文件处理参数"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建设置表（如果不存在）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    option_name TEXT UNIQUE NOT NULL,
                    option_value TEXT NOT NULL
                )
            ''')
            
            # 大文件配置项
            large_file_settings = {
                'max_size': '10737418240',  # 10GB per file
                'chunk_size': '5242880',     # 5MB chunks
                'max_parallel': '3',         # 3 parallel uploads
                'timeout': '3600',           # 1 hour timeout
                'auto_retry': 'true',
                'retry_count': '3',
                'buffer_size': '1048576'     # 1MB buffer
            }
            
            for key, value in large_file_settings.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (option_name, option_value)
                    VALUES (?, ?)
                ''', (key, value))
            
            conn.commit()
            conn.close()
            
            logger.info("大文件处理配置已完成")
            return True
            
        except Exception as e:
            logger.error(f"配置大文件处理失败: {e}")
            return False
    
    def setup(self):
        """执行完整的存储配置"""
        logger.info("开始配置存储策略...")
        
        # 等待数据库文件创建
        import time
        for i in range(30):
            if os.path.exists(self.db_path):
                break
            time.sleep(1)
        
        if not os.path.exists(self.db_path):
            logger.error("数据库文件未找到")
            return False
        
        # 执行配置
        self.init_storage_policy()
        self.configure_large_file_handling()
        
        logger.info("存储策略配置完成")
        return True

if __name__ == '__main__':
    manager = StoragePolicyManager()
    manager.setup()
