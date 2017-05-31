from __future__ import unicode_literals

import json

from channels import Group
from channels.shortcuts import JSON_Dict


class JSONDictTests(ChannelTestCase):
    """
    Tests the JSON_Dict
    """

    def test_basic(self):
        """
        Tests that object creation works as expected.
        """
        d = JSON_Dict(test=1, another=False)
        d['still_more'] = 42
        self.assertIn('text', d)
        self.assertNotIn('test', d)
        with self.assertRaises(ValueError):
            d['text'] = 'something'
        self.assertEqual(json.loads(d['text']), json.loads('{"another": false, "test": 1, "still_more": 42}'))

    def test_get_key(self):
        """
        Tests that the get_key method works as expected.
        """
        d = JSON_Dict(test=1, another=False)
        self.assertEqual(d.get_key('test'), 1)
        self.assertEqual(d.get_key('another'), False)
        with self.assertRaises(KeyError):
            tmp = d['test']

    def test_update(self):
        '''
        Tests that the update method works as expected.
        '''
        d = JSON_Dict(test=1, another=False)
        d.update({'another': True, 'answer': 42})
        self.assertEqual(json.loads(d['text']), json.loads('{"another": true, "test": 1, "answer": 42}'))

    def test_delete(self):
        '''
        Tests that deleting keys works
        '''
        d = JSON_Dict(test=1, another=False)
        del d['test']
        self.assertEqual(json.loads(d['text']), json.loads('{"another": false'))
