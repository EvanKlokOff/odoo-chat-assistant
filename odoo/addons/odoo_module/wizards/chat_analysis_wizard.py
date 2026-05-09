from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)


class ChatAnalysisWizard(models.TransientModel):
    _name = 'chat.analysis.wizard'
    _description = 'Chat Analysis Wizard'

    chat_id = fields.Many2one('chat.analysis.chat', string='Chat', required=True)
    target_datetime = fields.Datetime(string='Target Date/Time', required=True, default=fields.Datetime.now)
    lookback_minutes = fields.Integer(string='Lookback Minutes', default=60)
    lookforward_minutes = fields.Integer(string='Lookforward Minutes', default=60)
    instruction = fields.Text(string='Instruction', help='Instruction for compliance check')

    def action_review(self):
        """Выполнить ревью"""
        report = self.env['chat.analysis.report'].create({
            'chat_id': self.chat_id.id,
            'analysis_type': 'review',
            'target_datetime': self.target_datetime,
            'lookback_minutes': self.lookback_minutes,
            'lookforward_minutes': self.lookforward_minutes,
        })

        report.action_process_review()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'chat.analysis.report',
            'res_id': report.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_compliance(self):
        """Выполнить проверку соответствия"""
        if not self.instruction:
            raise UserError("Please provide an instruction for compliance check")

        report = self.env['chat.analysis.report'].create({
            'chat_id': self.chat_id.id,
            'analysis_type': 'compliance',
            'target_datetime': self.target_datetime,
            'instruction': self.instruction,
            'lookback_minutes': self.lookback_minutes,
            'lookforward_minutes': self.lookforward_minutes,
        })

        report.action_process_compliance()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'chat.analysis.report',
            'res_id': report.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _get_api_url(self):
        config = self.env['ir.config_parameter'].sudo()
        base_url = config.get_param('chat_analysis.api_url', 'http://localhost:8000')
        return base_url.rstrip('/') + '/api/v1'

    def _get_headers(self):
        config = self.env['ir.config_parameter'].sudo()
        api_key = config.get_param('chat_analysis.api_key', '')
        return {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }


class ChatSyncBatchWizard(models.TransientModel):
    _name = 'chat.sync.batch.wizard'
    _description = 'Batch Sync Wizard'

    sync_type = fields.Selection([
        ('users', 'Sync Users Only'),
        ('chats', 'Sync Chats Only'),
        ('messages', 'Sync Messages Only'),
        ('all', 'Sync All')
    ], string='Sync Type', required=True, default='all')

    def action_sync(self):
        """Выполнить пакетную синхронизацию"""
        try:
            config = self.env['ir.config_parameter'].sudo()
            api_url = config.get_param('chat_analysis.api_url', 'http://localhost:8000').rstrip('/') + '/api/v1'
            api_key = config.get_param('chat_analysis.api_key', '')
            headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

            if self.sync_type in ['users', 'all']:
                response = requests.get(f"{api_url}/users", headers=headers, timeout=30)
                if response.status_code == 200:
                    self._sync_users(response.json())

            if self.sync_type in ['chats', 'all']:
                response = requests.get(f"{api_url}/chats", headers=headers, timeout=30)
                if response.status_code == 200:
                    self._sync_chats(response.json())

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Synchronization completed successfully'),
                    'type': 'success',
                }
            }

        except Exception as e:
            raise UserError(f"Batch sync failed: {str(e)}")

    def _sync_users(self, users_data):
        User = self.env['chat.analysis.user']
        for user_data in users_data:
            existing = User.search([('external_id', '=', user_data['user_id'])], limit=1)
            if existing:
                existing.write({
                    'user_name': user_data.get('user_name', existing.user_name),
                    'telegram_id': user_data.get('telegram_id', existing.telegram_id),
                })
            else:
                User.create({
                    'external_id': user_data['user_id'],
                    'user_name': user_data.get('user_name', f"User_{user_data['user_id']}"),
                    'telegram_id': user_data.get('telegram_id', user_data['user_id']),
                })

    def _sync_chats(self, chats_data):
        Chat = self.env['chat.analysis.chat']
        for chat_data in chats_data:
            existing = Chat.search([('external_id', '=', chat_data['chat_id'])], limit=1)
            if existing:
                existing.write({
                    'title': chat_data.get('title', existing.title),
                })
            else:
                Chat.create({
                    'external_id': chat_data['chat_id'],
                    'title': chat_data.get('title', f"Chat_{chat_data['chat_id']}"),
                })