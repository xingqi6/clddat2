#!/usr/bin/env python3
"""
超大文件同步引擎 (稳定性优化版)
1. 增加上传间隔 (防止 I/O 占满导致 Cloudreve 无响应)
2. 强制同步空文件夹
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
        self.synced_files = set()
        
        if not self.hf_token:
            logger.error("❌ 未设置 HF_TOKEN")
            return
            
        self.api = HfApi(token=self.hf_token)
        self.full_repo = None
        self._init_repo()
        
        self.ignore_exts = ['.tmp', '.upload', '.part']

    def _init_repo(self):
        try:
            if "/" in self.dataset_repo:
                self.full_repo = self.dataset_repo
            else:
                user = self.api.whoami()['name']
                self.full_repo = f"{user}/{self.dataset_repo}"
            
            create_repo(
                self.full_repo, repo_type="dataset", private=True, exist_ok=True, token=self.hf_token
            )
            logger.info(f"✅ 仓库连接: {self.full_repo}")
        except Exception as e:
            logger.error(f"❌ 仓库连接失败: {e}")
            self.full_repo = None

    def is_file_stable(self, file_path):
        if file_path.endswith('.gitkeep'): return True
        try:
            size1 = os.path.getsize(file_path)
            mtime1 = os.path.getmtime(file_path)
            time.sleep(5)
            size2 = os.path.getsize(file_path)
            mtime2 = os.path.getmtime(file_path)
            return size2 > 0 and size1 == size2 and mtime1 == mtime2
        except:
            return False

    def upload_file(self, file_path, rel_path):
        try:
            logger.info(f"⬆️ 上传中: {rel_path}")
            self.api.upload_file(
                path_or_fileobj=file_path,
                path_in_repo=f"uploads/{rel_path}",
                repo_id=self.full_repo,
                repo_type="dataset",
                token=self.hf_token
            )
            self.synced_files.add(rel_path)
            
            # === 关键优化：上传完一个文件后休息 1 秒 ===
            # 让出 I/O 资源给 Cloudreve 主程序，防止前端请求超时
            time.sleep(1) 
            return True
        except Exception as e:
            logger.error(f"❌ 上传失败 {rel_path}: {e}")
            return False

    def upload_worker(self):
        if not self.hf_token: return
        logger.info(f"🚀 同步服务启动: {self.local_path}")
        
        while True:
            processed = False
            if not self.full_repo:
                time.sleep(60)
                self._init_repo()
                continue

            for root, dirs, files in os.walk(self.local_path):
                # 处理文件夹
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    gitkeep_path = os.path.join(dir_path, ".gitkeep")
                    if not os.path.exists(gitkeep_path):
                        try:
                            with open(gitkeep_path, 'w') as f: pass
                            rel_path = os.path.relpath(gitkeep_path, self.local_path)
                            if rel_path not in self.synced_files:
                                self.upload_file(gitkeep_path, rel_path)
                        except: pass

                # 处理文件
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.local_path)
                    
                    if any(file.endswith(e) for e in self.ignore_exts): continue
                    if file.startswith('.') and file != '.gitkeep': continue

                    # .gitkeep 特殊处理
                    if file == '.gitkeep':
                        if rel_path not in self.synced_files:
                            self.upload_file(file_path, rel_path)
                        continue
                    
                    if not self.is_file_stable(file_path): continue
                    
                    gb_size = os.path.getsize(file_path) / (1024**3)
                    logger.info(f"📦 新文件: {rel_path} ({gb_size:.2f} GB)")
                    
                    if self.upload_file(file_path, rel_path):
                        logger.info(f"✅ 完成: {rel_path}")
                        try:
                            os.remove(file_path)
                            logger.info(f"🗑️ 已清理")
                            processed = True
                        except: pass
            
            if not processed:
                time.sleep(5)

if __name__ == '__main__':
    HugeFileSync().upload_worker()
