# Renovate Helm Releases

Creates Renovate annotations in Flux2 Helm Releases

## Inputs

### `cluster-path`

**Required** Path to the folder containing your Flux2 Helm Repositories and Helm Releases

## Example usage

```yaml
uses: k8s-at-home/renovate-helm-releases@v1
with:
  cluster-path: './cluster'
```