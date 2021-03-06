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

from ast import literal_eval


class RadixNode:
    def __init__(self, children=None, readers=None, writer=None):
        self.children = children if children is not None else {}
        self.readers = readers if readers is not None else []
        self.writer = writer

    def __repr__(self):
        retval = {}

        if len(self.readers) > 0:
            retval['readers'] = self.readers
        if self.writer is not None:
            retval['writer'] = self.writer
        if len(self.children) > 0:
            retval['children'] = \
                {k: literal_eval(repr(v)) for k, v in self.children.items()}

        return repr(retval)


class RadixTree:
    def __init__(self, token_size=2):
        self._token_size = token_size
        self._root = RadixNode()

    def __repr__(self):
        return repr(self._root)

    def _tokenize_address(self, address):
        return [address[i:i + self._token_size]
                for i in range(0, len(address), self._token_size)]

    def _get(self, address, create=False):
        tokens = self._tokenize_address(address)

        node = self._root
        for token in tokens:
            if token in node.children:
                node = node.children[token]
            else:
                if not create:
                    return None
                child = RadixNode()
                node.children[token] = child
                node = child

        return node

    def get(self, address):
        return self._get(address)

    def add_reader(self, address, reader):
        node = self._get(address, create=True)
        node.readers.append(reader)

    def set_writer(self, address, writer):
        node = self._get(address, create=True)
        node.readers = []
        node.writer = writer
        node.children = {}

    def find_readers_and_writers(self, address):
        readers_and_writers = []

        tokens = self._tokenize_address(address)

        node = self._root
        for token in tokens:
            if token in node.children:
                node = node.children[token]
            else:
                break

            readers_and_writers.extend(node.readers)
            if node.writer is not None and \
                    node.writer not in readers_and_writers:
                readers_and_writers.append(node.writer)

        return readers_and_writers


class TopologicalSorter:
    def __init__(self):
        self._count = {}
        self._successors = {}
        self._identifiers = []

    def _init(self, identifier):
        if identifier not in self._count:
            self._count[identifier] = 0
        if identifier not in self._successors:
            self._successors[identifier] = []
        if identifier not in self._identifiers:
            self._identifiers.append(identifier)

    def add_relation(self, predecessor, successor):
        self._init(predecessor)
        self._init(successor)
        self._count[successor] += 1
        self._successors[predecessor].append(successor)

    def order(self):
        retval = []

        while len(self._identifiers) > 0:
            found = None
            for identifier in self._identifiers:
                if self._count[identifier] == 0:
                    found = identifier
                    break
            if found is not None:
                retval.append(found)
                for successor in self._successors[found]:
                    self._count[successor] -= 1

                self._identifiers.remove(found)
                del self._count[found]
                del self._successors[found]
            else:
                raise Exception("non-acyclic graph detected, aborting")

        return retval
