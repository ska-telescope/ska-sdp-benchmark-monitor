#!/usr/bin/bash

rm -rf src/api
sphinx-apidoc ../benchmon/ -o ./src/api --module-first --no-toc
