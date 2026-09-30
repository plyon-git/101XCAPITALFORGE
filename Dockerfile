FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/capitalforge
RUN groupadd --gid 10001 capitalforge && useradd --uid 10001 --gid capitalforge --create-home capitalforge
COPY --chown=capitalforge:capitalforge . .
RUN mkdir -p /var/lib/capitalforge && chown capitalforge:capitalforge /var/lib/capitalforge
USER capitalforge
ENV CAPITALFORGE_HOST=0.0.0.0 CAPITALFORGE_PORT=8787 CAPITALFORGE_DATA_DIR=/var/lib/capitalforge
VOLUME ["/var/lib/capitalforge"]
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/api/status',timeout=4).read()"
CMD ["python", "app.py"]
