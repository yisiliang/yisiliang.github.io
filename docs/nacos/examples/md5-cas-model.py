#!/usr/bin/env python3
"""Deterministic teaching model, NOT the Nacos implementation or concurrency test."""
from hashlib import md5

def digest(value):
    return md5(value.encode('utf-8')).hexdigest()

class Store:
    def __init__(self, content):
        self.content = content
    def publish(self, content, expected_md5):
        if digest(self.content) != expected_md5:
            return False
        self.content = content
        return True

def main():
    store = Store('limit=10')
    old = digest(store.content)
    assert store.publish('limit=20', old)
    assert not store.publish('limit=30', old)
    assert store.content == 'limit=20'
    # A notification ACK is deliberately independent of content refresh.
    cache = {'content': 'limit=10', 'consistent': True, 'ack': False}
    cache['consistent'] = False
    cache['ack'] = True
    assert cache['ack'] and cache['content'] == 'limit=10'
    assert digest(cache['content']) != digest(store.content)
    cache['content'] = store.content
    cache['consistent'] = True
    assert cache['content'] == 'limit=20'
    # Crash/partition is not simulated; this only demonstrates logical boundaries.
    print('PASS: stale CAS rejected; notification ACK precedes content refresh')

if __name__ == '__main__':
    main()
