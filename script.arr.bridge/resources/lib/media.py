"""Snapshot the selected item before opening any dialog. Parent IDs stay separate."""
import json
import re
from urllib.parse import parse_qs, urlsplit


HELPER = 'plugin.video.themoviedb.helper'


def positive(value):
    return str(value) if str(value).isdigit() and int(value) > 0 else ''


def clean_title(value):
    return re.sub(r'\[/?(?:B|I|COLOR[^\]]*)\]', '', value or '', flags=re.I).strip()


def normalize(raw, explicit=None):
    p = explicit or {}
    if any(p.get(name + '_id') for name in ('tmdb', 'tvdb', 'imdb')):
        # Explicit integrations must not inherit unrelated focused-item IDs.
        raw = {}
    query = {k: v[0] for k, v in parse_qs(urlsplit(raw.get('path', '')).query).items()}
    helper = urlsplit(raw.get('path', '')).netloc == HELPER
    dbtype = p.get('type') or raw.get('dbtype') or (query.get('tmdb_type') if helper else '')
    child = dbtype in ('episode', 'season') or (helper and ('episode' in query or 'season' in query))
    kind = 'tv' if dbtype in ('tv', 'tvshow', 'season', 'episode') else 'movie' if dbtype == 'movie' else ''
    if not kind and raw.get('showtitle'):
        kind = 'tv'
    ids = {}
    for provider in ('tmdb', 'tvdb', 'imdb'):
        value = p.get(provider + '_id', '')
        if not value:
            value = raw.get('parent_' + provider, '') if child else raw.get(provider, '')
        # TMDb Helper URLs carry the parent show TMDb ID even on episodes.
        if provider == 'tmdb' and not value and helper:
            value = query.get('tmdb_id', '')
        if provider == 'imdb':
            value = value if re.fullmatch(r'tt\d+', str(value)) else ''
        else:
            value = positive(value)
        ids[provider + 'Id'] = value
    title = p.get('title') or (raw.get('showtitle') if child else raw.get('title')) or ''
    if not title and not child:
        title = raw.get('label', '')
    return dict(kind=kind, title=clean_title(title), year=positive(p.get('year') or raw.get('year', '')),
                ids=ids, child=child, poster=raw.get('poster', ''))


def rpc(xbmc, method, params):
    response = json.loads(xbmc.executeJSONRPC(json.dumps(
        {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))
    return response.get('result', {})


def snapshot(xbmc, listitem=None):
    """Prefer sys.listitem. Fall back to info labels only for RunScript actions."""
    raw = {}
    tag = None
    if listitem is not None:
        raw['label'] = listitem.getLabel()
        raw['path'] = listitem.getPath()
        raw['poster'] = listitem.getArt('poster') or listitem.getArt('thumb')
        tag = listitem.getVideoInfoTag()
        def method(name, *args):
            try:
                return getattr(tag, name)(*args)
            except (AttributeError, TypeError, RuntimeError):
                return ''
        raw.update(dbtype=method('getMediaType'), title=method('getTitle'),
                   showtitle=method('getTVShowTitle'), year=method('getYear'),
                   dbid=method('getDbId'), parent_dbid=method('getTvShowId'))
        for name in ('tmdb', 'tvdb', 'imdb'):
            raw[name] = method('getUniqueID', name) or listitem.getProperty(name + '_id')
            raw['parent_' + name] = method('getUniqueID', 'tvshow.' + name) or listitem.getProperty('tvshow.' + name + '_id')
        raw['dbtype'] = raw['dbtype'] or listitem.getProperty('tmdb_type')
    else:
        # ListItem.* is the active information-dialog item, including AF2.
        get = lambda key: xbmc.getInfoLabel('ListItem.' + key)
        raw = {k: get(v) for k, v in {
            'label': 'Label', 'title': 'Title', 'showtitle': 'TVShowTitle', 'year': 'Year',
            'dbtype': 'DBTYPE', 'dbid': 'DBID', 'path': 'FolderPath', 'poster': 'Art(poster)'}.items()}
        raw['dbtype'] = raw['dbtype'] or get('Property(tmdb_type)')
        for name in ('tmdb', 'tvdb', 'imdb'):
            raw[name] = get('UniqueID({})'.format(name)) or get('Property({}_id)'.format(name))
            raw['parent_' + name] = get('UniqueID(tvshow.{})'.format(name)) or get('Property(tvshow.{}_id)'.format(name))
    # Kodi episode UIDs belong to the episode. Fetch the parent library record.
    parent_id = positive(raw.get('parent_dbid'))
    if raw.get('dbtype') == 'episode' and not parent_id and positive(raw.get('dbid')):
        detail = rpc(xbmc, 'VideoLibrary.GetEpisodeDetails', {
            'episodeid': int(raw['dbid']), 'properties': ['tvshowid', 'showtitle']}).get('episodedetails', {})
        parent_id = positive(detail.get('tvshowid'))
        raw['showtitle'] = detail.get('showtitle') or raw.get('showtitle')
    if raw.get('dbtype') in ('episode', 'season') and parent_id:
        detail = rpc(xbmc, 'VideoLibrary.GetTVShowDetails', {
            'tvshowid': int(parent_id), 'properties': ['uniqueid', 'title', 'year']}).get('tvshowdetails', {})
        for name, value in detail.get('uniqueid', {}).items():
            raw['parent_' + name] = value
        raw['showtitle'] = detail.get('title') or raw.get('showtitle')
        raw['year'] = detail.get('year') or raw.get('year')
    return raw
