FROM python:3.9-alpine

WORKDIR /app

COPY requirements.txt renovate.py /app/

RUN apk add --no-cache bash curl tini procps jq ca-certificates \
    && pip install -r requirements.txt

ENTRYPOINT [ "/sbin/tini", "--"]
CMD [ "renovate.py" ]
