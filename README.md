# GithubReleaseProxy
Simple proxy to enable fine download permissions on Github's releases.

As June 2018, it is not possible to generate Github's releases access tokens for a specific set of repositories. If you need to restrict a token to a set of repositories, it is necessary to create a machine user with only access to the repositories. It however costs money.

This proxy takes a personal access token from one account and offers releases with a fine access control. It allows the creation of access keys for each repositories, to download releases easily.

It also provide a simpler HTTP API to download releases, removing the need to use a Github client.

## Access Tokens

The access tokens define the access controls.

The access tokens are stored in a web passwd file. You may use [htpasswd](https://httpd.apache.org/docs/2.4/programs/htpasswd.html) from Apache or [Ansible](https://docs.ansible.com/ansible/latest/modules/htpasswd_module.html) to manipulate such a file.

The user is the name of the repository, or the user should start with the name of the repository and be prepend by a slash. The password is the access token.

Examples:

```bash
htpasswd -B ~/github-release-proxy-passwd secret-company/one-project 
htpasswd -B ~/github-release-proxy-passwd secret-company/super-secret-project/token1 1234
htpasswd -B ~/github-release-proxy-passwd secret-company/super-secret-project/token2 1234
```

## API

```
GET /<user>/<repo>/<tag>/<asset_name>
```

The API requires Basic HTTP Authentication, to send the access tokens.

Example:

```bash
wget --user "secret-company/super-secret-project/token1" --password 1234 \
    http://localhost:8080/secret-company/super-secret-project/8.0.1/8.0.1.tar.gz
```

## Deployment

[Generate a Personal Access Token](https://help.github.com/articles/creating-a-personal-access-token-for-the-command-line/)

```bash
docker run --restart=unless-stopped -d \
  --name github-release-proxy \
  -p 8080:8080 \
  -e GITHUB_PERSONAL_TOKEN=e7bc546316d2d0dc13a2d3117b13468f5e939f95 \
  -v ~/github-release-proxy-passwd:/usr/src/app/.passwd
  tellu/github-release-proxy
```

