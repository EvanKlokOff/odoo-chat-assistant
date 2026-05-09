from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    chat_analysis_api_url = fields.Char(
        string='API URL',
        config_parameter='chat_analysis.api_url',
        default='http://localhost:8000'
    )
    chat_analysis_api_key = fields.Char(
        string='API Key',
        config_parameter='chat_analysis.api_key',
        default=''
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