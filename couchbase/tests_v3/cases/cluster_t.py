# -*- coding:utf-8 -*-
#
# Copyright 2020, Couchbase, Inc.
# All Rights Reserved
#
# Licensed under the Apache License, Version 2.0 (the "License")
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import unittest

from couchbase_tests.base import CollectionTestCase
from couchbase.cluster import ClusterOptions, ClusterTimeoutOptions,\
    ClusterTracingOptions, Compression, DiagnosticsOptions, Cluster
from couchbase.auth import PasswordAuthenticator, ClassicAuthenticator
from couchbase.diagnostics import ServiceType, EndpointState, ClusterState
from couchbase.exceptions import AlreadyShutdownException, BucketNotFoundException
from couchbase.auth import NoBucketException
from datetime import timedelta
from unittest import SkipTest


class ClusterTests(CollectionTestCase):
    def setUp(self):
        super(ClusterTests, self).setUp()

    def test_diagnostics(self):
        result = self.cluster.diagnostics(DiagnosticsOptions(report_id="imareportid"))
        self.assertIn("imareportid", result.id)
        self.assertIsNotNone(result.sdk)
        self.assertIsNotNone(result.version)
        self.assertEquals(result.state, ClusterState.Online)
        if not self.is_mock:
            # no matter what there should be a config service type in there,
            # as long as we are not the mock.
            config = result.endpoints[ServiceType.Config]
            self.assertTrue(len(config) > 0)
            self.assertIsNotNone(config[0].id)
            self.assertIsNotNone(config[0].local)
            self.assertIsNotNone(config[0].remote)
            self.assertIsNotNone(config[0].last_activity)
            self.assertEqual(config[0].state, EndpointState.Connected)
            self.assertEqual(config[0].type, ServiceType.Config)

    def test_diagnostics_with_active_bucket(self):
        query_result = self.cluster.query('SELECT * FROM `beer-sample` LIMIT 1')
        if self.is_mock:
            try:
                query_result.rows()
            except:
                pass
        else:
            self.assertTrue(len(query_result.rows()) > 0)
        result = self.cluster.diagnostics(DiagnosticsOptions(report_id="imareportid"))
        print(result.as_json())
        self.assertIn("imareportid", result.id)

        if not self.is_mock:
            # no matter what there should be a config service type in there,
            # as long as we are not the mock.
            config = result.endpoints[ServiceType.Config]
            self.assertTrue(len(config) > 0)

        # but now, we have hit Query, so...
        q = result.endpoints[ServiceType.Query]
        self.assertTrue(len(q) > 0)
        self.assertIsNotNone(q[0].id)
        self.assertIsNotNone(q[0].local)
        self.assertIsNotNone(q[0].remote)
        self.assertIsNotNone(q[0].last_activity)
        self.assertEqual(q[0].state, EndpointState.Connected)
        self.assertEqual(q[0].type, ServiceType.Query)

    def test_disconnect(self):
        # for this test we need a new cluster...
        if self.is_mock:
            raise SkipTest("query not mocked")
        cluster = Cluster.connect(self.cluster.connstr, ClusterOptions(
            PasswordAuthenticator(self.cluster_info.admin_username, self.cluster_info.admin_password)))
        # Temporarily, lets open a bucket to insure the admin object was created
        b = cluster.bucket(self.bucket_name)
        # verify that we can get a bucket manager
        self.assertIsNotNone(cluster.buckets())
        # disconnect cluster
        cluster.disconnect()
        self.assertRaises(AlreadyShutdownException, cluster.buckets)

    def _authenticator(self):
        if self.is_mock:
            return ClassicAuthenticator(self.cluster_info.admin_username, self.cluster_info.admin_password)
        return PasswordAuthenticator(self.cluster_info.admin_username, self.cluster_info.admin_password)

    def _create_cluster_opts(self, **kwargs):
        return ClusterOptions(self._authenticator(), **kwargs)

    def _mock_hack(self):
        if self.is_mock:
            return {'bucket': self.bucket_name}
        return {}

    def test_can_override_timeout_options(self):
        timeout = timedelta(seconds=100)
        timeout2 = timedelta(seconds=50)
        opts = self._create_cluster_opts(timeout_options=ClusterTimeoutOptions(kv_timeout=timeout))
        args = self._mock_hack()
        args.update({'timeout_options': ClusterTimeoutOptions(kv_timeout=timeout2)})
        cluster = Cluster.connect(self.cluster.connstr, opts, **args)
        b = cluster.bucket(self.bucket_name)
        self.assertEqual(timeout2, b.kv_timeout)

    def test_can_override_tracing_options(self):
        timeout = timedelta(seconds=50)
        timeout2 = timedelta(seconds=100)
        opts = self._create_cluster_opts(
            tracing_options=ClusterTracingOptions(tracing_orphaned_queue_flush_interval=timeout))
        args = self._mock_hack()
        args.update({'tracing_options': ClusterTracingOptions(tracing_orphaned_queue_flush_interval=timeout2)})
        cluster = Cluster.connect(self.cluster.connstr, opts, **args)
        self.assertEqual(timeout2, cluster.tracing_orphaned_queue_flush_interval)
        b = cluster.bucket(self.bucket_name)
        self.assertEqual(timeout2, b.tracing_orphaned_queue_flush_interval)

    def test_can_override_cluster_options(self):
        compression = Compression.FORCE
        compression2 = Compression.IN
        opts = self._create_cluster_opts(compression=compression)
        args = self._mock_hack()
        args.update({'compression': compression2})
        cluster = Cluster.connect(self.cluster.connstr, opts, **args)
        self.assertEqual(compression2, cluster.compression)

    def test_kv_default_timeout(self):
        timeout = timedelta(seconds=50)
        opts = self._create_cluster_opts(timeout_options=ClusterTimeoutOptions(kv_timeout=timeout))
        cluster = Cluster.connect(self.cluster.connstr, opts, **self._mock_hack())
        b = cluster.bucket(self.bucket_name)
        self.assertEqual(timeout, b.kv_timeout)

    def test_views_default_timeout(self):
        timeout = timedelta(seconds=50)
        opts = self._create_cluster_opts(timeout_options=ClusterTimeoutOptions(views_timeout=timeout))
        cluster = Cluster.connect(self.cluster.connstr, opts, **self._mock_hack())
        b = cluster.bucket(self.bucket_name)
        self.assertEqual(timeout, b.views_timeout)

    def test_query_default_timeout(self):
        timeout = timedelta(seconds=50)
        opts = self._create_cluster_opts(timeout_options=ClusterTimeoutOptions(query_timeout=timeout))
        cluster = Cluster.connect(self.cluster.connstr, opts, **self._mock_hack())
        self.assertEqual(timeout, cluster.query_timeout)

    def test_tracing_orphaned_queue_flush_interval(self):
        timeout = timedelta(seconds=50)
        opts = self._create_cluster_opts(
            tracing_options=ClusterTracingOptions(tracing_orphaned_queue_flush_interval=timeout))
        cluster = Cluster.connect(self.cluster.connstr, opts, **self._mock_hack())
        self.assertEqual(timeout, cluster.tracing_orphaned_queue_flush_interval)
        b = cluster.bucket(self.bucket_name)
        self.assertEqual(timeout, b.tracing_orphaned_queue_flush_interval)

    def test_tracing_orphaned_queue_size(self):
        size = 10
        opt = ClusterTracingOptions(tracing_orphaned_queue_size=size)
        opts = self._create_cluster_opts(tracing_options=opt)
        cluster = Cluster.connect(self.cluster.connstr, opts, **self._mock_hack())
        self.assertEqual(10, cluster.tracing_orphaned_queue_size)
        b = cluster.bucket(self.bucket_name)
        self.assertEqual(size, b.tracing_orphaned_queue_size)

    def test_tracing_threshold_queue_flush_interval(self):
        timeout = timedelta(seconds=10)
        opt = ClusterTracingOptions(tracing_threshold_queue_flush_interval=timeout)
        opts = self._create_cluster_opts(tracing_options=opt)
        cluster = Cluster.connect(self.cluster.connstr, opts, **self._mock_hack())
        self.assertEqual(timeout, cluster.tracing_threshold_queue_flush_interval)
        b = cluster.bucket(self.bucket_name)
        self.assertEqual(timeout, b.tracing_threshold_queue_flush_interval)

    def test_tracing_threshold_queue_size(self):
        size = 100
        opt = ClusterTracingOptions(tracing_threshold_queue_size=size)
        opts = self._create_cluster_opts(tracing_options=opt)
        cluster = Cluster.connect(self.cluster.connstr, opts, **self._mock_hack())
        self.assertEqual(size, cluster.tracing_threshold_queue_size)
        b = cluster.bucket(self.bucket_name)
        self.assertEqual(size, b.tracing_threshold_queue_size)

    @unittest.skip("waiting on CCBC-1222")
    def test_tracing_threshold_query(self):
        timeout = timedelta(seconds=0.3)
        opt = ClusterTracingOptions(tracing_threshold_query=timeout)
        opts = self._create_cluster_opts(tracing_options=opt)
        cluster = Cluster.connect(self.cluster.connstr, opts, **self._mock_hack())
        self.assertEqual(timeout, cluster.tracing_threshold_query)

    @unittest.skip("waiting on CCBC-1222")
    def test_tracing_threshold_search(self):
        timeout = timedelta(seconds=0.3)
        opt = ClusterTracingOptions(tracing_threshold_search=timeout)
        opts = self._create_cluster_opts(tracing_options=opt)
        cluster = Cluster.connect(self.cluster.connstr, opts, **self._mock_hack())
        self.assertEqual(timeout, cluster.tracing_threshold_search)

    def test_tracing_threshold_analytics(self):
        timeout = timedelta(seconds=0.3)
        opt = ClusterTracingOptions(tracing_threshold_analytics=timeout)
        opts = self._create_cluster_opts(tracing_options=opt)
        cluster = Cluster.connect(self.cluster.connstr, opts, **self._mock_hack())
        self.assertEqual(timeout, cluster.tracing_threshold_analytics)

    def test_compression(self):
        compression = Compression.FORCE
        opts = self._create_cluster_opts(compression=compression)
        cluster = Cluster.connect(self.cluster.connstr, opts, **self._mock_hack())
        self.assertEqual(compression, cluster.compression)

    def test_compression_min_size(self):
        size = 5000
        opts = self._create_cluster_opts(compression_min_size=size)
        cluster = Cluster.connect(self.cluster.connstr, opts, **self._mock_hack())
        self.assertEqual(size, cluster.compression_min_size)

    def test_compression_min_ratio(self):
        ratio = 0.5
        opts = self._create_cluster_opts(compression_min_ratio=ratio)
        cluster = Cluster.connect(self.cluster.connstr, opts, **self._mock_hack())
        self.assertEqual(ratio, cluster.compression_min_ratio)

    def test_redaction(self):
        opts = self._create_cluster_opts(log_redaction=True)
        cluster = Cluster.connect(self.cluster.connstr, opts, **self._mock_hack())
        self.assertTrue(cluster.redaction)

    def test_is_ssl(self):
        # well, our tests are not ssl, so...
        self.assertFalse(self.cluster.is_ssl)

    @unittest.skip("Skip until the admin stuff is worked out")
    def test_cluster_may_need_open_bucket_before_admin_calls(self):
        # NOTE: some admin calls -- like listing query indexes, seem to require
        # that the admin was given a bucket.  That can only happen if we have already
        # opened a bucket, which is what usually happens in the tests.  This does not, and
        # checks for the exception when appropriate.
        if self.is_mock:
            raise SkipTest("mock doesn't support the admin call we are making")
        cluster = Cluster.connect(self.cluster.connstr, self._create_cluster_opts(), **self._mock_hack())
        if cluster._is_6_5_plus():
            self.assertIsNotNone(cluster.query_indexes().get_all_indexes(self.bucket_name))
        else:
            self.assertRaises(NoBucketException, cluster.query_indexes().list_all_indexes, self.bucket_name)

    def can_do_admin_calls_after_unsuccessful_bucket_openings(self):
        cluster = Cluster.connect(self.cluster.connstr, self._create_cluster_opts(), **self._mock_hack())
        self.assertRaises(BucketNotFoundException, cluster.bucket, "flkkjkjk")
        self.assertIsNotNone(cluster.bucket(self.bucket_name))
        self.assertIsNotNone(cluster.query_indexes().list_all_indexes(self.bucket_name))
