from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    chat_analysis_api_url = fields.Char(
        string='API URL',
        config_parameter='chat_analysis.api_url',
        default='http://chat_api:8000'
    )
    chat_analysis_api_key = fields.Char(
        string='API Key',
        config_parameter='chat_analysis.api_key',
        default='odoo_api_key_1'
    )
    chat_analysis_auto_sync = fields.Boolean(
        string='Auto Sync',
        config_parameter='chat_analysis.auto_sync',
        default=False
    )
    chat_analysis_sync_interval = fields.Integer(
        string='Sync Interval (hours)',
        config_parameter='chat_analysis.sync_interval',
        default=6
    )

    def action_test_api_connection(self):
        """Тест подключения к API"""
        from odoo.exceptions import UserError
        import requests

        config = self.env['ir.config_parameter'].sudo()
        api_url = config.get_param('chat_analysis.api_url', 'http://chat_api:8000')
        api_key = config.get_param('chat_analysis.api_key', '')

        try:
            response = requests.get(
                f"{api_url}/health",
                headers={'Authorization': f'Bearer {api_key}'},
                timeout=5
            )
            if response.status_code == 200:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': f'API connection successful! Server: {api_url}',
                        'type': 'success',
                    }
                }
            else:
                raise UserError(f'API returned status {response.status_code}')
        except Exception as e:
            raise UserError(f'API connection failed: {str(e)}')