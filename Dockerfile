FROM python:3.11-slim

WORKDIR /app

# ==========================================
# 关键修复：安装 locales 并设置 UTF-8
# 解决中文目录无法创建或写入的问题
# ==========================================
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    sqlite3 \
    openssl \
    ca-certificates \
    locales \
    && rm -rf /var/lib/apt/lists/* \
    && localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8

# 设置环境变量，强制整个环境使用 UTF-8
ENV LANG en_US.utf8
ENV LC_ALL en_US.utf8

# 安装 Python 依赖
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

# 复制脚本
COPY hf_sync.py /app/hf_sync.py
COPY backup_manager.py /app/backup_manager.py
COPY storage_policy.py /app/storage_policy.py
COPY startup.sh /app/startup.sh

# 权限设置
RUN chmod +x /app/startup.sh

# 端口和挂载点
EXPOSE 7860
VOLUME /app/uploads

# 启动
CMD ["/app/startup.sh"]
