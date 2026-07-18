#!/bin/bash
# Helper to interact with mud in tmux session 'mud'

tmux send-keys -t mud "$1" C-m
sleep 2 # Wait for processing
# Capture the last ~100 lines of the pane to get output
tmux capture-pane -pS -100 -t mud > /tmp/mud_output.txt
