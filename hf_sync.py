#!/usr/bin/env python3
"""
超大文件同步引擎 (Huge File Sync)
特点：流式上传不爆内存，上传后自动清理防爆硬盘
"""
import os
import time
import logging
from huggingface_hub import HfApi, create_repo

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class HugeFileSync:
    def __init__(self):
        self.hf_token = os.getenv('HF_TOKEN')
        self.dataset_repo = os.getenv('HF_DATASET_REPO', 'large-storage')
        self.local_path = "/app/uploads"
        
        if not self.hf_token:
            logger.error("❌ 未设置 HF_TOKEN 环境变量，无法同步")
            return
            
        self.api = HfApi(token=self.hf_token)
        self._init_repo()
        
        # 忽略的临时文件后缀
        self.ignore_exts = ['.tmp', '.upload', '.part']

    def _init_repo(self):
        try:
            user = self.api.whoami()['name']
            self.full_repo = f"{user}/{self.dataset_repo}"
            create_repo(
                self.full_repo, 
                repo_type="dataset", 
                private=True, 
                exist_ok=True, 
                token=self.hf_token
            )
            logger.info(f"✅ 仓库连接成功: {self.full_repo}")
        except Exception as e:
            logger.error(f"❌ 仓库初始化失败: {e}")

    def is_file_stable(self, file_path):
        """确保文件不是正在被 Cloudreve 写入中"""
        try:
            size1 = os.path.getsize(file_path)
            mtime1 = os.path.getmtime(file_path)
            # 等待10秒检测变化
            time.sleep(10)
            size2 = os.path.getsize(file_path)
            mtime2 = os.path.getmtime(file_path)
            
            # 只有大小不为0，且10秒内完全无变化，才认为上传完成
            return size2 > 0 and size1 == size2 and mtime1 == mtime2
        except:
            return False

    def upload_worker(self):
        if not self.hf_token: return
        logger.info(f"🚀 开始监控: {self.local_path}")
        
        while True:
            processed = False
            for root, dirs, files in os.walk(self.local_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    if file.startswith('.') or any(file.endswith(e) for e in self.ignore_exts):
                        continue
                    
                    if not self.is_file_stable(file_path):
                        continue
                        
                    rel_path = os.path.relpath(file_path, self.local_path)
                    gb_size = os.path.getsize(file_path) / (1024**3)
                    
                    logger.info(f"📦 发现新文件: {rel_path} ({gb_size:.2f} GB)")
                    
                    try:
                        logger.info(f"⬆️ 开始流式上传: {rel_path} ...")
                        # 关键：path_or_fileobj=file_path 触发流式传输
                        self.api.upload_file(
                            path_or_fileobj=file_path,
                            path_in_repo=f"uploads/{rel_path}",
                            repo_id=self.full_repo,
                            repo_type="dataset",
                            token=self.hf_token
                        )
                        logger.info(f"✅ 上传成功: {rel_path}")
                        
                        # 关键：删除本地文件释放磁盘
                        os.remove(file_path)
                        logger.info(f"🗑️ 已清理释放空间: {rel_path}")
                        processed = True
                    except Exception as e:
                        logger.error(f"❌ 上传失败: {e}")
                        time.sleep(10)
            
            if not processed:
                time.sleep(10)

if __name__ == '__main__':
    HugeFileSync().upload_worker()
