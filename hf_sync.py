#!/usr/bin/env python3
"""
超大文件同步引擎 (修复版 v3)
1. 强制同步空文件夹 (通过 .gitkeep)
2. 自动识别 Dataset 仓库 ID
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
        
        # 记录已同步的路径，防止重复上传
        self.synced_files = set()
        
        if not self.hf_token:
            logger.error("❌ 未设置 HF_TOKEN，同步停止")
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
            logger.info(f"✅ 仓库连接成功: {self.full_repo}")
        except Exception as e:
            logger.error(f"❌ 仓库初始化失败: {e}")
            self.full_repo = None

    def is_file_stable(self, file_path):
        """文件稳定性检测"""
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
        """统一上传函数"""
        try:
            logger.info(f"⬆️ 上传中: {rel_path}")
            self.api.upload_file(
                path_or_fileobj=file_path,
                path_in_repo=f"uploads/{rel_path}",
                repo_id=self.full_repo,
                repo_type="dataset",
                token=self.hf_token
            )
            # 记录已同步
            self.synced_files.add(rel_path)
            return True
        except Exception as e:
            logger.error(f"❌ 上传失败 {rel_path}: {e}")
            return False

    def upload_worker(self):
        if not self.hf_token: return
        logger.info(f"🚀 开始监控目录: {self.local_path}")
        
        while True:
            processed = False
            if not self.full_repo:
                time.sleep(60)
                self._init_repo()
                continue

            # 遍历本地目录
            for root, dirs, files in os.walk(self.local_path):
                
                # --- 1. 处理文件夹 (创建 .gitkeep) ---
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    gitkeep_path = os.path.join(dir_path, ".gitkeep")
                    
                    # 如果 .gitkeep 不存在，创建它
                    if not os.path.exists(gitkeep_path):
                        try:
                            with open(gitkeep_path, 'w') as f: pass
                            # 手动把这个新文件加入当前循环的 file 列表里不容易，
                            # 所以我们直接在这里触发上传逻辑
                            rel_path = os.path.relpath(gitkeep_path, self.local_path)
                            if rel_path not in self.synced_files:
                                logger.info(f"📁 发现新文件夹，同步结构: {os.path.dirname(rel_path)}")
                                self.upload_file(gitkeep_path, rel_path)
                        except Exception as e:
                            logger.error(f"无法创建占位文件: {e}")

                # --- 2. 处理文件 ---
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.local_path)
                    
                    # 过滤
                    if any(file.endswith(e) for e in self.ignore_exts): continue
                    if file.startswith('.') and file != '.gitkeep': continue

                    # 检查是否已同步过 (.gitkeep 特殊处理，不删除)
                    if file == '.gitkeep':
                        if rel_path not in self.synced_files:
                            self.upload_file(file_path, rel_path)
                        continue
                    
                    # 普通文件稳定性检测
                    if not self.is_file_stable(file_path): continue
                    
                    gb_size = os.path.getsize(file_path) / (1024**3)
                    logger.info(f"📦 发现新文件: {rel_path} ({gb_size:.2f} GB)")
                    
                    # 上传并删除
                    if self.upload_file(file_path, rel_path):
                        logger.info(f"✅ 上传成功: {rel_path}")
                        try:
                            os.remove(file_path)
                            logger.info(f"🗑️ 本地释放: {rel_path}")
                            processed = True
                        except:
                            pass
            
            if not processed:
                time.sleep(5)

if __name__ == '__main__':
    HugeFileSync().upload_worker()
