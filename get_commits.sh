#!/bin/bash

# This file pulls all commits from our repos and puts them into a log txt file for each repo.
# The goal is to have a `blogger` mode codex come and make blogposts with the date for each day.
# We are also going to try to have this run on a action (once a day) for the mono repo.
# Maybe we could also add Meta, Discord, and Linkedin posting too.

find .codex/blog/ -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rvf {} +

clear

echo "Pulling github commits for blogger"

run_date="$(date +%F)"
output_dir=".codex/blog/$run_date"
mkdir -p "$output_dir"

find . -type d -name ".git" | while read gitdir; do
  repo_dir="$(dirname "$gitdir")"
  file_name="$(echo "$repo_dir" | sed 's|^\./||; s|/|_|g')_commits.txt"
  commits=$(git --git-dir="$gitdir" --work-tree="$repo_dir" log -n 100 --pretty=format:"%h %ad %s" --date=short)
  if echo "$commits" | grep -q "$run_date"; then
    {
      echo "Commits for $repo_dir:"
      echo "$commits"
    } > "$output_dir/$file_name"
  else
    {
      echo "Commits for $repo_dir:"
      echo "No work has been done today."
    } > "$output_dir/$file_name"
  fi
  
done

echo "All done pulling commits"
echo "Check `$output_dir` for more info..."
