"""The equipment Strata browser installer is retired; this command never changes services."""


def insert_include(text):
    """[MINI-COMMENT: STRATA.DEPLOY.NGINX]
    [EN rev.2]
    [Role] Rejects attempts to reinstall the retired equipment browser gateway.
    [Dependencies] No Nginx file, key, database or service is opened.
    [Impact] Historical callers fail before mutating their supplied configuration.
    """
    raise RuntimeError('Retired gateway: use the reviewed Strata retirement procedure')


def main():
    """[MINI-COMMENT: STRATA.DEPLOY.APPLY]
    [EN rev.2]
    [Role] Refuses the former enabling command with a clear nonzero retirement result.
    [Dependencies] The reviewed docs/strata-integration.md replacement procedure.
    [Impact] Does not install keys, rewrite environment files, restart Flask or reload Nginx.
    """
    raise SystemExit('The equipment Strata browser UI is retired. Follow docs/strata-integration.md; no changes were made.')


if __name__ == '__main__':
    main()
