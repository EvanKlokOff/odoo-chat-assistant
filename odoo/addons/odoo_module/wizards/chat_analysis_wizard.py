from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import logging

_logger = logging.getLogger(__name__)


class ChatAnalysisWizard(models.TransientModel):
    _name = 'chat.analysis.wizard'
    _description = 'Chat Analysis Wizard'

    chat_id = fields.Many2one('chat.analysis.chat', string='Chat', required=True)
    report_type = fields.Selection([
        ('review', 'Review'),
        ('compliance', 'Compliance Check')
    ], string='Report Type', required=True, default='review')

    date_start = fields.Datetime(string='Start Date', required=True,
                                 default=fields.Datetime.now)
    date_end = fields.Datetime(string='End Date', required=True,
                               default=fields.Datetime.now)

    instruction = fields.Text(string='Instruction',
                              help='Instruction for compliance check (required for Compliance Check)',
                              placeholder="Example: All messages must be respectful, professional, and comply with company policies...")

    instruction_domain = fields.Char(string='Instruction Domain',
                                     help='Domain/context of the instruction (e.g., customer support, sales, internal communication)')

    def action_analyze(self):
        """Execute analysis based on selected report type"""
        self.ensure_one()

        # Validation
        if self.date_start >= self.date_end:
            raise ValidationError("Start date must be before end date")

        if self.report_type == 'compliance' and not self.instruction:
            raise ValidationError("Instruction is required for compliance check")

        try:
            # Create report record with period-based fields
            report = self.env['chat.analysis.report'].create({
                'chat_id': self.chat_id.id,
                'analysis_type': self.report_type,
                'date_start': self.date_start,
                'date_end': self.date_end,
                'instruction': self.instruction,
                'instruction_domain': self.instruction_domain,
                'state': 'pending',
                'user_id': self.env.user.id,
            })

            # Trigger async analysis
            report.action_analyze()

            # Return to report form
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'chat.analysis.report',
                'res_id': report.id,
                'view_mode': 'form',
                'target': 'current',
            }

        except Exception as e:
            _logger.error(f"Analysis wizard failed: {e}")
            raise UserError(f"Failed to start analysis: {str(e)}")


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
            api_url = config.get_param('chat_analysis.api_url', 'http://chat_api:8000').rstrip('/') + '/api/v1'
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
