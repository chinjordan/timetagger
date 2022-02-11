"""
basic script to run timetagger.

You can use this to run timetagger locally. If you want to run it
online, you'd need to take care of authentication.
"""

import logging
from pkg_resources import resource_filename

import asgineer
from timetagger import config
from timetagger.server import (
    authenticate,
    AuthException,
    api_handler_triage,
    get_webtoken_unsafe,
    create_assets_from_dir,
    enable_service_worker,
)

import requests
import config as app
from expiringdict import ExpiringDict
import random
import string

logger = logging.getLogger("asgineer")

# Get sets of assets provided by TimeTagger
common_assets = create_assets_from_dir(resource_filename("timetagger.common", "."))
apponly_assets = create_assets_from_dir(resource_filename("timetagger.app", "."))
image_assets = create_assets_from_dir(resource_filename("timetagger.images", "."))
page_assets = create_assets_from_dir(resource_filename("timetagger.pages", "."))
page_assets.pop('login')
custom_assets = create_assets_from_dir('./custom')
custom_assets['login'] = custom_assets['login'].replace('github_oauth', app.github_auth)


# Combine into two groups. You could add/replace assets here.
app_assets = dict(**common_assets, **image_assets, **apponly_assets)
web_assets = dict(**common_assets, **image_assets, **page_assets, **custom_assets)

# Enable the service worker so the app can be used offline and is installable
enable_service_worker(app_assets)

# Turn asset dicts into handlers. This feature of Asgineer provides
# lightning fast handlers that support compression and HTTP caching.
app_asset_handler = asgineer.utils.make_asset_handler(app_assets, max_age=0)
web_asset_handler = asgineer.utils.make_asset_handler(web_assets, max_age=0)

logins = ExpiringDict(max_len=float("inf"), max_age_seconds=3)


@asgineer.to_asgi
async def main_handler(request):
    """
    The main handler where we delegate to the API or asset handler.

    We serve at /timetagger for a few reasons, one being that the service
    worker won't interfere with other stuff you might serve on localhost.
    """

    if request.path == "/":
        return 307, {"Location": "/timetagger/"}, b""  # Redirect

    elif request.path.startswith("/timetagger/"):

        if request.path.startswith("/timetagger/api/v2/"):
            path = request.path[19:].strip("/")
            return await api_handler(request, path)
        elif request.path.startswith("/timetagger/app/"):
            path = request.path[16:].strip("/")
            return await app_asset_handler(request, path)
        else:
            path = request.path[12:].strip("/")
            return await web_asset_handler(request, path)

    else:
        return 404, {}, "only serving at /timetagger/"


async def api_handler(request, path):
    """The default API handler. Designed to be short, so that
    applications that implement alternative authentication and/or have
    more API endpoints can use this as a starting point.
    """

    # Some endpoints do not require authentication
    if not path and request.method == "GET":
        return 200, {}, "See https://timetagger.readthedocs.io"
    elif path == "oauth/github":
        return await webtoken(request)
    elif path == "getKey":
        return await getKeyFromTemp(request)

    # Authenticate and get user db
    try:
        auth_info, db = await authenticate(request)
    except AuthException as err:
        return 401, {}, f"unauthorized: {err}"

    # Handle endpoints that require authentication
    return await api_handler_triage(request, path, auth_info, db)

async def getKeyFromTemp(request):
    key = request.querydict['token']
    token = logins.get(key)
    print(token)
    return 200, {}, dict(token=token)

async def webtoken(request):

    github = requests.post(f"{app.github_token}{request.querydict['code']}",
                           headers={'Accept': 'application/json'})

    ghub_token = github.json()['access_token']

    user = requests.get('https://api.github.com/user', headers={'Authorization': f"token {ghub_token}"})
    if 'login' in user.json():
        if user.json()['login'] in app.acceptable_accounts or len(app.acceptable_accounts) == 0:
            temp = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            token = await get_webtoken_unsafe(user.json()['login'])
            logins[temp] = token
            return 307, {"Location": f"/timetagger/login?token={temp}",}, "nice!"
        else:
            return 418, {}, "I'm not a teapot: YOU'RE A TEAPOT"
    else:
        print(github)
        return 500, {}, "Error: Probably on our end. Webmaster, check logs."



if __name__ == "__main__":
    asgineer.run(main_handler, "uvicorn", config.bind, log_level="warning")
