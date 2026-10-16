#!/bin/sh
# Install the latency check as a pre-commit step without overwriting any existing hook.
set -e
root="$(git rev-parse --show-toplevel)"
hooks="$(git rev-parse --git-path hooks)"
case "$hooks" in /*) ;; *) hooks="$root/$hooks" ;; esac
dir="$hooks/pre-commit.d"
mkdir -p "$dir"
if [ ! -e "$hooks/pre-commit" ]; then
  cat > "$hooks/pre-commit" <<'DISPATCH'
#!/bin/sh
# run every executable in pre-commit.d/ in name order
dir="$(dirname "$0")/pre-commit.d"
[ -d "$dir" ] || exit 0
for h in "$dir"/*; do
  [ -f "$h" ] && [ -x "$h" ] || continue
  "$h" "$@" || exit $?
done
exit 0
DISPATCH
  chmod +x "$hooks/pre-commit"
fi
cp "$root/scripts/hooks/latency_check.sh" "$dir/10-latency"
chmod +x "$dir/10-latency"
echo "installed $dir/10-latency"
