"""Retired equipment-browser key writer; existing private key files remain untouched."""


def write_key_include(output, key):
    """[MINI-COMMENT: STRATA.KEY.INCLUDE]
    [EN rev.2]
    [Role] Refuses creation of authorization includes for the retired browser proxy.
    [Dependencies] No input/output path or secret value is inspected.
    [Impact] Existing keys are neither deleted nor rotated; new assistant bootstrap uses protected explicit input.
    """
    raise RuntimeError('The equipment Strata browser key writer is retired')


def main():
    """[Role] Refuses the former CLI before reading credentials or writing an include.
    [Dependencies] The replacement private USER_AI configuration/bootstrap procedure.
    [Impact] Shared-service keys and existing files remain unchanged.
    """
    raise SystemExit('Retired browser gateway. Existing key files were not read, changed or removed.')


if __name__ == '__main__':
    main()
