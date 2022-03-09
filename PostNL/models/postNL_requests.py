# -*- coding: utf-8 -*-
from odoo import _
from odoo.exceptions import ValidationError, UserError
import requests
import json


class PostNLRequets:
    def __init__(self, api_key=None, prod_environment=False):
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = '1'
        if prod_environment:
            self.postNL_url = 'https://api.postnl.nl/shipment/'
        else:
            self.postNL_url = 'https://api-sandbox.postnl.nl/'

    def __str__(self):
        return f'PostNLRequets with key {self.api_key}'

    def ship(self, body):
        try:
            body = json.loads(json.dumps(body))
        except Exception as e:
            raise UserError(_('Data Error: [%s]' % (e)))
        hdr = {'content-type': 'application/json',
               'apikey': self.api_key}
        url = f'{self.postNL_url}v1/shipment'
        try:
            response = requests.post(url, data=body, headers=hdr)
        except Exception as e:
            raise UserError(_('Error Connecting to PostNL : [%s]' % (e)))
        response_json_string = response.content.decode('utf-8')
        response_json_object = json.loads(str(response_json_string))
        return dict(response_json_object), response.status_code
