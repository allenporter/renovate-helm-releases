# Renovate Helm Releases

This script / action adds a [Renovate](https://github.com/renovatebot/renovate) annotation (comment) in [Flux2](https://github.com/fluxcd/flux2) `HelmRelease`'s. 

Combined with a `regexManager` in the `Renovate` config will allow `Renovate` to pick up newer versions of Helm charts.

```yaml
---
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: ingress-nginx-1
  namespace: default
spec:
  interval: 5m
  chart:
    spec:
      # renovate: registryUrl=https://kubernetes.github.io/ingress-nginx
      chart: ingress-nginx
      version: 3.23.0
      sourceRef:
        kind: HelmRepository
        name: ingress-nginx-charts
        namespace: flux-system
      interval: 5m
```

## Workflow example usage

```yaml
uses: k8s-at-home/renovate-helm-releases@v1
with:
  # Path to the folder containing your Flux2 Helm Repositories and Helm Releases
  cluster-path: './cluster'
  # Turn on debug logging
  debug: 'no'
  # Do not alter Helm Release files
  dry-run: 'no'
```

## Script usage example

This script will only work with Python 3

```bash
# install python dependencies
pip install -U -r requirements.txt
# run the script
./renovate.py --cluster-path="./cluster"
```

## Renovate configuration example

Something like the following is needed in order for `Renovate` to pick up `HelmReposistory`'s and `HelmRelease`'s

```jsonc
  "regexManagers": [
    // regexManager to read and process helm repositories
    {
      // tell renovatebot to parse only helm releases
      "fileMatch": ["cluster/.+helm-release\\.yaml$"],
      // tell renovatebot to match the following pattern in helm release files
      "matchStrings": [
        "registryUrl=(?<registryUrl>.*?)\n *chart: (?<depName>.*?)\n *version: (?<currentValue>.*)\n"
      ],
      // tell renovatebot to search helm repositories
      "datasourceTemplate": "helm"
    },
```
