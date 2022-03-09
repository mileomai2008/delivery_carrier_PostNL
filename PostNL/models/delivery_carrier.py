# -*- coding:  utf-8 -*-

from odoo import fields,  models, api, _
from .postNL_requests import PostNLRequets
from odoo.exceptions import UserError
from odoo.exceptions import UserError
import json
import time
import logging
_logger = logging.getLogger(__name__)


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"
    delivery_type = fields.Selection(selection_add=[("post_nl",  "PostNL")])
    api_key = fields.Char('PostNL Api Key')
    postnl_customer_code = fields.Char("Company Code")
    postnl_customer_number = fields.Char("Company Number")
    postnl_default_product_code = fields.Selection(
        [('3085', '3085, Dutch domestic products -'
                  ' Standard shipping - Guaranteed Morning delivery'),
         ('4945', '4945: Global shipping')
         # @TODo add the rest of shipping types
         ], default='3085', string="Default Product Code Delivery")
    postnl_gloable_license_nr = fields.Char("Global Shipping License")
    postnl_base_shipping_cost = fields.Float('Base Shipping Coast')

    def weight_converter(self, from_uom, weight):
        """Weigh convertor because PostNL only accept shippiments in gram.
        @TODO we can search for gram in the uom.uom table
        in case that the uom.product_uom_gram was deleted
        and raise and error if no unit of gram mesaure exists."""
        to_uom = self.env.ref('uom.product_uom_gram')
        if to_uom:
            return from_uom._compute_quantity(weight, to_uom)
        else:
            return weight

    def get_product_code(self, picking):
        """@TODO this function can be changed to check for sender
        and reciver destion or add the product option to
        the SO or stock picking.
        Might need to add more paramters in the future."""
        return picking.carrier_id.postnl_default_product_code

    def _prepare_shipments_addresses_data(self, picking):
        vals = {}
        vals.update({
            "AddressType":  "01",
            "City": picking.partner_id.city or ' ',
            "CompanyName": picking.partner_id.name or ' ',
            "Countrycode": picking.partner_id.country_id.code or ' ',
            "HouseNr": picking.partner_id.street2 or ' ',
            "Street": picking.partner_id.street or ' ',
            "Zipcode":  picking.partner_id.zip or ''
            })
        return vals

    def _prepare_shipments_contacts_data(self, picking):
        vals = {}
        vals.update({
            "ContactType":  "01",
            "Email": picking.partner_id.email or ' ',
            "SMSNr": picking.partner_id.phone or ' '
            })
        return vals

    def _prepare_customs(self, picking):
        """@TODO add a function to switch all values
        to EUR (POSTNL only accept EURO or USS)."""
        vals = {}
        _logger.info('getting customs for gloabl shippings only')
        vals.update({
            "Content": [{
                "CountryOfOrigin": picking.company_id.country_id.code,
                "Description": line.product_id.name,
                "Quantity": line.product_uom_qty,
                "Value": abs(line.value),
                "Weight": self.weight_converter(
                    picking.weight_uom_id, line.weight
                    )}
                for line in picking.move_lines],
            "Currency":  "EUR",
            "HandleAsNonDeliverable":  "false",
            "License":  "true",
            "LicenseNr": picking.carrier_id.postnl_gloable_license_nr or ' ',

            "ShipmentType":  "Commercial Goods"})
        _logger.info(vals)
        return vals

    def _prepare_customer_data(self, picking):
        vals = {}
        vals.update({
            "Address": {
                "AddressType":  "02",
                "City": picking.company_id.city or ' ',
                "CompanyName": picking.company_id.name or ' ',
                "Countrycode": picking.company_id.country_id.code or ' ',
                "HouseNr": picking.company_id.street2 or ' ',
                "Street": picking.company_id.street or ' ',
                "Zipcode":  picking.company_id.zip or ''},
            "CollectionLocation":  picking.company_id.zip or '',
            "ContactPerson":  picking.company_id.name or '',
            "CustomerCode":  picking.carrier_id.postnl_customer_code or '',
            "CustomerNumber": picking.carrier_id.postnl_customer_number or '',
            "Email": picking.company_id.email,
            "Name": picking.create_uid.name
            })
        return vals

    def _prepare_shipments_data(self, picking):
        vals = {}
        if picking.shipping_weight != 0:
            weight = self.weight_converter(
                picking.weight_uom_id,
                picking.shipping_weight
                )
        else:
            weight = self.weight_converter(
                picking.weight_uom_id,
                sum([line.weight for line in picking.move_lines])
                )

        vals.update({
            "Addresses": [self._prepare_shipments_addresses_data(picking)],
            "Contacts": [self._prepare_shipments_contacts_data(picking)],
            "Dimension": {"Weight": weight},
            "ProductCodeDelivery": self.get_product_code(picking)})
        if self.get_product_code(picking) == '4945':
            # customs ar required in globale shipping only.
            vals["Customs"] = self._prepare_customs(picking)
        return vals

    def _prepare_shipping_body(self, picking):
        vals = {}
        current_date = time.strftime('%d-%m-%Y %H: %M: %S')
        vals.update({
            "Customer":  self._prepare_customer_data(picking),
            "Message":  {
                "MessageID":  "01",
                "MessageTimeStamp":  current_date,
                "Printertype":  "GraphicFile|PDF"},
            "Shipments":  [self._prepare_shipments_data(picking)]
            })
        return vals


    def post_nl_send_shipping(self, pickings):

        _logger.info('starting the ship PostNL Porcess')
        for picking in pickings:
            data = self._prepare_shipping_body(picking)

            _logger.info('JSON body to the shipping api:  %s' % ((data)))
            response, status_code = PostNLRequets(
                self.api_key, self.prod_environment).ship(data)
            _logger.info('PostNL Response :  %s' % (response))
            _logger.info('PostNL Response Status Code :  %s' % (status_code))

            # TODO insepct repsonse and get barcode
            # or tracking_number and Generated file
            # then send them to the stock_picking.
            # The rest is just a guess base on
            # PostNL api response example.

            try:
                for response_shipment in response['ResponseShipments']:
                    if 'Barcode' in response_shipment:
                        return [{
                            "exact_price": self.postnl_base_shipping_cost or 0,
                            "tracking_number": response_shipment['Barcode']
                            }]
            except Exception:
                if 'fault' in response:
                    msg = _(f'Error<{status_code}>:\n'
                            f" {response['fault']['faultstring']}")
                else:
                    msg = _('Error While Shipping to PostNL.\n'
                            'Please Revise Your Shippment Data.')
                raise UserError(msg)

    def post_nl_get_tracking_link(self, picking):
        if picking.carrier_tracking_ref:
            url = 'https://www.internationalparceltracking.com/#/search?barcode='
            return '%s%s' % (url, picking.carrier_tracking_ref)
        else:
            return False

    def post_nl_cancel_shipment(self,  picking):
        raise UserError(_("Can't Cancel PonstNL Shipments"))
