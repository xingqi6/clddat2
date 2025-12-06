FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    sqlite3 \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# 下载 Cloudreve
RUN CLOUDREVE_VERSION=$(curl -s https://api.github.com/repos/cloudreve/Cloudreve/releases/latest | grep "tag_name" | cut -d '"' -f 4) && \
    wget https://github.com/cloudreve/Cloudreve/releases/download/${CLOUDREVE_VERSION}/cloudreve_${CLOUDREVE_VERSION}_linux_amd64.tar.gz && \
    tar -zxvf cloudreve_${CLOUDREVE_VERSION}_linux_amd64.tar.gz && \
    rm cloudreve_${CLOUDREVE_VERSION}_linux_amd64.tar.gz && \
    chmod +x cloudreve

# 安装 Python 依赖
RUN pip install --no-cache-dir \
    webdavclient3 \
    schedule \
    huggingface_hub

# 复制脚本
COPY backup_manager.py /app/backup_manager.py
COPY startup.sh /app/startup.sh
RUN chmod +x /app/startup.sh /app/backup_manager.py

# 暴露端口
EXPOSE 7860

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

# 启动应用
CMD ["/app/startup.sh"]
