# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2019 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#     Valerio Cosentino <valcos@bitergia.com>
#

from contextlib import contextmanager
import datetime
import json
import os
import unittest.mock

import cherrypy
import dateutil
import requests

from arthur.server import ArthurServer

from base import TestBaseRQ


@contextmanager
def run_server(conn):
    """Start CherryPy server for the tests in the background and shut it down once a test is finished"""

    server = ArthurServer(conn, None, async_mode=False, writer=None)
    cherrypy.tree.mount(server, '/')
    cherrypy.engine.start()
    cherrypy.engine.wait(cherrypy.engine.states.STARTED)
    yield server
    cherrypy.engine.exit()
    cherrypy.engine.block()


class TestArthurServer(TestBaseRQ):
    """Unit tests for ArthurServer"""

    def test_init(self):
        """Check arguments initialization"""

        with run_server(self.conn) as server:
            self.assertTrue(server.conn, self.conn)
            self.assertIsNone(server.archive_path, None)
            self.assertIsNotNone(server._tasks)
            self.assertIsNotNone(server._scheduler)

    def test_add(self):
        """Check whether tasks are added"""

        with run_server(self.conn) as server:
            self.assertEqual(len(server._tasks.tasks), 0)

            data = {
                "tasks": [
                    {
                        "task_id": "arthur.git",
                        "backend": "git",
                        "backend_args": {
                            "gitpath": os.path.join(self.dir, 'data/git_log.txt'),
                            "uri": "http://example.com/",
                        },
                        "category": "commit",
                        "archive": {},
                        "scheduler": {
                            "delay": 10
                        }
                    }
                ]
            }

            response = requests.post("http://127.0.0.1:8080/add",
                                     json=data, headers={'Content-Type': 'application/json'})

            self.assertTrue(response.status_code, 200)
            self.assertTrue(len(server._tasks.tasks), 1)

            t = server._tasks.tasks[0]

            self.assertEqual(t.task_id, data["tasks"][0]["task_id"])
            self.assertEqual(t.backend, data["tasks"][0]["backend"])

    def test_remove(self):
        """Check whether tasks are removed"""

        with run_server(self.conn) as server:
            data = {
                "tasks": [
                    {
                        "task_id": "arthur.git",
                        "backend": "git",
                        "backend_args": {
                            "gitpath": os.path.join(self.dir, 'data/git_log.txt'),
                            "uri": "http://example.com/",
                        },
                        "category": "commit",
                        "archive": {},
                        "scheduler": {
                            "delay": 10
                        }
                    },
                    {
                        "task_id": "bugzilla_redhat",
                        "backend": "bugzilla",
                        "backend_args": {
                            "url": "https://bugzilla.example.com/",
                            "from_date": "2016-09-19"
                        },
                        "category": "issue",
                        "archive": {
                            'archive_path': '/tmp/archive',
                            'fetch_from_archive': False
                        },
                        "scheduler": {
                            "delay": 60
                        }
                    }
                ]
            }

            response = requests.post("http://127.0.0.1:8080/add",
                                     json=data, headers={'Content-Type': 'application/json'})

            self.assertTrue(response.status_code, 200)
            self.assertTrue(len(server._tasks.tasks), 2)

            response = requests.post("http://127.0.0.1:8080/remove",
                                     json=data, headers={'Content-Type': 'application/json'})

            self.assertTrue(response.status_code, 200)
            self.assertEqual(len(server._tasks.tasks), 0)

    def test_tasks(self):
        """Check whether tasks are retrieved"""

        with run_server(self.conn) as server:
            data = {
                "tasks": [
                    {
                        "task_id": "arthur.git",
                        "backend": "git",
                        "backend_args": {
                            "gitpath": os.path.join(self.dir, 'data/git_log.txt'),
                            "uri": "http://example.com/",
                        },
                        "category": "commit",
                        "archive": {},
                        "scheduler": {
                            "delay": 10
                        }
                    },
                    {
                        "task_id": "bugzilla_redhat",
                        "backend": "bugzilla",
                        "backend_args": {
                            "url": "https://bugzilla.example.com/",
                            "from_date": "2016-09-19"
                        },
                        "category": "issue",
                        "archive": {
                            'archive_path': '/tmp/archive',
                            'fetch_from_archive': True,
                            'archived_after': "2010-10-10",
                        },
                        "scheduler": {
                            "delay": 60
                        }
                    }
                ]
            }

            response = requests.post("http://127.0.0.1:8080/add",
                                     json=data, headers={'Content-Type': 'application/json'})

            self.assertTrue(response.status_code, 200)
            self.assertTrue(len(server._tasks.tasks), 2)

            response = requests.post("http://127.0.0.1:8080/tasks",
                                     json=data, headers={'Content-Type': 'application/json'})

            self.assertTrue(response.status_code, 200)

            content = json.loads(response.content.decode('utf8').replace("'", '"'))

            self.assertEqual(len(content['tasks']), len(server._tasks.tasks))
            self.assertEqual(content["tasks"][0]["task_id"], data["tasks"][0]["task_id"])
            self.assertEqual(content["tasks"][1]["task_id"], data["tasks"][1]["task_id"])

    @unittest.mock.patch('arthur.tasks.datetime_utcnow')
    def test_task(self, mock_utcnow):
        """Check whether task data is retrieved"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        with run_server(self.conn) as server:
            data = {
                "tasks": [
                    {
                        "task_id": "arthur.git",
                        "backend": "git",
                        "backend_args": {
                            "gitpath": os.path.join(self.dir, 'data/git_log.txt'),
                            "uri": "http://example.com/",
                        },
                        "category": "commit",
                        "archive": {},
                        "scheduler": {
                            "delay": 10
                        }
                    }
                ]
            }
            response = requests.post("http://127.0.0.1:8080/add",
                                     json=data, headers={'Content-Type': 'application/json'})

            self.assertTrue(response.status_code, 200)
            self.assertTrue(len(server._tasks.tasks), 2)

            # Run the tasks
            server.start()

            response = requests.post("http://127.0.0.1:8080/task/arthur.git",
                                     json=data, headers={'Content-Type': 'application/json'})
            self.assertTrue(response.status_code, 200)

            task = json.loads(response.content.decode('utf8').replace("'", '"'))
            jobs = task.pop('jobs')

            expected_task = {
                'task_id': 'arthur.git',
                'backend': 'git',
                'status': 'ENQUEUED',
                'age': 1,
                'backend_args': {
                    'gitpath': os.path.join(self.dir, 'data/git_log.txt'),
                    'uri': 'http://example.com/',
                },
                'created_on': 1483228800.0,
                'category': 'commit',
                'archiving_cfg': None,
                'scheduling_cfg': {
                    'delay': 10,
                    'max_retries': 3,
                    'max_age': None,
                    'queue': None
                }
            }

            # Check task data
            self.assertDictEqual(task, expected_task)
            self.assertEqual(len(jobs), 1)

            # Check jobs data
            job = jobs[0]
            self.assertEqual(job['task_id'], 'arthur.git')
            self.assertEqual(job['job_status'], 'finished')

            # TODO: mock job ids generator
            expected_job_result = {
                'task_id': 'arthur.git',
                'last_uuid': '1375b60d3c23ac9b81da92523e4144abc4489d4c',
                'max_date': 1392185439.0,
                'nitems': 9,
                'offset': None,
            }

            job_result = job['result']
            job_result.pop('job_id')

            self.assertEqual(job_result, expected_job_result)


if __name__ == "__main__":
    unittest.main()
