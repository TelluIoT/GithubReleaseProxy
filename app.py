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
passwd = None
passwd_mtime = 0

def login():
    global ghclient

    if ghclient is None:
        app.logger.debug('Login with token')
        ghclient = github3.login(token = github_personal_token)
        if ghclient is None:
            app.logger.error('Unable to login with token')
            abort(500)



def update_passwd():
    global passwd
    global passwd_mtime
    passwd_exists = os.path.exists(passwd_path)
    if passwd_exists:
        # Use the modified time to update the passwd file if necessary
        try:
            new_passwd_mtime = os.stat(passwd_path).st_mtime
        except Exception as e:
            print(str(e))
            new_passwd_mtime = 0
        # If the file has changed
        if new_passwd_mtime != passwd_mtime:
            app.logger.debug('Update passwd file')
            passwd = HtpasswdFile(passwd_path, new = False)
            passwd_mtime = new_passwd_mtime
    else:
        if passwd_mtime > 0 or passwd is None:
            passwd = HtpasswdFile(passwd_path, new = True)

@auth.verify_password
def auth_verify_password(username, password):
    update_passwd()
    return passwd.check_password(username, password)

@app.route('/')
def index():
    return ('', 204)

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