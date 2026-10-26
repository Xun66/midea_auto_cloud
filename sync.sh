#!/usr/bin/env bash
# Rebuild custom_components/ from an upstream release + patches/*.patch.
# Usage: ./sync.sh [TAG]   (default: upstream's latest release; FORCE=1 rebuilds the same tag)
set -euo pipefail
UPSTREAM=sususweet/midea_auto_cloud
tag=${1:-$(gh api "repos/$UPSTREAM/releases/latest" -q .tag_name)}
if [ "$tag" = "$(cat UPSTREAM_VERSION 2>/dev/null || true)" ] && [ -z "${FORCE:-}" ]; then
  echo "already at $tag"; exit 0
fi
tmp=$(mktemp -d)
curl -fsSL "https://github.com/$UPSTREAM/archive/refs/tags/$tag.tar.gz" | tar -xz -C "$tmp" --strip-components=1
rm -rf custom_components
cp -r "$tmp/custom_components" .
cp "$tmp/LICENSE" "$tmp/hacs.json" .
for p in patches/*.patch; do
  echo "applying $p"
  git apply --whitespace=nowarn "$p"   # fails (and so does the workflow) if upstream changed the patched lines
done
echo "$tag" > UPSTREAM_VERSION
echo "tag=$tag" >> "${GITHUB_OUTPUT:-/dev/null}"
