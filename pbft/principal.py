import secrets

import rsa

from .message import NewKey

class Principal():
    
    hash_method = 'SHA-256'

    zero_hmac_nounce = bytes(NewKey.hmac_nounce_length)

    def __init__(self,
                 index:int,
                 private_key = None, public_key = None,
                 ip:str = '127.0.0.1', port:int = 25600):
        self.index = index
        self.ip = ip # we send/recv by udp
        self.port = port
            
        self.private_key = private_key
        self.public_key = public_key

        # using hmac-256 for session keys
        self.outkey = self.zero_hmac_nounce
        self.outkeyts = 0 # outkey timestamp
        self.inkey = self.zero_hmac_nounce

    def sign(self, message:bytes) -> bytes:
        return rsa.sign(message, self.private_key, self.hash_method)

    def verify(self, message:bytes, signature) -> bool:
        return rsa.verify(message, signature, self.hash_method)

    def encrypt(self, message:bytes) -> bytes:
        return rsa.encrypt(message, self.public_key)

    def decrypt(self, message:bytes) -> bytes:
        return rsa.encrypt(message, self.private_key)

    def gen_inkey(self):
        self.inkey = secrets.token_bytes(NewKey.hmac_nounce_length)
        return self.inkey
