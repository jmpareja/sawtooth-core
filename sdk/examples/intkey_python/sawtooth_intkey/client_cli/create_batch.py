#!/usr/bin/python
#
# Copyright 2016 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

import argparse
import hashlib
import os
import logging
import random
import string
import time
import cbor
import bitcoin

import sawtooth_protobuf.batch_pb2 as batch_pb2
import sawtooth_protobuf.transaction_pb2 as transaction_pb2


LOGGER = logging.getLogger(__name__)


class IntKeyPayload(object):
    def __init__(self, verb, name, value):
        self._verb = verb
        self._name = name
        self._value = value

        self._cbor = None
        self._sha512 = None

    def to_hash(self):
        return {
            'Verb': self._verb,
            'Name': self._name,
            'Value': self._value
        }

    def to_cbor(self):
        if self._cbor is None:
            self._cbor = cbor.dumps(self.to_hash(), sort_keys=True)
        return self._cbor

    def sha512(self):
        if self._sha512 is None:
            self._sha512 = hashlib.sha512(self.to_cbor()).hexdigest()
        return self._sha512


def create_intkey_transaction(verb, name, value, private_key, public_key):
    payload = IntKeyPayload(
        verb=verb, name=name, value=value)

    # The prefix should eventually be looked up from the
    # validator's namespace registry.
    intkey_prefix = hashlib.sha512('intkey'.encode('utf-8')).hexdigest()[0:6]

    addr = intkey_prefix + hashlib.sha512(name.encode('utf-8')).hexdigest()

    header = transaction_pb2.TransactionHeader(
        signer_pubkey=public_key,
        family_name='intkey',
        family_version='1.0',
        inputs=[addr],
        outputs=[addr],
        dependencies=[],
        payload_encoding="application/cbor",
        payload_sha512=payload.sha512(),
        batcher_pubkey=public_key,
        nonce=time.time().hex().encode())

    header_bytes = header.SerializeToString()

    signature = bitcoin.ecdsa_sign(
        header_bytes,
        private_key)

    transaction = transaction_pb2.Transaction(
        header=header_bytes,
        payload=payload.to_cbor(),
        header_signature=signature)

    return transaction


def create_batch(transactions, private_key, public_key):
    transaction_signatures = [t.header_signature for t in transactions]

    header = batch_pb2.BatchHeader(
        signer_pubkey=public_key,
        transaction_ids=transaction_signatures)

    header_bytes = header.SerializeToString()

    signature = bitcoin.ecdsa_sign(
        header_bytes,
        private_key)

    batch = batch_pb2.Batch(
        header=header_bytes,
        transactions=transactions,
        header_signature=signature)

    return batch


def generate_word():
    return ''.join([random.choice(string.ascii_letters) for _ in range(0, 6)])


def generate_word_list(count):
    if os.path.isfile('/usr/share/dict/words'):
        with open('/usr/share/dict/words', 'r') as fd:
            return [x.strip() for x in fd.readlines()[0:count]]
    else:
        return [generate_word() for _ in range(0, count)]


def do_populate(args, batches, words):
    private_key = bitcoin.random_key()
    public_key = bitcoin.encode_pubkey(
        bitcoin.privkey_to_pubkey(private_key), "hex")

    total_txn_count = 0
    txns = []
    for i in range(0, len(words)):
        txn = create_intkey_transaction(
            verb='set',
            name=words[i],
            value=random.randint(9000, 100000),
            private_key=private_key,
            public_key=public_key)
        total_txn_count += 1
        txns.append(txn)

    batch = create_batch(
        transactions=txns,
        private_key=private_key,
        public_key=public_key)

    batches.append(batch)


def do_generate(args, batches, words):
    private_key = bitcoin.random_key()
    public_key = bitcoin.encode_pubkey(
        bitcoin.privkey_to_pubkey(private_key), "hex")

    start = time.time()
    total_txn_count = 0
    for i in range(0, args.count):
        txns = []
        for _ in range(0, random.randint(1, args.batch_max_size)):
            txn = create_intkey_transaction(
                verb=random.choice(['inc', 'dec']),
                name=random.choice(words),
                value=1,
                private_key=private_key,
                public_key=public_key)
            total_txn_count += 1
            txns.append(txn)

        batch = create_batch(
            transactions=txns,
            private_key=private_key,
            public_key=public_key)

        batches.append(batch)

        if i % 100 == 0 and i != 0:
            stop = time.time()

            txn_count = 0
            for batch in batches[-100:]:
                txn_count += len(batch.transactions)

            fmt = 'batches {}, batch/sec: {:.2f}, txns: {}, txns/sec: {:.2f}'
            print(fmt.format(
                str(i),
                100 / (stop - start),
                str(total_txn_count),
                txn_count / (stop - start)))
            start = stop


def write_batch_file(args, batches):
    batch_list = batch_pb2.BatchList(batches=batches)
    print("Writing to {}...".format(args.output))
    with open(args.output, "wb") as fd:
        fd.write(batch_list.SerializeToString())


def do_create_batch(args):
    batches = []
    words = generate_word_list(args.pool_size)
    do_populate(args, batches, words)
    do_generate(args, batches, words)
    write_batch_file(args, batches)


def add_create_batch_parser(subparsers, parent_parser):

    epilog = '''
    details:
     create sample batch of intkey transactions.
     populates state with intkey word/value pairs
     then generates inc and dec transactions.
    '''

    parser = subparsers.add_parser(
        'create_batch',
        parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog)

    parser.add_argument(
        '-o', '--output',
        type=str,
        help='location of output file',
        default='batches.intkey',
        metavar='')

    parser.add_argument(
        '-c', '--count',
        type=int,
        help='number of batches',
        default=1000,
        metavar='')

    parser.add_argument(
        '-B', '--batch-max-size',
        type=int,
        help='max size of the batch',
        default=20,
        metavar='')

    parser.add_argument(
        '-P', '--pool-size',
        type=int,
        help='size of the word pool',
        default=100,
        metavar='')
