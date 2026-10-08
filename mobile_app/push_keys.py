"""Generate VAPID keys locally; print only the destination, never key material."""
import argparse
import base64
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Create a private VAPID environment file without overwriting it.')
    parser.add_argument('--output', type=Path, default=Path('mobile_app/.state/.env.vapid'))
    args = parser.parse_args()
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    except ImportError:
        parser.exit(1, 'Install mobile_app/requirements.txt before generating push keys.\n')
    private = ec.generate_private_key(ec.SECP256R1())
    private_bytes = private.private_numbers().private_value.to_bytes(32, 'big')
    public_bytes = private.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    encode = lambda value: base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')
    path = args.output.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        parser.exit(1, 'The destination already exists. Existing keys were preserved.\n')
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(f'VAPID_PUBLIC_KEY={encode(public_bytes)}\nVAPID_PRIVATE_KEY={encode(private_bytes)}\n')
        stream.write('# Set VAPID_SUBJECT separately to the real operator mailto: or HTTPS contact.\n')
    print(path)


if __name__ == '__main__':
    main()
