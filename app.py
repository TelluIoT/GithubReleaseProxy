import os
import logging
import github3
from flask import Flask, abort, Response
from flask_httpauth import HTTPBasicAuth
from passlib.apache import HtpasswdFile
from gevent.pywsgi import WSGIServer

app = Flask(__name__)
auth = HTTPBasicAuth()

passwd_path = os.getenv('PASSWD_PATH', '.passwd')
github_personal_token = os.getenv('GITHUB_PERSONAL_TOKEN')
http_port = int(os.getenv('HTTP_PORT', '8080'))

ghclient = None
passwd = HtpasswdFile(passwd_path, new=(not os.path.exists(passwd_path)))

def login():
    global ghclient

    if ghclient is None:
        app.logger.debug('Login with token')
        ghclient = github3.login(token = github_personal_token)

@auth.verify_password
def auth_verify_password(username, password):
    return passwd.check_password(username, password)

@app.route('/<user>/<repo>/<tag>/<asset_name>')
@auth.login_required
def release(user, repo, tag, asset_name):

    username = auth.username()
    repokey = '%s/%s' % (user, repo)
    if username != repokey and not username.startswith(repokey + '/'):
        abort(403)

    global ghclient
    login()

    try:
        app.logger.debug('Loading repository %s', repokey)
        repository = ghclient.repository(str(user), str(repo))
        if not repository:
            abort(404)

        app.logger.debug('Loading release %s', str(tag))
        release = repository.release_from_tag(tag)
        if not release:
            abort(404)

    except github3.exceptions.NotFoundError:
        abort(404)

    asset_id = None
    for asset in release.assets():
        app.logger.debug('release %s', asset.name)
        if asset.name == asset_name:
            asset_id = asset.id
            break

    if asset_id is None:
        abort(404)

    asset = release.asset(asset_id)

    # The following code is inspired and copy/pasted from sigmavirus24/github3.py
    # to download the release as a stream and not as a file
    try:
        app.logger.debug('Start Download Release %s', asset_name)
        headers = {
            'Accept': 'application/octet-stream'
        }
        resp = asset._get(asset._api, allow_redirects=False, stream=True,
                         headers=headers)
        if resp.status_code == 302:
            app.logger.debug('Got 302 %s', resp.headers['location'])
            # Amazon S3 will reject the redirected request unless we omit
            # certain request headers
            headers.update({
                'Content-Type': None,
            })

            with asset.session.no_auth():
                resp = asset._get(resp.headers['location'], stream=True,
                                 headers=headers)
        if asset._boolean(resp, 200, 404):
            app.logger.debug('Got Stream for %s', asset_name)
            return Response(resp.iter_content(chunk_size=512),
                content_type=resp.headers['Content-Type'])
        else:
            abort(403)
    except Exception as e:
        app.logger.error('Error while downloading release', str(e))
        abort(500)

if __name__ == '__main__':
    app.logger.setLevel(logging.INFO)
    WSGIServer(('0.0.0.0', http_port), app).serve_forever()