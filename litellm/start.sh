echo "Starting litellm on port 4000. tail -f nohup.out"

# Ensure Python loads sitecustomize.py in this directory (auto-imports rag_callback)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Script " $SCRIPT_DIR
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH}"
echo $PYTHONPATH
litellm --config "${SCRIPT_DIR}/config.yaml" --port 4000 --debug