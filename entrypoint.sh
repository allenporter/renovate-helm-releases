#!/bin/sh -l

CLUSTER_PATH="${1}"
DEBUG="${2}"
DRY_RUN="${3}"

if [ "${DEBUG}" = "yes" ]; then
    DEBUG="--debug"
else
    DEBUG=""
fi

if [ "${DRY_RUN}" = "yes" ]; then
    DRY_RUN="--dry-run"
else
    DRY_RUN=""
fi

# /usr/local/bin/python /app/renovate.py --cluster-path="${CLUSTER_PATH}" ${DEBUG} ${DRY_RUN}

python renovate.py --cluster-path="${CLUSTER_PATH}" ${DEBUG} ${DRY_RUN}