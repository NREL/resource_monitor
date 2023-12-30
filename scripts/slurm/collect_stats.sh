#!/bin/bash

module load mamba
mamba activate my_env

# Start collecting stats as a background operation.
rmon collect \
    --name=$(hostname) \
    --interval=3 \
    --cpu \
    --disk \
    --memory \
    --network \
    --plots \
    --overwrite &

# Wait until the parent process creates the file shutdown.
while ! [ -f shutdown ];
do
    sleep 5
done

# This will inform rmon to stop collection, make plots, and shut down.
for pid in $(pgrep -f "rmon collect");
do
    kill -TERM ${pid}
done

while [ $(pgrep -f "rmon collect") ];
do
    sleep 1
done

mamba deactivate
