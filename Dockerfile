FROM python:3.11-slim

WORKDIR /app

# 安装环境和编译工具
RUN apt-get update && apt-get install -y \
    wget curl sqlite3 openssl ca-certificates locales binutils \
    && rm -rf /var/lib/apt/lists/* \
    && localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8

ENV LANG en_US.utf8
ENV LC_ALL en_US.utf8

# 安装依赖 + PyInstaller
RUN pip install --no-cache-dir \
    huggingface_hub webdavclient3 schedule requests pyinstaller

# 下载 Cloudreve
RUN wget https://github.com/cloudreve/Cloudreve/releases/download/3.8.3/cloudreve_3.8.3_linux_amd64.tar.gz && \
    tar -zxvf cloudreve_3.8.3_linux_amd64.tar.gz && \
    rm cloudreve_3.8.3_linux_amd64.tar.gz && \
    chmod +x cloudreve

# 复制源码
COPY hf_sync.py /app/hf_sync.py
COPY backup_manager.py /app/backup_manager.py
COPY storage_policy.py /app/storage_policy.py
COPY startup.sh /app/startup.sh

# =========================================================
# 混淆与编译步骤
# =========================================================
# 1. 编译 Python 脚本为二进制文件
RUN pyinstaller --onefile --name sys_core hf_sync.py && \
    pyinstaller --onefile --name sys_daemon backup_manager.py && \
    pyinstaller --onefile --name sys_init storage_policy.py

# 2. 将编译好的二进制文件移动到 /app
RUN mv dist/sys_core /app/sys_core && \
    mv dist/sys_daemon /app/sys_daemon && \
    mv dist/sys_init /app/sys_init

# 3. 删除源代码和编译垃圾 (清理现场)
RUN rm -rf build dist *.spec *.py __pycache__

# 4. 赋予权限
RUN chmod +x /app/startup.sh /app/sys_core /app/sys_daemon /app/sys_init

EXPOSE 7860
VOLUME /app/uploads

CMD ["/app/startup.sh"]
