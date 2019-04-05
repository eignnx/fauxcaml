#!/bin/bash

fauxcaml_root={{}}

if ! [[ $VIRTUAL_ENV ]]
then
    source "${fauxcaml_root}/venv/bin/activate"
fi

PYTHONPATH=$fauxcaml_root python -m fauxcaml "$@"

