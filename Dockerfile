FROM python:3-alpine

LABEL "name"="Renovate Helm Releases"
LABEL "maintainer"="Devin Buhl <devin.kray@gmail.com>, Bernd Schorgers <me@bjw-s.dev>"

LABEL "com.github.actions.name"="Renovate Helm Releases"
LABEL "com.github.actions.description"="Creates Renovate annotations in Flux2 Helm Releases"
LABEL "com.github.actions.icon"="send"
LABEL "com.github.actions.color"="blue"

# Meta note: Need a way to rennovate this
ENV KUSTOMIZE_VERSION=4.0.5

RUN apk add --no-cache curl

RUN curl -sLf https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv${KUSTOMIZE_VERSION}/kustomize_v${KUSTOMIZE_VERSION}_linux_amd64.tar.gz -o kustomize.tar.gz\
    && tar xf kustomize.tar.gz \
    && mv kustomize /usr/local/bin \
    && chmod +x /usr/local/bin/kustomize \
    && rm -rf kustomize.tar.gz

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

COPY renovate.py /app/renovate.py

COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "/entrypoint.sh" ]
