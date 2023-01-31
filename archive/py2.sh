#!/bin/bash
filepath=$1
func=$2
python -c "from $filepath import $func; $func()"
