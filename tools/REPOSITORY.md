# Publishing Kodi updates

The repository add-on reads `docs/repo/addons.xml` from raw.githubusercontent.com.
GitHub Pages serves only the convenient installation directory from `main:/docs`.
No credentials, paid hosting, or third-party service are required by Kodi.

## Release an update

1. Update the source and bump the version in `script.arr.bridge/addon.xml`.
2. Run `python3 -m unittest discover -s script.arr.bridge/tests -v`.
3. Package `script.arr.bridge/` as `dist/script.arr.bridge-VERSION.zip`, excluding
   `__pycache__`, `.pyc` and user settings. Use exactly one top-level add-on folder.
4. Run `python3 tools/build_repository.py` from the repository checkout.
5. Commit the source, release ZIP and generated `docs/` files together, then push.
6. Check the public feed and ZIP URLs. Kodi detects the changed checksum during
   its next repository check. Users can select Check for updates to refresh sooner.

Never overwrite an already published version. The builder rejects changed bytes
at an existing versioned package path. Preserve older ZIPs for rollback.
The repository add-on is itself included in the feed, so it can receive updates.

The checksum file is an MD5 change marker for Kodi's feed, not a security signature.
GitHub Raw does not supply the Kodi content-sha256 package header, so the repository
sets hashes=false. Downloads use HTTPS; SHA-256 sidecars are provided for independent
package verification. Never treat the change marker as authentication.

## Enable the installation page once

In GitHub Settings → Pages, select Deploy from a branch, main, /docs, then Save.
The installation address is https://wodka78.github.io/kodi-arr-bridge/ once deployed.
This setting cannot be enabled by a normal content-only repository push.
