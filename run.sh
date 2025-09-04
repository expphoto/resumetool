#!/bin/bash
# ResumeTool convenience script
# Usage: ./run.sh wizard
#        ./run.sh analyze resume.pdf
#        ./run.sh discover "software engineer"

source .venv/bin/activate
export PYTHONPATH=src
resumetool "$@"