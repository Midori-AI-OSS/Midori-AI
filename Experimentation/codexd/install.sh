#!/usr/bin/env sh
set -eu

cat >/usr/local/bin/codexd <<'EOF'
#!/usr/bin/env sh
export UV_PROJECT_ENVIRONMENT=/tmp/midoriai/codexd
export UV_COMPILE_BYTECODE=1
exec uv run --project "/home/lunamidori/nfs/Midori-AI-Github/Midori-AI-Mono-Repo/Experimentation/codexd" codexd "$@"
EOF

chmod 0755 /usr/local/bin/codexd
