#!/bin/sh

set -e

cat >/etc/apt/preferences.d/99experimental <<EOT
Package: *
Pin: release a=experimental
Pin-Priority: 900
EOT

