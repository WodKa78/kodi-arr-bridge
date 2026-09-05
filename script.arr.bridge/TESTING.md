# Validation record — 0.1.1

Date: 2026-09-05. Target device setup: Kodi 22.0 beta, Arctic Fuse 2. Target Arr APIs: Radarr v3 API and Sonarr 4's v3 API.

## Completed here

- **42 automated tests passed** using Python 3.12, with Kodi UI doubles and a local HTTP test server.
- Verified GET/POST paths, URL-base handling, `X-Api-Key` headers, payload propagation, duplicate checks, duplicate races, authentication failures, invalid JSON, refused redirects and no automatic POST retry after a timeout.
- Verified TMDb Helper movie/episode URLs, parent-series ID handling, local library episode-to-series resolution, explicit-ID isolation, and match confirmation when exact identifiers are unavailable.
- Verified form cancellation makes no add call, successful confirmation passes the selected options through, missing profiles block the add, and API failures do not show success.
- Verified monitoring and selected-season request payloads, including specials exclusion when not selected and no search when monitoring is disabled.
- Parsed Python source and add-on/settings/dialog XML. Checked dialog control IDs.
- Checked representative movie/series payload field names, JSON types, enum values and external-ID GET filters against the official Radarr/Sonarr OpenAPI documents retrieved for this build. This is not a live server compatibility test.
- Applied the AF2 insertion to the actual inspected upstream `Includes_Items.xml`, parsed the result, and removed the insertion to recover the exact original text. Tested idempotence, unsupported layouts, and ID collisions.
- Packaged the ZIP with one top-level `script.arr.bridge` directory, excluding Python caches and development research files.

## Remaining device acceptance test

Kodi is not installed in this build environment and the user's Arr servers are not connected. Installation, visual layout, remote focus behavior and real server additions are **not yet verified**. The test doubles do not emulate Kodi's skin renderer or all Kodi 22 beta API behavior.

On the target setup:

1. Install the ZIP, enter server settings, and run the read-only connection tests.
2. Search a movie in TMDb Helper. Open **Add to Radarr / Sonarr**, verify profiles/folders load, then cancel. Confirm no movie was added.
3. Reopen the dialog and add a wanted movie with search off. Verify its quality profile, folder, tags and monitoring in Radarr. Repeat the add and verify the duplicate message.
4. Select a show and add it with selected seasons and search off. Verify series type, folder and monitored seasons in Sonarr.
5. Enable the AF2 information button. Open information for both a movie and a series from a home widget, TMDb Helper search and the Kodi library. Verify the displayed title and external ID before adding.
6. Open information for an episode and verify the add form refers to its parent series. If that series already exists, expect an Already added message.
7. If wanted, test Search after adding on one wanted title. Check the Arr application's Activity/History for the resulting search.
8. Remove the AF2 button and verify the original action bar remains intact. Restore the backup manually only if necessary.

If a test fails, report the exact Kodi build, AF2 version, Radarr/Sonarr versions, where the selected item came from, and the on-screen error. Do not share API keys or unredacted settings files.

## 0.1.1 settings fix

Added an explicit Save settings / Cancel form and a native settings shortcut to it. Added tests for cancellation without writes, successful persistence, validation before writes, and rollback after a failed write. Kodi UI rendering still requires device verification.
