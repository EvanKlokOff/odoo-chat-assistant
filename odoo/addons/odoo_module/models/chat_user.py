from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import requests
from datetime import datetime

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
    chat_count = fields.Integer(string='Chats Count', compute='_compute_chat_count', store=False)

    _sql_constraints = [
        ('external_id_unique', 'unique(external_id)', 'User ID must be unique!')
    ]

    def _parse_datetime(self, dt_str):
        """Парсит datetime из API в формат Odoo"""
        if not dt_str:
            return False
        try:
            # Пробуем ISO формат с микросекундами
            if '.' in dt_str:
                # Обрезаем микросекунды и Z (timezone)
                dt_str = dt_str.split('.')[0].replace('Z', '')
            return datetime.strptime(dt_str, '%Y-%m-%dT%H:%M:%S')
        except:
            try:
                return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            except:
                return False

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

    def _compute_chat_count(self):
        """Вычисляет количество чатов пользователя"""
        for user in self:
            user.chat_count = len(user.chat_ids)

    def action_view_messages(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'User Messages',
            'res_model': 'chat.analysis.message',
            'view_mode': 'tree,form',
            'domain': [('user_id', '=', self.id)],
            'context': {'default_user_id': self.id},
        }

    def action_sync_user_data(self):
        """Синхронизировать данные пользователя"""
        self.ensure_one()

        try:
            config = self.env['ir.config_parameter'].sudo()
            api_url = config.get_param('chat_analysis.api_url', 'http://chat_api:8000').rstrip('/') + '/api/v1'
            api_key = config.get_param('chat_analysis.api_key', '')
            headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

            response = requests.get(
                f"{api_url}/users/{self.external_id}",
                headers=headers, timeout=30
            )

            if response.status_code == 200:
                user_data = response.json()
                self.write({
                    'user_name': user_data.get('user_name', self.user_name),
                    'telegram_id': user_data.get('telegram_id', self.telegram_id),
                })

            # 2. Синхронизация чатов пользователя
            chats_response = requests.get(
                f"{api_url}/users/{self.external_id}/chats",
                headers=headers, timeout=30
            )

            if chats_response.status_code == 200:
                user_chats = chats_response.json()

                # Обновляем связи пользователь-чат
                chat_ids = []
                for chat_data in user_chats:
                    # Находим или создаем чат
                    chat = self.env['chat.analysis.chat'].search([
                        ('external_id', '=', chat_data['chat_id'])
                    ], limit=1)

                    last_used = self._parse_datetime(chat_data['last_used'])

                    if not chat:
                        chat = self.env['chat.analysis.chat'].create({
                            'external_id': chat_data['chat_id'],
                            'title': chat_data.get('title', f"Chat_{chat_data['chat_id']}"),
                            'last_used': last_used,
                            'selected': chat_data.get('selected', False),
                            'sync_enabled': True,
                        })
                    else:
                        # Обновляем существующий чат
                        chat.write({
                            'title': chat_data.get('title', chat.title),
                            'last_used': last_used or chat.last_used,
                            'selected': chat_data.get('selected', chat.selected),
                        })

                    chat_ids.append(chat.id)

                # Обновляем связи Many2many
                self.write({'chat_ids': [(6, 0, chat_ids)]})
                self._compute_chat_count()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _(f'User data synchronized. Found {len(chat_ids)} chats'),
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(f"Sync failed: {str(e)}")

    def action_sync_user_chats(self):
        """Синхронизировать только чаты пользователя (без обновления данных пользователя)"""
        self.ensure_one()

        try:
            config = self.env['ir.config_parameter'].sudo()
            api_url = config.get_param('chat_analysis.api_url', 'http://chat_api:8000').rstrip('/') + '/api/v1'
            api_key = config.get_param('chat_analysis.api_key', '')
            headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

            chats_response = requests.get(
                f"{api_url}/users/{self.external_id}/chats",
                headers=headers, timeout=30
            )

            if chats_response.status_code == 200:
                user_chats = chats_response.json()

                chat_ids = []
                for chat_data in user_chats:
                    chat = self.env['chat.analysis.chat'].search([
                        ('external_id', '=', chat_data['chat_id'])
                    ], limit=1)

                    last_used = self._parse_datetime(chat_data.get('last_used'))

                    if not chat:
                        chat = self.env['chat.analysis.chat'].create({
                            'external_id': chat_data['chat_id'],
                            'title': chat_data.get('title', f"Chat_{chat_data['chat_id']}"),
                            'last_used': last_used,
                            'selected': chat_data.get('selected', False),
                            'sync_enabled': True,
                        })
                    else:
                        chat.write({
                            'title': chat_data.get('title', chat.title),
                            'last_used': last_used or chat.last_used,
                        })

                    chat_ids.append(chat.id)

                self.write({'chat_ids': [(6, 0, chat_ids)]})
                self._compute_chat_count()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _(f'User chats synchronized. Found {len(chat_ids)} chats'),
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(f"Sync failed: {str(e)}")

    def action_sync_all_users_chats(self):
        """Синхронизировать чаты для всех пользователей"""
        users = self.search([])
        success_count = 0

        for user in users:
            try:
                config = self.env['ir.config_parameter'].sudo()
                api_url = config.get_param('chat_analysis.api_url', 'http://chat_api:8000').rstrip('/') + '/api/v1'
                api_key = config.get_param('chat_analysis.api_key', '')
                headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

                chats_response = requests.get(
                    f"{api_url}/users/{user.external_id}/chats",
                    headers=headers, timeout=30
                )

                if chats_response.status_code == 200:
                    user_chats = chats_response.json()
                    chat_ids = []

                    for chat_data in user_chats:
                        chat = self.env['chat.analysis.chat'].search([
                            ('external_id', '=', chat_data['chat_id'])
                        ], limit=1)

                        last_used = self._parse_datetime(chat_data.get('last_used'))

                        if not chat:
                            chat = self.env['chat.analysis.chat'].create({
                                'external_id': chat_data['chat_id'],
                                'title': chat_data.get('title', f"Chat_{chat_data['chat_id']}"),
                                'last_used': last_used,
                                'selected': chat_data.get('selected', False),
                                'sync_enabled': True,
                            })
                        else:
                            chat.write({
                                'title': chat_data.get('title', chat.title),
                                'last_used': last_used or chat.last_used,
                            })

                        chat_ids.append(chat.id)

                    user.write({'chat_ids': [(6, 0, chat_ids)]})
                    success_count += 1

            except Exception as e:
                _logger.error(f"Failed to sync chats for user {user.external_id}: {e}")
                continue

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _(f'Chats synchronized for {success_count} users'),
                'type': 'success',
            }
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
            api_url = config.get_param('chat_analysis.api_url', 'http://chat_api:8000').rstrip('/') + '/api/v1'
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

    def action_analyze_chat(self):
        """Открыть wizard для анализа чата"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Analyze Chat',
            'res_model': 'chat.analysis.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chat_id': self.id,
                'default_target_datetime': fields.Datetime.now(),
            }
        }

    def action_sync_all_messages(self):
        """Синхронизировать все страницы сообщений чата"""
        self.ensure_one()

        try:
            config = self.env['ir.config_parameter'].sudo()
            api_url = config.get_param('chat_analysis.api_url', 'http://chat_api:8000').rstrip('/') + '/api/v1'
            api_key = config.get_param('chat_analysis.api_key', '')
            headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

            page = 1
            total_synced = 0

            while True:
                response = requests.get(
                    f"{api_url}/chats/{self.external_id}/messages?page={page}&per_page=500",
                    headers=headers, timeout=30
                )

                if response.status_code != 200:
                    break

                data = response.json()
                self._sync_messages(data)
                total_synced += len(data.get('items', []))

                # Проверяем, есть ли ещё страницы
                if not data.get('has_next', False):
                    break

                page += 1

            self._compute_message_count()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _(f'Synchronized {total_synced} messages from {page} pages'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(f"Sync failed: {str(e)}")

    def action_check_compliance_quick(self):
        """Быстрая проверка соответствия (создаёт отчёт и запускает)"""
        self.ensure_one()

        # Создаём wizard и сразу запускаем compliance
        wizard = self.env['chat.analysis.wizard'].create({
            'chat_id': self.id,
            'target_datetime': fields.Datetime.now(),
            'lookback_minutes': 60,
            'lookforward_minutes': 60,
            'instruction': 'Проверить соответствие переписки правилам сервиса'
        })

        return wizard.action_compliance()

    def action_export_chat_data(self):
        """Экспорт данных чата в JSON"""
        self.ensure_one()

        messages = self.env['chat.analysis.message'].search([
            ('chat_id', '=', self.id)
        ], order='timestamp')

        export_data = {
            'chat_title': self.title,
            'chat_id': self.external_id,
            'total_messages': len(messages),
            'export_date': fields.Datetime.now().isoformat(),
            'messages': [{
                'id': msg.message_id,
                'sender': msg.sender_name,
                'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
                'content': msg.content,
            } for msg in messages]
        }

        # Создаём attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'chat_{self.id}_export.json',
            'datas': json.dumps(export_data, ensure_ascii=False, indent=2).encode('utf-8'),
            'res_model': 'chat.analysis.chat',
            'res_id': self.id,
            'mimetype': 'application/json',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
