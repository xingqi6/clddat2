FROM python:3.11-slim

WORKDIR /app

# 安装系统基础依赖
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    sqlite3 \
    openssl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖 (HF库、WebDAV库等)
RUN pip install --no-cache-dir \
    huggingface_hub \
    webdavclient3 \
    schedule \
    requests

# 下载 Cloudreve (V3.8.3 稳定版)
RUN wget https://github.com/cloudreve/Cloudreve/releases/download/3.8.3/cloudreve_3.8.3_linux_amd64.tar.gz && \
    tar -zxvf cloudreve_3.8.3_linux_amd64.tar.gz && \
    rm cloudreve_3.8.3_linux_amd64.tar.gz && \
    chmod +x cloudreve

# 复制当前目录下的所有脚本到容器
COPY hf_sync.py /app/hf_sync.py
COPY backup_manager.py /app/backup_manager.py
COPY storage_policy.py /app/storage_policy.py
COPY startup.sh /app/startup.sh

# 赋予启动脚本执行权限
RUN chmod +x /app/startup.sh

# 暴露端口
EXPOSE 7860

# 挂载卷 (可选，用于本地调试，HF Space会自动处理)
VOLUME /app/uploads

# 启动命令
CMD ["/app/startup.sh"]
