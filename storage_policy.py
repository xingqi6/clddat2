#!/usr/bin/env python3
"""
存储策略配置
1. 优化分片大小 (5MB)
2. 修正命名规则 (去除随机前缀，保持原文件名)
"""
import os
import json
import sqlite3
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_policy():
    db_path = '/app/cloudreve.db'
    
    for _ in range(120):
        if os.path.exists(db_path): break
        time.sleep(1)
    
    if not os.path.exists(db_path):
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 5MB 分片，且启用 auto_rename 防止冲突
        policy_options = json.dumps({
            'sys_path': '/app/uploads/{uid}/{path}',
            'chunk_size': 5242880
        })
        
        # =======================================================
        # 关键修改：file_name_rule 改为 '{originname}'
        # 这样上传到 Dataset 的文件名就是干净的
        # =======================================================
        cursor.execute('''
            INSERT OR REPLACE INTO policies (
                id, name, type, max_size, options, 
                dir_name_rule, file_name_rule, auto_rename, is_origin_link_enable
            ) VALUES (
                1, 'Local Storage (Clean Name)', 'local', 
                10995116277760, ?, 
                'uploads/{uid}/{date}', '{originname}', 
                1, 0
            )
        ''', (policy_options,))
        
        cursor.execute("UPDATE groups SET policy_list=? WHERE id IN (1, 2)", (json.dumps([1]),))
        
        conn.commit()
        conn.close()
        logger.info("✅ 存储策略更新: 5MB分片 + 原文件名存储")
        
    except Exception as e:
        logger.error(f"❌ 策略配置失败: {e}")

if __name__ == '__main__':
    setup_policy()
