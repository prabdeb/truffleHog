# Enable Scan in CI System

This is a simple setup to enable a complete scan of all repositories and generate a Excel based report.
Also this can be enabled with Pull Request/Push, so that any new changes can be detected and scan can be performed on the PR commit

## Currently Supported

1. Excel report for all types of repository
2. Authenticated repository for BitBucket
3. All repositories inside a BitBucket Project
4. Enable with CI System - Drone (However it can be enabled in CI System, that supports Docker as runtime env)

## How to use in Generic CI Environment

```sh
$ docker run --rm -d prabdeb/trufflehog-ci --help
usage: scan.py [-h] [-s SCM] [-t TOKEN] [-u USERNAME] [-p PROJECT]
               [-r REPOSITORY] [-e EXCLUDE] [-er EXCLUDEREPOSITORIES]
               [-o OUTPUT] [-pr PULLREQUEST] [-cd COMMITDEPTH] [-en ENTROPY]
               [-v] [-ex]

scan.py: Execute and parse report of truffleHog

optional arguments:
  -h, --help            show this help message and exit
  -s SCM, --scm SCM     SCM parent URL for scaning (Mandatory) ENV: SCM_URL
  -t TOKEN, --token TOKEN
                        SCM OAuth Token (Mandatory) ENV: BITBUCKET_LOGIN
  -u USERNAME, --userName USERNAME
                        SCM User Name (Mandatory) ENV: DRONE_NETRC_USERNAME
  -p PROJECT, --project PROJECT
                        Project/Owner Name (Mandatory) ENV: DRONE_REPO_OWNER
  -r REPOSITORY, --repository REPOSITORY
                        Repository Name, if not mentioned all repositories
                        will be scanned ENV: DRONE_REPO_NAME
  -e EXCLUDE, --exclude EXCLUDE
                        Excluded files patterns coma (,) separated ENV:
                        EXCLUDE_FILE_PATTERN
  -er EXCLUDEREPOSITORIES, --excludeRepositories EXCLUDEREPOSITORIES
                        Excluded repositories coma (,) separated ENV:
                        EXCLUDED_REPOSITORIES
  -o OUTPUT, --output OUTPUT
                        Store result to mentioned report file (Microsoft
                        Excel)
  -pr PULLREQUEST, --pullRequest PULLREQUEST
                        Enable diff based scan for Pull Request ENV:
                        CI_PULL_REQUEST
  -cd COMMITDEPTH, --commitDepth COMMITDEPTH
                        Enable diff based scan for commit depth ENV:
                        DRONE_BUILD_EVENT
  -en ENTROPY, --entropy ENTROPY
                        Enable (default) or disable entropy ENV:
                        TRUFFLEHOG_ENTROPY
  -v, --verbose         Verbose output for debug
  -ex, --exit           Exit with error if any secrets found ENV: RAISE_ERROR
```

## How to use in Drone

```yaml
  git-secret-scan:
    image: prabdeb/trufflehog-ci
    pull: true
    environment:
      - SCM_URL=<Bitbucket URL>
      - RAISE_ERROR=True
    when:
      event: [pull_request]
```