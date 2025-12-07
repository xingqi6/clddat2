#!/usr/bin/env python3
"""
超大文件同步引擎 (Huge File Sync)
修复版：
1. 自动识别 Dataset 仓库 ID 格式
2. 支持同步空文件夹 (通过 .gitkeep)
3. 避免反复上传占位文件
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
        
        # 记录已同步的 .gitkeep 文件，防止重复上传
        self.synced_gitkeeps = set()
        
        if not self.hf_token:
            logger.error("❌ 未设置 HF_TOKEN 环境变量，无法同步")
            return
            
        self.api = HfApi(token=self.hf_token)
        self.full_repo = None
        self._init_repo()
        
        # 忽略的临时文件后缀
        self.ignore_exts = ['.tmp', '.upload', '.part']

    def _init_repo(self):
        try:
            if "/" in self.dataset_repo:
                self.full_repo = self.dataset_repo
            else:
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
            self.full_repo = None

    def is_file_stable(self, file_path):
        """确保文件不是正在被 Cloudreve 写入中"""
        try:
            # .gitkeep 不需要检测稳定性
            if file_path.endswith('.gitkeep'):
                return True
                
            size1 = os.path.getsize(file_path)
            mtime1 = os.path.getmtime(file_path)
            time.sleep(5) # 5秒检测
            size2 = os.path.getsize(file_path)
            mtime2 = os.path.getmtime(file_path)
            
            return size2 > 0 and size1 == size2 and mtime1 == mtime2
        except:
            return False

    def ensure_gitkeep(self, root, dirs):
        """
        遍历所有子目录，如果目录下没有 .gitkeep，就创建一个。
        这是为了让 HF/Git 能“感知”到空文件夹的存在。
        """
        for d in dirs:
            dir_path = os.path.join(root, d)
            gitkeep_path = os.path.join(dir_path, ".gitkeep")
            if not os.path.exists(gitkeep_path):
                try:
                    # 创建空文件
                    with open(gitkeep_path, 'w') as f:
                        pass
                    # logger.info(f"📁 创建文件夹占位符: {d}")
                except Exception as e:
                    logger.error(f"无法创建 .gitkeep: {e}")

    def upload_worker(self):
        if not self.hf_token: return
        logger.info(f"🚀 开始监控: {self.local_path}")
        
        while True:
            processed = False
            if not self.full_repo:
                time.sleep(60)
                self._init_repo()
                continue

            for root, dirs, files in os.walk(self.local_path):
                # 1. 确保所有文件夹里都有 .gitkeep
                self.ensure_gitkeep(root, dirs)
                
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.local_path)
                    
                    # 过滤临时文件
                    if file.startswith('.') and file != '.gitkeep': continue
                    if any(file.endswith(e) for e in self.ignore_exts): continue
                    
                    # === 特殊处理 .gitkeep ===
                    if file == '.gitkeep':
                        if rel_path in self.synced_gitkeeps:
                            continue # 已经同步过了，跳过
                        
                        try:
                            # 上传 .gitkeep 以同步文件夹结构
                            self.api.upload_file(
                                path_or_fileobj=file_path,
                                path_in_repo=f"uploads/{rel_path}",
                                repo_id=self.full_repo,
                                repo_type="dataset",
                                token=self.hf_token
                            )
                            # 记录到内存，不删除本地 .gitkeep (0字节不占空间)
                            self.synced_gitkeeps.add(rel_path)
                            # logger.info(f"✅ 同步文件夹结构: {os.path.dirname(rel_path)}")
                        except Exception as e:
                            logger.error(f"❌ 文件夹同步失败: {e}")
                        continue
                    # ========================

                    # 正常文件处理
                    if not self.is_file_stable(file_path):
                        continue
                        
                    gb_size = os.path.getsize(file_path) / (1024**3)
                    logger.info(f"📦 发现新文件: {rel_path} ({gb_size:.2f} GB)")
                    
                    try:
                        logger.info(f"⬆️ 上传中: {rel_path} ...")
                        self.api.upload_file(
                            path_or_fileobj=file_path,
                            path_in_repo=f"uploads/{rel_path}",
                            repo_id=self.full_repo,
                            repo_type="dataset",
                            token=self.hf_token
                        )
                        logger.info(f"✅ 上传成功: {rel_path}")
                        
                        # 删除本地文件释放空间
                        os.remove(file_path)
                        logger.info(f"🗑️ 已清理本地文件")
                        processed = True
                        
                    except Exception as e:
                        logger.error(f"❌ 上传失败: {e}")
                        time.sleep(10)
            
            if not processed:
                time.sleep(5) # 稍微加快轮询频率，提高响应速度

if __name__ == '__main__':
    HugeFileSync().upload_worker()
