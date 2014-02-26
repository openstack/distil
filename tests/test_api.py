from webtest import TestApp
from . import test_interface
from api.web import get_app
from artifice import models
from artifice import interface
from datetime import datetime, timedelta
from random import randint 
import mock

import unittest


class TestApi(test_interface.TestInterface):

    def setUp(self):
        super(TestApi, self).setUp()
        self.app = TestApp(get_app(test_interface.config))
         
    def tearDown(self):
        super(TestApi, self).tearDown()
        self.app = None

    def fill_db(self, numb_tenants, numb_resources, now):
        self.session.begin(subtransactions=True)
        for i in range(numb_tenants):
            self.session.add(models.Tenant(
                id="tenant_id_" + str(i),
                info="metadata",
                name="tenant_name_" + str(i),
                created=now
            ))
            for ii in range(numb_resources):
                self.session.add(models.Resource(
                    id="resource_id_" + str(ii),
                    info=str({"type": "Resource" + str(ii)}),
                    tenant_id="tenant_id_" + str(i),
                    created=now
                ))
                self.session.add(models.UsageEntry(
                    service="service" + str(ii),
                    volume=5,
                    resource_id="resource_id_" + str(ii),
                    tenant_id="tenant_id_" + str(i),
                    start=(now - timedelta(days=30)),
                    end=now,
                    created=now
                ))
        self.session.commit()

    
    # Modify Artifice, the Ceilometer client
    @mock.patch("artifice.interface.keystone")
    def test_usage_run_for_all(self, keystone):
        """Asserts a usage run generates data for all tenants"""
        
        self.test_get_usage()

        with mock.patch('artifice.interface.Artifice') as Artifice:

            tenants = []

            for tenant in test_interface.TENANTS:
                t = mock.Mock(spec=interface.Tenant)
                t.usage.return_value = self.usage
                t.conn = tenant
                tenants.append(t)

            artifice = mock.Mock(spec=interface.Artifice)

            artifice.tenants = tenants

            Artifice.return_value = artifice

            resp = self.app.post("/collect_usage")
            self.assertEquals(resp.status_int, 200)

            tenants = self.session.query(models.Tenant)
            self.assertTrue(tenants.count() > 0)

            usages = self.session.query(models.UsageEntry)
            self.assertTrue(usages.count() > 0)
            resources = self.session.query(models.Resource)
            count = 0
            for res_type in self.usage.values():
                count += len(res_type)
            self.assertEquals(resources.count(), count)

    @unittest.skip
    def test_sales_run_for_all(self):
        """"Assertion that a sales run generates all tenant information"""
        # We need to set up the usage information first

        self.test_usage_run_for_all()
        resp = self.app.post("/sales_order", dict(tenants=[]))
        self.assertEquals(resp.status_int, 201)
        
        tenants = self.db.query(models.Tenant)
        for tenant in tenants:
            self.assertTrue(len( tenant.orders ) == 1) # One sales order only

    def test_sales_run_single(self):
        """Assertion that a sales run generates one tenant only"""

        now = datetime.now()
        self.fill_db(1, 3, now)
        resp = self.app.post("/sales_order", dict(tenants=["tenant_name_0"]))

        self.assertEquals(resp.status_int, 201)
        
        tenant = self.session.query(models.Tenant).get(self.tenant)
        order_count = self.session.query(models.SalesOrder).count()
        self.assertEqual(order_count, 1)
    
    @unittest.skip
    def test_no_usage_body_raises_403(self):
        """Assertion that no body on usage request raises 403"""
        resp = self.app.post("/collect_usage")
        self.assertTrue(resp.status_int, 403)

    @unittest.skip
    def test_no_sales_body_raises_403(self):
        """Assertion that no body on sales request raises 403"""
        resp = self.app.post("/generate_sales_order")
        self.assertTrue(resp.status_int, 403)
