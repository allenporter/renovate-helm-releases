FROM python:3-alpine

RUN pip install --no-cache-dir \
    click==7.1.2 \
    PyYAML==5.4.1

COPY renovate.py /renovate.py

COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "/entrypoint.sh" ]
