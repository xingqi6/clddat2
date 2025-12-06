#!/usr/bin/env python3
"""
Hugging Face Datasets 存储适配器
将上传的文件存储到 Datasets 而不是本地磁盘
"""
import os
import sys
from pathlib import Path
from huggingface_hub import HfApi, create_repo, upload_file, hf_hub_download
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatasetStorage:
    def __init__(self):
        self.hf_token = os.getenv('HF_TOKEN')
        self.dataset_repo = os.getenv('HF_DATASET_REPO', 'storage-data')
        self.api = HfApi(token=self.hf_token)
        
        # 确保 dataset 存在
        self._ensure_dataset()
    
    def _ensure_dataset(self):
        """确保 dataset 仓库存在"""
        try:
            full_repo = f"{self.api.whoami()['name']}/{self.dataset_repo}"
            create_repo(
                full_repo,
                repo_type="dataset",
                private=True,
                exist_ok=True,
                token=self.hf_token
            )
            logger.info(f"Dataset 仓库已准备: {full_repo}")
        except Exception as e:
            logger.error(f"创建 dataset 失败: {e}")
    
    def upload_file(self, local_path, remote_path):
        """上传文件到 Datasets"""
        try:
            full_repo = f"{self.api.whoami()['name']}/{self.dataset_repo}"
            
            upload_file(
                path_or_fileobj=local_path,
                path_in_repo=remote_path,
                repo_id=full_repo,
                repo_type="dataset",
                token=self.hf_token
            )
            
            logger.info(f"文件已上传: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"上传文件失败: {e}")
            return False
    
    def download_file(self, remote_path, local_path):
        """从 Datasets 下载文件"""
        try:
            full_repo = f"{self.api.whoami()['name']}/{self.dataset_repo}"
            
            downloaded = hf_hub_download(
                repo_id=full_repo,
                filename=remote_path,
                repo_type="dataset",
                token=self.hf_token,
                local_dir=os.path.dirname(local_path)
            )
            
            logger.info(f"文件已下载: {remote_path}")
            return downloaded
        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            return None
    
    def delete_file(self, remote_path):
        """删除 Datasets 中的文件"""
        try:
            full_repo = f"{self.api.whoami()['name']}/{self.dataset_repo}"
            
            self.api.delete_file(
                path_in_repo=remote_path,
                repo_id=full_repo,
                repo_type="dataset",
                token=self.hf_token
            )
            
            logger.info(f"文件已删除: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False
    
    def list_files(self, path_prefix=""):
        """列出 Datasets 中的文件"""
        try:
            full_repo = f"{self.api.whoami()['name']}/{self.dataset_repo}"
            
            files = self.api.list_repo_files(
                repo_id=full_repo,
                repo_type="dataset",
                token=self.hf_token
            )
            
            if path_prefix:
                files = [f for f in files if f.startswith(path_prefix)]
            
            return files
        except Exception as e:
            logger.error(f"列出文件失败: {e}")
            return []

# 文件系统钩子 - 拦截 Cloudreve 的文件操作
class DatasetFileSystemHook:
    def __init__(self):
        self.storage = DatasetStorage()
        self.cache_dir = "/tmp/cache"
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def intercept_write(self, filepath, data):
        """拦截文件写入操作"""
        # 写入临时缓存
        cache_path = os.path.join(self.cache_dir, os.path.basename(filepath))
        with open(cache_path, 'wb') as f:
            f.write(data)
        
        # 上传到 Datasets
        remote_path = filepath.replace('/app/uploads/', '')
        self.storage.upload_file(cache_path, remote_path)
        
        # 清理缓存
        os.remove(cache_path)
    
    def intercept_read(self, filepath):
        """拦截文件读取操作"""
        remote_path = filepath.replace('/app/uploads/', '')
        cache_path = os.path.join(self.cache_dir, os.path.basename(filepath))
        
        # 从 Datasets 下载到缓存
        downloaded = self.storage.download_file(remote_path, cache_path)
        
        if downloaded:
            with open(downloaded, 'rb') as f:
                return f.read()
        
        return None

if __name__ == '__main__':
    # 测试存储功能
    storage = DatasetStorage()
    print("Datasets 存储适配器已初始化")
