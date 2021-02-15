FROM python:3-alpine

RUN pip install --no-cache-dir \
    click==7.1.2 \
    ruamel.yaml==0.16.12

COPY renovate.py /app

COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "/entrypoint.sh" ]
