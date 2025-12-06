#!/usr/bin/env python3
"""
WebDAV Backup Manager - 配置数据备份与恢复
"""
import os
import sys
import time
import tarfile
import shutil
from datetime import datetime
from pathlib import Path
from webdav3.client import Client
import schedule
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BackupManager:
    def __init__(self):
        self.webdav_url = os.getenv('WEBDAV_URL')
        self.webdav_user = os.getenv('WEBDAV_USERNAME')
        self.webdav_pass = os.getenv('WEBDAV_PASSWORD')
        self.backup_path = os.getenv('WEBDAV_BACKUP_PATH', 'sys_backup')
        self.sync_interval = int(os.getenv('SYNC_INTERVAL', '3600'))
        self.max_backups = 5
        
        # 需要备份的配置目录和文件
        self.backup_dirs = [
            '/app/conf',
            '/app/uploads/.thumbs',
        ]
        self.backup_files = [
            '/app/cloudreve.db',
            '/app/conf.ini',
        ]
        
        # 初始化 WebDAV 客户端
        self.client = Client({
            'webdav_hostname': self.webdav_url,
            'webdav_login': self.webdav_user,
            'webdav_password': self.webdav_pass,
            'webdav_timeout': 300
        })
        
        self._ensure_backup_dir()
    
    def _ensure_backup_dir(self):
        """确保备份目录存在"""
        try:
            if not self.client.check(self.backup_path):
                self.client.mkdir(self.backup_path)
                logger.info(f"创建备份目录: {self.backup_path}")
        except Exception as e:
            logger.error(f"创建备份目录失败: {e}")
    
    def create_backup(self):
        """创建备份"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"backup_{timestamp}.tar.gz"
            local_backup = f"/tmp/{backup_name}"
            
            logger.info("开始创建备份...")
            
            # 创建 tar.gz 备份
            with tarfile.open(local_backup, "w:gz") as tar:
                for dir_path in self.backup_dirs:
                    if os.path.exists(dir_path):
                        tar.add(dir_path, arcname=os.path.basename(dir_path))
                        logger.info(f"已添加目录: {dir_path}")
                
                for file_path in self.backup_files:
                    if os.path.exists(file_path):
                        tar.add(file_path, arcname=os.path.basename(file_path))
                        logger.info(f"已添加文件: {file_path}")
            
            # 上传到 WebDAV
            remote_path = f"{self.backup_path}/{backup_name}"
            self.client.upload_sync(remote_path=remote_path, local_path=local_backup)
            logger.info(f"备份已上传: {remote_path}")
            
            # 清理本地临时文件
            os.remove(local_backup)
            
            # 清理旧备份
            self._cleanup_old_backups()
            
            return True
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            return False
    
    def restore_backup(self):
        """恢复最新的备份"""
        try:
            logger.info("开始恢复备份...")
            
            # 获取所有备份文件
            backups = self._list_backups()
            if not backups:
                logger.warning("没有找到备份文件")
                return False
            
            # 使用最新的备份
            latest_backup = backups[-1]
            remote_path = f"{self.backup_path}/{latest_backup}"
            local_backup = f"/tmp/{latest_backup}"
            
            logger.info(f"下载备份: {latest_backup}")
            self.client.download_sync(remote_path=remote_path, local_path=local_backup)
            
            # 解压备份
            logger.info("解压备份文件...")
            with tarfile.open(local_backup, "r:gz") as tar:
                tar.extractall(path="/app")
            
            # 清理临时文件
            os.remove(local_backup)
            
            logger.info("备份恢复完成")
            return True
        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return False
    
    def _list_backups(self):
        """列出所有备份文件"""
        try:
            files = self.client.list(self.backup_path)
            backups = [f for f in files if f.startswith('backup_') and f.endswith('.tar.gz')]
            return sorted(backups)
        except Exception as e:
            logger.error(f"列出备份失败: {e}")
            return []
    
    def _cleanup_old_backups(self):
        """清理旧备份，保留最新的 5 份"""
        try:
            backups = self._list_backups()
            if len(backups) <= self.max_backups:
                return
            
            # 删除多余的旧备份
            to_delete = backups[:-self.max_backups]
            for backup in to_delete:
                remote_path = f"{self.backup_path}/{backup}"
                self.client.clean(remote_path)
                logger.info(f"已删除旧备份: {backup}")
        except Exception as e:
            logger.error(f"清理旧备份失败: {e}")
    
    def run_scheduler(self):
        """运行定时备份"""
        logger.info(f"启动定时备份，间隔: {self.sync_interval} 秒")
        
        # 立即执行一次备份
        self.create_backup()
        
        # 设置定时任务
        schedule.every(self.sync_interval).seconds.do(self.create_backup)
        
        while True:
            schedule.run_pending()
            time.sleep(60)

def main():
    # 检查必要的环境变量
    required_vars = ['WEBDAV_URL', 'WEBDAV_USERNAME', 'WEBDAV_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"缺少必要的环境变量: {', '.join(missing_vars)}")
        sys.exit(1)
    
    manager = BackupManager()
    
    # 如果存在备份，先恢复
    if manager._list_backups():
        logger.info("发现现有备份，开始恢复...")
        manager.restore_backup()
    else:
        logger.info("未发现备份，这是首次运行")
    
    # 运行定时备份
    manager.run_scheduler()

if __name__ == '__main__':
    main()
