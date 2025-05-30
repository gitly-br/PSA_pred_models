#!/bin/bash

# Define the path to the SSH key
SSH_KEY="/keys/psa_models.dev.pri"

# Check if the SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo "SSH key not found at $SSH_KEY."
    exit 1
fi

# Navigate to the /source directory
cd /source

# Check if the cd command was successful
if [ $? -ne 0 ]; then
    echo "Failed to navigate to /source. Directory does not exist."
    exit 1
fi

echo "==============================[update]==============================" 

# Perform a git pull with rebase using the specified SSH key
GIT_SSH_COMMAND="ssh -i $SSH_KEY -o IdentitiesOnly=yes" git pull --rebase

# Check if the git pull command was successful
if [ $? -ne 0 ]; then
    echo "Failed to pull and rebase the repository."
    exit 1
fi

echo "Successfully pulled and rebased the repository."
