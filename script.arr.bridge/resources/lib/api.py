"""Arr v3 API transport. No Kodi imports and no third-party dependencies."""
import copy
import json
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler


class ArrError(Exception):
    pass


class AlreadyExists(ArrError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward API credentials to a redirected server/login portal.
        return None


def api_base(url):
    p = urlsplit(url.strip())
    if p.scheme not in ('http', 'https') or not p.hostname:
        raise ArrError('Enter a full http:// or https:// server URL in settings.')
    if p.username or p.password or p.query or p.fragment:
        raise ArrError('Use a server URL without embedded credentials, query or fragment.')
    path = p.path.rstrip('/')
    if not path.endswith('/api/v3'):
        path += '/api/v3'
    return urlunsplit((p.scheme, p.netloc, path, '', ''))


class ArrClient:
    def __init__(self, url, key, kind, timeout=20):
        self.base = api_base(url)
        self.key = key.strip()
        self.kind = kind
        self.resource = 'movie' if kind == 'radarr' else 'series'
        self.id_key = 'tmdbId' if kind == 'radarr' else 'tvdbId'
        self.timeout = max(3, min(int(timeout), 120))
        if not self.key:
            raise ArrError('Set the {} API key in add-on settings.'.format(kind.title()))
        self.opener = build_opener(NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))

    def request(self, path, params=None, payload=None):
        url = self.base + '/' + path.lstrip('/')
        if params:
            url += '?' + urlencode(params)
        headers = {'X-Api-Key': self.key, 'Accept': 'application/json'}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        req = Request(url, data=data, headers=headers, method='POST' if data is not None else 'GET')
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                raw = response.read()
            return json.loads(raw.decode('utf-8')) if raw else None
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise ArrError('Authentication refused. Check the API key and reverse-proxy access.') from None
            if 300 <= exc.code < 400:
                raise ArrError('Server redirected the request. Set its final URL and URL base in settings.') from None
            # Inspect error codes without displaying/logging arbitrary response content.
            raw = exc.read(65536).decode('utf-8', 'replace')
            if exc.code == 409 or (exc.code == 400 and any(
                    code in raw for code in ('MovieExistsValidator', 'SeriesExistsValidator'))):
                raise AlreadyExists('This title is already in {}.'.format(self.kind.title())) from None
            raise ArrError('{} returned HTTP {}. Check its logs and selected options.'.format(
                self.kind.title(), exc.code)) from None
        except (URLError, socket.timeout, TimeoutError, OSError):
            suffix = ' The add may have completed; check the server before retrying.' if data else ''
            raise ArrError('Cannot reach {}. Check address, connection and HTTPS certificate.{}'.format(
                self.kind.title(), suffix)) from None
        except (ValueError, UnicodeError):
            raise ArrError('Server returned invalid JSON. Check the URL base and reverse proxy.') from None

    def lookup(self, term):
        result = self.request(self.resource + '/lookup', {'term': term})
        if not isinstance(result, list):
            raise ArrError('Unexpected lookup response from the server.')
        return result

    def existing(self, external_id):
        # Both APIs accept these external-ID filters; still compare IDs locally.
        rows = self.request(self.resource, {self.id_key: external_id})
        return next((r for r in rows if str(r.get(self.id_key)) == str(external_id)), None)

    def add(self, candidate, options):
        if self.existing(candidate[self.id_key]):
            raise AlreadyExists('This title is already in {}. Its settings were not changed.'.format(self.kind.title()))
        return self.request(self.resource, payload=build_payload(self.kind, candidate, options))


def build_payload(kind, candidate, options):
    """Send writable lookup metadata plus explicit user choices."""
    fields = ('title', 'titleSlug', 'year', 'images', 'tmdbId', 'imdbId') if kind == 'radarr' else (
        'title', 'titleSlug', 'year', 'images', 'tvdbId', 'seasons')
    data = {k: copy.deepcopy(candidate[k]) for k in fields if k in candidate}
    data.update(qualityProfileId=int(options['qualityProfileId']),
                rootFolderPath=options['rootFolderPath'], tags=options.get('tags', []))
    if kind == 'radarr':
        monitored = options.get('monitored', True)
        data.update(monitored=monitored, minimumAvailability=options.get('availability', 'released'),
                    addOptions={'searchForMovie': bool(options.get('search') and monitored)})
    else:
        monitor = options.get('monitor', 'all')
        data.update(monitored=monitor != 'none', seasonFolder=options.get('seasonFolder', True),
                    seriesType=options.get('seriesType', 'standard'))
        if monitor == 'selected':
            selected = set(options.get('seasons', []))
            if not selected:
                raise ArrError('Select at least one season, or choose monitoring: None.')
            for season in data.get('seasons', []):
                season['monitored'] = season['seasonNumber'] in selected
            monitor = 'skip'  # Preserve explicit per-season monitoring flags.
        data['addOptions'] = {'monitor': monitor,
                              'searchForMissingEpisodes': bool(options.get('search') and data['monitored']),
                              'searchForCutoffUnmetEpisodes': False}
    return data


def exact_match(rows, ids):
    """Require all comparable external IDs to agree; never infer from title alone."""
    matches = []
    for row in rows:
        comparable = [(str(row.get(k)), str(v)) for k, v in ids.items() if v and row.get(k)]
        if comparable and all(a == b for a, b in comparable):
            matches.append(row)
    return matches[0] if len(matches) == 1 else None
