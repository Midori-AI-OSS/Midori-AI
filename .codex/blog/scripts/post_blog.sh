#!/bin/bash
# Simulate posting a blog post and remove the .md file

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <postfile.md>"
  exit 1
fi

POSTFILE="$1"

if [ ! -f "$POSTFILE" ]; then
  echo "File $POSTFILE does not exist."
  exit 1
fi

echo "[BLOGGER] Posted blog: $POSTFILE"
rm "$POSTFILE"
echo "[BLOGGER] Removed post file: $POSTFILE"
