#!/usr/bin/env bash
# Downloads the headless Linux build of StarCraft II and the map packs into /root/StarCraftII.
#
# The archives are protected with the password "iagreetotheeula". Supplying it means
# accepting Blizzard's AI and Machine Learning License:
#   https://blzdistsc2-a.akamaihd.net/AI_AND_MACHINE_LEARNING_LICENSE.html
#
# Inputs (environment): SC2_VERSION, MAP_PACKS (space separated), SC2_SHA256 (optional).
# Downloads are kept in /var/cache/sc2 (a BuildKit cache mount), so rebuilding the image
# does not fetch the 4 GB archive again.
set -euo pipefail

: "${SC2_VERSION:?SC2_VERSION is required}"
MAP_PACKS="${MAP_PACKS:-}"
SC2_SHA256="${SC2_SHA256:-}"

CACHE_DIR=/var/cache/sc2
BASE_URL=https://blzdistsc2-a.akamaihd.net
ARCHIVE_PASSWORD=iagreetotheeula
INSTALL_DIR=/root/StarCraftII

mkdir -p "${CACHE_DIR}"

# fetch <url> <destination>: resumable download, skipped when already complete.
fetch() {
    local url=$1 dest=$2
    if [ -f "${dest}.complete" ]; then
        echo "cached: ${dest}"
        return
    fi
    echo "downloading: ${url}"
    curl --fail --location --silent --show-error \
        --retry 5 --retry-delay 5 --continue-at - \
        --output "${dest}" "${url}"
    touch "${dest}.complete"
}

game_zip="${CACHE_DIR}/SC2.${SC2_VERSION}.zip"
fetch "${BASE_URL}/Linux/SC2.${SC2_VERSION}.zip" "${game_zip}"

echo "sha256 of SC2.${SC2_VERSION}.zip: $(sha256sum "${game_zip}" | cut -d' ' -f1)"
if [ -n "${SC2_SHA256}" ]; then
    echo "${SC2_SHA256}  ${game_zip}" | sha256sum --check --strict -
fi

unzip -q -P "${ARCHIVE_PASSWORD}" "${game_zip}" -d /root

# Not needed for API-driven headless games.
rm -rf "${INSTALL_DIR}/Battle.net/"* "${INSTALL_DIR}"/Versions/Shaders*

mkdir -p "${INSTALL_DIR}/Maps"
for pack in ${MAP_PACKS}; do
    pack_zip="${CACHE_DIR}/${pack}.zip"
    fetch "${BASE_URL}/MapPacks/${pack}.zip" "${pack_zip}"
    unzip -q -o -P "${ARCHIVE_PASSWORD}" "${pack_zip}" -d "${INSTALL_DIR}/Maps"
done

# python-sc2 prefers a lowercase "maps" directory on Linux.
ln -sfn "${INSTALL_DIR}/Maps" "${INSTALL_DIR}/maps"

echo "installed maps:"
find "${INSTALL_DIR}/Maps/" -name '*.SC2Map' | sort
