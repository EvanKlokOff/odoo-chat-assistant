from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import requests

_logger = logging.getLogger(__name__)


class ChatAnalysisUser(models.Model):
    _name = 'chat.analysis.user'
    _description = 'Chat User'
    _rec_name = 'user_name'
    _order = 'user_name'

    external_id = fields.Char(string='External ID', required=True, index=True)
    user_name = fields.Char(string='User Name', required=True)
    telegram_id = fields.Char(string='Telegram ID', index=True)

    chat_ids = fields.Many2many('chat.analysis.chat', string='Chats', relation='chat_user_analysis_rel')
    report_ids = fields.One2many('chat.analysis.report', 'user_id', string='Reports')

    message_count = fields.Integer(string='Messages Count', compute='_compute_message_count')
    last_active = fields.Datetime(string='Last Active', compute='_compute_last_active')

    _sql_constraints = [
        ('external_id_unique', 'unique(external_id)', 'User ID must be unique!')
    ]

    def _compute_message_count(self):
        for user in self:
            user.message_count = self.env['chat.analysis.message'].search_count([
                ('user_id', '=', user.id)
            ])

    def _compute_last_active(self):
        for user in self:
            last_message = self.env['chat.analysis.message'].search([
                ('user_id', '=', user.id)
            ], order='timestamp desc', limit=1)
            user.last_active = last_message.timestamp if last_message else False

    def action_view_messages(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'User Messages',
            'res_model': 'chat.analysis.message',
            'view_mode': 'tree,form',
            'domain': [('user_id', '=', self.id)],
            'context': {'default_user_id': self.id},
        }


class ChatAnalysisChat(models.Model):
    _name = 'chat.analysis.chat'
    _description = 'Chat Analysis'
    _rec_name = 'title'
    _order = 'last_used desc'

    external_id = fields.Char(string='External ID', required=True, index=True)
    title = fields.Char(string='Chat Title', required=True)
    selected = fields.Boolean(string='Selected', default=False)
    last_used = fields.Datetime(string='Last Used')
    message_count = fields.Integer(string='Message Count', compute='_compute_message_count', store=False)

    user_ids = fields.Many2many('chat.analysis.user', string='Users', relation='chat_user_analysis_rel')
    report_ids = fields.One2many('chat.analysis.report', 'chat_id', string='Reports')

    active = fields.Boolean(string='Active', default=True)
    sync_enabled = fields.Boolean(string='Auto Sync', default=True)

    def _compute_message_count(self):
        for chat in self:
            chat.message_count = self.env['chat.analysis.message'].search_count([
                ('chat_id', '=', chat.id)
            ])

    def action_sync_messages(self):
        """Синхронизировать сообщения чата"""
        self.ensure_one()

        try:
            # Получаем настройки API
            config = self.env['ir.config_parameter'].sudo()
            api_url = config.get_param('chat_analysis.api_url', 'http://localhost:8000').rstrip('/') + '/api/v1'
            api_key = config.get_param('chat_analysis.api_key', '')
            headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

            # Синхронизируем сообщения
            response = requests.get(
                f"{api_url}/chats/{self.external_id}/messages?page=1&per_page=500",
                headers=headers, timeout=30
            )
            if response.status_code == 200:
                self._sync_messages(response.json())

            self._compute_message_count()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Messages synchronized successfully'),
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(f"Sync failed: {str(e)}")

    def _sync_messages(self, messages_data):
        """Синхронизирует сообщения из API"""
        Message = self.env['chat.analysis.message']
        User = self.env['chat.analysis.user']

        for item in messages_data.get('items', []):
            user = User.search([('external_id', '=', item['sender_id'])], limit=1)

            if not user:
                user = User.create({
                    'external_id': item['sender_id'],
                    'user_name': item.get('sender_name', f"User_{item['sender_id']}"),
                    'telegram_id': item['sender_id'],
                })

            existing = Message.search([
                ('chat_id', '=', self.id),
                ('message_id', '=', item['message_id'])
            ], limit=1)

            if not existing:
                Message.create({
                    'external_id': item['id'],
                    'message_id': item['message_id'],
                    'chat_id': self.id,
                    'user_id': user.id,
                    'sender_name': item.get('sender_name', user.user_name),
                    'content': item.get('content', ''),
                    'timestamp': item.get('timestamp'),
                    'reply_to_message_id': item.get('reply_to_message_id'),
                })

    def action_refresh_stats(self):
        """Обновить статистику чата"""
        self.ensure_one()
        self._compute_message_count()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Statistics updated'),
                'type': 'success',
            }
        }