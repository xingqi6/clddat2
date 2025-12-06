#!/usr/bin/env python3
import os
import json
import sqlite3
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_policy():
    db_path = '/app/cloudreve.db'
    
    # 等待数据库生成
    for _ in range(60):
        if os.path.exists(db_path): break
        time.sleep(1)
    
    if not os.path.exists(db_path):
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 配置本机存储策略：10TB 容量
        policy_options = json.dumps({'sys_path': '/app/uploads/{uid}/{path}'})
        
        # 强制覆盖 ID=1 的策略
        cursor.execute('''
            INSERT OR REPLACE INTO policies (
                id, name, type, max_size, options, 
                dir_name_rule, file_name_rule, auto_rename, is_origin_link_enable
            ) VALUES (
                1, 'Local (Sync to HF)', 'local', 
                10995116277760, ?, 
                'uploads/{uid}/{date}', '{originname}', 
                1, 0
            )
        ''', (policy_options,))
        
        # 应用到用户组
        cursor.execute("UPDATE groups SET policy_list=? WHERE id IN (1, 2)", (json.dumps([1]),))
        
        conn.commit()
        conn.close()
        logger.info("✅ 存储策略已修正为：本机存储 (10TB)")
        
    except Exception as e:
        logger.error(f"❌ 策略配置失败: {e}")

if __name__ == '__main__':
    setup_policy()
