#!/usr/bin/env python3
"""
System Core Sync Service
"""
import os
import time
import logging
import re
from huggingface_hub import HfApi, create_repo

# 隐蔽日志：只记录错误，平时保持安静
logging.basicConfig(
    level=logging.ERROR, 
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CoreService:
    def __init__(self):
        self.token = os.getenv('HF_TOKEN')
        self.repo = os.getenv('HF_DATASET_REPO', 'storage-data')
        self.path = "/app/uploads"
        self.synced = set()
        
        if not self.token: return
            
        self.api = HfApi(token=self.token)
        self.full_repo = None
        self._init_conn()
        
        self.skip = ['.tmp', '.upload', '.part']

    def _init_conn(self):
        try:
            if "/" in self.repo:
                self.full_repo = self.repo
            else:
                user = self.api.whoami()['name']
                self.full_repo = f"{user}/{self.repo}"
            
            create_repo(self.full_repo, repo_type="dataset", private=True, exist_ok=True, token=self.token)
        except:
            self.full_repo = None

    def _clean_name(self, filename):
        """
        核心修复：清洗文件名
        Cloudreve 格式通常为: {uid}_{random8}_{origin}
        例如: 1_SMVjPXWe_photo.jpg -> photo.jpg
        """
        # 正则匹配：数字开头 + 下划线 + 8位随机字符 + 下划线
        clean = re.sub(r'^\d+_[a-zA-Z0-9]{8}_', '', filename)
        return clean

    def is_stable(self, path):
        if path.endswith('.gitkeep'): return True
        try:
            s1 = os.path.getsize(path)
            t1 = os.path.getmtime(path)
            time.sleep(2) # 缩短检测时间提高响应
            s2 = os.path.getsize(path)
            t2 = os.path.getmtime(path)
            return s1 > 0 and s1 == s2 and t1 == t2
        except:
            return False

    def push(self, local_f, rel_path):
        try:
            # 1. 计算清洗后的远程路径
            # rel_path 可能是 "1/NewFolder/1_SMVjPXWe_photo.jpg"
            # 我们需要把文件名部分洗掉
            dir_name = os.path.dirname(rel_path)
            file_name = os.path.basename(rel_path)
            clean_file_name = self._clean_name(file_name)
            
            # 最终的远程路径: uploads/1/NewFolder/photo.jpg
            remote_path = f"uploads/{os.path.join(dir_name, clean_file_name)}"

            self.api.upload_file(
                path_or_fileobj=local_f,
                path_in_repo=remote_path,
                repo_id=self.full_repo,
                repo_type="dataset",
                token=self.token
            )
            self.synced.add(rel_path)
            time.sleep(0.5) 
            return True
        except:
            return False

    def run(self):
        if not self.token: return
        
        while True:
            processed = False
            if not self.full_repo:
                time.sleep(30)
                self._init_conn()
                continue

            for root, dirs, files in os.walk(self.path):
                # 隐藏文件处理 (.gitkeep)
                for d in dirs:
                    d_path = os.path.join(root, d)
                    kp = os.path.join(d_path, ".gitkeep")
                    if not os.path.exists(kp):
                        try:
                            with open(kp, 'w') as f: pass
                            rp = os.path.relpath(kp, self.path)
                            if rp not in self.synced: self.push(kp, rp)
                        except: pass

                for file in files:
                    fp = os.path.join(root, file)
                    rp = os.path.relpath(fp, self.path)
                    
                    if any(file.endswith(e) for e in self.skip): continue
                    if file.startswith('.') and file != '.gitkeep': continue

                    if file == '.gitkeep':
                        if rp not in self.synced: self.push(fp, rp)
                        continue
                    
                    if not self.is_stable(fp): continue
                    
                    # 上传并删除
                    if self.push(fp, rp):
                        try:
                            os.remove(fp)
                            processed = True
                        except: pass
            
            if not processed:
                time.sleep(3)

if __name__ == '__main__':
    CoreService().run()
