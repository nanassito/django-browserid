"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
import logging
import urllib
from warnings import warn
try:
    import json
except ImportError:
    import simplejson as json  # NOQA


from django.conf import settings

import requests


log = logging.getLogger(__name__)


DEFAULT_HTTP_TIMEOUT = 5
DEFAULT_VERIFICATION_URL = 'https://verifier.login.persona.org/verify'
OKAY_RESPONSE = 'okay'


def get_audience(request):
    """Uses Django settings to format the audience.

    To use this function, make sure there is either a SITE_URL in
    your settings.py file or PROTOCOL and DOMAIN.

    Examples using SITE_URL:
        SITE_URL = 'http://127.0.0.1:8001'
        SITE_URL = 'https://example.com'
        SITE_URL = 'http://example.com'

    If none are set, we trust the request to populate the audience.
    This is *not secure*!
    """
    site_url = getattr(settings, 'SITE_URL', False)

    # Note audience based on request for developer warnings
    if request.is_secure():
        req_proto = 'https://'
    else:
        req_proto = 'http://'
    req_domain = request.get_host()

    req_url = "%s%s" % (req_proto, req_domain)
    if site_url != "%s%s" % (req_proto, req_domain):
        log.warning('Misconfigured SITE_URL? settings has {0}, but '
                    'actual request was {1} BrowserID may fail on '
                    'audience'.format(site_url, req_url))
    return site_url


def _verify_http_request(url, qs):
    parameters = {
        'data': qs,
        'proxies': getattr(settings, 'BROWSERID_PROXY_INFO', None),
        'verify': not getattr(settings, 'BROWSERID_DISABLE_CERT_CHECK', False),
        'headers': {'Content-type': 'application/x-www-form-urlencoded'},
        'timeout': getattr(settings, 'BROWSERID_HTTP_TIMEOUT',
                           DEFAULT_HTTP_TIMEOUT),
    }

    if parameters['verify']:
        parameters['verify'] = getattr(settings, 'BROWSERID_CACERT_FILE', True)

    r = requests.post(url, **parameters)

    try:
        rv = json.loads(r.content)
    except ValueError:
        log.debug('Failed to decode JSON. Resp: {0}, Content: {1}'.format(r.status_code, r.content))
        return dict(status='failure')

    return rv


def verify(assertion, audience, extra_params=None):
    """Verify assertion using an external verification service.
       extra_params is a dict of additional parameters to send to the
        verification service.
    """
    verify_url = getattr(settings, 'BROWSERID_VERIFICATION_URL',
                         DEFAULT_VERIFICATION_URL)

    log.info("Verification URL: {0}".format(verify_url))

    args = {'assertion': assertion,
            'audience': audience}
    if extra_params:
        args.update(extra_params)
    result = _verify_http_request(verify_url, urllib.urlencode(args))

    if result['status'] == OKAY_RESPONSE:
        return result

    log.error('BrowserID verification failure. Response: {0} '
              'Audience: {1}'.format(result, audience))
    log.error("BID assert: {0}".format(assertion))
    return False
