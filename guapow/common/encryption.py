import hashlib
import json
from base64 import b64encode, b64decode

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes


def encrypt(text: str, password: str) -> str:
    salt = get_random_bytes(AES.block_size)
    random_key = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    cipher_config = AES.new(random_key, AES.MODE_GCM)
    encrypted, tag = cipher_config.encrypt_and_digest(bytes(text, 'utf-8'))

    return b64encode(json.dumps({
        'text': b64encode(encrypted).decode('utf-8'),
        'salt': b64encode(salt).decode('utf-8'),
        'nonce': b64encode(cipher_config.nonce).decode('utf-8'),
        'tag': b64encode(tag).decode('utf-8')
    }).encode()).decode('utf-8')


def decrypt(encrypted_token: str, password: str) -> str:
    token = json.loads(b64decode(encrypted_token))
    salt = b64decode(token['salt'])
    text = b64decode(token['text'])
    nonce = b64decode(token['nonce'])
    tag = b64decode(token['tag'])

    private_key = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    cipher = AES.new(private_key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(text, tag).decode()
