import hashlib

import rlp
from rlp.sedes import List, CountableList, big_endian_int, raw

from ..basic import Configuration as conf
from .base_message import BaseMessage
from .request import Request

class PrePrepare(BaseMessage):

    content_sedes = List([
        big_endian_int, # view
        big_endian_int, # seqno
        big_endian_int, # extra
        # requests, with sha256(b'\x12...') or payload('\x60...')
        CountableList(raw),
        raw, # non_det_choices
    ])

    payload_sedes = List([
        raw, # content
        raw, # auth(signature)
    ])

    def __init__(self, view, seqno, extra,
                 requests, non_det_choices):
        self.view = view
        self.seqno = seqno
        self.extra = extra
        self.requests = requests
        self.non_det_choices = non_det_choices

        self.content = None
        self.auth = None
        self.payload = None

    @property
    def consensus_digest(self):
        """Used to make sure that primary did NOT tamper the requests
        including all request.consensus_digest and non_det_choices
        """
        d = hashlib.sha256()
        for r in self.requests:
            d.update(r.consensus_digest)
        d.update(self.non_det_choices)

        return d.digest()

    @property
    def content_digest(self):
        d = hashlib.sha256()
        d.update('{}'.format(self.view).encode())
        d.update('{}'.format(self.seqno).encode())
        d.update('{}'.format(self.extra).encode())
        for r in self.requests:
            if type(r) is bytes:
                # r is content_digest of a Request
                d.update(r)
            else:
                # r is an instance of Request
                d.update(r.content_digest)
        d.update(self.non_det_choices)
        return d.digest()

    def authenticate(self, node):
        if self.use_signature:
            self.auth = node.principal.sign(self.content_digest)
        else:
            self.auth = node.gen_authenticators(self.content_digest)

        return self.auth

    def verify(self, node, peer_principal):
        pp = peer_principal

        if self.use_signature:
            return pp.verify(self.content_digest, self.auth)

        if len(node.replica_principals) != len(self.auth):
            return False

        return (pp.gen_hmac('in', self.content_digest)
                == self.auth[node.sender])

    @classmethod
    def from_node(cls, node, use_signature:bool):
        extra = 0
        if use_signature:
            extra |= 2

        requests = [] # request payload or sha256
        for r in node.requests:
            if r.pre_prepare:
                continue

            requests.append(r)
            r.in_pre_prepare = True

            if len(requests) >= conf.request_in_pre_prepare:
                break

        non_det_choices = b'' # TODO: non deterministic choices

        message = cls(node.view, node.seqno, extra,
                      requests, non_det_choices)

        message.content = rlp.encode([message.view, message.seqno,
                                      message.extra, message.requests,
                                      message.non_det_choices],
                                     cls.content_sedes)

        if message.use_signature:
            message.auth = node.principal.sign(message.content_digest)
            auth = message.auth
        else:
            message.auth = node.gen_authenticators(message.content_digest)
            auth = rlp.encode(message.auth, cls.authenticators_sedes)

        message.payload = rlp.encode([message,content, auth],
                                     cls.payload_sedes)

        return message

    @classmethod
    def from_payload(cls, payload, addr):
        try:
            [content, auth] = rlp.decode(payload, cls.payload_sedes)
            [view, seqno, extra, requests, non_det_choices] = rlp.decode(
                content, cls.content_sedes)

            for i, r in enumerate(requests):
                if r[0] == 0x60:
                    requests[i] = Request.from_payload(r[1:], addr)
                elif r[0] == 0x12:
                    requests[i] = r[1:]
                else:
                    raise ValueError('wrong flag in requests')
            
            message = cls(view, seqno, extra, requests, non_det_choices)

            message.content= content
            if message.use_signature:
                message.auth = auth
            else:
                message.auth = rlp.decode(auth, cls.authenticators_sedes)
            message.payload = payload
            message.from_addr = addr

            return message
        except rlp.DecodingError as exc:
            raise ValueError('decoding error: {}'.format(exc))
