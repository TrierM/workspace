"""Run a command with credentials from one named AWS profile; never modify shared credentials."""
import argparse
import configparser
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile

# Credential providers that can override a selected profile in child SDK processes.
CREDENTIAL_OVERRIDES = (
    'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
    'AWS_SECURITY_TOKEN', 'AWS_ACCESS_KEY', 'AWS_SECRET_KEY',
    'AWS_CREDENTIAL_EXPIRATION', 'AWS_ROLE_ARN', 'AWS_ROLE_SESSION_NAME',
    'AWS_WEB_IDENTITY_TOKEN_FILE', 'AWS_CONTAINER_CREDENTIALS_RELATIVE_URI',
    'AWS_CONTAINER_CREDENTIALS_FULL_URI', 'AWS_CONTAINER_AUTHORIZATION_TOKEN',
    'AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE',
)


def profile_environment(profile):
    environment = dict(os.environ)
    for name in CREDENTIAL_OVERRIDES:
        environment.pop(name, None)
    environment['AWS_PROFILE'] = profile
    environment['AWS_DEFAULT_PROFILE'] = profile
    return environment


def resolve_credentials(aws, profile, environment):
    identity = subprocess.run([aws, 'sts', 'get-caller-identity', '--profile', profile],
                              env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if identity.returncode:
        login = subprocess.run([aws, 'sso', 'login', '--profile', profile],
                               env=environment, stdout=sys.stderr)
        if login.returncode:
            raise ValueError('AWS SSO login failed; command not started')
    else:
        print(f'Reusing existing {profile} session.', file=sys.stderr)
    result = subprocess.run([aws, 'configure', 'export-credentials', '--profile', profile,
                             '--format', 'process'], env=environment, capture_output=True, text=True)
    if result.returncode:
        raise ValueError('Could not resolve credentials for the selected profile; command not started')
    try:
        data = json.loads(result.stdout)
        values = [data[key] for key in ('AccessKeyId', 'SecretAccessKey', 'SessionToken')]
        if not all(isinstance(value, str) and value and not any(c in value for c in '\r\n\x00')
                   for value in values):
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise ValueError('Invalid temporary credentials returned by AWS; command not started') from None
    return values


def legacy_command(command, environment, profile, credentials):
    # Only this child's file contains [default]; no machine-wide profile is changed.
    with tempfile.TemporaryDirectory(prefix='ais-aws-') as directory:
        path = Path(directory) / 'credentials'
        config = configparser.RawConfigParser()
        values = dict(zip(('aws_access_key_id', 'aws_secret_access_key', 'aws_session_token'), credentials))
        config['default'] = values
        config[profile] = values
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            config.write(stream)
        environment['AWS_SHARED_CREDENTIALS_FILE'] = str(path)
        child = subprocess.Popen(command, env=environment, start_new_session=True)
        def forward(signum, frame):
            try:
                os.killpg(child.pid, signum)
            except ProcessLookupError:
                pass
        previous = {sig: signal.signal(sig, forward) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            status = child.wait()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
        return status if status >= 0 else 128 - status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', choices=('dev', 'staging', 'prod'))
    parser.add_argument('--legacy-default', action='store_true',
                        help='Give this command a temporary credentials file with a default profile')
    # Stop helper-option parsing at the command, preserving all command flags.
    arguments = sys.argv[1:]
    if len(arguments) < 1:
        parser.error('a profile is required')
    leading = arguments[:1]
    remaining = arguments[1:]
    if remaining[:1] == ['--legacy-default']:
        leading.append(remaining.pop(0))
    if remaining[:1] == ['--']:
        remaining.pop(0)
    elif remaining[:1] in (['-h'], ['--help']):
        parser.print_help()
        return 0
    args = parser.parse_args(leading)
    if args.legacy_default and not remaining:
        parser.error('--legacy-default requires a command')
    environment = profile_environment(args.profile)
    aws = shutil.which('aws', path=environment.get('PATH'))
    if aws is None:
        parser.exit(127, 'AWS CLI is missing from PATH\n')
    try:
        credentials = resolve_credentials(aws, args.profile, environment)
        if not remaining:
            print(f'{args.profile} credentials are available; no shared default profile was changed.', file=sys.stderr)
            return 0
        for key, value in zip(('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN'), credentials):
            environment[key] = value
        if args.legacy_default:
            return legacy_command(remaining, environment, args.profile, credentials)
        os.execvpe(remaining[0], remaining, environment)
    except (OSError, ValueError) as error:
        # Credential contents and captured AWS output must never enter error messages.
        if isinstance(error, OSError):
            parser.exit(1, 'Could not start AWS helper or requested command\n')
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
