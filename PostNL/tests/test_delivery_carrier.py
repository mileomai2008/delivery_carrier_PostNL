from odoo.tests.common import Form, SavepointCase
from odoo.tools import mute_logger
from odoo.addons.PostNL.models.postNL_requests import PostNLRequets
import json


class TestDeliveryCarrier(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner_18 = cls.env.ref("base.res_partner_18")
        cls.product_4 = cls.env.ref("product.product_product_4")
        cls.serice_product = cls.env["product.product"].create(
            {"name": "shipping", "type": "service"}
        )
        cls.carrier = cls.env["delivery.carrier"].create(
            {
                "name": "post_nl",
                "delivery_type": "post_nl",
                "prod_environment": False,
                "product_id": cls.serice_product.id,
            }
        )
        cls.carrier_gloable = cls.env["delivery.carrier"].create(
            {
                "name": "post_nl Gloable",
                "delivery_type": "post_nl",
                "prod_environment": False,
                "product_id": cls.serice_product.id,
                "postnl_default_product_code": "4945",
            }
        )

        cls.sale = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner_18.id,
                "partner_shipping_id": cls.partner_18.id,
                "state": "draft",
                "carrier_id": cls.carrier.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "name": "PC Assamble + 2GB RAM",
                            "product_id": cls.product_4.id,
                            "product_uom_qty": 1,
                            "price_unit": 750.00,
                        },
                    )
                ],
            }
        )
        cls.sale_gloable = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner_18.id,
                "partner_shipping_id": cls.partner_18.id,
                "state": "draft",
                "carrier_id": cls.carrier_gloable.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "name": "PC Assamble + 2GB RAM",
                            "product_id": cls.product_4.id,
                            "product_uom_qty": 1,
                            "price_unit": 750.00,
                        },
                    )
                ],
            }
        )
        cls.sale.action_confirm()
        cls.picking = cls.sale.picking_ids
        cls.sale_gloable.action_confirm()
        cls.picking_gloabale = cls.sale_gloable.picking_ids

    def test_check_type(self):
        """ Checking Carrier Type"""
        self.assertEqual(
            self.picking.carrier_id.delivery_type,
            'post_nl',
            'delivery_type should be post_nl')

    def test_picking_shipping_data(self):
        """Checking data types"""
        data = self.carrier._prepare_shipping_body(self.picking)
        self.assertEqual(
            type(data),
            type({}),
            'data should be a dict')

    def test_picking_local_shipping_Customs(self):
        """Checking Customs doesn't exists"""
        data = self.carrier._prepare_shipping_body(self.picking)
        first_shipping = data['Shipments'][0]
        keys = [*first_shipping.keys()]
        self.assertEqual(
            'Customs' in keys,
            False,
            'No Customs For Loacal Shippings')

    def test_picking_gloable_shipping_Customs(self):
        """Checking Customs exists for gloable shippings"""
        data = self.carrier_gloable._prepare_shipping_body(self.picking_gloabale)
        first_shipping = data['Shipments'][0]
        keys = [*first_shipping.keys()]
        self.assertEqual(
            'Customs' in keys,
            True,
            'Customs Required For Gloable Shippings')

    def test_post_no_api_key(self):
        """Get 401 Unauthorized If No API Key"""
        data = self.carrier._prepare_shipping_body(self.picking)
        response, status_code = PostNLRequets(
                '', self.carrier.prod_environment).ship(data)
        self.assertEqual(
            str(status_code),
            '401',
            '401 Error If No Api Key')
